"""Composition root. Application services depend on ports, not adapter selection."""
from .settings import FIXTURES, Settings
from .session import Session
from .storage import Storage
from .robot.simulator import SimulatedRobot
from .vision.cards import FixtureCardRecognizer


def build_session(settings: Settings | None = None) -> Session:
    cfg = settings or Settings.from_env()
    if cfg.robot == "esp32":
        from .robot.esp32_ws import Esp32WebSocketRobot
        robot = Esp32WebSocketRobot(cfg.robot_url)
    else:
        robot = SimulatedRobot()
    if cfg.cards == "opencv":
        from .vision.cards import OpenCvCardRecognizer
        recognizer = OpenCvCardRecognizer(cfg.card_camera)
    else:
        recognizer = FixtureCardRecognizer(FIXTURES / "scans")
    return Session(robot, recognizer, Storage(cfg.data_dir))


def build_tracker(session: Session, settings: Settings):
    if settings.tracker != "camera":
        return None
    from .vision.camera_tracker import CameraTracker
    tracker = CameraTracker(session.puzzle.rows, session.puzzle.cols, settings.track_camera)
    tracker.on_pose = session.on_pose
    return tracker
