"""
    Tile Acceptance calculator
"""
from itertools import chain

from group_finder import all_groups_for, find_sequences, find_three_of_a_kind, merge_group_tuple
from mahjong_objects import MahjongTiles, MahjongTile, Family, MahjongHand, MahjongGroup, Constraint, \
    get_tiles_from_family, parse_tiles, generate_random_closed_hand, MahjongGroups, MahjongCombination
from pattern_generator import pattern_generator


def _get_read_groups_from_combi_tiles(combi: MahjongTiles, full_combination: MahjongTiles) -> list[MahjongGroup]:
    full_groups: list[MahjongCombination] = all_groups_for(full_combination, 3, 0, 0)
    result: list[MahjongGroup] = []
    tiles_left = list(combi)
    for full_res in full_groups:
        full_group, _ = full_res
        for group in full_group:
            new_group = []
            for tile in group:
                if tile in tiles_left:
                    tiles_left.remove(tile)
                    new_group.append(tile)
            result.append(tuple(new_group))
    return result

def _can_construct_straight(hand: MahjongHand):
    return _can_construct(hand, '123a456b789c')

def _can_construct_shifted(hand: MahjongHand):
    return _can_construct(hand, 'ABCaBCDbCDEc')

def _can_construct_triple_chows(hand: MahjongHand):
    return _can_construct(hand, 'ABCaABCbABCc')

def _can_construct_pure_straight(hand: MahjongHand):
    return _can_construct(hand, '123456789c')

def _can_construct_pure_shifted(hand: MahjongHand):
    return _can_construct(hand, 'ABCBCDCDEc')

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
    best_groups = []
    for constraint in [Constraint.FLUSH_CHARACTER, Constraint.FLUSH_BAMBOO, Constraint.FLUSH_CIRCLE]:
        for nb_seq in range(0, 5):
            best_groups += all_groups_for(hand.hand_tiles, nb_seq, 4 - nb_seq, 1, [constraint])
    if not best_groups:
        print("Too far away")
        return [], []
    real_shanten = min(len(residue) for group, residue in best_groups)
    groups_to_return = []
    acceptance = set()
    has_empty_group = False
    for best_group, residue in best_groups:
        if len(residue) == real_shanten:
            groups_to_return.append((best_group, residue))
            acceptance.update(_get_tile_acceptance_of_groups(best_group))
            if _has_empty_group(best_group):
                has_empty_group = True
    if has_empty_group:
        family = groups_to_return[0][0][0].family
        for tile in parse_tiles('123456789' + family.value):
            if tile not in acceptance and hand.hand_tiles.count(tile) < 4:
                acceptance.add(tile)
        for tile in parse_tiles('1234567z'):
            if tile not in acceptance and hand.hand_tiles.count(tile) < 2:
                acceptance.add(tile)
    return groups_to_return, acceptance

def _has_empty_group(groups):
    for group in groups:
        if len(group) == 0:
            return True
    return False

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
        for group, residue in chain(find_sequences(tiles), find_three_of_a_kind(tiles)):
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

def _can_construct(hand: MahjongHand, input_pattern: str) -> tuple[list[tuple[[list[MahjongGroup], MahjongTiles]]],
                                                                  set[MahjongTile]]:
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
        shanten, result = _can_construct_combination(tiles)
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


def _can_construct_combination(tiles: MahjongTiles) -> tuple[int, list[MahjongCombination]]:
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


# pylint: disable=too-many-branches
def analyze_hand(hand: MahjongHand, display_all=False) -> str:
    """
    analyze given mahjong hand for each supported hand type
    :param hand: hand to analyze
    :param display_all: if False, only show the hand types closest to victory
    :return: a string containing the analysis
    """
    if len(hand.hand_tiles) < 13:
        raise AttributeError('Not enough tiles. At least 13 are needed for analysis.')

    results = {}
    best_results = []
    closest_away = 15

    acceptance = {}

    straight_results, straight_acceptance = _can_construct_straight(hand)
    # print_result(straight_results)
    away = len(straight_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Straight")
    results["Straight"] = straight_results
    acceptance["Straight"] = straight_acceptance

    shifted_results, shifted_acceptance = _can_construct_shifted(hand)
    # print_result(shifted_results)
    away = len(shifted_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Shifted")
    results["Shifted"] = shifted_results
    acceptance["Shifted"] = shifted_acceptance

    triple_chows_results, triple_chow_acceptance = _can_construct_triple_chows(hand)
    # print_result(triple_chows_results)
    away = len(triple_chows_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Triple chows")
    results["Triple chows"] = triple_chows_results
    acceptance["Triple chows"] = triple_chow_acceptance

    pure_straight_results, pure_straight_acceptance = _can_construct_pure_straight(hand)
    # print_result(pure_straight_results)
    away = len(pure_straight_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Pure straight")
    results["Pure straight"] = pure_straight_results
    acceptance["Pure straight"] = pure_straight_acceptance

    pure_shifted_results, pure_shifted_acceptance = _can_construct_pure_shifted(hand)
    # print_result(pure_shifted_results)
    away = len(pure_shifted_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Pure shifted")
    results["Pure shifted"] = pure_shifted_results
    acceptance["Pure shifted"] = pure_shifted_acceptance

    seven_pairs_results, seven_pairs_acceptance = _can_construct_seven_pairs(hand)
    # print_result(seven_pairs_results)
    away = len(seven_pairs_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Seven pairs")
    results["Seven pairs"] = seven_pairs_results
    acceptance["Seven pairs"] = seven_pairs_acceptance

    all_pungs_results, all_pungs_acceptance = _can_construct_all_pungs(hand)
    # print_result(all_pungs_results)
    away = len(all_pungs_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("All pungs")
    results["All pungs"] = all_pungs_results
    acceptance["All pungs"] = all_pungs_acceptance

    half_flush_results, half_flush_acceptance = _can_construct_half_flush(hand)
    # print_result(half_flush_results)
    away = len(half_flush_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("Half flush")
    results["Half flush"] = half_flush_results
    acceptance["Half flush"] = half_flush_acceptance

    all_types_results, all_types_acceptance = _can_construct_all_types(hand)
    # print_result(all_types_results)
    away = len(all_types_results[0][1])
    if away <= closest_away:
        if away < closest_away:
            best_results.clear()
            closest_away = away
        best_results.append("All types")
    results["All types"] = all_types_results
    acceptance["All types"] = all_types_acceptance

    to_display = results.keys() if display_all else best_results
    printed_result = f'Analyzed hand : {hand}\n'
    for result_type in to_display:
        printed_result += '-----------------------------\n'
        printed_result += result_type + '\n'
        printed_result += _print_result(results[result_type])
        printed_result += "Tile acceptance " + str(sorted(acceptance[result_type])) + \
              f" ({_get_acceptance_tile_number(hand, acceptance[result_type])} tiles)\n"
    return printed_result


def analyze_hand_from_string(hand: str, display_all=False) -> str:
    """
    parse hand and analyze it for each supported hand type
    :param hand: hand to parse and analyze
    :param display_all: if False, only show the hand types closest to victory
    :return: a string containing the analysis
    """
    return analyze_hand(MahjongHand(parse_tiles(hand.lower())), display_all)


if __name__ == "__main__":
    random_hand = generate_random_closed_hand(2)
    print(analyze_hand(random_hand, display_all=True))
