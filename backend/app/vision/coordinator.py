"""Shared webcam for card scanning. Never commands motors.

Robot tracking does not live here: it is the markerless BoardCamera (board_camera.py). The two
never hold the webcam at the same time; the API refuses to open one while the other is running.
"""
import asyncio
import threading
import time


class CameraCoordinator:
    def __init__(self, session, index: int, data_dir=None):
        self.session, self.index = session, index
        self.role = "closed"
        self.error = None
        self.frame = None
        self.jpeg = None
        self.resolution = None
        self.timestamp = 0
        self._task = None
        self._capture_context = None
        self._cap = None
        self._lock = threading.Lock()
        self._role_lock = asyncio.Lock()

    def status(self):
        return dict(role=self.role, error=self.error, resolution=self.resolution,
                    timestampMs=self.timestamp, index=self.index)

    def image(self):
        if self.jpeg is None or int(time.time() * 1000) - self.timestamp > 800:
            raise ValueError('camera has no fresh image')
        return self.jpeg

    def _release(self):
        with self._lock:
            if self._cap:
                self._capture_context.__exit__(None, None, None)
                self._cap = None
                self._capture_context = None

    async def close(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await asyncio.to_thread(self._release)
        self.role = 'closed'

    async def switch(self, role):
        if role not in ('scan', 'closed'):
            raise ValueError("camera role must be 'scan' or 'closed'")
        async with self._role_lock:
            await self.close()
            self.role, self.error = role, None
            self.frame, self.jpeg, self.resolution = None, None, None
            if role != 'closed':
                self._task = asyncio.create_task(self._run())
            self.session.changed()

    def _read(self):
        import cv2
        with self._lock:
            if self._cap is None:
                from .camera import OpenCvCameraSource
                self._capture_context = OpenCvCameraSource().open(self.index, self.role)
                self._cap = self._capture_context.__enter__()
            ok, frame = self._cap.read()
            if not ok:
                raise RuntimeError('webcam read failed')
            ok, jpg = cv2.imencode('.jpg', frame)
            if not ok:
                raise RuntimeError('camera image encoding failed')
            return frame, jpg.tobytes(), [int(frame.shape[1]), int(frame.shape[0])]

    async def _run(self):
        try:
            while True:
                frame, jpeg, resolution = await asyncio.to_thread(self._read)
                self.frame, self.jpeg, self.resolution = frame, jpeg, resolution
                self.timestamp = int(time.time() * 1000)
                self.error = None
                await asyncio.sleep(.05)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.error = str(e)
            self.session.log('error', f'camera: {e}')
        finally:
            await asyncio.to_thread(self._release)
            self.session.changed()
