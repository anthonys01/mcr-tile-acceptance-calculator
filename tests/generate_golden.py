"""Regenerate the golden snapshot file for tile_acceptance_calculator tests.

Run from the repository root:

    python tests/generate_golden.py

Only run this when the change in behaviour is intentional. Review the diff of
``tests/golden_acceptance.json`` carefully before committing.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.snapshot_util import build_all_snapshots

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_acceptance.json")


def main():
    snapshots = build_all_snapshots()
    with open(GOLDEN_PATH, "w", encoding="utf-8") as golden_file:
        json.dump(snapshots, golden_file, indent=2, ensure_ascii=False, sort_keys=True)
        golden_file.write("\n")
    print(f"Wrote {len(snapshots)} snapshots to {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
