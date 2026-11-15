"""Run grading with the real ESP32 adapter and no camera: tiles light from the commanded moves.

The WebSocket link is replaced by a fake that acknowledges each command after the move's
duration, so the full Run -> robot commands -> estimated poses -> grader path is exercised.
"""
import asyncio

import pytest

from app.models import Instruction, SessionState
from app.robot.base import Ack
from app.robot.esp32_ws import Esp32WebSocketRobot
from app.session import Session
from app.storage import FIXTURES, Storage
from app.vision.cards import FixtureCardRecognizer

MS_PER_CELL = 300   # several pose frames per cell, like the real 2 s per cell


def fake_robot(fail_on=None):
    """ESP32 adapter with a scripted link: DONE after the move time, or STOPPED on `fail_on`."""
    r = Esp32WebSocketRobot("ws://fake")
    r._ws = object()                       # 'connected'
    r.preflight = lambda *a, **k: None     # readiness is covered by other tests
    r._ms_per_cell = lambda: MS_PER_CELL
    sent = []

    async def exchange(msg, timeout):
        sent.append((msg["kind"], msg["value"]))
        if msg["kind"] == "MOVE":
            await asyncio.sleep(abs(msg["value"]) * MS_PER_CELL / 1000 + 0.02)
        if fail_on is not None and len(sent) == fail_on:
            return Ack(msg["msgId"], "STOPPED", "heartbeat watchdog expired")
        return Ack(msg["msgId"], "DONE")

    async def start():                     # no real link: only the pose stream runs
        r._tasks.append(asyncio.create_task(r._pose_loop()))

    r._exchange = exchange
    r.start = start
    r.sent = sent
    return r


def prog(*spec):
    return [Instruction(op=s[0], steps=s[1]) if isinstance(s, tuple) else Instruction(op=s) for s in spec]


async def make_session(tmp_path, robot):
    s = Session(robot, FixtureCardRecognizer(FIXTURES / "scans"), Storage(tmp_path))
    await s.start()
    s.set_puzzle(next(p for p in s.storage.list_puzzles() if p.id == "fire-station"))
    await asyncio.sleep(0.15)
    return s


async def wait_done(s, timeout=10):
    for _ in range(int(timeout / 0.05)):
        if s.state != SessionState.RUNNING:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("run did not finish")


async def test_place_and_moves_update_the_estimate():
    r = fake_robot()
    poses = []
    r.on_pose = poses.append
    r.place(4, 1, 0)                       # facing north
    assert (poses[-1].x, poses[-1].y) == (1.5, 4.5)
    await r.execute(__import__("app.robot.base", fromlist=["Primitive"]).Primitive("t", 0, "a", "MOVE", 2))
    assert (r.x, r.y) == (1.5, 2.5)        # two cells north
    await r.execute(__import__("app.robot.base", fromlist=["Primitive"]).Primitive("t", 1, "b", "TURN", 90))
    await r.execute(__import__("app.robot.base", fromlist=["Primitive"]).Primitive("t", 2, "c", "MOVE", 1))
    assert (r.x, r.y, r.heading) == (2.5, 2.5, 90)   # then one cell east


async def test_correct_program_lights_every_tile_green(tmp_path):
    s = await make_session(tmp_path, fake_robot())
    try:
        s.confirm_program(prog("START", ("FORWARD", 2), "RIGHT", ("FORWARD", 3), "LEFT", ("FORWARD", 2), "STOP"))
        await s.run()
        await wait_done(s)
        assert s.state == SessionState.COMPLETED
        events = s.attempt["events"]
        assert len(events) == len(s.puzzle.targetEntries)
        assert all(e["correct"] for e in events)          # each new tile turned green in order
        assert s.attempt["summary"]["success"]
    finally:
        await s.close()


async def test_wrong_turn_marks_the_tile_red(tmp_path):
    s = await make_session(tmp_path, fake_robot())
    try:
        s.confirm_program(prog("START", ("FORWARD", 3), "STOP"))   # should turn right after 2
        await s.run()
        await wait_done(s)
        events = s.attempt["events"]
        assert [e["correct"] for e in events][:2] == [True, True]
        assert events[2]["correct"] is False                # turned the wrong way: red tile
    finally:
        await s.close()


async def test_robot_stop_ends_the_run_without_more_green(tmp_path):
    s = await make_session(tmp_path, fake_robot(fail_on=2))   # 2nd command (the turn) is stopped
    try:
        s.confirm_program(prog("START", ("FORWARD", 2), "RIGHT", ("FORWARD", 3), "STOP"))
        await s.run()
        await wait_done(s)
        assert s.state != SessionState.COMPLETED or not s.attempt["summary"]["success"]
        assert len(s.attempt["events"]) == 2                 # only the two tiles actually commanded
    finally:
        await s.close()
