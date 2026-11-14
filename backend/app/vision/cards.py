"""Card recognition adapters.

Marker ID registry (ArUco DICT_4X4_100). Repeated cards get distinct IDs that map to one opcode:
  0-3   board corners TL, TR, BR, BL     4  robot
  10-19 START   20-39 FORWARD   40-59 BACKWARD   60-69 LEFT   70-79 RIGHT   80-89 STOP
OCR is a replaceable adapter; the default returns no candidate so the instructor
must type every step count (never guess a motion parameter silently).
"""
from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path
from typing import Optional, Protocol

from ..models import ScannedCard, ScanResult
from .camera import CameraSource, OpenCvCameraSource

CORNER_IDS = {0: "TL", 1: "TR", 2: "BR", 3: "BL"}
ROBOT_ID = 4
OP_RANGES = [
    (10, 19, "START"), (20, 39, "FORWARD"), (40, 59, "BACKWARD"),
    (60, 69, "LEFT"), (70, 79, "RIGHT"), (80, 89, "STOP"),
]


def op_for_marker(marker_id: int) -> Optional[str]:
    for lo, hi, op in OP_RANGES:
        if lo <= marker_id <= hi:
            return op
    return None


def finalize(cards: list[ScannedCard], source: str) -> ScanResult:
    """Common post-processing: duplicates, unknown cards, missing numbers."""
    errors: list[str] = []
    seen: set[int] = set()
    for c in cards:
        if c.cardId is not None:
            if c.cardId in seen:
                c.issues.append("duplicate detection of the same physical card")
            seen.add(c.cardId)
        if c.op is None:
            c.issues.append("unsupported or unknown card")
        if c.op in ("FORWARD", "BACKWARD"):
            if c.rawSteps is None:
                c.issues.append("step count unreadable — instructor must enter it")
            elif (c.stepsConfidence or 0) < 0.85:
                c.issues.append("low-confidence step count — confirm it")
    if not cards:
        errors.append("no cards detected on the scan mat")
    return ScanResult(scanId=uuid.uuid4().hex[:8], source=source, cards=cards, errors=errors,
                      needsReview=True)


class CardRecognizer(Protocol):
    name: str
    def scan(self, image_bytes: Optional[bytes] = None) -> ScanResult: ...


class FixtureCardRecognizer:
    """Plays back fixtures/scans/*.json, cycling on each scan. For demos without a camera."""
    name = "fixture"

    def __init__(self, directory: Path):
        self.files = sorted(directory.glob("*.json"))
        self.i = 0

    def scan(self, image_bytes: Optional[bytes] = None) -> ScanResult:
        if not self.files:
            return finalize([], "fixture:none")
        f = self.files[self.i % len(self.files)]
        self.i += 1
        data = json.loads(f.read_text())
        cards = [ScannedCard(**c) for c in data["cards"]]
        return finalize(cards, f"fixture:{f.name}")


class OcrPort(Protocol):
    """Existing numeric-crop callback; no handwriting model is provided."""
    def __call__(self, gray_crop: object) -> tuple[int | None, float]: ...


class OpenCvCardRecognizer:
    """Single ordered horizontal row of cards, read left-to-right. Needs opencv-contrib-python.

    Each card: marker on the left half, numeric box on the right half (see tools/make_cards.py).
    The numeric crop is rectified from the marker's corners so card tilt doesn't matter.
    """
    name = "opencv"

    def __init__(self, camera_index: int = 0, ocr: OcrPort | None = None,
                 camera: CameraSource | None = None):
        import cv2  # noqa: F401  (fail fast if not installed)
        self.camera_index = camera_index
        self.camera = camera or OpenCvCameraSource()
        self.ocr = ocr  # callable(gray_crop) -> (int|None, confidence)

    def _grab(self) -> bytes:
        import cv2
        with self.camera.open(self.camera_index, "scan") as cap:
            for _ in range(5):  # let exposure settle
                ok, frame = cap.read()
        if not ok:
            raise RuntimeError("card camera frame grab failed")
        return cv2.imencode(".png", frame)[1].tobytes()

    def scan(self, image_bytes: Optional[bytes] = None) -> ScanResult:
        import cv2
        import numpy as np
        if image_bytes is None:
            image_bytes = self._grab()
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100))
        corners, ids, _ = detector.detectMarkers(gray)
        found = []
        if ids is not None:
            for quad, mid in zip(corners, ids.flatten()):
                mid = int(mid)
                if mid in CORNER_IDS or mid == ROBOT_ID:
                    continue
                found.append((float(quad[0][:, 0].mean()), mid, quad[0]))
        found.sort(key=lambda t: t[0])
        cards: list[ScannedCard] = []
        for order, (_, mid, quad) in enumerate(found):
            op = op_for_marker(mid)
            card = ScannedCard(order=order, cardId=mid, op=op)
            if op in ("FORWARD", "BACKWARD"):
                # Marker occupies unit square [0,1]^2 in card space; numeric box is [1.25,2.75]x[0,1].
                side = 96
                src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
                H = cv2.getPerspectiveTransform(src, quad.astype(np.float32))
                box = np.array([[1.25, 0], [2.75, 0], [2.75, 1], [1.25, 1]], np.float32)
                img_box = cv2.perspectiveTransform(box[None], H)[0]
                dst = np.array([[0, 0], [side * 1.5, 0], [side * 1.5, side], [0, side]], np.float32)
                M = cv2.getPerspectiveTransform(img_box, dst)
                crop = cv2.warpPerspective(gray, M, (int(side * 1.5), side))
                card.cropDataUrl = "data:image/png;base64," + base64.b64encode(
                    cv2.imencode(".png", crop)[1].tobytes()).decode()
                if self.ocr:
                    card.rawSteps, card.stepsConfidence = self.ocr(crop)
            cards.append(card)
        return finalize(cards, "opencv")
