"""Camera acquisition boundary. No arbitration or scan/track handoff yet.

Each consumer owns a scoped capture. A future single-camera coordinator can implement
CameraSource without changing card detection or pose processing. Frame timestamps
continue to be assigned by the existing pose processor.
"""
from contextlib import contextmanager
from typing import Any, ContextManager, Iterator, Literal, Protocol

CameraRole = Literal["scan", "track"]


class FrameReader(Protocol):
    def read(self) -> tuple[bool, Any]: ...


class CameraSource(Protocol):
    def open(self, index: int, role: CameraRole) -> ContextManager[FrameReader]: ...


class OpenCvCameraSource:
    @contextmanager
    def open(self, index: int, role: CameraRole) -> Iterator[FrameReader]:
        import cv2
        cap = cv2.VideoCapture(index)
        try:
            yield cap
        finally:
            cap.release()
