"""Joystick demonstration -> block program.

Uses executed actions (which encode heading changes and travel direction) plus
observed cell entries. Position alone cannot distinguish BACKWARD from a turn +
FORWARD, so actions are the primary source and observations are cross-checked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .compiler import DEFAULT_MAX_STEPS
from .models import Cell, Instruction

Action = Literal["FORWARD", "BACKWARD", "LEFT", "RIGHT"]


@dataclass
class RecordedAction:
    action: Action
    observedEntries: list[Cell] = field(default_factory=list)


@dataclass
class GeneratedProgram:
    instructions: list[Instruction]
    warnings: list[str]
    observedPath: list[Cell]


def generate_program(actions: list[RecordedAction], max_steps: int = DEFAULT_MAX_STEPS) -> GeneratedProgram:
    out: list[Instruction] = [Instruction(op="START")]
    warnings: list[str] = []
    path: list[Cell] = []
    for i, a in enumerate(actions):
        path.extend(a.observedEntries)
        if a.action in ("FORWARD", "BACKWARD"):
            if len(a.observedEntries) != 1:
                warnings.append(
                    f"action {i + 1} ({a.action}): expected 1 cell entry, observed "
                    f"{len(a.observedEntries)}; block reflects the commanded action"
                )
            last = out[-1]
            if last.op == a.action and (last.steps or 0) < max_steps:
                last.steps = (last.steps or 0) + 1
            else:
                out.append(Instruction(op=a.action, steps=1))
        else:
            if a.observedEntries:
                warnings.append(f"action {i + 1} ({a.action}): robot changed cell during a turn")
            out.append(Instruction(op=a.action))
    out.append(Instruction(op="STOP"))
    return GeneratedProgram(out, warnings, path)
