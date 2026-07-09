"""Helpers to build deterministic, JSON-serialisable snapshots of the
``training_engine`` public functions.

The snapshots are used for non-regression testing: the structured output of
``new_game``, ``analyze_turn``, ``evaluate_discard`` and ``score_winning_tiles``
is captured for a set of representative inputs and compared against a golden
file. When behaviour changes intentionally, regenerate the golden file with
``generate_golden_training.py``.

Determinism notes
-----------------
* ``new_game`` is driven by fixed seeds so the shuffled pool and the two winds
  are reproducible.
* ``visible`` vectors are built from the stable tile index (length 34).
* Hands are given as explicit tile-string lists so the "drawn" tile
  (``tiles[-1]``) is stable across runs.
"""

import json

from mahjong_objects import MahjongTile
import training_engine as te


# --- new_game: fixed seeds reproduce the exact pool + winds --------------------
NEW_GAME_SEEDS = [0, 1, 42, 2024, 123456789]


def _visible(counts=None):
    """Build a length-34 visible-tile vector from a {tile_str: count} mapping."""
    vector = [0] * 34
    for tile_str, count in (counts or {}).items():
        vector[MahjongTile(tile_str).index] = count
    return vector


# --- analyze_turn: 14-tile hands that still need a discard ---------------------
# name -> (tiles14, visible_counts, prevalent_wind, seat_wind)
ANALYZE_CASES = {
    "pure_straight_pinzu_wait": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "4p", "5p"],
        {},
        0,
        0,
    ),
    "pure_straight_with_visible": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "4p", "5p"],
        {"2p": 2, "5p": 1},
        0,
        0,
    ),
    "honors_with_winds": (
        ["1m", "2m", "3m", "1p", "2p", "3p", "5s", "5s", "5s",
         "1z", "1z", "2z", "5z", "5z"],
        {},
        1,
        2,
    ),
    "full_flush_shape": (
        ["1s", "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s",
         "9s", "9s", "3s", "5s", "7s"],
        {"1s": 1},
        0,
        0,
    ),
    "seven_pairs_shape": (
        ["1m", "1m", "3m", "3m", "5m", "5m", "7m", "7m", "9m",
         "9m", "2p", "2p", "4p", "6p"],
        {},
        0,
        0,
    ),
}


# --- evaluate_discard: score a single user-chosen discard ----------------------
# name -> (tiles14, discard, visible_counts, prevalent_wind, seat_wind)
EVALUATE_CASES = {
    "discard_terminal_keep_tenpai": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "4p", "5p"],
        "1p",
        {},
        0,
        0,
    ),
    "discard_middle_tile": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "4p", "5p"],
        "5p",
        {"4p": 1},
        0,
        0,
    ),
    "discard_with_winds": (
        ["1m", "2m", "3m", "1p", "2p", "3p", "5s", "5s", "5s",
         "1z", "1z", "2z", "5z", "5z"],
        "2z",
        {},
        1,
        2,
    ),
}


# --- score_winning_tiles: tenpai 13-tile hand + its acceptance -----------------
# name -> (tiles13, acceptance, self_drawn, last_tile, prevalent_wind, seat_wind)
SCORE_CASES = {
    "pure_straight_tanki": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "1z"],
        ["1z"],
        False,
        False,
        1,
        1,
    ),
    "pure_straight_tanki_self_drawn": (
        ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
         "1p", "2p", "3p", "1z"],
        ["1z"],
        True,
        False,
        1,
        1,
    ),
    "two_sided_wait": (
        ["2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p",
         "1p", "2s", "3s", "4s"],
        ["1m", "4m"],
        False,
        False,
        0,
        0,
    ),
}


def new_game_snapshot(seed) -> dict:
    """Deterministic snapshot of ``new_game`` for a fixed seed."""
    return json.loads(te.new_game(seed))


def analyze_turn_snapshot(tiles14, visible_counts, prevalent_wind, seat_wind) -> dict:
    return json.loads(
        te.analyze_turn(
            json.dumps(tiles14),
            json.dumps(_visible(visible_counts)),
            prevalent_wind,
            seat_wind,
        )
    )


def evaluate_discard_snapshot(
    tiles14, discard, visible_counts, prevalent_wind, seat_wind
) -> dict:
    return json.loads(
        te.evaluate_discard(
            json.dumps(tiles14),
            discard,
            json.dumps(_visible(visible_counts)),
            prevalent_wind,
            seat_wind,
        )
    )


def score_winning_tiles_snapshot(
    tiles13, acceptance, self_drawn, last_tile, prevalent_wind, seat_wind
) -> list:
    return json.loads(
        te.score_winning_tiles(
            json.dumps(tiles13),
            json.dumps(acceptance),
            self_drawn,
            last_tile,
            prevalent_wind,
            seat_wind,
        )
    )


def build_all_snapshots() -> dict:
    """Build the full deterministic snapshot mapping for every case."""
    return {
        "new_game": {
            str(seed): new_game_snapshot(seed) for seed in NEW_GAME_SEEDS
        },
        "analyze_turn": {
            name: analyze_turn_snapshot(*args)
            for name, args in ANALYZE_CASES.items()
        },
        "evaluate_discard": {
            name: evaluate_discard_snapshot(*args)
            for name, args in EVALUATE_CASES.items()
        },
        "score_winning_tiles": {
            name: score_winning_tiles_snapshot(*args)
            for name, args in SCORE_CASES.items()
        },
    }
