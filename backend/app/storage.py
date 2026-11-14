"""Local JSON persistence (puzzles, calibration, attempt records)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import ProjectorCalibration, Puzzle

from .settings import FIXTURES, ROOT, env_value

# Preserve legacy imports and the direct Storage() default. Wiring resolves settings at startup.
DATA = Path(env_value("DATA_DIR", str(ROOT / "data")))


class Storage:
    def __init__(self, data_dir: Path = DATA):
        self.dir = data_dir
        (self.dir / "puzzles").mkdir(parents=True, exist_ok=True)
        (self.dir / "attempts").mkdir(parents=True, exist_ok=True)

    def _write(self, path: Path, obj) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, indent=2))
        tmp.replace(path)

    # puzzles: user puzzles in data/, bundled examples in fixtures/
    def list_puzzles(self) -> list[Puzzle]:
        out: dict[str, Puzzle] = {}
        for d in (FIXTURES / "puzzles", self.dir / "puzzles"):
            for f in sorted(d.glob("*.json")):
                p = Puzzle.model_validate_json(f.read_text())
                out[p.id] = p
        return list(out.values())

    def save_puzzle(self, p: Puzzle) -> None:
        self._write(self.dir / "puzzles" / f"{p.id}.json", p.model_dump(mode="json"))

    def load_calibration(self) -> Optional[ProjectorCalibration]:
        f = self.dir / "projector_calibration.json"
        return ProjectorCalibration.model_validate_json(f.read_text()) if f.exists() else None

    def save_calibration(self, c: ProjectorCalibration) -> None:
        self._write(self.dir / "projector_calibration.json", c.model_dump(mode="json"))

    def save_attempt(self, attempt_id: str, record: dict) -> None:
        self._write(self.dir / "attempts" / f"{attempt_id}.json", record)
