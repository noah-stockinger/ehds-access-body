"""Locations of the challenge data and loaders for requests and expected answers."""

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from hdab.contracts import Answer, Request

TRACK3_DIR = Path(os.environ.get("TRACK3_DATA", Path(__file__).resolve().parents[2] / "data" / "track3"))
DATA_DIR = TRACK3_DIR / "data"
REQUESTS_DIR = TRACK3_DIR / "requests"
VAR_DIR = Path(os.environ.get("HDAB_VAR", Path(__file__).resolve().parents[2] / "var"))  # register and SPE files


def load_requests() -> list[Request]:
    return [Request.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(REQUESTS_DIR.glob("R*.json"))]


def load_expected() -> dict[str, Answer]:
    return {k: Answer.model_validate(v) for k, v in json.loads((REQUESTS_DIR / "expected.json").read_text(encoding="utf-8")).items()}


@lru_cache(maxsize=1)
def load_tables() -> dict[str, pd.DataFrame]:
    """The five CSVs as strings (dates stay ISO text, values keep their exact decimal digits)."""
    tables = {name: pd.read_csv(DATA_DIR / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8")
              for name in ["patients", "conditions", "medications", "observations", "encounters"]}
    tables["patients"]["opted_out"] = tables["patients"]["opted_out"].str.lower() == "true"
    return tables
