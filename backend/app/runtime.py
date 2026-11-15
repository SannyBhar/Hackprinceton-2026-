"""Own application resources independently of HTTP/WebSocket handlers."""
import asyncio
from contextlib import asynccontextmanager
from .dependencies import build_tracker
from .session import Session
from .settings import Settings


@asynccontextmanager
async def running_session(session: Session):
    tracker_task = None
    try:
        await session.start()
        cfg = Settings.from_env()
        session._bg.append(asyncio.create_task(session.joystick.watchdog()))
        if cfg.joystick_port:
            session._bg.append(asyncio.create_task(session.joystick.serial_loop(cfg.joystick_port)))
        if cfg.cards == "opencv" or cfg.tracker == "camera":
            from .vision.coordinator import CameraCoordinator
            session.camera = CameraCoordinator(session, cfg.card_camera, cfg.data_dir)
            if session.robot.name == "simulator":
                session.robot.on_pose = None  # physical camera is the exclusive pose source
            await session.camera.switch("scan")
        else:
            tracker = build_tracker(session, cfg)
            if tracker is not None:
                tracker_task = asyncio.create_task(tracker.run())
        yield
    finally:
        if session.camera:
            await session.camera.close()
        if tracker_task is not None:
            tracker_task.cancel()
            await asyncio.gather(tracker_task, return_exceptions=True)
        await session.close()
