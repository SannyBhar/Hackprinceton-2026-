"""End-to-end with the simulator: program -> robot motion -> poses -> tracker -> grader."""
import asyncio

import pytest

from app.models import Instruction, SessionState
from app.robot.simulator import SimulatedRobot
from app.session import ConflictError, Session
from app.storage import FIXTURES, Storage
from app.vision.cards import FixtureCardRecognizer


def prog(*spec):
    return [Instruction(op=s[0], steps=s[1]) if isinstance(s, tuple) else Instruction(op=s) for s in spec]


@pytest.fixture
async def session(tmp_path):
    robot = SimulatedRobot(speed_cells_s=8, turn_deg_s=900, tick_s=0.01, noise=0.005)
    s = Session(robot, FixtureCardRecognizer(FIXTURES / "scans"), Storage(tmp_path))
    await s.start()
    await asyncio.sleep(0.15)
    yield s
    await s.close()


async def wait_done(s, timeout=10):
    for _ in range(int(timeout / 0.05)):
        if s.state != SessionState.RUNNING:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("run did not finish")


async def test_correct_program_succeeds(session):
    assert session.puzzle.id == "fire-station"
    session.confirm_program(prog("START", ("FORWARD", 2), "RIGHT", ("FORWARD", 3), "LEFT",
                                 ("FORWARD", 2), "STOP"))
    await session.run()
    await wait_done(session)
    a = session.attempt
    assert session.state == SessionState.COMPLETED
    assert [e["correct"] for e in a["events"]] == [True] * 7
    assert a["summary"]["success"]


async def test_wrong_entries_do_not_stop_and_recover_green(session):
    # one cell too far north, then right 3, then down... follows a parallel row
    session.confirm_program(prog("START", ("FORWARD", 1), "RIGHT", ("FORWARD", 1), "LEFT",
                                 ("FORWARD", 1), "LEFT", ("FORWARD", 1), "RIGHT", ("FORWARD", 1), "STOP"))
    await session.run()
    await wait_done(session)
    res = [e["correct"] for e in session.attempt["events"]]
    # entries: (3,0) ok, (3,1) bad, (2,1) bad [target idx2 is (2,1)? -> index 2 expects (2,1): ok]
    assert res[0] is True and res[1] is False
    assert res[2] is True  # same-index match after an error is green
    assert session.state == SessionState.COMPLETED
    assert not session.attempt["summary"]["success"]


async def test_frozen_program_and_conflicting_actions(session):
    session.confirm_program(prog("START", ("FORWARD", 2), "STOP"))
    await session.run()
    with pytest.raises(ConflictError):
        session.confirm_program(prog("START", "STOP"))
    with pytest.raises(ConflictError):
        await session.toggle_recording()
    await wait_done(session)


async def test_drift_triggers_boundary_stop(session):
    session.robot.lateral_drift = -0.5  # veer left, toward the west edge
    session.confirm_program(prog("START", ("FORWARD", 4), "STOP"))
    await session.run()
    await wait_done(session)
    assert session.state == SessionState.STOPPED
    assert session.attempt["stopReason"] == "BOUNDARY"


async def test_tracking_loss_stops(session):
    import time
    session.robot.speed = 1.5  # long enough run for the 800 ms stale threshold to trip
    session.confirm_program(prog("START", ("FORWARD", 4), "STOP"))
    await session.run()
    session.robot.tracking_lost_until = int(time.time() * 1000) + 3000
    await wait_done(session)
    assert session.attempt["stopReason"] == "TRACKING_LOST"


async def test_recording_generates_blocks(session):
    await session.toggle_recording()
    for a in ("FORWARD", "FORWARD", "RIGHT", "FORWARD", "BACKWARD"):
        assert await session.record_action(a)
    await session.toggle_recording()
    gen = [(i["op"], i.get("steps")) for i in session.recording["generated"]]
    assert gen == [("START", None), ("FORWARD", 2), ("RIGHT", None), ("FORWARD", 1),
                   ("BACKWARD", 1), ("STOP", None)]
    assert session.state == SessionState.IDLE


async def test_reconnect_snapshot_has_seq(session):
    snap = session.snapshot()
    assert snap["seq"] == session.seq and snap["state"] == "IDLE"
