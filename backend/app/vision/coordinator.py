"""One webcam owner. Role changes invalidate calibration and never command motors."""
import asyncio
import json
import threading
import time
from pathlib import Path


class CameraCoordinator:
    def __init__(self, session, index: int, data_dir: Path):
        self.session, self.index, self.data_dir = session, index, data_dir
        self.role = "closed"
        self.generation = 0
        self.calibrated = False
        self.error = None
        self.frame = None
        self.jpeg = None
        self.resolution = None
        self.timestamp = 0
        self._task = None
        self._cap = None
        self._tracker = None
        self._mapping = None
        self._lock = threading.Lock()

    def invalidate(self):
        self.generation += 1
        self.calibrated = False
        self._mapping = None
        self.session.pose = None

    def status(self):
        return dict(role=self.role, generation=self.generation, calibrated=self.calibrated,
                    ready=self.ready(), error=self.error, resolution=self.resolution,
                    timestampMs=self.timestamp, index=self.index)

    def ready(self):
        return self.role == 'track' and self.calibrated and not self.error and 0 <= int(time.time()*1000)-self.timestamp < 800

    def image(self):
        if self.jpeg is None or int(time.time()*1000)-self.timestamp > 800:
            raise ValueError('camera has no fresh image')
        return self.jpeg

    def _release(self):
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None

    async def close(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await asyncio.to_thread(self._release)
        self.role = 'closed'
        self.invalidate()

    async def switch(self, role):
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
                self._cap = cv2.VideoCapture(self.index)
            ok, frame = self._cap.read()
            if not ok:
                raise RuntimeError('webcam read failed')
            ok, jpg = cv2.imencode('.jpg', frame)
            if not ok:
                raise RuntimeError('camera image encoding failed')
            return frame, jpg.tobytes(), [int(frame.shape[1]), int(frame.shape[0])]

    async def _run(self):
        from .camera_tracker import CameraTracker
        try:
            self._tracker = CameraTracker(self.session.puzzle.rows, self.session.puzzle.cols, self.index)
            while True:
                frame, jpeg, resolution = await asyncio.to_thread(self._read)
                if self.resolution and resolution != self.resolution:
                    self.invalidate()
                self.frame, self.jpeg, self.resolution = frame, jpeg, resolution
                self.timestamp = int(time.time()*1000)
                self.error = None
                if self.role == 'track':
                    self._tracker.rows, self._tracker.cols = self.session.puzzle.rows, self.session.puzzle.cols
                    # No stale mapping may conceal occluded/moved corner markers.
                    self._tracker.H = None
                    pose = await asyncio.to_thread(self._tracker.process, frame)
                    if self.calibrated and self._tracker.H is not None:
                        import numpy as np
                        import cv2
                        pts = np.array([[[0, 0], [self._tracker.cols, 0],
                                         [self._tracker.cols, self._tracker.rows], [0, self._tracker.rows]]], np.float32)
                        before = cv2.perspectiveTransform(pts, np.linalg.inv(self._mapping))
                        after = cv2.perspectiveTransform(pts, np.linalg.inv(self._tracker.H))
                        if np.max(np.linalg.norm(before-after, axis=2)) > 8:
                            self.invalidate()
                            self.error = 'camera or corner markers moved; revalidate calibration'
                    if not self.calibrated:
                        pose = pose.model_copy(update={'trackingValid': False})
                    self.session.on_pose(pose)
                await asyncio.sleep(.05)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.error = str(e)
            self.invalidate()
            self.session.log('error', f'camera: {e}')
        finally:
            await asyncio.to_thread(self._release)
            self.session.changed()

    async def calibrate(self):
        if self.role != 'track' or self._tracker is None or self.frame is None:
            raise ValueError('select arena tracking and wait for camera frames')
        # Freeze this generation; role changes cannot validate an earlier image.
        generation = self.generation
        self._tracker.H = None
        pose = await asyncio.to_thread(self._tracker.process, self.frame.copy())
        if generation != self.generation or self._tracker.H is None or not pose.trackingValid:
            raise ValueError('all four corner markers and robot marker must be visible')
        self._mapping = self._tracker.H.copy()
        self.calibrated = True
        self.error = None
        record = dict(index=self.index, resolution=self.resolution, generation=self.generation,
                      rows=self.session.puzzle.rows, cols=self.session.puzzle.cols,
                      homography=self._mapping.tolist(), validatedAt=int(time.time()*1000))
        await asyncio.to_thread(self._save, record)
        self.session.on_pose(pose)
        self.session.changed()
        return record

    def _save(self, record):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir/'camera_calibration.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(path)
