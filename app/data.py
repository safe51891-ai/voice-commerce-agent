"""Loads the synthetic store data from the data/ folder."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> list[dict]:
    return json.loads((ROOT / "data" / name).read_text())
