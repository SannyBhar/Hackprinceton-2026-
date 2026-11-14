import asyncio

import pytest

from app.compiler import plan, validate_syntax
from app.grading import Grader, grade_sequence, reduce_tile, summarize
from app.models import Cell, Instruction, Puzzle, RobotPose
from app.recording import RecordedAction, generate_program
from app.robot.base import Primitive
from app.robot.simulator import SimulatedRobot
from app.tracking import CellEntryDetector


def C(r, c):
    return Cell(row=r, col=c)


A, B, Cc, D = C(0, 0), C(0, 1), C(1, 1), C(1, 0)


def prog(*spec):
    out = []
    for s in spec:
        if isinstance(s, tuple):
            out.append(Instruction(op=s[0], steps=s[1]))
        else:
            out.append(Instruction(op=s))
    return out


PUZ = Puzzle(id="t", name="t", rows=5, cols=6, startCell=C(4, 0), startHeading="N", goalCell=C(0, 3),
             targetEntries=[C(3, 0), C(2, 0), C(2, 1), C(2, 2), C(2, 3), C(1, 3), C(0, 3)])
GOOD = prog("START", ("FORWARD", 2), "RIGHT", ("FORWARD", 3), "LEFT", ("FORWARD", 2), "STOP")


# ---------------------------------------------------------------- grading
def test_same_index_grading_acceptance_case():
    assert grade_sequence([A, B, Cc, D], [A, Cc, B, D]) == [True, False, False, True]


def test_no_latching_and_no_pointer_hold():
    # wrong at 1, back on track at 2 -> green at 2
    assert grade_sequence([A, B, Cc], [A, D, Cc]) == [True, False, True]


def test_extra_entries_red_and_missing_incomplete():
    assert grade_sequence([A, B], [A, B, Cc, D]) == [True, True, False, False]
    g = Grader("x", [A, B, Cc])
    g.on_entry(A, 0)
    s = summarize([A, B, Cc], g.events, Cc, True)
    assert s.missing == 2 and not s.success and s.entries == 1


def test_success_requires_everything():
    g = Grader("x", [A, B])
    for c in (A, B):
        g.on_entry(c, 0)
    assert summarize([A, B], g.events, B, True).success
    assert not summarize([A, B], g.events, B, False).success  # operational stop


def test_extra_event_expected_is_null():
    g = Grader("x", [A])
    g.on_entry(A, 0)
    ev = g.on_entry(B, 0)
    assert ev.expected is None and not ev.correct and ev.index == 1


# ---------------------------------------------------------------- tiles
@pytest.mark.parametrize("hist,kind,left,right", [
    ([], "unvisited", None, None),
    ([True], "solid", True, True),
    ([True, True], "solid", True, True),
    ([False], "solid", False, False),
    ([False, True], "split", False, True),
    ([True, False], "split", True, False),
    ([True, False, True], "solid", True, True),   # first==latest (documented default)
    ([False, True, False, True], "split", False, True),
])
def test_tile_reducer(hist, kind, left, right):
    t = reduce_tile(hist)
    assert (t.kind, t.left, t.right) == (kind, left, right)


# ---------------------------------------------------------------- compiler
def test_plan_good_program():
    r = plan(PUZ, GOOD)
    assert r.ok and r.plannedEntries == PUZ.targetEntries and r.finalHeading == "N"


def test_syntax_errors():
    assert validate_syntax(prog(("FORWARD", 1), "STOP"))  # missing START
    assert validate_syntax(prog("START", ("FORWARD", 6), "STOP"))  # over limit
    assert validate_syntax(prog("START", ("FORWARD", 0), "STOP"))
    assert validate_syntax(prog("START", "STOP", "STOP"))
    assert not validate_syntax(prog("START", "STOP"))


def test_missing_steps_rejected_by_model():
    with pytest.raises(ValueError):
        Instruction(op="FORWARD")
    with pytest.raises(ValueError):
        Instruction(op="LEFT", steps=2)


def test_bounds_flagged_not_clipped():
    r = plan(PUZ, prog("START", ("FORWARD", 5), "STOP"))
    assert not r.ok and "leave the board" in r.errors[0]


def test_backward_uses_heading():
    r = plan(PUZ, prog("START", ("FORWARD", 1), ("BACKWARD", 1), "STOP"))
    assert r.plannedEntries == [C(3, 0), C(4, 0)]


def test_puzzle_rejects_non_adjacent_route():
    with pytest.raises(ValueError):
        Puzzle(id="x", name="x", rows=3, cols=3, startCell=C(0, 0), startHeading="E",
               goalCell=C(0, 2), targetEntries=[C(0, 2)])


# ---------------------------------------------------------------- recording
def test_recording_compression_and_turns():
    acts = [RecordedAction("FORWARD", [C(3, 0)]), RecordedAction("FORWARD", [C(2, 0)]),
            RecordedAction("FORWARD", [C(1, 0)]), RecordedAction("RIGHT"),
            RecordedAction("BACKWARD", [C(1, 0)]), RecordedAction("LEFT")]
    g = generate_program(acts)
    ops = [(i.op, i.steps) for i in g.instructions]
    assert ops == [("START", None), ("FORWARD", 3), ("RIGHT", None), ("BACKWARD", 1),
                   ("LEFT", None), ("STOP", None)]
    assert not g.warnings


def test_recording_splits_at_card_limit_and_warns_on_mismatch():
    acts = [RecordedAction("FORWARD", [C(0, i)]) for i in range(7)] + [RecordedAction("FORWARD", [])]
    g = generate_program(acts, max_steps=5)
    assert [(i.op, i.steps) for i in g.instructions][1:3] == [("FORWARD", 5), ("FORWARD", 3)]
    assert len(g.warnings) == 1


# ---------------------------------------------------------------- tracking
def pose(x, y, t=0, valid=True):
    return RobotPose(timestampMs=t, x=x, y=y, headingDeg=0, trackingValid=valid)


def test_detector_ignores_start_and_repeated_frames():
    d = CellEntryDetector(5, 5, C(4, 0))
    assert all(d.update(pose(0.5, 4.5)).entered is None for _ in range(10))
    entries = [d.update(pose(0.5, y)).entered for y in (4.1, 3.95, 3.7, 3.5, 3.5, 3.5, 3.5)]
    assert [e for e in entries if e] == [C(3, 0)]


def test_detector_hysteresis_on_boundary_jitter():
    d = CellEntryDetector(5, 5, C(4, 0))
    seq = [4.02, 3.98, 4.01, 3.97, 4.03]  # dithering on the edge
    assert not any(d.update(pose(0.5, y)).entered for y in seq)


def test_detector_revisit_counts():
    d = CellEntryDetector(5, 5, C(4, 0))
    got = []
    for y in (3.5, 3.5, 4.5, 4.5, 3.5, 3.5):
        e = d.update(pose(0.5, y)).entered
        if e:
            got.append(e)
    assert got == [C(3, 0), C(4, 0), C(3, 0)]


def test_detector_flags_skips_and_boundary():
    d = CellEntryDetector(5, 5, C(4, 0))
    d.update(pose(0.5, 2.5))
    out = d.update(pose(0.5, 2.5))
    assert out.entered == C(2, 0) and out.skipped
    assert d.update(pose(0.03, 2.5)).boundary


# ---------------------------------------------------------------- duplicate commands
async def test_duplicate_msg_id_never_moves_twice():
    r = SimulatedRobot(speed_cells_s=50, tick_s=0.001, noise=0)
    r.place(4, 0, 0)
    p = Primitive("run", 1, "m1", "MOVE", 1)
    assert (await r.execute(p)).status == "DONE"
    y = r.y
    assert (await r.execute(p)).status == "DUPLICATE"
    assert r.y == y
