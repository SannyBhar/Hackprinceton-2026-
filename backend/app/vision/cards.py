"""Two-inch DICT_4X4_1000 movement blocks, read as one left-to-right row.

IDs 0/1/2/3 = FORWARD/BACKWARD/RIGHT/LEFT. Repeated IDs are separate physical blocks.
START/STOP markers 10/80 remain optional; the review UI supplies missing bookends.
Legacy fixture finalization is retained for stored numeric-scan compatibility only.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional, Protocol

from ..models import ScannedCard, ScanResult
from .camera import CameraSource, OpenCvCameraSource
from .markers import CARD_OPS, DICTIONARY_NAME


def op_for_marker(marker_id: int) -> Optional[str]:
    return CARD_OPS.get(marker_id)


def finalize(cards: list[ScannedCard], source: str, *, unit_blocks: bool = False) -> ScanResult:
    """Common post-processing: duplicates, unknown cards, missing numbers."""
    errors: list[str] = []
    seen: set[int] = set()
    for c in cards:
        if c.cardId is not None and not unit_blocks:
            if c.cardId in seen:
                c.issues.append("duplicate detection of the same physical card")
            seen.add(c.cardId)
        if c.op is None:
            c.issues.append("unsupported or unknown card")
        if c.op in ("FORWARD", "BACKWARD"):
            if unit_blocks:
                c.rawSteps = 1
            elif c.rawSteps is None:
                c.issues.append("step count unreadable — instructor must enter it")
            elif c.stepsConfidence is None:
                c.issues.append("OCR confidence uncalibrated; instructor review required")
            elif c.stepsConfidence < 0.85:
                c.issues.append("low-confidence step count — confirm it")
    if not cards:
        errors.append("no cards detected on the scan mat")
    return ScanResult(unitBlocks=unit_blocks, scanId=uuid.uuid4().hex[:8], source=source, cards=cards, errors=errors,
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
        return finalize(cards, f"fixture:{f.name}", unit_blocks=data.get("unitBlocks", False))


class OcrPort(Protocol):
    """Numeric-crop callback; confidence is None when the OCR adapter is uncalibrated."""
    def __call__(self, gray_crop: object) -> tuple[int | None, float | None]: ...


class OpenCvCardRecognizer:
    """One ordered row; no numeric box, crop or handwriting inference.

    The optional OCR argument remains accepted for older callers but is never invoked.
    Arena tracking is markerless and lives independently in board_camera.py.
    """
    name = "opencv"

    def __init__(self, camera_index: int = 0, ocr: OcrPort | None = None,
                 camera: CameraSource | None = None):
        import cv2  # noqa: F401  (fail fast if not installed)
        self.camera_index = camera_index
        self.camera = camera or OpenCvCameraSource()
        self.ocr = ocr  # deprecated compatibility argument; physical blocks have no distances

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
        if img is None:
            raise ValueError("scan image could not be decoded")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, DICTIONARY_NAME)))
        corners, ids, _ = detector.detectMarkers(gray)
        found = []
        if ids is not None:
            for quad, mid in zip(corners, ids.flatten()):
                mid = int(mid)
                found.append((float(quad[0][:, 0].mean()), mid, quad[0]))
        found.sort(key=lambda t: (t[0], float(t[2][:, 1].mean())))
        cards: list[ScannedCard] = []
        for order, (_, mid, quad) in enumerate(found):
            op = op_for_marker(mid)
            card = ScannedCard(order=order, cardId=mid, op=op)
            if op in ("FORWARD", "BACKWARD"):
                card.rawSteps = 1
            cards.append(card)
        return finalize(cards, "opencv", unit_blocks=True)
