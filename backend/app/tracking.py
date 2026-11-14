"""Turn a noisy pose stream into stable cell-entry events.

Works identically for the simulator and for the real overhead camera, so the
grading path is exercised end-to-end before hardware exists.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .models import Cell, RobotPose


@dataclass
class TrackerConfig:
    inner_margin: float = 0.18      # pose must be this far (cell units) inside a new cell
    confirm_frames: int = 2         # consecutive frames needed to confirm a new cell
    boundary_margin: float = 0.08   # stop if pose centre gets closer than this to the board edge
    stale_ms: int = 800             # tracking considered lost after this long without valid pose


@dataclass
class TrackerOutput:
    entered: Optional[Cell] = None
    skipped: bool = False          # entered a non-adjacent cell (tracking jumped)
    boundary: bool = False
    warnings: list[str] = field(default_factory=list)


class CellEntryDetector:
    def __init__(self, rows: int, cols: int, start: Cell, cfg: TrackerConfig | None = None):
        self.rows, self.cols = rows, cols
        self.cfg = cfg or TrackerConfig()
        self.current = start          # initial stationary start is NOT an entry
        self._candidate: Optional[Cell] = None
        self._count = 0
        self.last_valid_ms: Optional[int] = None

    def update(self, pose: RobotPose) -> TrackerOutput:
        out = TrackerOutput()
        if not pose.trackingValid:
            return out
        self.last_valid_ms = pose.timestampMs
        m = self.cfg.boundary_margin
        if pose.x < m or pose.y < m or pose.x > self.cols - m or pose.y > self.rows - m:
            out.boundary = True
        col, row = math.floor(pose.x), math.floor(pose.y)
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return out
        cell = Cell(row=row, col=col)
        if cell == self.current:
            self._candidate, self._count = None, 0
            return out
        fx, fy = pose.x - col, pose.y - row
        im = self.cfg.inner_margin
        if not (im <= fx <= 1 - im and im <= fy <= 1 - im):
            return out  # still near a boundary: hysteresis, don't decide yet
        if cell != self._candidate:
            self._candidate, self._count = cell, 0
        self._count += 1
        if self._count >= self.cfg.confirm_frames:
            if abs(cell.row - self.current.row) + abs(cell.col - self.current.col) != 1:
                out.skipped = True
                out.warnings.append(
                    f"tracking jumped from {self.current.key()} to {cell.key()}; "
                    "intermediate cells were not observed and are not fabricated"
                )
            self.current = cell
            self._candidate, self._count = None, 0
            out.entered = cell
        return out

    def is_stale(self, now_ms: int) -> bool:
        return self.last_valid_ms is not None and now_ms - self.last_valid_ms > self.cfg.stale_ms
