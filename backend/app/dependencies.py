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
        ocr = None
        if cfg.ocr:
            from .vision.ocr import LocalHandwritingOcr
            ocr = LocalHandwritingOcr()
        recognizer = OpenCvCardRecognizer(cfg.card_camera, ocr=ocr)
    else:
        recognizer = FixtureCardRecognizer(FIXTURES / "scans")
    if cfg.storage == "sqlite":
        from .sqlite_store import SQLiteStorage
        store = SQLiteStorage(cfg.data_dir)
    else:
        store = Storage(cfg.data_dir)
    return Session(robot, recognizer, store)


def build_tracker(session: Session, settings: Settings):
    if settings.tracker != "camera":
        return None
    from .vision.camera_tracker import CameraTracker
    tracker = CameraTracker(session.puzzle.rows, session.puzzle.cols, settings.track_camera)
    tracker.on_pose = session.on_pose
    return tracker
