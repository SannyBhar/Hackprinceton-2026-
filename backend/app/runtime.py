"""Own application resources independently of HTTP/WebSocket handlers."""
import asyncio
from contextlib import asynccontextmanager
from .dependencies import build_board_camera, build_tracker
from .session import Session
from .settings import Settings


@asynccontextmanager
async def running_session(session: Session):
    tracker_task = camera_task = None
    camera = None
    try:
        await session.start()
        settings = Settings.from_env()
        tracker = build_tracker(session, settings)
        if tracker is not None:
            tracker_task = asyncio.create_task(tracker.run())
        camera = build_board_camera(session, settings)
        camera_task = asyncio.create_task(camera.run())
        yield
    finally:
        for task in (tracker_task, camera_task):
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if camera is not None:
            camera.stop_camera()
        await session.close()
