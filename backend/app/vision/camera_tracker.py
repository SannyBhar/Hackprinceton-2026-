"""Overhead camera -> RobotPose in grid cell units (UNVERIFIED against hardware).

1. Detect the four board-corner markers (IDs 0-3 = TL, TR, BR, BL); use each marker's
   outermost corner as the board corner and compute a camera->grid homography.
2. Detect the robot marker (ID 4); centre -> (x, y) in cell units, marker 'up' edge -> heading.

Elevation caveat: the robot marker sits above the floor plane, so a floor homography
shifts it radially away from the camera's principal point. `height_correction` applies a
validated linear approximation (scale toward the image centre) — measure and tune it,
or replace with full solvePnP pose using camera intrinsics.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Optional

from ..models import RobotPose

OUTER_CORNER_INDEX = {0: 0, 1: 1, 2: 2, 3: 3}  # aruco corner order TL,TR,BR,BL matches board


class CameraTracker:
    def __init__(self, rows: int, cols: int, camera_index: int = 1, fps: float = 20.0,
                 height_correction: float = 0.0):
        import cv2
        self.cv2 = cv2
        self.rows, self.cols = rows, cols
        self.camera_index = camera_index
        self.period = 1.0 / fps
        self.height_correction = height_correction
        self.H = None
        self.on_pose = None
        self.detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100))

    def _homography(self, corners, ids):
        import numpy as np
        pts = {}
        for quad, mid in zip(corners, ids.flatten()):
            if int(mid) in OUTER_CORNER_INDEX:
                pts[int(mid)] = quad[0][OUTER_CORNER_INDEX[int(mid)]]
        if len(pts) < 4:
            return None
        src = np.array([pts[0], pts[1], pts[2], pts[3]], np.float32)
        dst = np.array([[0, 0], [self.cols, 0], [self.cols, self.rows], [0, self.rows]], np.float32)
        return self.cv2.getPerspectiveTransform(src, dst)

    def process(self, frame) -> RobotPose:
        import numpy as np
        cv2 = self.cv2
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        ts = int(time.time() * 1000)
        if ids is None:
            return RobotPose(timestampMs=ts, x=0, y=0, headingDeg=0, trackingValid=False)
        H = self._homography(corners, ids)
        if H is not None:
            self.H = H  # keep last good mapping if a corner is briefly occluded
        robot = [q[0] for q, m in zip(corners, ids.flatten()) if int(m) == 4]
        if self.H is None or not robot:
            return RobotPose(timestampMs=ts, x=0, y=0, headingDeg=0, trackingValid=False)
        q = robot[0]
        h, w = gray.shape
        centre = q.mean(axis=0)
        if self.height_correction:
            c0 = np.array([w / 2, h / 2])
            centre = c0 + (centre - c0) * (1 - self.height_correction)
        front = (q[0] + q[1]) / 2  # marker top edge faces robot front
        g = cv2.perspectiveTransform(np.array([[centre, front]], np.float32), self.H)[0]
        dx, dy = g[1] - g[0]
        heading = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
        return RobotPose(timestampMs=ts, x=float(g[0][0]), y=float(g[0][1]),
                         headingDeg=heading, trackingValid=True)

    async def run(self):
        cap = self.cv2.VideoCapture(self.camera_index)
        try:
            while True:
                ok, frame = await asyncio.to_thread(cap.read)
                if ok and self.on_pose:
                    self.on_pose(self.process(frame))
                await asyncio.sleep(self.period)
        finally:
            cap.release()
