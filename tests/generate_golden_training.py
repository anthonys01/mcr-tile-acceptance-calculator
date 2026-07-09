"""Regenerate the golden snapshot file for training_engine tests.

Run from the repository root:

    python tests/generate_golden_training.py

Only run this when the change in behaviour is intentional. Review the diff of
``tests/golden_training.json`` carefully before committing.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.training_snapshot_util import build_all_snapshots

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "golden_training.json"
)


def main():
    snapshots = build_all_snapshots()
    with open(GOLDEN_PATH, "w", encoding="utf-8") as golden_file:
        json.dump(snapshots, golden_file, indent=2, ensure_ascii=False, sort_keys=True)
        golden_file.write("\n")
    total = sum(len(section) for section in snapshots.values())
    print(f"Wrote {total} snapshots to {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
