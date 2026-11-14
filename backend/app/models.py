"""Shared data contracts (mirror of frontend/src/api/types.ts).

Conventions (implementation defaults, see docs/ASSUMPTIONS.md):
- Cell {row, col}: zero-indexed, row grows downward, col grows rightward.
- Continuous pose {x, y} in cell units; cell centre = (col + 0.5, row + 0.5).
- headingDeg: 0 = N (up, -row), 90 = E (+col), 180 = S, 270 = W.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Heading = Literal["N", "E", "S", "W"]
HEADINGS: list[str] = ["N", "E", "S", "W"]
HEADING_DEG = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}
# (drow, dcol) for one cell of forward travel
HEADING_VEC = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}


class Cell(BaseModel):
    model_config = ConfigDict(frozen=True)
    row: int
    col: int

    def key(self) -> str:
        return f"{self.row},{self.col}"


Op = Literal["START", "STOP", "LEFT", "RIGHT", "FORWARD", "BACKWARD"]


class Instruction(BaseModel):
    op: Op
    steps: Optional[int] = None
    cardId: Optional[int] = None

    @model_validator(mode="after")
    def _steps_only_for_translation(self):
        if self.op in ("FORWARD", "BACKWARD"):
            if self.steps is None:
                raise ValueError(f"{self.op} requires an integer step count")
        elif self.steps is not None:
            raise ValueError(f"{self.op} does not take a step count")
        return self


class Puzzle(BaseModel):
    id: str
    version: int = 1
    name: str
    rows: int = Field(ge=2, le=20)
    cols: int = Field(ge=2, le=20)
    startCell: Cell
    startHeading: Heading
    goalCell: Cell
    targetEntries: list[Cell]
    # Purely visual maze features (cells drawn as scenery/walls). Never used for grading.
    sceneryCells: list[Cell] = []

    @model_validator(mode="after")
    def _validate_geometry(self):
        def inb(c: Cell) -> bool:
            return 0 <= c.row < self.rows and 0 <= c.col < self.cols

        for name, c in (("startCell", self.startCell), ("goalCell", self.goalCell)):
            if not inb(c):
                raise ValueError(f"{name} {c.key()} is outside the {self.rows}x{self.cols} board")
        prev = self.startCell
        for i, c in enumerate(self.targetEntries):
            if not inb(c):
                raise ValueError(f"targetEntries[{i}] {c.key()} is out of bounds")
            if abs(c.row - prev.row) + abs(c.col - prev.col) != 1:
                raise ValueError(
                    f"targetEntries[{i}] {c.key()} is not orthogonally adjacent to {prev.key()}"
                )
            prev = c
        if self.targetEntries and self.targetEntries[-1] != self.goalCell:
            raise ValueError("goalCell must equal the last target entry")
        return self


class RobotPose(BaseModel):
    timestampMs: int
    x: float
    y: float
    headingDeg: float
    trackingValid: bool = True


class VisitEvent(BaseModel):
    attemptId: str
    index: int
    timestampMs: int
    actual: Cell
    expected: Optional[Cell]
    correct: bool


class SessionState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    PROGRAM_READY = "PROGRAM_READY"
    RUNNING = "RUNNING"
    RECORDING = "RECORDING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAULT = "FAULT"


class StopReason(str, Enum):
    PROGRAM_COMPLETE = "PROGRAM_COMPLETE"
    INSTRUCTOR_STOP = "INSTRUCTOR_STOP"
    BOUNDARY = "BOUNDARY"
    TRACKING_LOST = "TRACKING_LOST"
    CONNECTION_LOST = "CONNECTION_LOST"
    ROBOT_FAULT = "ROBOT_FAULT"
    RECORDING_ENDED = "RECORDING_ENDED"


class ScannedCard(BaseModel):
    """One recognised card. Raw recognition is kept separate from confirmed values."""
    order: int
    cardId: Optional[int]
    op: Optional[Op]
    rawSteps: Optional[int] = None          # OCR candidate, never used directly
    stepsConfidence: Optional[float] = None
    markerConfidence: float = 1.0
    cropDataUrl: Optional[str] = None       # numeric field crop for instructor review
    issues: list[str] = []


class ScanResult(BaseModel):
    scanId: str
    source: str
    cards: list[ScannedCard]
    errors: list[str] = []
    needsReview: bool = True


class Corner(BaseModel):
    x: float  # normalised 0..1 of projection viewport width
    y: float


class ProjectorCalibration(BaseModel):
    """Projected-board quadrilateral TL, TR, BR, BL in normalised viewport coordinates."""
    corners: list[Corner] = Field(min_length=4, max_length=4)
    viewportWidth: int
    viewportHeight: int
    markerMask: float = 0.35  # fraction of a cell kept dark at each board corner
    showGrid: bool = True


class ProjectionSettings(BaseModel):
    calibrating: bool = False
    testPattern: bool = False
    activeCorner: int = 0
    theme: str = "city"          # prepared fallback theme id (AI artwork is a later milestone)
    showRobot: bool = True         # draw the tracked robot glyph on the projection
