"""Own application resources independently of HTTP/WebSocket handlers."""
import asyncio
from contextlib import asynccontextmanager
from .dependencies import build_board_camera
from .session import Session
from .settings import Settings


@asynccontextmanager
async def running_session(session: Session):
    camera_task = None
    camera = None
    try:
        await session.start()
        cfg = Settings.from_env()
        from .ai.themes import ThemeJobs
        session.themes = ThemeJobs(session,cfg.data_dir)
        for job in await session.themes.list():
            if job.get("status") == "GENERATING":
                job.update(status="FAILED",error="application restarted; regenerate")
                await session.themes.save(job)
        session._bg.append(asyncio.create_task(session.joystick.watchdog()))
        if cfg.joystick_port:
            session._bg.append(asyncio.create_task(session.joystick.serial_loop(cfg.joystick_port)))
        if cfg.cards == "opencv":
            # Shared webcam for card scanning. The board camera refuses to open while it's held.
            from .vision.coordinator import CameraCoordinator
            session.camera = CameraCoordinator(session, cfg.camera_index, cfg.data_dir)
            await session.camera.switch("scan")
        # Markerless overhead tracking: created always, opens the webcam only when started.
        camera = build_board_camera(session, cfg)
        camera_task = asyncio.create_task(camera.run())
        yield
    finally:
        await session.robot.stop("application shutdown")
        if session.themes:
            await session.themes.close()
        if session.camera:
            await session.camera.close()
        for task in (camera_task,):
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if camera is not None:
            camera.stop_camera()
        await session.close()
