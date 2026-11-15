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
        tracker = build_tracker(session, Settings.from_env())
        if tracker is not None:
            tracker_task = asyncio.create_task(tracker.run())
        yield
    finally:
        if tracker_task is not None:
            tracker_task.cancel()
            await asyncio.gather(tracker_task, return_exceptions=True)
        await session.close()
