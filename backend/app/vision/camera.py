"""Scoped capture port used by card detection and the shared CameraCoordinator.

Role arbitration/revalidation lives in coordinator.py; this adapter only owns acquisition.
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
