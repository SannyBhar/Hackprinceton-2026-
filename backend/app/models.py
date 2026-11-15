"""Shared data contracts (mirror of frontend/src/api/types.ts).

Conventions (implementation defaults, see docs/ASSUMPTIONS.md):
- Cell {row, col}: zero-indexed, row grows downward, col grows rightward.
- Continuous pose {x, y} in cell units; cell centre = (col + 0.5, row + 0.5).
- headingDeg: 0 = N (up, -row), 90 = E (+col), 180 = S, 270 = W.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator, StrictInt

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
    steps: Optional[StrictInt] = None
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
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")  # also a filename: no paths
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
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    headingDeg: float = Field(allow_inf_nan=False)
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
    TRACKING_UNCERTAIN = "TRACKING_UNCERTAIN"
    CONNECTION_LOST = "CONNECTION_LOST"
    ROBOT_FAULT = "ROBOT_FAULT"
    RECORDING_ENDED = "RECORDING_ENDED"


class ScannedCard(BaseModel):
    """One recognised card. Raw recognition is kept separate from confirmed values."""
    order: int
    cardId: Optional[int]
    op: Optional[Op]
    ocrText: Optional[str] = None
    ocrModel: Optional[str] = None
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
    x: float = Field(ge=0, le=1, allow_inf_nan=False)  # normalised 0..1 of projection viewport width
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class ProjectorCalibration(BaseModel):
    """Projected-board quadrilateral TL, TR, BR, BL in normalised viewport coordinates."""
    corners: list[Corner] = Field(min_length=4, max_length=4)
    viewportWidth: int = Field(gt=0)
    viewportHeight: int = Field(gt=0)
    markerMask: float = 0.35  # fraction of a cell kept dark at each board corner
    showGrid: bool = True

    @model_validator(mode="after")
    def _convex(self):
        points = self.corners
        for i in range(4):
            a, b, c = points[i], points[(i+1)%4], points[(i+2)%4]
            if (b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x) <= 1e-8:
                raise ValueError("projector corners must be convex TL/TR/BR/BL")
        return self


class ProjectionSettings(BaseModel):
    calibrating: bool = False
    testPattern: bool = False
    activeCorner: int = 0
    artworkId: Optional[str] = None
    artworkHash: Optional[str] = None
    theme: str = "glossy"          # prepared fallback theme id (AI artwork is a later milestone)
    showRobot: bool = True         # draw the tracked robot glyph on the projection


def puzzle_hash(puzzle: Puzzle) -> str:
    import hashlib
    return hashlib.sha256(puzzle.model_dump_json().encode()).hexdigest()
