"""
Tile Acceptance calculator
"""
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
    best_discard_tile, acceptance_after_discard, acceptance_nb = (
        _get_best_discard_choice(best_results, results, acceptance, hand)
    )
    return f"Tile to discard next: {best_discard_tile} (acceptance: {sorted(acceptance_after_discard)} -> {acceptance_nb} tiles)\n"


def _get_best_discard_choice(best_results, results, acceptance, hand: MahjongHand):
    # tile -> set union des acceptances de tous les types où elle est dans le résidu
    candidate_acceptance: dict[MahjongTile, set] = defaultdict(set)
    candidate_type_occurrence: dict[MahjongTile, set] = defaultdict(set)

    for best_result in best_results:
        acceptance_pool = acceptance[best_result]
        for combi, residue in results[best_result]:
            for tile in set(residue):
                candidate_type_occurrence[tile].add(best_result)
                if best_result == HandType.SEVEN_PAIRS.value:
                    seven_pair_acceptance = set(acceptance_pool)
                    seven_pair_acceptance.remove(tile)
                    candidate_acceptance[tile].update(seven_pair_acceptance)
                elif best_result == HandType.KNITTED.value and len(results[best_result][0][0]) == 4:
                    # with honors
                    candidate_acceptance[tile].update(acceptance_pool)
                else:
                    hand_full_acceptance = get_tile_acceptance_of_groups(combi)
                    candidate_acceptance[tile].update(
                        hand_full_acceptance.intersection(acceptance_pool)
                    )  # union

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
    return to_discard, candidate_acceptance[to_discard], best_score


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


def analyze_hand(hand: MahjongHand, hand_types=None, prevalent_wind=0, seat_wind=0):
    """
    analyze given mahjong hand for each supported hand type
    :param hand: hand to analyze
    :param hand_types: list all hand types to analyze, if specified
    :param prevalent_wind: prevalent wind (1-4) or 0 if unknown
    :param seat_wind: seat wind (1-4) or 0 if unknown
    :return: a string containing the analysis
    """
    if len(hand.hand_tiles) < hand.get_natural_size():
        raise AttributeError(
            f"Not enough tiles. At least {hand.get_natural_size()} are needed for analysis."
        )

    if not hand_types:
        hand_types = HandType

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

    return results, acceptance, best_results, closest_away, basic_yakus


def get_tile_to_discard_from(hand: MahjongHand):
    """
    get the next tile to discard, and current number of tiles away after discard
    :param hand: hand to analyze
    :return: the tile to discard
    """
    if not hand.needs_to_discard():
        raise AttributeError(f"Number of tiles not supported : {len(hand.hand_tiles)}")
    results, acceptance, best_results, nb_away, yakus = analyze_hand(hand)
    return (
        _get_best_discard_choice(best_results, results, acceptance, hand),
        nb_away - 1,
        best_results,
        yakus
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


if __name__ == "__main__":
    # print(analyze_hand_from_string_and_print("(123)45678m(222)334p"))
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
