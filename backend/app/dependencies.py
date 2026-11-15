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
        # Physical movement blocks no longer contain handwritten distances.
        recognizer = OpenCvCardRecognizer(cfg.card_camera)
    else:
        recognizer = FixtureCardRecognizer(FIXTURES / "scans")
    if cfg.storage == "sqlite":
        from .sqlite_store import SQLiteStorage
        store = SQLiteStorage(cfg.data_dir)
    else:
        store = Storage(cfg.data_dir)
    return Session(robot, recognizer, store)


def build_board_camera(session: Session, settings: Settings):
    """Markerless overhead-camera tracking. The camera only opens when started from the UI/API
    (or automatically with CA_TRACKER=camera), so tests and sim runs never touch it."""
    from .vision.board_camera import BoardCamera
    cam = BoardCamera(
        lambda: (session.puzzle.rows, session.puzzle.cols, session.calibration.markerMask,
                 session.puzzle.startHeading),
        session.camera_pose, settings.data_dir)
    session.board_camera = cam
    holder = getattr(session, "camera", None)          # card-scanning webcam, if configured
    if settings.tracker in ("camera", "board-camera") and (holder is None or holder.role == "closed"):
        cam.start_camera(settings.track_camera)
        session.pose_source = "camera"
    return cam
