"""Kev decision model: is the server up, and does it answer a typed question on a request purpose (S-031, S-032)."""

import os

import httpx
from _common import SENTENCE, skip

KEV = os.environ.get("KEV_BASE_URL", "http://127.0.0.1:8009")

try:
    models = httpx.get(f"{KEV}/v1/models", timeout=5).json()
except httpx.HTTPError:
    skip(f"Kev not reachable at {KEV} (runs on the GPU machine, see README.md)")
print(models)

r = httpx.post(f"{KEV}/v1/systemone", timeout=60, json={
    "state": SENTENCE,
    "model": "kev-latest",
    "questions": {"prohibited": {"type": "noul",
                                 "instructions": "Is this purpose setting insurance premiums?"}},
})
r.raise_for_status()
print(r.json()["answers"]["prohibited"])
