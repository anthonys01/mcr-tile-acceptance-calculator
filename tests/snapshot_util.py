"""Helpers to build deterministic, JSON-serialisable snapshots of the
``tile_acceptance_calculator`` public functions.

The snapshots are used for non-regression testing: the structured output of
``analyze_hand`` and ``get_tile_to_discard_from`` is captured for a set of
representative hands and compared against a golden file. When behaviour changes
intentionally, regenerate the golden file with ``generate_golden.py``.
"""

from tile_acceptance_calculator import analyze_hand, get_tile_to_discard_from
from tiles_utils import parse_hand


# Hands to snapshot. Includes every hand from the ``__main__`` block of
# ``tile_acceptance_calculator`` (commented and active), plus extra hands chosen
# to exercise distinct hand types (seven pairs, knitted, all pungs, honors...).
SNAPSHOT_HANDS = [
    # --- hands from tile_acceptance_calculator __main__ ---
    "(123)45678m(222)334p",
    "(111)44778m(222)334p",
    "(123)m(234)s334p(111)55z",
    "147m289s346p12347z",
    "147m28899s334566p",
    "(123)678m667p223s11z",
    "(123)(789)m223s11445z",
    "123479s67p448m466z",
    "34s4455m668899p77z",
    "147m258p369s22334m",
    "13m588p36s124566z",
    "147m258p369s12(333)m",
    "147m258p36s124566z",
    "[2222]3p(333)s445m1145z",
    "67m344568p345688s",
    "45s13447m135799p",
    # --- extra hands covering more hand types ---
    "1122334455667p",         # seven pairs / full flush shapes
    "147m258p369s147m2p",     # knitted straight shape
    "11122233344455m",        # pungs heavy / character full flush
    "1112345678999m",         # nine gates shape
    "112233m112233p11s",      # triple/mixed chows shape
    "19m19p19s1234567z",      # thirteen orphans shape
]


def _tiles_to_strs(tiles):
    return sorted(str(tile) for tile in tiles)


def _acceptance_by_type_to_strs(acceptance):
    return {
        hand_type: _tiles_to_strs(tiles) for hand_type, tiles in acceptance.items()
    }


def snapshot_for_hand(hand_str: str) -> dict:
    """Build a deterministic snapshot dict for a single hand string."""
    hand = parse_hand(hand_str)
    results, acceptance, best_results, closest_away, _basic_yakus = analyze_hand(hand)

    snapshot = {
        "best_results": sorted(best_results),
        "closest_away": closest_away,
        "acceptance": _acceptance_by_type_to_strs(acceptance),
        "needs_discard": hand.needs_to_discard(),
    }

    if hand.needs_to_discard():
        try:
            (discard, acc_after, acc_nb, acc_by_type), away, discard_best, _yakus, _res, _acc = (
                get_tile_to_discard_from(hand)
            )
        except ValueError as error:
            # Complete (already winning) 14-tile hands have no tile to discard.
            snapshot["discard"] = {"error": str(error)}
        else:
            snapshot["discard"] = {
                "tile": str(discard),
                "away_after_discard": away,
                "acceptance_count": acc_nb,
                "acceptance": _tiles_to_strs(acc_after),
                "acceptance_by_type": _acceptance_by_type_to_strs(acc_by_type),
                "best_results": sorted(discard_best),
            }

    return snapshot


def build_all_snapshots() -> dict:
    return {hand: snapshot_for_hand(hand) for hand in SNAPSHOT_HANDS}
