"""
Backend logic for the interactive "training" tenpai game.

Exposes small JSON-in / JSON-out functions so the browser (pyodide) can drive
the game loop while all mahjong logic stays in python.
"""

import json
import random
from random import Random

from mahjong_objects import MahjongTile, MahjongHand
from tiles_utils import generate_tile_pool
from tile_acceptance_calculator import (
    analyze_hand,
    get_simple_acceptance,
    get_tile_to_discard_from,
)
from mcr_scorer import get_won_hand_yakus, get_total_points, print_yakus


def _hand_from_tiles(tile_strs, drawn=None) -> MahjongHand:
    tiles = [MahjongTile(t) for t in tile_strs]
    return MahjongHand(tiles, drawn_tile=MahjongTile(drawn) if drawn else None)


def new_game(seed=None) -> str:
    """
    Shuffle the full tile pool for a consistent draw order.
    :return: json list of tile strings (e.g. ["1m", "5z", ...])
    """
    pool = generate_tile_pool()
    if not seed:
        seed = random.randint(0, 2**32 - 1)
    print(seed)
    rng = Random(seed)
    rng.shuffle(pool)
    return json.dumps([str(tile) for tile in pool])


def _acceptance_number(acceptance_tiles, visible) -> int:
    """Sum over acceptance tiles of (4 - visible count) = tiles still drawable."""
    return sum(4 - visible[tile.index] for tile in acceptance_tiles)


def _evaluate_discard(tile_strs, discard, visible):
    remaining = list(tile_strs)
    remaining.remove(discard)
    hand13 = _hand_from_tiles(remaining)
    results, acceptance, best_results, away, _basic = analyze_hand(hand13)
    acc_tiles = sorted(
        get_simple_acceptance(results, best_results, acceptance),
        key=lambda tile: tile.index,
    )
    return {
        "acceptance": [str(tile) for tile in acc_tiles],
        "number": _acceptance_number(acc_tiles, visible),
        "away": away,
        "best_results": list(best_results),
    }


def analyze_turn(hand_json: str, visible_json: str) -> str:
    """
    Analyze a 14-tile hand for the engine's recommended discard.

    Returns the engine discard tile together with the resulting shanten
    ("away"), tile acceptance and acceptance number (vs the visible vector).
    The user's own discard is scored on demand with ``evaluate_discard``.
    """
    tile_strs = json.loads(hand_json)
    visible = json.loads(visible_json)
    hand = _hand_from_tiles(tile_strs, drawn=tile_strs[-1])

    (engine_discard, acc, _score), away, best_results, _yk = get_tile_to_discard_from(
        hand
    )
    engine_discard = str(engine_discard)
    acc_tiles = sorted(acc)

    return json.dumps(
        {
            "engine_discard": engine_discard,
            "engine": {
                "acceptance": [str(tile) for tile in acc_tiles],
                "number": _acceptance_number(acc_tiles, visible),
                "away": away,
                "best_results": list(best_results),
            }
        }
    )


def evaluate_discard(hand_json: str, discard: str, visible_json: str) -> str:
    """Score a single user-chosen discard against the visible-tile vector."""
    tile_strs = json.loads(hand_json)
    visible = json.loads(visible_json)
    return json.dumps(_evaluate_discard(tile_strs, discard, visible))


def score_winning_tiles(
    hand13_json: str,
    acceptance_json: str,
    self_drawn: bool = False,
    last_tile: bool = False,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
) -> str:
    """
    For every acceptance tile of a tenpai 13-tile hand, build the completed hand
    and return its yaku breakdown, total points and the ordered winning tiles.
    """
    tile_strs = json.loads(hand13_json)
    acceptance = json.loads(acceptance_json)
    out = []
    for tile_str in acceptance:
        won = _hand_from_tiles(tile_strs + [tile_str], drawn=tile_str)
        _acc, groups, yakus = get_won_hand_yakus(
            won, self_drawn, last_tile, prevalent_wind, seat_wind
        )
        won_groups = [[str(tile) for tile in group] for group in groups]
        out.append(
            {
                "tile": tile_str,
                "points": get_total_points(yakus),
                "table": print_yakus(yakus),
                "won_groups": won_groups,
            }
        )
    out.sort(key=lambda entry: entry["points"], reverse=True)
    return json.dumps(out)
