"""Fill the register with R01–R10 (as proposals), so the frontend has data to show.

Usage: uv run python scripts/seed_demo.py [--confirm R01,R05]   (writes to $HDAB_VAR, default var/)
"""

import argparse

from dotenv import load_dotenv

from hdab import pipeline
from hdab.data import load_requests


def main() -> None:
    load_dotenv()  # KEV_MODE / TYPESAFE_API_KEY from .env, like the API
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", default="", help="comma-separated IDs to confirm as staff 'demo.officer'")
    confirm = {i for i in parser.parse_args().confirm.split(",") if i}
    for r in load_requests():
        a = pipeline.submit(r)
        if r.id in confirm:
            pipeline.confirm(r.id, "demo.officer")
        print(r.id, a.decision, a.mode, "flagged" if a.needs_review else "", "confirmed" if r.id in confirm else "")


if __name__ == "__main__":
    main()
