"""
Tile Acceptance calculator
"""
import json
from collections import defaultdict
from enum import Enum
from typing import Iterable

from acceptance import get_tile_acceptance_of_groups
from hand_types.all_pungs import can_construct_all_pungs
from hand_types.all_types import can_construct_all_types
from hand_types.basic import can_construct_hand
from hand_types.knitted import can_construct_knitted
from hand_types.precompute import (
    precompute_constraints,
    can_construct_half_flush_from_precomputed,
    can_construct_first_last_hand_from_precomputed,
    can_construct_symmetry_from_precomputed,
)
from hand_types.seven_pairs import can_construct_seven_pairs
from hand_types.three_group_pattern import can_construct_with_3_group_pattern
from mahjong_objects import (
    MahjongTiles,
    MahjongTile,
    Family,
    MahjongHand,
    MahjongCombination,
    MahjongMCRYaku,
    get_tiles_from_family,
)
from mcr_scorer import print_yakus
from tiles_utils import (
    parse_hand,
)


class HandType(Enum):
    """
    Types of hand to analyze
    """

    MIXED_STRAIGHT = "Mixed Straight"
    MIXED_SHIFTED = "Mixed Shifted"
    PURE_STRAIGHT = "Pure Straight"
    PURE_SHIFTED = "Pure Shifted"
    TRIPLE_CHOWS = "Triple Chows"
    ALL_PUNGS = "All Pungs"
    SEVEN_PAIRS = "Seven Pairs"
    HALF_FLUSH = "Half Flush"
    ALL_TYPES = "All Types"
    KNITTED = "Knitted"
    FIRST_OR_LAST_N_TILES = "First or Last n tiles"
    SYMMETRY = "Symmetry"
    BASIC = "Basic"


def _print_shanten(best_groups, natural_size) -> str:
    real_shanten = min(len(residue) for _, residue in best_groups)
    groups, residue = best_groups[0]
    nb_tiles = sum(len(group) for group in groups) + len(residue)
    to_discard = nb_tiles - natural_size
    if nb_tiles == natural_size:
        return f"{real_shanten} away ({len(best_groups)} results)\n"
    return f"{real_shanten - to_discard} away with {to_discard} tile to discard ({len(best_groups)} results)\n"


def _print_result(best_groups, hand) -> str:
    if not best_groups:
        return "Too far away"
    to_print = _print_shanten(best_groups, hand.get_natural_size())
    if len(best_groups) < 10:
        to_print += "\n".join(str(res) for res in best_groups) + "\n"
        return to_print

    lone_tile_groups_nb = 10
    nice_groups = []
    for possible_hand in best_groups:
        lone_tile_groups = 0
        hand, _ = possible_hand
        for group in hand:
            if len(group) <= 1:
                lone_tile_groups += 1
        if lone_tile_groups > lone_tile_groups_nb:
            continue
        if lone_tile_groups < lone_tile_groups_nb:
            nice_groups.clear()
            lone_tile_groups_nb = lone_tile_groups
        nice_groups.append(possible_hand)
    to_print += "\n".join(str(res) for res in nice_groups[:10]) + "\n...\n"
    return to_print


def _print_result_for_basic(best_groups, hand, basic_yakus) -> str:
    if not best_groups:
        return "Too far away"
    to_print = _print_shanten(best_groups, hand.get_natural_size())
    if len(best_groups) < 10:
        to_print += (
            "\n".join(
                f"{hand} {residue}\nComplete: {won_hand}\n{print_yakus(yakus)}"
                for (hand, residue), (won_hand, yakus) in zip(best_groups, basic_yakus)
            )
            + "\n"
        )
        return to_print

    lone_tile_groups_nb = 10
    nice_groups = []
    for group_index, possible_hand in enumerate(best_groups):
        hand, residue = possible_hand
        lone_tile_groups = 0
        for group in hand:
            if len(group) <= 1:
                lone_tile_groups += 1
        if lone_tile_groups > lone_tile_groups_nb:
            continue
        if lone_tile_groups < lone_tile_groups_nb:
            nice_groups.clear()
            lone_tile_groups_nb = lone_tile_groups
        won_hand, yakus = basic_yakus[group_index]
        nice_groups.append(
            f"{hand} {residue}\nComplete: {won_hand}\n{print_yakus(yakus)}"
        )
    to_print += "\n".join(str(res) for res in nice_groups[:10]) + "\n...\n"

    return to_print


def _get_acceptance_tile_number(
    hand: MahjongHand, acceptance_tiles: Iterable[MahjongTile]
) -> int:
    total = 0
    for tile in acceptance_tiles:
        total += 4 - hand.hand_tiles.count(tile)
    return total


def _can_construct_hand_type(
    hand_type: HandType, hand: MahjongHand, precomputed, cache: dict
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    result: list[MahjongCombination] = []
    acceptance: set[MahjongTile] = set()
    match hand_type:
        case HandType.MIXED_SHIFTED:
            result, acceptance = can_construct_with_3_group_pattern(
                hand, "ABCaBCDbCDEc", cache
            )
        case HandType.MIXED_STRAIGHT:
            result, acceptance = can_construct_with_3_group_pattern(
                hand, "123a456b789c", cache
            )
        case HandType.TRIPLE_CHOWS:
            result, acceptance = can_construct_with_3_group_pattern(
                hand, "ABCaABCbABCc", cache
            )
        case HandType.PURE_SHIFTED:
            result, acceptance = can_construct_with_3_group_pattern(
                hand, "ABCCDEEFGa", cache
            )
        case HandType.PURE_STRAIGHT:
            result, acceptance = can_construct_with_3_group_pattern(
                hand, "123456789a", cache
            )
        case HandType.SEVEN_PAIRS:
            result, acceptance = can_construct_seven_pairs(hand)
        case HandType.ALL_PUNGS:
            result, acceptance = can_construct_all_pungs(hand)
        case HandType.HALF_FLUSH:
            result, acceptance = can_construct_half_flush_from_precomputed(
                hand, precomputed
            )
        case HandType.ALL_TYPES:
            result, acceptance = can_construct_all_types(hand)
        case HandType.KNITTED:
            result, acceptance = can_construct_knitted(hand, cache)
        case HandType.FIRST_OR_LAST_N_TILES:
            result, acceptance = can_construct_first_last_hand_from_precomputed(
                hand, precomputed
            )
        case HandType.SYMMETRY:
            result, acceptance = can_construct_symmetry_from_precomputed(
                hand, precomputed
            )
    return result, acceptance


def _get_most_useless_tile_from(most_useless_tiles: MahjongTiles, candidates_occurrences):
    max_occurrence = max(
        len(candidates_occurrences[tile]) for tile in most_useless_tiles
    )
    best_candidates = [
        tile
        for tile in most_useless_tiles
        if len(candidates_occurrences[tile]) == max_occurrence
    ]
    if len(best_candidates) == 1:
        return best_candidates[0]
    honors = get_tiles_from_family(best_candidates, Family.HONOR)
    if honors:
        return honors[0]
    return sorted(best_candidates, key=lambda tile: abs(5 - tile.number))[-1]


def _print_best_discard_choice(best_results, results, acceptance, hand):
    best_discard_tile, acceptance_after_discard, acceptance_nb, _by_type = (
        _get_best_discard_choice(best_results, results, acceptance, hand)
    )
    return f"Tile to discard next: {best_discard_tile} (acceptance: {sorted(acceptance_after_discard)} -> {acceptance_nb} tiles)\n"


_BASIC_MAIN_YAKU_MIN_POINTS = 4

# Yakus that are already surfaced by a dedicated HandType. When a Basic
# combination's main yaku maps to one of these and that hand type is among the
# closest results, the combination is dropped from the Basic breakdown to avoid
# showing the same information twice.
_YAKU_TO_HAND_TYPE = {
    MahjongMCRYaku.MIXED_STRAIGHT: HandType.MIXED_STRAIGHT,
    MahjongMCRYaku.MIXED_SHIFTED_CHOWS: HandType.MIXED_SHIFTED,
    MahjongMCRYaku.PURE_STRAIGHT: HandType.PURE_STRAIGHT,
    MahjongMCRYaku.PURE_SHIFTED_CHOWS: HandType.PURE_SHIFTED,
    MahjongMCRYaku.MIXED_TRIPLE_CHOW: HandType.TRIPLE_CHOWS,
    MahjongMCRYaku.PURE_TRIPLE_CHOW: HandType.TRIPLE_CHOWS,
    MahjongMCRYaku.ALL_PUNGS: HandType.ALL_PUNGS,
    MahjongMCRYaku.SEVEN_PAIRS: HandType.SEVEN_PAIRS,
    MahjongMCRYaku.HALF_FLUSH: HandType.HALF_FLUSH,
    MahjongMCRYaku.FULL_FLUSH: HandType.HALF_FLUSH,
    MahjongMCRYaku.ALL_TYPES: HandType.ALL_TYPES,
    MahjongMCRYaku.KNITTED_STRAIGHT: HandType.KNITTED,
    MahjongMCRYaku.LESSER_HONORS_AND_KNITTED_TILES: HandType.KNITTED,
    MahjongMCRYaku.GREATER_HONORS_AND_KNITTED_TILES: HandType.KNITTED,
    MahjongMCRYaku.UPPER_TILES: HandType.FIRST_OR_LAST_N_TILES,
    MahjongMCRYaku.MIDDLE_TILES: HandType.FIRST_OR_LAST_N_TILES,
    MahjongMCRYaku.LOWER_TILES: HandType.FIRST_OR_LAST_N_TILES,
    MahjongMCRYaku.UPPER_FOUR: HandType.FIRST_OR_LAST_N_TILES,
    MahjongMCRYaku.LOWER_FOUR: HandType.FIRST_OR_LAST_N_TILES,
    MahjongMCRYaku.REVERSIBLE_TILES: HandType.SYMMETRY,
}


def _yaku_display_name(yaku: MahjongMCRYaku) -> str:
    return yaku.name.replace("_", " ").title()


def _basic_combo_label(yakus, best_results):
    """Display label for a single Basic combination, or None to drop it.

    The label is the combination's "main" yaku: the highest scoring yaku, which
    must be worth at least ``_BASIC_MAIN_YAKU_MIN_POINTS``. Combinations whose
    main yaku is already represented by a dedicated hand type present in
    ``best_results`` are dropped to avoid redundancy. Combinations without a
    valuable enough main yaku keep the generic "Basic" label.
    """
    if not yakus:
        return HandType.BASIC.value
    main_yaku, _count = max(
        yakus,
        key=lambda yaku_count: (yaku_count[0].get_points(), -yaku_count[0].get_id()),
    )
    if main_yaku.get_points() < _BASIC_MAIN_YAKU_MIN_POINTS:
        return HandType.BASIC.value
    overlapping_type = _YAKU_TO_HAND_TYPE.get(main_yaku)
    if overlapping_type is not None and overlapping_type.value in best_results:
        return None
    return _yaku_display_name(main_yaku)


def _build_discard_candidates(
    best_results, results, acceptance, hand: MahjongHand, basic_yakus=None
):
    """Compute, for every discardable tile, the union of accepted tiles it keeps.

    Returns three mappings keyed by the candidate discard tile:
      * ``candidate_acceptance``: union of useful acceptance tiles across types
      * ``candidate_acceptance_by_type``: same, split per displayed hand-type label
      * ``candidate_type_occurrence``: set of hand types the tile appears in
    """
    # tile -> set union des acceptances de tous les types où elle est dans le résidu
    candidate_acceptance: dict[MahjongTile, set] = defaultdict(set)
    candidate_acceptance_by_type: dict[MahjongTile, dict] = defaultdict(
        lambda: defaultdict(set)
    )
    candidate_type_occurrence: dict[MahjongTile, set] = defaultdict(set)

    for best_result in best_results:
        acceptance_pool = acceptance[best_result]
        for combo_index, (combi, residue) in enumerate(results[best_result]):
            # Basic combinations are labelled by their main yaku (or dropped from
            # the breakdown when redundant); the discard selection below is left
            # untouched so the chosen tile is unaffected.
            if best_result == HandType.BASIC.value:
                combo_yakus = basic_yakus[combo_index][1] if basic_yakus else []
                label = _basic_combo_label(combo_yakus, best_results)
            else:
                label = best_result
            for tile in set(residue):
                candidate_type_occurrence[tile].add(best_result)
                if best_result == HandType.SEVEN_PAIRS.value:
                    useful_acceptance = set(acceptance_pool)
                    useful_acceptance.remove(tile)
                elif best_result == HandType.KNITTED.value and len(results[best_result][0][0]) == 4:
                    # with honors
                    useful_acceptance = set(acceptance_pool)
                else:
                    hand_full_acceptance = get_tile_acceptance_of_groups(combi)
                    useful_acceptance = hand_full_acceptance.intersection(
                        acceptance_pool
                    )
                candidate_acceptance[tile].update(useful_acceptance)  # union
                if label is not None:
                    candidate_acceptance_by_type[tile][label].update(useful_acceptance)

    return candidate_acceptance, candidate_acceptance_by_type, candidate_type_occurrence


def _get_best_discard_choice(
    best_results, results, acceptance, hand: MahjongHand, basic_yakus=None
):
    candidate_acceptance, candidate_acceptance_by_type, candidate_type_occurrence = (
        _build_discard_candidates(best_results, results, acceptance, hand, basic_yakus)
    )

    if not candidate_acceptance:
        raise ValueError("No tile to discard")

    # Comparer par nombre de tuiles acceptées (après union)
    best_score = max(
        _get_acceptance_tile_number(hand, acc) for acc in candidate_acceptance.values()
    )
    best_tiles = [
        tile
        for tile, acc in candidate_acceptance.items()
        if _get_acceptance_tile_number(hand, acc) == best_score
    ]
    to_discard = _get_most_useless_tile_from(best_tiles, candidate_type_occurrence)
    return (
        to_discard,
        candidate_acceptance[to_discard],
        best_score,
        dict(candidate_acceptance_by_type[to_discard]),
    )


def get_discard_choices(
    best_results, results, acceptance, hand: MahjongHand, basic_yakus=None
):
    """Rank every discardable tile from best (most acceptance) to worst.

    Each entry is ``(tile, acceptance_set, acceptance_count, acceptance_by_type,
    is_recommended)``. The recommended flag marks the single tile that
    ``_get_best_discard_choice`` would pick (top score, useless-tile tiebreak).
    """
    candidate_acceptance, candidate_acceptance_by_type, candidate_type_occurrence = (
        _build_discard_candidates(best_results, results, acceptance, hand, basic_yakus)
    )

    if not candidate_acceptance:
        raise ValueError("No tile to discard")

    best_score = max(
        _get_acceptance_tile_number(hand, acc) for acc in candidate_acceptance.values()
    )
    best_tiles = [
        tile
        for tile, acc in candidate_acceptance.items()
        if _get_acceptance_tile_number(hand, acc) == best_score
    ]
    recommended = _get_most_useless_tile_from(best_tiles, candidate_type_occurrence)

    ranked = sorted(
        candidate_acceptance,
        key=lambda tile: (
            -_get_acceptance_tile_number(hand, candidate_acceptance[tile]),
            tile.index,
        ),
    )
    choices = []
    for tile in ranked:
        acc = candidate_acceptance[tile]
        choices.append(
            (
                tile,
                acc,
                _get_acceptance_tile_number(hand, acc),
                dict(candidate_acceptance_by_type[tile]),
                tile is recommended,
            )
        )
    return choices


def get_simple_acceptance(results, best_results, acceptance):
    """Concatenate the acceptance from the best results"""
    simple_acceptance = set()
    for best_result in best_results:
        acceptance_pool = acceptance[best_result]
        for combi, residue in results[best_result]:
            if best_result == HandType.SEVEN_PAIRS.value or (best_result == HandType.KNITTED.value and len(results[best_result][0][0]) == 4):
                simple_acceptance.update(acceptance_pool)
            else:
                hand_full_acceptance = get_tile_acceptance_of_groups(combi)
                simple_acceptance.update(
                    hand_full_acceptance.intersection(acceptance_pool)
                )
    return simple_acceptance


def get_acceptance_by_hand_type(results, best_results, acceptance, basic_yakus=None):
    """Acceptance tiles split per hand type, so a caller can show which tiles
    are useful for which of the best hand types.

    The generic "Basic" hand type is expanded into one entry per combination,
    labelled by its main yaku (e.g. Chicken Hand, Outside Hand, Three Concealed
    Pungs). Combinations that merely duplicate another displayed hand type are
    dropped (see ``_basic_combo_label``).
    """
    acceptance_by_type: dict[str, set] = defaultdict(set)
    for best_result in best_results:
        acceptance_pool = acceptance[best_result]
        for combo_index, (combi, residue) in enumerate(results[best_result]):
            if best_result == HandType.BASIC.value:
                combo_yakus = basic_yakus[combo_index][1] if basic_yakus else []
                label = _basic_combo_label(combo_yakus, best_results)
                if label is None:
                    continue
            else:
                label = best_result
            if best_result == HandType.SEVEN_PAIRS.value or (best_result == HandType.KNITTED.value and len(results[best_result][0][0]) == 4):
                acceptance_by_type[label].update(acceptance_pool)
            else:
                hand_full_acceptance = get_tile_acceptance_of_groups(combi)
                acceptance_by_type[label].update(
                    hand_full_acceptance.intersection(acceptance_pool)
                )
    return dict(acceptance_by_type)


_ANALYZE_CACHE: dict = {}
_ANALYZE_CACHE_MAX = 200_000


def _hand_signature(hand: MahjongHand, prevalent_wind, seat_wind, include_basic):
    """Canonical, hashable identity of a hand for the transposition cache.

    Tiles are interned flyweights, so the sorted tuple is a stable multiset key.
    """
    tiles = tuple(sorted(hand.hand_tiles, key=lambda tile: tile.index))
    return (
        tiles,
        frozenset(hand.declared_tiles),
        frozenset(hand.kongs),
        prevalent_wind,
        seat_wind,
        include_basic,
    )


def clear_analyze_cache() -> None:
    """Empty the transposition cache (call between independent benchmark runs)."""
    _ANALYZE_CACHE.clear()


def analyze_hand(
    hand: MahjongHand,
    hand_types=None,
    prevalent_wind=0,
    seat_wind=0,
    include_basic=True,
    use_cache=True,
):
    """
    analyze given mahjong hand for each supported hand type
    :param hand: hand to analyze
    :param hand_types: list all hand types to analyze, if specified
    :param prevalent_wind: prevalent wind (1-4) or 0 if unknown
    :param seat_wind: seat wind (1-4) or 0 if unknown
    :param include_basic: analyze the (expensive) BASIC hand type; disable for a
        fast structural-only leaf evaluation (see ``evaluate_hand_fast``)
    :param use_cache: reuse/populate the transposition cache for full analyses
    :return: a string containing the analysis
    """
    if len(hand.hand_tiles) < hand.get_natural_size():
        raise AttributeError(
            f"Not enough tiles. At least {hand.get_natural_size()} are needed for analysis."
        )

    cache_key = None
    if use_cache and hand_types is None:
        cache_key = _hand_signature(hand, prevalent_wind, seat_wind, include_basic)
        cached = _ANALYZE_CACHE.get(cache_key)
        if cached is not None:
            return cached

    if not hand_types:
        hand_types = list(HandType)
    if not include_basic:
        hand_types = [ht for ht in hand_types if ht != HandType.BASIC]

    results = {}
    best_results = []
    closest_away = 15

    acceptance = {}

    precomputed = precompute_constraints(hand)
    cache: dict = {}
    basic_yakus = []

    for hand_type in hand_types:
        if hand_type == HandType.BASIC:
            hand_results, hand_acceptance, yakus = can_construct_hand(
                hand, prevalent_wind, seat_wind
            )
            basic_yakus.extend(yakus)
        else:
            hand_results, hand_acceptance = _can_construct_hand_type(
                hand_type, hand, precomputed, cache
            )
        if not hand_results or not hand_results[0]:
            continue
        away = len(hand_results[0][1])
        if away <= closest_away:
            if away < closest_away:
                best_results.clear()
                closest_away = away
            best_results.append(hand_type.value)
        results[hand_type.value] = hand_results
        acceptance[hand_type.value] = hand_acceptance

    result = (results, acceptance, best_results, closest_away, basic_yakus)
    if cache_key is not None and len(_ANALYZE_CACHE) < _ANALYZE_CACHE_MAX:
        _ANALYZE_CACHE[cache_key] = result
    return result


def evaluate_hand_fast(hand: MahjongHand, prevalent_wind=0, seat_wind=0):
    """Cheap leaf evaluation for tree search.

    Skips the BASIC hand type (~80% of the analysis cost, see profiling) and only
    evaluates the structural MCR hand types. Returns the structural shanten
    (``nb_away``), the closest hand type labels and their combined tile acceptance.

    :return: (nb_away, best_results, simple_acceptance)
    """
    results, acceptance, best_results, nb_away, _ = analyze_hand(
        hand,
        prevalent_wind=prevalent_wind,
        seat_wind=seat_wind,
        include_basic=False,
    )
    simple_acceptance = get_simple_acceptance(results, best_results, acceptance)
    return nb_away, best_results, simple_acceptance


def get_tile_to_discard_from(hand: MahjongHand, prevalent_wind=0, seat_wind=0):
    """
    get the next tile to discard, and current number of tiles away after discard
    :param hand: hand to analyze
    :param prevalent_wind: prevalent wind (1-4) or 0 if unknown
    :param seat_wind: seat wind (1-4) or 0 if unknown
    :return: ((discard, acceptance, acceptance_nb, acceptance_by_type), away,
             best_results, yakus, results, acceptance)
    """
    if not hand.needs_to_discard():
        raise AttributeError(f"Number of tiles not supported : {len(hand.hand_tiles)}")
    results, acceptance, best_results, nb_away, yakus = analyze_hand(
        hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )
    return (
        _get_best_discard_choice(best_results, results, acceptance, hand, yakus),
        nb_away - 1,
        best_results,
        yakus,
        results,
        acceptance,
    )


def analyze_hand_from_string_and_print(
    hand: str, display_all=False, prevalent_wind=0, seat_wind=0
) -> str:
    """
    parse hand, analyze it for each supported hand type and print result
    :param hand: hand to parse and analyze
    :param display_all: if False, only show the hand types closest to victory
    :param prevalent_wind: prevalent wind (1-4) or 0 if unknown
    :param seat_wind: seat wind (1-4) or 0 if unknown
    :return: a string containing the analysis
    """
    mahjong_hand = parse_hand(hand)
    results, acceptance, best_results, _, basic_yakus = analyze_hand(
        mahjong_hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )
    return _print_hand_analysis(
        mahjong_hand, results, acceptance, best_results, display_all, basic_yakus
    )


def _print_hand_analysis(
    hand, results, acceptance, best_results, display_all, basic_yakus
) -> str:
    to_display = results.keys() if display_all else best_results
    to_display = sorted(to_display, key=lambda t: len(results[t][0][1]))
    printed_result = f"Analyzed hand : {hand}\n"
    if hand.needs_to_discard():
        printed_result += "-----------------------------\n"
        printed_result += _print_best_discard_choice(
            best_results, results, acceptance, hand
        )
    else:
        printed_result += "-----------------------------\n"
        full_acceptance = get_simple_acceptance(results, best_results, acceptance)
        acceptance_nb = _get_acceptance_tile_number(hand, full_acceptance)
        printed_result += f"Full acceptance: {sorted(full_acceptance)} - {acceptance_nb} tiles\n"
    for result_type in to_display:
        printed_result += "-----------------------------\n"
        printed_result += result_type + "\n"
        if result_type == HandType.BASIC.value:
            printed_result += _print_result_for_basic(
                results[result_type], hand, basic_yakus
            )
        else:
            printed_result += _print_result(results[result_type], hand)
        printed_result += (
            "Tile acceptance "
            + str(sorted(acceptance[result_type]))
            + f" ({_get_acceptance_tile_number(hand, acceptance[result_type])} tiles)\n"
        )
    printed_result += "-----------------------------\n"
    return printed_result


def _select_combo_indices(best_groups):
    """Mirror the truncation logic of ``_print_result`` and return the indices
    of the combinations to display, plus whether the list was truncated.
    """
    if len(best_groups) < 10:
        return list(range(len(best_groups))), False
    lone_tile_groups_nb = 10
    selected: list[int] = []
    for index, (groups, _residue) in enumerate(best_groups):
        lone_tile_groups = sum(1 for group in groups if len(group) <= 1)
        if lone_tile_groups > lone_tile_groups_nb:
            continue
        if lone_tile_groups < lone_tile_groups_nb:
            selected.clear()
            lone_tile_groups_nb = lone_tile_groups
        selected.append(index)
    return selected[:10], True


def _yakus_to_list(yakus):
    rows = sorted(
        ((_yaku_display_name(yaku), yaku.get_points(), int(count)) for yaku, count in yakus),
        key=lambda row: (-row[1] * row[2], row[0]),
    )
    return [{"name": name, "points": points, "count": count} for name, points, count in rows]


def _combo_to_dict(combi, residue, yaku_info=None):
    combo = {
        "groups": [[str(tile) for tile in group] for group in combi],
        "residue": sorted(str(tile) for tile in residue),
    }
    if yaku_info is not None:
        won_hand, yakus = yaku_info
        combo["complete"] = [[str(tile) for tile in group] for group in won_hand]
        combo["yakus"] = _yakus_to_list(yakus)
        combo["total_points"] = sum(row["points"] * row["count"] for row in combo["yakus"])
    return combo


def _hand_type_to_dict(name, best_groups, hand, acceptance_tiles, basic_yakus=None):
    indices, truncated = _select_combo_indices(best_groups)
    combos = []
    for index in indices:
        combi, residue = best_groups[index]
        yaku_info = None
        if name == HandType.BASIC.value and basic_yakus:
            yaku_info = basic_yakus[index]
        combos.append(_combo_to_dict(combi, residue, yaku_info))
    return {
        "name": name,
        "away": len(best_groups[0][1]),
        "result_count": len(best_groups),
        "truncated": truncated,
        "combos": combos,
        "acceptance": sorted(str(tile) for tile in acceptance_tiles),
        "acceptance_count": _get_acceptance_tile_number(hand, acceptance_tiles),
    }


def _declared_groups_to_list(hand: MahjongHand):
    declared = []
    for group in hand.declared_tiles:
        tiles = sorted(group)
        if len(tiles) == 4:
            kind = "kong"
        elif len(set(tiles)) == 1:
            kind = "pung"
        else:
            kind = "chow"
        declared.append(
            {"tiles": [str(tile) for tile in tiles], "kind": kind, "concealed": False}
        )
    for group in hand.kongs:
        if group in hand.declared_tiles:
            continue
        tiles = sorted(group)
        declared.append(
            {"tiles": [str(tile) for tile in tiles], "kind": "kong", "concealed": True}
        )
    declared.sort(key=lambda entry: entry["tiles"][0])
    return declared


def analyze_hand_structured(
    hand_str: str, display_all=False, prevalent_wind=0, seat_wind=0
) -> dict:
    """Analyze a hand and return a JSON-serialisable structured description.

    Unlike ``analyze_hand_from_string_and_print`` (which returns a formatted
    text blob), this returns machine-readable data so a rich UI can render
    tiles, collapsible hand-type breakdowns and a ranked list of discards.
    Tiles are exposed as their short string (e.g. ``"1m"``, ``"5z"``).
    """
    hand = parse_hand(hand_str)
    results, acceptance, best_results, closest_away, basic_yakus = analyze_hand(
        hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )

    data = {
        "hand": str(hand),
        "concealed": [str(tile) for tile in sorted(hand.get_free_tiles())],
        "declared": _declared_groups_to_list(hand),
        "needs_discard": hand.needs_to_discard(),
        "closest_away": closest_away,
        "best_results": list(best_results),
    }

    if hand.needs_to_discard():
        try:
            choices = get_discard_choices(
                best_results, results, acceptance, hand, basic_yakus
            )
        except ValueError:
            choices = []
        data["discards"] = [
            {
                "tile": str(tile),
                "acceptance": sorted(str(accepted) for accepted in acc),
                "acceptance_count": count,
                "recommended": recommended,
                "by_type": {
                    label: sorted(str(accepted) for accepted in tiles)
                    for label, tiles in by_type.items()
                },
            }
            for tile, acc, count, by_type, recommended in choices
        ]
        data["away_after_discard"] = max(closest_away - 1, 0)
    else:
        full_acceptance = get_simple_acceptance(results, best_results, acceptance)
        data["full_acceptance"] = sorted(str(tile) for tile in full_acceptance)
        data["full_acceptance_count"] = _get_acceptance_tile_number(
            hand, full_acceptance
        )

    to_display = list(results.keys()) if display_all else list(best_results)
    to_display = sorted(to_display, key=lambda hand_type: len(results[hand_type][0][1]))
    data["hand_types"] = [
        _hand_type_to_dict(
            hand_type, results[hand_type], hand, acceptance[hand_type], basic_yakus
        )
        for hand_type in to_display
    ]
    return data


def analyze_hand_structured_json(
    hand_str: str, display_all=False, prevalent_wind=0, seat_wind=0
) -> str:
    """JSON-string wrapper around ``analyze_hand_structured`` for the web UI."""
    return json.dumps(
        analyze_hand_structured(hand_str, display_all, prevalent_wind, seat_wind)
    )


if __name__ == "__main__":
    # print(analyze_hand_from_string_and_print("(111)44778m(222)334p"))
    # print(analyze_hand_from_string_and_print("(123)m(234)s334p(111)55z"))
    # print(analyze_hand_from_string_and_print("147m289s346p12347z"))
    # print(analyze_hand_from_string_and_print("147m28899s334566p"))
    # print(analyze_hand_from_string_and_print("(123)678m667p223s11z"))
    # print(analyze_hand_from_string_and_print("(123)(789)m223s11445z"))
    # print(analyze_hand_from_string_and_print("123479s67p448m466z", True))
    # print(analyze_hand_from_string_and_print("34s4455m668899p77z"))
    # print(analyze_hand_from_string_and_print("147m258p369s22334m"))
    # print(analyze_hand_from_string_and_print("13m588p36s124566z"))
    # print(analyze_hand_from_string_and_print("147m258p369s12(333)m"))
    # print(analyze_hand_from_string_and_print("147m258p36s124566z"))
    # print(analyze_hand_from_string_and_print("[2222]3p(333)s445m1145z"))
    # print(analyze_hand_from_string_and_print("67m344568p345688s"))
    print(analyze_hand_from_string_and_print("45s13447m135799p"))
