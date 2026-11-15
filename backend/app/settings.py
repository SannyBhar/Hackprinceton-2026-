"""Backend adapter configuration, with legacy CA_* compatibility."""
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def env_value(name: str, default: str, env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    return source.get("GRASSROOT_" + name, source.get("CA_" + name, default))


@dataclass(frozen=True)
class Settings:
    robot: str = "sim"
    robot_url: str = "ws://192.168.4.1:81/"
    cards: str = "fixture"
    card_camera: int = 0
    tracker: str = "sim"
    track_camera: int = 1
    data_dir: Path = ROOT / "data"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        def get(key: str, default: str) -> str:
            return env_value(key, default, env)
        cards, tracker = get("CARDS", "fixture"), get("TRACKER", "sim")
        return cls(robot=get("ROBOT", "sim"), robot_url=get("ROBOT_URL", "ws://192.168.4.1:81/"),
                   cards=cards, tracker=tracker,
                   card_camera=int(get("CARD_CAMERA", "0")) if cards == "opencv" else 0,
                   track_camera=int(get("TRACK_CAMERA", "1")) if tracker in ("camera", "board-camera") else 1,
                   data_dir=Path(get("DATA_DIR", str(ROOT / "data"))))
