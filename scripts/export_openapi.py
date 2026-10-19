"""Regenerate contract/openapi.json from the application code.

Run from the repository root:   python scripts/export_openapi.py

Do this ONLY when you deliberately change the API's public shape, and commit the new
file in the same commit as the code change so reviewers (and other teams) see the diff.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "contract" / "openapi.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build() -> dict:
    """The contract as the code describes it right now (normalised through JSON)."""
    from main import app

    return json.loads(json.dumps(app.openapi()))


def main() -> None:
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
