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

    def list_library(self) -> list[dict]:
        return [{**p.model_dump(mode="json"), "builtin": self.is_builtin(p.id),
                 "edited": (self.dir / "puzzles" / f"{p.id}.json").exists()}
                for p in self.list_puzzles()]

    def is_builtin(self, puzzle_id: str) -> bool:
        return any(Puzzle.model_validate_json(f.read_text()).id == puzzle_id
                   for f in (FIXTURES / "puzzles").glob("*.json"))

    def delete_puzzle(self, puzzle_id: str) -> str:
        """Remove a user puzzle. For a bundled example this only reverts local edits."""
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", puzzle_id):
            return "missing"
        f = self.dir / "puzzles" / f"{puzzle_id}.json"
        if not f.exists():
            return "missing"
        f.unlink()
        return "reverted" if self.is_builtin(puzzle_id) else "deleted"

    def save_puzzle(self, p: Puzzle) -> None:
        self._write(self.dir / "puzzles" / f"{p.id}.json", p.model_dump(mode="json"))

    def load_calibration(self) -> Optional[ProjectorCalibration]:
        f = self.dir / "projector_calibration.json"
        return ProjectorCalibration.model_validate_json(f.read_text()) if f.exists() else None

    def save_calibration(self, c: ProjectorCalibration) -> None:
        self._write(self.dir / "projector_calibration.json", c.model_dump(mode="json"))

    def save_attempt(self, attempt_id: str, record: dict) -> None:
        self._write(self.dir / "attempts" / f"{attempt_id}.json", record)

    def list_attempts(self):
        return sorted([json.loads(f.read_text()) for f in (self.dir / "attempts").glob("*.json")], key=lambda r:r.get("startedAt",0))

    def _record_path(self, kind, id):
        import re
        from .repository import RECORD_KINDS as KINDS
        if kind not in KINDS or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", id):
            raise ValueError("invalid record identifier")
        path = self.dir / kind / (id + ".json")
        path.parent.mkdir(exist_ok=True)
        return path

    def put_record(self, kind, id, body):
        self._write(self._record_path(kind,id),body)

    def get_record(self, kind, id):
        path = self._record_path(kind,id)
        return json.loads(path.read_text()) if path.exists() else None

    def list_records(self, kind):
        path = self._record_path(kind,"index").parent
        return [json.loads(f.read_text()) for f in sorted(path.glob("*.json"))]
