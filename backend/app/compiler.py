"""Program validation and dry-run planning against board bounds."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import HEADING_VEC, HEADINGS, Cell, Instruction, Puzzle

DEFAULT_MAX_STEPS = 5


@dataclass
class PlanResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    # Expected cell entries if the robot executes perfectly (not the grading target).
    plannedEntries: list[Cell] = field(default_factory=list)
    finalCell: Cell | None = None
    finalHeading: str | None = None


def turn(heading: str, op: str) -> str:
    i = HEADINGS.index(heading)
    return HEADINGS[(i + (1 if op == "RIGHT" else -1)) % 4]


def validate_syntax(program: list[Instruction], max_steps: int = DEFAULT_MAX_STEPS) -> list[str]:
    errs: list[str] = []
    if not program:
        return ["program is empty"]
    if program[0].op != "START":
        errs.append("program must begin with START")
    if program[-1].op != "STOP":
        errs.append("program must end with STOP")
    for i, ins in enumerate(program):
        if ins.op == "START" and i != 0:
            errs.append(f"card {i + 1}: START may only appear first")
        if ins.op == "STOP" and i != len(program) - 1:
            errs.append(f"card {i + 1}: STOP may only appear last")
        if ins.op in ("FORWARD", "BACKWARD"):
            s = ins.steps
            if not isinstance(s, int) or isinstance(s, bool) or s < 1 or s > max_steps:
                errs.append(f"card {i + 1}: {ins.op} steps must be an integer 1–{max_steps} (got {s})")
    return errs


def plan(puzzle: Puzzle, program: list[Instruction], max_steps: int = DEFAULT_MAX_STEPS) -> PlanResult:
    errs = validate_syntax(program, max_steps)
    if errs:
        return PlanResult(False, errs)
    r, c, h = puzzle.startCell.row, puzzle.startCell.col, puzzle.startHeading
    entries: list[Cell] = []
    for i, ins in enumerate(program):
        if ins.op in ("LEFT", "RIGHT"):
            h = turn(h, ins.op)
        elif ins.op in ("FORWARD", "BACKWARD"):
            dr, dc = HEADING_VEC[h]
            sign = 1 if ins.op == "FORWARD" else -1
            for _ in range(ins.steps or 0):
                r, c = r + sign * dr, c + sign * dc
                if not (0 <= r < puzzle.rows and 0 <= c < puzzle.cols):
                    errs.append(
                        f"card {i + 1}: {ins.op} {ins.steps} would leave the board "
                        f"(at row {r}, col {c}). Correct the program before running."
                    )
                    return PlanResult(False, errs, entries)
                entries.append(Cell(row=r, col=c))
    return PlanResult(True, [], entries, Cell(row=r, col=c), h)
