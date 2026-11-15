"""Camera tracking tests.

* Real-frame tests use webcam captures of the actual board in data/camera_check/ (gitignored,
  local only) and are skipped elsewhere.
* Session tests feed camera poses directly, so they always run.
"""
import asyncio
import time
from pathlib import Path

import pytest

from app.models import RobotPose, SessionState
from app.robot.simulator import SimulatedRobot
from app.session import ConflictError, Session
from app.storage import FIXTURES, Storage
from app.vision.cards import FixtureCardRecognizer

FRAMES = Path(__file__).resolve().parents[2] / "data" / "camera_check"


def frame(name):
    cv2 = pytest.importorskip("cv2")
    f = FRAMES / name
    if not f.exists():
        pytest.skip(f"local capture {name} not present")
    return cv2.imread(str(f))


# --------------------------------------------------------------------------- real frames
def test_border_fit_is_repeatable_across_captures():
    from app.vision.board_camera import find_test_pattern_border
    a = find_test_pattern_border(frame("testpattern_cam0.jpg"))
    b = find_test_pattern_border(frame("robot_testpattern.jpg"))  # person partly blocks the top edge
    for p, q in zip(a, b):
        assert abs(p[0] - q[0]) < 6 and abs(p[1] - q[1]) < 6


def _calibrated_detector():
    from app.vision.board_camera import (CameraCalibration, RobotDetector, board_corners_from_border,
                                         find_test_pattern_border)
    corners = board_corners_from_border(find_test_pattern_border(frame("robot_testpattern.jpg")), 7, 7)
    return CameraCalibration(0, 1920, 1080, corners).board_to_image(7, 7), RobotDetector()


@pytest.mark.parametrize("name", ["robot_board_2.jpg", "robot_board.jpg"])
def test_robot_found_in_start_cell(name):
    H, det = _calibrated_detector()
    r = det.detect(frame(name), H, 7, 7, 0.35)
    assert r["found"] and (int(r["y"]), int(r["x"])) == (6, 1)
    assert r["area"] > 3 * r["runnerUp"]  # clear margin over everything else on the board


def test_dark_board_is_refused_not_misread():
    """On the black test pattern nearly the whole board is dark; must not invent a robot."""
    from app.vision.board_camera import RobotDetector
    H, _ = _calibrated_detector()
    r = RobotDetector().detect(frame("robot_testpattern.jpg"), H, 7, 7, 0.35)
    assert not r["found"] and "too dark" in r["reason"]


# --------------------------------------------------------------------------- session wiring
@pytest.fixture
async def session(tmp_path):
    s = Session(SimulatedRobot(speed_cells_s=8, tick_s=0.01, noise=0), FixtureCardRecognizer(FIXTURES / "scans"),
                Storage(tmp_path))
    await s.start()
    await asyncio.sleep(0.05)
    yield s
    await s.close()


def cam_pose(x, y, valid=True):
    return RobotPose(timestampMs=int(time.time() * 1000), x=x, y=y, headingDeg=0, trackingValid=valid)


async def test_only_the_selected_pose_source_is_used(session):
    session.camera_pose(cam_pose(3.5, 3.5))
    assert session.pose is None or (session.pose.x, session.pose.y) != (3.5, 3.5)  # robot adapter is the source
    session.set_pose_source("camera")
    session.camera_pose(cam_pose(3.5, 3.5))
    assert (session.pose.x, session.pose.y) == (3.5, 3.5)
    await asyncio.sleep(0.15)  # simulator keeps emitting; it must be ignored now
    assert (session.pose.x, session.pose.y) == (3.5, 3.5)


async def test_hand_push_test_grades_camera_entries_and_finishes(session):
    p = session.puzzle  # starter 7x7: start (6,1) facing N
    session.set_pose_source("camera")
    session.camera_pose(cam_pose(p.startCell.col + .5, p.startCell.row + .5))
    await session.start_manual_attempt()
    assert session.state == SessionState.RUNNING
    for c in p.targetEntries:             # push the robot along the route, 3 frames per cell
        for _ in range(3):
            session.camera_pose(cam_pose(c.col + .5, c.row + .5))
    assert session.state == SessionState.COMPLETED
    assert [e["correct"] for e in session.attempt["events"]] == [True] * len(p.targetEntries)
    assert session.attempt["summary"]["success"]


async def test_hand_push_test_needs_robot_on_start(session):
    session.set_pose_source("camera")
    session.camera_pose(cam_pose(4.5, 2.5))
    with pytest.raises(ConflictError):
        await session.start_manual_attempt()


async def test_hand_push_test_not_stopped_by_hidden_robot(session):
    p = session.puzzle
    session.set_pose_source("camera")
    session.camera_pose(cam_pose(p.startCell.col + .5, p.startCell.row + .5))
    await session.start_manual_attempt()
    session.camera_pose(cam_pose(0, 0, valid=False))   # a hand covers the robot
    await asyncio.sleep(1.2)                           # longer than the 800 ms stale limit
    assert session.state == SessionState.RUNNING
    await session.operational_stop(__import__("app.models", fromlist=["StopReason"]).StopReason.INSTRUCTOR_STOP)
    assert session.state == SessionState.STOPPED
