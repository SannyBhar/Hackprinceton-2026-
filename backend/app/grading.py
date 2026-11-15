"""Pure, deterministic grading. No I/O, no robot, no AI.

Same-index ordered grading (scope §5): entry i is correct iff
    i < len(target) and actual[i] == target[i]
The index always advances; an error never latches later entries red, and the
target pointer is never held waiting for recovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from .models import Cell, VisitEvent


class Grader:
    def __init__(self, attempt_id: str, target: list[Cell]):
        self.attempt_id = attempt_id
        self.target = list(target)
        self.events: list[VisitEvent] = []

    @property
    def index(self) -> int:
        return len(self.events)

    def on_entry(self, cell: Cell, timestamp_ms: int) -> VisitEvent:
        i = self.index
        expected = self.target[i] if i < len(self.target) else None
        ev = VisitEvent(
            attemptId=self.attempt_id,
            index=i,
            timestampMs=timestamp_ms,
            actual=cell,
            expected=expected,
            correct=expected is not None and cell == expected,
        )
        self.events.append(ev)
        return ev


def grade_sequence(target: list[Cell], actual: list[Cell]) -> list[bool]:
    g = Grader("pure", target)
    return [g.on_entry(c, 0).correct for c in actual]


# ---------------------------------------------------------------- tile rendering

TileKind = Literal["unvisited", "solid", "split"]


@dataclass
class TileState:
    kind: TileKind
    left: Optional[bool] = None   # left/top-left triangle result (or solid result)
    right: Optional[bool] = None  # right/bottom-right triangle result
    visits: int = 0

    def to_dict(self) -> dict:
        return {"kind": self.kind, "left": self.left, "right": self.right, "visits": self.visits}


def reduce_tile(history: list[bool], policy: str = "first_latest") -> TileState:
    """Reduce a physical cell's visit-correctness history to a display state.

    Two-visit cases are agreed (scope §6). Three+ mixed visits are NOT settled;
    the default 'first_latest' policy keeps the FIRST result on the left and the
    LATEST on the right, rendering solid when they are equal. Full history is
    always preserved separately.
    """
    if not history:
        return TileState("unvisited")
    if all(history):
        return TileState("solid", True, True, len(history))
    if not any(history):
        return TileState("solid", False, False, len(history))
    if policy == "first_latest":
        first, last = history[0], history[-1]
    elif policy == "first_other":  # alternative: first vs. first differing result
        first = history[0]
        last = next(h for h in history if h != first)
    else:
        raise ValueError(f"unknown tile policy {policy}")
    if first == last:
        return TileState("solid", first, last, len(history))
    return TileState("split", first, last, len(history))


@dataclass
class AttemptSummary:
    entries: int
    correct: int
    incorrect: int
    missing: int
    extra: int
    reachedGoal: bool
    success: bool
    details: list[str] = field(default_factory=list)
    pathExactlyCorrect: bool = False


def summarize(target: list[Cell], events: list[VisitEvent], goal: Cell,
              finished_normally: bool) -> AttemptSummary:
    correct = sum(e.correct for e in events)
    extra = max(0, len(events) - len(target))
    missing = max(0, len(target) - len(events))
    final = events[-1].actual if events else None
    reached_goal = final == goal
    success = (
        finished_normally
        and len(events) == len(target)
        and correct == len(target)
        and reached_goal
    )
    details = []
    if missing:
        details.append(f"{missing} target cell(s) not reached (incomplete)")
    if extra:
        details.append(f"{extra} extra cell(s) after the route ended")
    if not finished_normally:
        details.append("run ended by an operational stop, not program completion")
    return AttemptSummary(len(events), correct, len(events) - correct, missing, extra,
                          reached_goal, success, details, len(events)==len(target) and correct==len(target))
