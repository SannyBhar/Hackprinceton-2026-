"""Robot transport contract. Grading never flows to the robot; it only receives motion primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Protocol

from ..models import RobotPose

PrimitiveKind = Literal["MOVE", "TURN", "STOP"]


@dataclass
class Primitive:
    runId: str
    instrIndex: int
    msgId: str            # unique; a retried/duplicate msgId must never move twice
    kind: PrimitiveKind
    value: int = 0        # MOVE: signed cells (+fwd / -back). TURN: signed degrees (+right / -left)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Ack:
    msgId: str
    status: Literal["DONE", "STOPPED", "DUPLICATE", "ERROR"]
    error: Optional[str] = None


PoseCallback = Callable[[RobotPose], None]


class RobotAdapter(Protocol):
    name: str
    on_pose: Optional[PoseCallback]   # set when the adapter itself is the pose source (simulator)

    @property
    def connected(self) -> bool: ...
    async def start(self) -> None: ...
    async def execute(self, p: Primitive) -> Ack: ...
    async def stop(self, reason: str) -> None: ...
    def place(self, row: int, col: int, heading_deg: float) -> None: ...
