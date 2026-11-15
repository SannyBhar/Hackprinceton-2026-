"""Overhead webcam -> board cells, without markers on the board or the robot.

Validated on real frames from the classroom setup (data/camera_check, Nov 2026):
  * Calibration: project the test pattern; its cyan border is found by colour, one straight line
    is fitted per side (Hough segments + robust fit) and the corners are the line intersections.
    Predicted board centre landed within ~3 px of the projected centre cross.
  * Robot: dark, colourless pixels on the board (robot chassis V≈75, S≈0; tiles V≈211;
    grid lines V≈124), ignoring the board's own dark areas (grid gaps, corner dark zones).
    The largest remaining blob was the robot with a ~4x area margin; its bottom-centre
    (ground contact) mapped to the correct cell.

NOT yet verified: a moving robot, heading (inferred from motion only — in-place turns are
invisible without a marker), red/green feedback tiles under the camera, other lighting,
people on the board (their dark clothing can win), and a different camera position.

Calibration is stored as the board's 4 corners in the camera image, so it survives switching
between puzzle sizes: the physical board area is fixed by the projector calibration.
"""
from __future__ import annotations

import asyncio
import json
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..models import RobotPose

PERMISSION_HINT = ("On macOS, start the backend from Terminal.app and allow camera access "
                   "(System Settings → Privacy & Security → Camera → Terminal).")
TEST_PATTERN_INSET = 0.04   # test-pattern border stroke centre, in cells from the board edge


def now_ms() -> int:
    return int(time.time() * 1000)


# --------------------------------------------------------------------------- calibration
def find_test_pattern_border(frame) -> "list[list[float]]":
    """Return the projected test-pattern border corners TL, TR, BR, BL in image pixels."""
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # The cyan border reads as a dull teal on camera: hue ~80-85, low-ish saturation (measured).
    mask = cv2.inRange(hsv, (70, 25, 60), (100, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    segs = cv2.HoughLinesP(mask, 1, np.pi / 360, 60, minLineLength=60, maxLineGap=25)
    if segs is None:
        raise ValueError("no projected border found — is the test pattern showing and the room dim enough?")
    segs = segs.reshape(-1, 4).astype(np.float32)
    cx, cy = segs[:, [0, 2]].mean(), segs[:, [1, 3]].mean()
    groups: dict[str, list] = {k: [] for k in ("top", "bottom", "left", "right")}
    for x1, y1, x2, y2 in segs:
        ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180
        horiz = ang < 35 or ang > 145
        side = ("top" if (y1 + y2) / 2 < cy else "bottom") if horiz else ("left" if (x1 + x2) / 2 < cx else "right")
        n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 5))
        groups[side] += list(zip(np.linspace(x1, x2, n), np.linspace(y1, y2, n)))
    missing = [k for k, v in groups.items() if len(v) < 10]
    if missing:
        raise ValueError(f"could not see the {', '.join(missing)} edge(s) of the projected border")
    lines = {k: cv2.fitLine(np.float32(v), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel() for k, v in groups.items()}

    def meet(a: str, b: str):
        (vx1, vy1, x1, y1), (vx2, vy2, x2, y2) = lines[a], lines[b]
        t = np.linalg.solve(np.array([[vx1, -vx2], [vy1, -vy2]]), [x2 - x1, y2 - y1])
        return [float(x1 + vx1 * t[0]), float(y1 + vy1 * t[0])]

    return [meet("top", "left"), meet("top", "right"), meet("bottom", "right"), meet("bottom", "left")]


def board_corners_from_border(border: list[list[float]], rows: int, cols: int) -> list[list[float]]:
    """The border stroke sits slightly inside the board edge; extrapolate to the true board corners."""
    import cv2
    import numpy as np
    i = TEST_PATTERN_INSET
    H = cv2.getPerspectiveTransform(
        np.float32([[i, i], [cols - i, i], [cols - i, rows - i], [i, rows - i]]), np.float32(border))
    out = cv2.perspectiveTransform(np.float32([[[0, 0], [cols, 0], [cols, rows], [0, rows]]]), H)[0]
    return out.tolist()


@dataclass
class CameraCalibration:
    cameraIndex: int
    imageWidth: int
    imageHeight: int
    corners: list[list[float]]          # board TL, TR, BR, BL in image pixels
    method: str = "test-pattern"
    createdAt: int = field(default_factory=now_ms)

    def board_to_image(self, rows: int, cols: int):
        """Homography from board cells (x=col, y=row) to image pixels."""
        import cv2
        import numpy as np
        return cv2.getPerspectiveTransform(
            np.float32([[0, 0], [cols, 0], [cols, rows], [0, rows]]), np.float32(self.corners)).astype(np.float64)


# --------------------------------------------------------------------------- robot detection
@dataclass
class DetectParams:
    max_value: int = 95          # robot chassis V≈75 vs grid lines ≈124, tiles ≈211 (measured)
    max_saturation: int = 60     # robot is colourless (S≈0); keeps coloured feedback tiles out
    line_band: float = 0.10      # half-width (cells) of each grid gap to ignore
    corner_extra: float = 0.05   # margin added to the projector's corner dark zones
    min_area_cells: float = 0.04  # smallest blob accepted, as a fraction of one cell's image area
    foot: float = 0.85           # ground contact = this fraction down the blob's bounding box
    max_dark_fraction: float = 0.25  # above this the board itself is dark (test pattern, dark theme)


class RobotDetector:
    def __init__(self, params: DetectParams | None = None):
        self.p = params or DetectParams()
        self._cache_key = None
        self._ignore = self._inside = None

    def _masks(self, H, rows, cols, corner_mask, shape):
        import cv2
        import numpy as np
        key = (tuple(np.round(H, 6).ravel()), rows, cols, round(corner_mask, 3), shape)
        if key == self._cache_key:
            return self._ignore, self._inside
        S = 100
        exp = np.zeros((rows * S, cols * S), np.uint8)
        b = int(self.p.line_band * S)
        for i in range(cols + 1):
            cv2.rectangle(exp, (i * S - b, 0), (i * S + b, rows * S), 255, -1)
        for j in range(rows + 1):
            cv2.rectangle(exp, (0, j * S - b), (cols * S, j * S + b), 255, -1)
        m = int((corner_mask + self.p.corner_extra) * S)
        if corner_mask > 0:
            for x, y in [(0, 0), (cols * S - m, 0), (cols * S - m, rows * S - m), (0, rows * S - m)]:
                cv2.rectangle(exp, (x, y), (x + m, y + m), 255, -1)
        Hpx = H @ np.diag([1 / S, 1 / S, 1.0])
        h, w = shape
        self._ignore = cv2.warpPerspective(exp, Hpx, (w, h))
        self._inside = cv2.warpPerspective(np.full((rows * S, cols * S), 255, np.uint8), Hpx, (w, h))
        self._cache_key = key
        return self._ignore, self._inside

    def detect(self, frame, H, rows: int, cols: int, corner_mask: float) -> dict:
        """Return {'found', 'x', 'y' (cells), 'area', 'runnerUp', 'bbox'} for the robot blob."""
        import cv2
        import numpy as np
        ignore, inside = self._masks(H, rows, cols, corner_mask, frame.shape[:2])
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dark = ((hsv[:, :, 2] < self.p.max_value) & (hsv[:, :, 1] < self.p.max_saturation)
                & (inside > 0) & (ignore == 0)).astype(np.uint8) * 255
        usable = np.count_nonzero((inside > 0) & (ignore == 0))
        frac = np.count_nonzero(dark) / max(1, usable)
        if frac > self.p.max_dark_fraction:
            # Markerless detection needs a bright board: refuse rather than report a false robot.
            return {"found": False, "reason": f"board too dark for camera tracking ({frac:.0%} dark) — "
                                               "use a bright theme and keep the test pattern off"}
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        cnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cell_area = cv2.contourArea(np.float32(cv2.perspectiveTransform(
            np.float32([[[0, 0], [1, 0], [1, 1], [0, 1]]]) + np.float32([cols / 2 - .5, rows / 2 - .5]), H)[0]))
        min_area = self.p.min_area_cells * cell_area
        cnts = sorted([c for c in cnts if cv2.contourArea(c) >= min_area], key=cv2.contourArea, reverse=True)
        if not cnts:
            return {"found": False}
        x, y, w, h = cv2.boundingRect(cnts[0])
        foot = np.float32([[[x + w / 2, y + h * self.p.foot]]])
        g = cv2.perspectiveTransform(foot, np.linalg.inv(H))[0][0]
        return {"found": True, "x": float(g[0]), "y": float(g[1]), "area": float(cv2.contourArea(cnts[0])),
                "runnerUp": float(cv2.contourArea(cnts[1])) if len(cnts) > 1 else 0.0,
                "bbox": [x, y, w, h]}


# --------------------------------------------------------------------------- capture
class CameraService:
    """One background capture thread; preview, calibration and tracking share the latest frame."""

    def __init__(self, open_capture: Callable[[int], object] | None = None):
        self._open = open_capture or self._open_cv
        self.index: Optional[int] = None
        self.error: Optional[str] = None
        self.frame = None
        self.frame_ms = 0
        self.frame_count = 0
        self.fps = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _open_cv(index: int):
        import cv2
        cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        return cap

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, index: int):
        self.stop()
        self.index, self.error, self.frame = index, None, None
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(index,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def _loop(self, index: int):
        cap = self._open(index)
        try:
            if not cap.isOpened():
                self.error = f"Camera {index} could not be opened. {PERMISSION_HINT}"
                return
            window: list[float] = []
            fails = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if fails > 100:
                        self.error = f"Camera {index} stopped delivering frames. {PERMISSION_HINT}"
                        return
                    time.sleep(0.02)
                    continue
                fails = 0
                t = time.time()
                self.frame, self.frame_ms = frame, int(t * 1000)
                self.frame_count += 1
                window = [s for s in window if t - s < 1.0] + [t]
                self.fps = float(len(window))
        finally:
            cap.release()

    def jpeg(self, max_width: int = 960, quality: int = 70) -> Optional[bytes]:
        import cv2
        f = self.frame
        if f is None:
            return None
        h, w = f.shape[:2]
        if w > max_width:
            f = cv2.resize(f, (max_width, int(h * max_width / w)))
        ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None

    async def wait_new_frames(self, n: int, timeout: float = 3.0) -> bool:
        start, t0 = self.frame_count, time.time()
        while self.frame_count < start + n:
            if time.time() - t0 > timeout:
                return False
            await asyncio.sleep(0.03)
        return True


# --------------------------------------------------------------------------- service
class BoardCamera:
    """Camera + calibration + robot tracking loop. Emits RobotPose in cells via on_pose."""

    def __init__(self, get_board: Callable[[], tuple[int, int, float, str]],
                 on_pose: Callable[[RobotPose], None], data_dir: Path,
                 camera: CameraService | None = None, hz: float = 30.0):
        self.get_board = get_board         # -> (rows, cols, corner-mask fraction, start heading)
        self.on_pose = on_pose
        # Own file: data/camera_calibration.json belongs to the marker-based CameraCoordinator.
        self.path = Path(data_dir) / "board_camera_calibration.json"
        self._legacy_path = Path(data_dir) / "camera_calibration.json"
        self.camera = camera or CameraService()
        self.detector = RobotDetector()
        self.period = 1.0 / hz
        self.calibration = self._load()
        self.tracking = False
        self.paused = False                # true while calibrating (test pattern hides the robot)
        self.last: dict = {}
        self.latency_ms = 0
        self._last_frame = -1
        self._heading: Optional[float] = None
        self._anchor: Optional[tuple[float, float]] = None
        self._last_pose: Optional[RobotPose] = None

    def _load(self) -> Optional[CameraCalibration]:
        try:
            return CameraCalibration(**json.loads(self.path.read_text()))
        except (OSError, ValueError, TypeError):
            pass
        # One-time migration: earlier builds saved this calibration as camera_calibration.json.
        # Only take that file if it has OUR schema (the coordinator's has a 'homography' instead).
        try:
            data = json.loads(self._legacy_path.read_text())
            if "corners" in data and "homography" not in data:
                cal = CameraCalibration(**data)
                self._save(cal)
                return cal
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _save(self, cal: CameraCalibration):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(cal), indent=2))
        tmp.replace(self.path)
        self.calibration = cal

    def start_camera(self, index: int):
        self.camera.start(index)
        self.tracking = True

    def stop_camera(self):
        self.tracking = False
        self.camera.stop()

    def reset_heading(self):
        self._heading, self._anchor = None, None

    def calibrate_from_frame(self, frame) -> dict:
        rows, cols, _, _ = self.get_board()
        border = find_test_pattern_border(frame)
        corners = board_corners_from_border(border, rows, cols)
        h, w = frame.shape[:2]
        self._save(CameraCalibration(self.camera.index or 0, w, h, corners))
        self.detector._cache_key = None
        return self.status()

    def process(self, frame, ts: int) -> Optional[RobotPose]:
        if self.calibration is None:
            return None
        rows, cols, corner_mask, start_heading = self.get_board()
        H = self.calibration.board_to_image(rows, cols)
        d = self.detector.detect(frame, H, rows, cols, corner_mask)
        self.last = d
        prev = self._last_pose
        if not d["found"]:
            return RobotPose(timestampMs=ts, x=prev.x if prev else 0.0, y=prev.y if prev else 0.0,
                             headingDeg=prev.headingDeg if prev else 0.0, trackingValid=False)
        x, y = d["x"], d["y"]
        # Heading without a marker: the puzzle's start heading until the robot has moved
        # 0.35 cell, then the direction of travel. In-place turns are NOT observable.
        if self._heading is None:
            self._heading = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}.get(start_heading, 0.0)
            self._anchor = (x, y)
        ax, ay = self._anchor
        if math.hypot(x - ax, y - ay) > 0.35:
            self._heading = (math.degrees(math.atan2(x - ax, -(y - ay))) + 360) % 360
            self._anchor = (x, y)
        pose = RobotPose(timestampMs=ts, x=x, y=y, headingDeg=self._heading, trackingValid=True)
        self._last_pose = pose
        return pose

    async def run(self):
        while True:
            await asyncio.sleep(self.period)
            cam = self.camera
            if not self.tracking or self.paused or not cam.running or cam.frame is None:
                continue
            if cam.frame_count == self._last_frame:
                continue
            self._last_frame = cam.frame_count
            frame, ts = cam.frame, cam.frame_ms
            try:
                pose = await asyncio.to_thread(self.process, frame, ts)
            except Exception as e:  # one bad frame must not kill tracking
                cam.error = f"tracking error: {e}"
                continue
            if pose is not None:
                self.latency_ms = now_ms() - ts
                self.on_pose(pose)

    def status(self) -> dict:
        cam, cal = self.camera, self.calibration
        rows, cols, _, _ = self.get_board()
        H_norm = None
        if cal is not None:
            import numpy as np
            H = cal.board_to_image(rows, cols) @ np.diag([cols, rows, 1.0])     # board 0..1 -> px
            H = np.diag([1 / cal.imageWidth, 1 / cal.imageHeight, 1.0]) @ H     # -> image 0..1
            H_norm = [float(v) for v in (H / H[2, 2]).ravel()]
        d = self.last or {}
        return {
            "cameraIndex": cam.index, "running": cam.running, "tracking": self.tracking,
            "error": cam.error, "fps": cam.fps, "latencyMs": self.latency_ms,
            "frameSize": list(cam.frame.shape[1::-1]) if cam.frame is not None else None,
            "calibrated": cal is not None,
            "calibratedAt": cal.createdAt if cal else None,
            "boardToImage": H_norm,
            "detection": {"found": bool(d.get("found")), "reason": d.get("reason"), "x": d.get("x"), "y": d.get("y"),
                          "area": d.get("area"), "runnerUp": d.get("runnerUp"), "bbox": d.get("bbox")},
        }
