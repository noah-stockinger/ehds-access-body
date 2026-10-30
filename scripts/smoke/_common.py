"""Shared helpers for smoke tests. Exit 0 = PASS, 77 = SKIP, other = FAIL."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "smoke-out"
OUT.mkdir(exist_ok=True)
load_dotenv(os.environ.get("ENV_FILE", REPO / ".env"))

# A request purpose, like those in data/track3/requests (request text only, never patient-level data; S-022).
SENTENCE = "We want to align private health insurance premiums for customers with diabetes with their actual risk."
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
GENERAL_MODEL = os.environ.get("OLLAMA_GENERAL_MODEL", "gemma4:12b")


def skip(reason: str) -> None:
    print(f"SKIP: {reason}")
    sys.exit(77)
