from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(name: str) -> Any:
    path = DATA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(name: str, payload: Any) -> None:
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_all() -> dict[str, Any]:
    return {
        "matches": load_json("matches.json"),
        "users": load_json("users.json"),
        "predictions": load_json("predictions.json"),
        "third_place_predictions": load_json("third_place_predictions.json"),
        "config": load_json("config.json"),
    }
