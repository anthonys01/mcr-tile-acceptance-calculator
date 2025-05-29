"""
    Tile Acceptance calculator
"""
from collections import Counter
from enum import Enum
from itertools import chain

from group_finder import all_groups_for, find_sequences, find_three_of_a_kind, merge_group_tuple, \
    all_groups_for_with_constraints
from mahjong_objects import MahjongTiles, MahjongTile, Family, MahjongHand, MahjongGroup, Constraint, \
    get_tiles_from_family, parse_tiles, generate_random_closed_hand, MahjongGroups, MahjongCombination
from pattern_generator import pattern_generator


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


def _get_read_groups_from_combi_tiles(hand_tiles: MahjongTiles, full_combination: MahjongTiles) -> list[MahjongGroup]:
    combi_list = all_groups_for(full_combination, 3, 0, 0)
    return _get_read_groups_from_full_groups(hand_tiles, combi_list[0][0])


def _get_read_groups_from_full_groups(hand_tiles: MahjongTiles, groups: MahjongGroups) -> list[MahjongGroup]:
    result: list[MahjongGroup] = []
    tiles_left = list(hand_tiles)
    for group in groups:
        new_group = []
        for tile in group:
            if tile in tiles_left:
                tiles_left.remove(tile)
                new_group.append(tile)
        result.append(tuple(new_group))
    return result


def _can_construct_seven_pairs(hand: MahjongHand):
    acceptance = set()
    all_groups = all_groups_for(hand.hand_tiles, 0, 0, 7)
    if all_groups:
        groups, residue = all_groups[0]
        acceptance.update(residue)
        for group in groups:
            if len(group) == 1:
                acceptance.add(group[0])
    return all_groups, acceptance


def _can_construct_all_pungs(hand: MahjongHand):
    acceptance = set()
    all_groups = all_groups_for(hand.hand_tiles, 0, 4, 1)
    if all_groups:
        groups, residue = all_groups[0]
        has_lone_group = False
        for group in groups:
            if len(group) == 3:
                continue
            if len(group) == 2:
                acceptance.add(group[0])
            elif len(group) == 1:
                has_lone_group = True
                acceptance.add(group[0])
        if has_lone_group:
            acceptance.update(residue)
    return all_groups, acceptance


def _can_construct_half_flush(hand: MahjongHand):
    best_combinations: dict[Constraint, list[MahjongCombination]] = {Constraint.FLUSH_BAMBOO: [],
                                                                     Constraint.FLUSH_CIRCLE: [],
                                                                     Constraint.FLUSH_CHARACTER: []}
    for nb_seq in range(0, 5):
        for constraint, combinations in all_groups_for_with_constraints(hand.hand_tiles, nb_seq, 4 - nb_seq, 1,
                    [Constraint.FLUSH_CHARACTER, Constraint.FLUSH_CIRCLE, Constraint.FLUSH_BAMBOO]).items():
            best_combinations[constraint] += combinations
    return _can_construct_half_flush_from_precomputed(hand, best_combinations)


def _can_construct_half_flush_from_precomputed(hand: MahjongHand,
                                               precomputed: dict[Constraint, list[MahjongCombination]]):
    best_groups = _get_best_groups_from_multiple_constraints(
        [Constraint.FLUSH_CHARACTER, Constraint.FLUSH_CIRCLE, Constraint.FLUSH_BAMBOO], precomputed)

    if not best_groups:
        print("Too far away")
        return [], []

    return best_groups, _get_half_flush_acceptance(hand, best_groups)


def _get_best_groups_from_multiple_constraints(constraints, precomputed):
    best_combinations = {constraint: precomputed[constraint] for constraint in constraints}

    best_groups = []
    best_shanten = 14
    for constraint, combinations in best_combinations.items():
        if not combinations:
            continue
        real_shanten = min(len(residue) for group, residue in combinations)
        if real_shanten > best_shanten:
            continue
        if real_shanten < best_shanten:
            best_groups.clear()
            best_shanten = real_shanten
        best_groups += [(groups, residue) for groups, residue in combinations if len(residue) == best_shanten]
    return best_groups


def _get_half_flush_acceptance(hand, best_groups):
    acceptance = set()
    has_empty_group = False
    for best_group, _ in best_groups:
        acceptance.update(_get_tile_acceptance_of_groups(best_group))
        if _has_empty_group(best_group):
            has_empty_group = True
    if has_empty_group:
        family = best_groups[0][0][0].family
        for tile in parse_tiles('123456789' + family.value):
            if tile not in acceptance and hand.hand_tiles.count(tile) < 4:
                acceptance.add(tile)
        for tile in parse_tiles('1234567z'):
            if tile not in acceptance and hand.hand_tiles.count(tile) < 2:
                acceptance.add(tile)
    return acceptance


def _has_empty_group(groups):
    for group in groups:
        if len(group) == 0:
            return True
    return False


def _can_construct_first_last_hand(hand: MahjongHand):
    best_combinations: dict[Constraint, list[MahjongCombination]] = {Constraint.FIRST_FOUR: [],
                                                                     Constraint.LAST_FOUR: []}
    for nb_seq in range(0, 5):
        for constraint, combinations in all_groups_for_with_constraints(hand.hand_tiles, nb_seq, 4 - nb_seq, 1,
                                                    [Constraint.FIRST_FOUR, Constraint.LAST_FOUR]).items():
            best_combinations[constraint] += combinations
    return _can_construct_first_last_hand_from_precomputed(hand, best_combinations)


def _get_first_last_tile_acceptance(hand, best_groups):
    acceptance = set()
    has_empty_group = False
    for best_group, _ in best_groups:
        acceptance.update(_get_tile_acceptance_of_groups(best_group))
        if _has_empty_group(best_group):
            has_empty_group = True
    if has_empty_group:
        first_four_tiles = parse_tiles('1234s1234m1234p')
        last_four_tiles = parse_tiles('6789s6789p6789m')
        if best_groups[0][0][0].number in first_four_tiles:
            for tile in first_four_tiles:
                if tile not in acceptance and hand.hand_tiles.count(tile) < 4:
                    acceptance.add(tile)
        elif best_groups[0][0][0].number in last_four_tiles:
            for tile in last_four_tiles:
                if tile not in acceptance and hand.hand_tiles.count(tile) < 4:
                    acceptance.add(tile)
    return acceptance


def _can_construct_first_last_hand_from_precomputed(hand: MahjongHand,
                                               precomputed: dict[Constraint, list[MahjongCombination]]):
    best_groups = _get_best_groups_from_multiple_constraints([Constraint.FIRST_FOUR, Constraint.LAST_FOUR], precomputed)

    if not best_groups:
        print("Too far away")
        return [], []

    return best_groups, _get_first_last_tile_acceptance(hand, best_groups)


def _can_construct_all_types(hand: MahjongHand):
    concatenated_results = []
    acceptance = set()

    for family in [Family.CIRCLE, Family.CHARACTER, Family.BAMBOO]:
        concatenated_results, acceptance = _find_groups_and_concatenate(
            get_tiles_from_family(hand.hand_tiles, family),
            concatenated_results, parse_tiles('123456789' + family.value), acceptance)

    tiles = get_tiles_from_family(hand.hand_tiles, Family.HONOR)
    concatenated_results, acceptance = _find_groups_and_concatenate(
        [tile for tile in tiles if tile.is_wind()],
        concatenated_results, parse_tiles('1234z'), acceptance)
    concatenated_results, acceptance = _find_groups_and_concatenate(
        [tile for tile in tiles if tile.is_dragon()],
        concatenated_results, parse_tiles('567z'), acceptance)
    return concatenated_results, acceptance


def _find_groups_and_concatenate(tiles, concatenated_results, all_valid_tiles, acceptance):
    good_groups = []
    if not tiles:
        good_groups = [(tuple([()]), tiles)]
    else:
        smallest_residue_length = 13
        for group, residue, _ in chain(find_sequences(tiles, [Constraint.NONE]),
                                       find_three_of_a_kind(tiles, [Constraint.NONE])):
            residue_length = len(residue)
            if residue_length > smallest_residue_length:
                continue
            if residue_length < smallest_residue_length:
                smallest_residue_length = len(residue)
                good_groups.clear()
            good_groups.append((tuple([group]), residue))
    for good_group_tuple, _ in good_groups:
        if len(good_group_tuple[0]) == 0:
            acceptance.update(all_valid_tiles)
        else:
            acceptance.update(_get_tile_acceptance_of_groups(good_group_tuple))
    if not concatenated_results:
        return good_groups, acceptance

    new_concatenated_results = []
    for found_groups, found_residue in good_groups:
        new_group = found_groups[0]
        for groups, residue in concatenated_results:
            new_concatenated_results.append(
                (merge_group_tuple(groups, new_group), residue + found_residue))
    return new_concatenated_results, acceptance


def _print_shanten(best_groups) -> str:
    real_shanten = min(len(residue) for group, residue in best_groups)
    groups, residue = best_groups[0]
    nb_tiles = sum(len(group) for group in groups) + len(residue)
    to_discard = nb_tiles - 13
    if nb_tiles == 13:
        return f"{real_shanten} away ({len(best_groups)} results)\n"
    return f"{real_shanten - to_discard} away with {to_discard} tile to discard ({len(best_groups)} results)\n"


def _print_result(best_groups) -> str:
    if not best_groups:
        return "Too far away"
    to_print = _print_shanten(best_groups)
    if len(best_groups) < 10:
        to_print += "\n".join(str(res) for res in best_groups) + '\n'
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
    to_print += "\n".join(str(res) for res in nice_groups[:10]) + '\n...\n'
    return to_print


def _can_construct_with_3_group_pattern(hand: MahjongHand, input_pattern: str) -> \
                                        tuple[list[tuple[[list[MahjongGroup], MahjongTiles]]], set[MahjongTile]]:
    best_shanten: int = 13
    best_result: list[MahjongCombination] = []
    best_combi: list[MahjongGroup] = []
    best_acceptance: MahjongTiles = []

    for pattern in pattern_generator(input_pattern):
        orig_combi = parse_tiles(pattern)
        combi = list(orig_combi)
        missing = hand.get_missing_tiles(combi)
        tiles = hand.get_residue_after(combi)
        for tile in missing:
            combi.remove(tile)
        shanten, result = _can_construct_one_group_one_pair(tiles)
        if shanten < best_shanten:
            best_shanten = shanten
            best_combi = _get_read_groups_from_combi_tiles(combi, orig_combi)
            best_result = result
            best_acceptance = missing
    acceptance: set[MahjongTile] = set(best_acceptance)
    result_to_return: list[tuple[[list[MahjongGroup], MahjongTiles]]] = []
    for groups, res in best_result:
        acceptance.update(_get_tile_acceptance_of_groups(groups))
        result_to_return.append((best_combi + list(groups), res))
    return result_to_return, acceptance


def _is_pair(group: MahjongGroup) -> bool:
    return len(group) == 2 and group[0] == group[1]


def _find_simple_waits(group: MahjongGroup) -> set[MahjongTile]:
    tile1, tile2 = min(group), max(group)
    waits = set()
    if tile1 == tile2:
        waits.add(tile1)
    elif tile2.number - tile1.number == 1:
        if tile1.number > 1:
            waits.add(MahjongTile(number=tile1.number - 1, family=tile1.family))
        if tile2.number < 9:
            waits.add(MahjongTile(number=tile2.number + 1, family=tile1.family))
    elif tile2.number - tile1.number == 2:
        waits.add(MahjongTile(number=(tile1.number + tile2.number)//2, family=tile1.family))
    return waits


def _get_tile_acceptance_of_groups(groups: MahjongGroups) -> set[MahjongTile]:
    acceptance = set()
    number_of_pairs = sum(_is_pair(group) for group in groups)
    for group in groups:
        if len(group) == 3:
            continue
        if len(group) == 2:
            if _is_pair(group) and number_of_pairs == 1:
                continue
            acceptance.update(_find_simple_waits(group))
        elif len(group) == 0:
            # not managed here
            continue
        elif number_of_pairs > 0:
            tile_value = group[0].number
            tile_family = group[0].family
            if tile_family == Family.HONOR:
                acceptance.add(group[0])
            else:
                for neighbour in range(-2, 3):
                    if 1 <= tile_value + neighbour <= 9:
                        acceptance.add(MahjongTile(number=tile_value + neighbour, family=tile_family))
        else:
            acceptance.add(group[0])
    return acceptance


def _can_construct_one_group_one_pair(tiles: MahjongTiles) -> tuple[int, list[MahjongCombination]]:
    best_groups: list[MahjongCombination] = all_groups_for(tiles, 0, 1, 1)
    best_groups += all_groups_for(tiles, 1, 0, 1)
    real_shanten = min(len(residue) for group, residue in best_groups)
    groups_to_return: list[MahjongCombination] = []
    for best_group, residue in best_groups:
        if len(residue) == real_shanten:
            groups_to_return.append((best_group, residue))
    return real_shanten, groups_to_return


def _get_acceptance_tile_number(hand: MahjongHand, acceptance_tiles: MahjongTiles) -> int:
    total = 0
    for tile in acceptance_tiles:
        total += 4 - hand.hand_tiles.count(tile)
    return total


def _can_construct_knitted(hand: MahjongHand):
    best_shanten: int = 13
    best_result: list[MahjongCombination] = []
    best_combi: list[MahjongGroup] = []
    best_acceptance: MahjongTiles = []

    for pattern in pattern_generator('147a258b369c'):
        orig_combi = parse_tiles(pattern)
        combi = list(orig_combi)
        missing = hand.get_missing_tiles(combi)
        tiles = hand.get_residue_after(combi)
        for tile in missing:
            combi.remove(tile)
        usable_honor_tiles = set(get_tiles_from_family(tiles, Family.HONOR))
        leftover = list(tiles)
        for tile in usable_honor_tiles:
            leftover.remove(tile)
        shanten = len(leftover)
        if shanten < best_shanten:
            best_shanten = shanten
            best_combi = _get_read_groups_from_full_groups(combi,
                                        (tuple(orig_combi[:3]), tuple(orig_combi[3:6]), tuple(orig_combi[6:])))
            best_result = [(tuple([tuple(usable_honor_tiles)]), leftover)]
            best_acceptance = missing
    acceptance: set[MahjongTile] = set(best_acceptance)
    result_to_return: list[tuple[[list[MahjongGroup], MahjongTiles]]] = []
    for groups, res in best_result:
        acceptance.update(set(parse_tiles('1234567z')) - set(groups[0]))
        result_to_return.append((best_combi + list(groups), res))
    return result_to_return, acceptance


def _can_construct_hand_type(hand_type: HandType, hand: MahjongHand):
    result, acceptance = [], []
    match hand_type:
        case HandType.MIXED_SHIFTED:
            result, acceptance = _can_construct_with_3_group_pattern(hand, 'ABCaBCDbCDEc')
        case HandType.MIXED_STRAIGHT:
            result, acceptance = _can_construct_with_3_group_pattern(hand, '123a456b789c')
        case HandType.TRIPLE_CHOWS:
            result, acceptance = _can_construct_with_3_group_pattern(hand, 'ABCaABCbABCc')
        case HandType.PURE_SHIFTED:
            result, acceptance = _can_construct_with_3_group_pattern(hand, 'ABCCDEEFGa')
        case HandType.PURE_STRAIGHT:
            result, acceptance = _can_construct_with_3_group_pattern(hand, '123456789a')
        case HandType.SEVEN_PAIRS:
            result, acceptance = _can_construct_seven_pairs(hand)
        case HandType.ALL_PUNGS:
            result, acceptance = _can_construct_all_pungs(hand)
        case HandType.HALF_FLUSH:
            result, acceptance = _can_construct_half_flush(hand)
        case HandType.ALL_TYPES:
            result, acceptance = _can_construct_all_types(hand)
        case HandType.KNITTED:
            result, acceptance = _can_construct_knitted(hand)
        case HandType.FIRST_OR_LAST_N_TILES:
            result, acceptance = _can_construct_first_last_hand(hand)
    return result, acceptance


def _print_best_discard_choice(best_results, results):
    tile_count = Counter()
    for best_result in best_results:
        for _, residue in results[best_result]:
            tile_count.update(residue)
    most_useless_tiles = tile_count.most_common(1)
    if most_useless_tiles:
        return f"Tile to discard next: {most_useless_tiles[0][0]}\n"
    return '\n'



def analyze_hand(hand: MahjongHand, hand_types=None, display_all=False) -> str:
    """
    analyze given mahjong hand for each supported hand type
    :param hand: hand to analyze
    :param hand_types: list all hand types to analyze, if specified
    :param display_all: if False, only show the hand types closest to victory
    :return: a string containing the analysis
    """
    if len(hand.hand_tiles) < 13:
        raise AttributeError('Not enough tiles. At least 13 are needed for analysis.')

    if not hand_types:
        hand_types = HandType

    results = {}
    best_results = []
    closest_away = 15

    acceptance = {}

    for hand_type in hand_types:
        hand_results, hand_acceptance = _can_construct_hand_type(hand_type, hand)
        if not hand_results:
            continue
        away = len(hand_results[0][1])
        if away <= closest_away:
            if away < closest_away:
                best_results.clear()
                closest_away = away
            best_results.append(hand_type.value)
        results[hand_type.value] = hand_results
        acceptance[hand_type.value] = hand_acceptance

    to_display = results.keys() if display_all else best_results
    printed_result = f'Analyzed hand : {hand}\n'
    for result_type in to_display:
        printed_result += '-----------------------------\n'
        printed_result += result_type + '\n'
        printed_result += _print_result(results[result_type])
        printed_result += "Tile acceptance " + str(sorted(acceptance[result_type])) + \
              f" ({_get_acceptance_tile_number(hand, acceptance[result_type])} tiles)\n"
    printed_result += '-----------------------------\n'
    printed_result += _print_best_discard_choice(best_results, results)
    return printed_result


def analyze_hand_from_string(hand: str, display_all=False) -> str:
    """
    parse hand and analyze it for each supported hand type
    :param hand: hand to parse and analyze
    :param display_all: if False, only show the hand types closest to victory
    :return: a string containing the analysis
    """
    return analyze_hand(MahjongHand(parse_tiles(hand.lower())), display_all=display_all)


if __name__ == "__main__":
    random_hand = generate_random_closed_hand(2)
    # random_hand = MahjongHand(parse_tiles("1234789p1356m667s"))
    print(analyze_hand(random_hand, display_all=False))
    #from timeit import default_timer as timer
    #start = timer()
    #for _ in range(10):
    #    random_hand = generate_random_closed_hand(2)
    #    print(analyze_hand(random_hand, display_all=True))
    #end = timer()
    #print(end - start)
