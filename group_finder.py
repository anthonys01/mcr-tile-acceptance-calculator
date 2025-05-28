"""
    functions to find all the best groups (that minimize the number of tiles away)
"""
from collections import Counter
from typing import Iterator

from mahjong_objects import MahjongGroup, Constraint, Family, MahjongTiles, get_tiles_from_family, MahjongTile, \
    MahjongGroups, MahjongCombination, MahjongGroupAndResidue


def _get_group(numbers:list[int], family: Family) -> MahjongGroup:
    return tuple(MahjongTile(number=num, family=family) for num in numbers)

def _get_group_residue(group: MahjongGroup, tiles: MahjongTiles) -> MahjongTiles:
    leftover = list(tiles)
    for group_tile in group:
        leftover.remove(group_tile)
    return leftover

# pylint: disable=too-many-branches
def _are_constraints_respected(group: MahjongGroup, constraints: list[Constraint]) -> bool:
    if not constraints:
        return True

    for constraint in constraints:
        match constraint:
            case Constraint.FLUSH_BAMBOO:
                if any(not tile.is_compatible_with_half_flush(Family.BAMBOO) for tile in group):
                    return False
            case Constraint.FLUSH_CIRCLE:
                if any(not tile.is_compatible_with_half_flush(Family.CIRCLE) for tile in group):
                    return False
            case Constraint.FLUSH_CHARACTER:
                if any(not tile.is_compatible_with_half_flush(Family.BAMBOO) for tile in group):
                    return False
            case Constraint.FIRST_FOUR:
                if any(tile.number > 4 or tile.is_honor() for tile in group):
                    return False
            case Constraint.LAST_FOUR:
                if any(tile.number < 6 or tile.is_honor() for tile in group):
                    return False
            case Constraint.FIRST_THREE:
                if any(tile.number > 3 or tile.is_honor() for tile in group):
                    return False
            case Constraint.MIDDLE_THREE:
                if any(not (4 <= tile.number <= 6) or tile.is_honor() for tile in group):
                    return False
            case Constraint.LAST_THREE:
                if any(tile.number < 7 or tile.is_honor() for tile in group):
                    return False
            case Constraint.SYMMETRIC:
                if any(not tile.is_symmetric() for tile in group):
                    return False
            case Constraint.FULL_TERMINALS_OR_HONORS:
                if any(not tile.is_honor() and not tile.is_terminal() for tile in group):
                    return False
            case Constraint.FULL_HONORS:
                if any(not tile.is_honor() for tile in group):
                    return False
            case Constraint.FULL_TERMINALS:
                if any(not tile.is_terminal() for tile in group):
                    return False
            case Constraint.EVEN:
                if any(not tile.is_even() for tile in group):
                    return False
            case Constraint.GREEN:
                if any(not tile.is_green() for tile in group):
                    return False
    return True

def find_sequences(tiles: MahjongTiles,
                   constraints: list[Constraint]=None) -> Iterator[MahjongGroupAndResidue]:
    """
    generate all possible sequence proto-groups for given tiles and constraints
    :param tiles: tiles to use
    :param constraints: constraints to respect
    :return: an iterator returning tuples of proto-groups and residue tiles
    """
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        family_tiles = get_tiles_from_family(tiles, family)
        family_tiles_num = list(sorted(tile.number for tile in family_tiles))
        for current_tile in family_tiles_num:
            if current_tile > 7:
                break
            if current_tile + 1 in family_tiles_num and current_tile + 2 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 1, current_tile + 2], family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if current_tile + 1 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 1], family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if current_tile + 2 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 2], family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            new_group = _get_group([current_tile], family)
            if _are_constraints_respected(new_group, constraints):
                yield new_group, _get_group_residue(new_group, tiles)

def find_three_of_a_kind(tiles: MahjongTiles,
                         constraints: list[Constraint]=None) -> Iterator[MahjongGroupAndResidue]:
    """
    generate all possible three of a kind proto-groups for given tiles and constraints
    :param tiles: tiles to use
    :param constraints: constraints to respect
    :return: an iterator returning tuples of proto-groups and residue tiles
    """
    for family in Family:
        family_tiles = get_tiles_from_family(tiles, family)
        count = Counter(tile.number for tile in family_tiles)
        for current_tile, tile_count in count.items():
            if tile_count >= 3:
                new_group = _get_group([current_tile] * 3, family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if tile_count >= 2:
                new_group = _get_group([current_tile] * 2, family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            new_group = _get_group([current_tile], family)
            if _are_constraints_respected(new_group, constraints):
                yield new_group, _get_group_residue(new_group, tiles)

def find_pair(tiles: MahjongTiles,
              constraints: list[Constraint]=None) -> Iterator[MahjongGroupAndResidue]:
    """
    generate all possible pair proto-groups for given tiles and constraints
    :param tiles: tiles to use
    :param constraints: constraints to respect
    :return: an iterator returning tuples of proto-groups and residue tiles
    """
    for family in Family:
        family_tiles = get_tiles_from_family(tiles, family)
        count = Counter(tile.number for tile in family_tiles)
        for current_tile, tile_count in count.items():
            if tile_count >= 2:
                new_group = _get_group([current_tile] * 2, family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            else:
                new_group = _get_group([current_tile], family)
                if _are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)

def all_groups_for(tiles: MahjongTiles, sequence: int, three_same: int, pair: int,
                   constraints=None) -> list[MahjongCombination]:
    """
    Find all combinations of groups respecting given conditions
    :param tiles: the tiles to use
    :param sequence: number of sequences to have
    :param three_same: number of three of a kind to have
    :param pair: number of pairs to have
    :param constraints: constraints to respect
    :return: list of all combinations matching the requirements, and their residue tiles
    """
    return _find_all_groups_for(tiles, sequence, three_same, pair, constraints, set(), ())

def merge_group_tuple(group_tuple: MahjongGroups, new_group: MahjongGroup) -> MahjongGroups:
    """
    merge a new group into a sortable tuple of groups
    :param group_tuple: previous mahjong groups
    :param new_group: new group
    :return: sortable tuple of groups
    """
    return tuple(sorted(list(group_tuple) + [new_group]))

def _find_group_and_recurse(found_groups: Iterator[MahjongGroupAndResidue],
                            new_sequence, new_three_same, new_pair, constraints,
                            cache, previous_context):
    possible_groups_residue_pair: list[MahjongCombination] = []
    current_smallest_leftover = 14
    for found_group, residue in found_groups:
        new_match = merge_group_tuple(previous_context, found_group)
        if new_match in cache:
            continue
        cache.add(new_match)

        if new_sequence == 0 and new_three_same == 0 and new_pair == 0:
            possible_groups_residue_pair.append((tuple([found_group]), residue))
        else:
            for best_group, res in _find_all_groups_for(residue, new_sequence, new_three_same, new_pair,
                                                        constraints, cache, new_match):
                residue_size = len(res)
                if residue_size > current_smallest_leftover:
                    continue
                if residue_size < current_smallest_leftover:
                    possible_groups_residue_pair.clear()
                    current_smallest_leftover = residue_size
                possible_groups_residue_pair.append((merge_group_tuple(best_group, found_group), res))
    return possible_groups_residue_pair


def _find_all_groups_for(tiles: MahjongTiles,
                         sequence: int, three_same: int, pair: int, constraints,
                         cache, previous_context) -> list[MahjongCombination]:
    needed_tiles = 3 * (sequence + three_same) + 2 * pair
    if len(tiles) < needed_tiles - 1:
        raise AttributeError(f'Not enough tiles, need at least {needed_tiles - 1} tiles')

    if pair > 0:
        return _find_group_and_recurse(find_pair(tiles, constraints),
                                       sequence, three_same, pair - 1, constraints, cache, previous_context)
    if sequence > 0:
        return _find_group_and_recurse(find_sequences(tiles, constraints),
                                       sequence - 1, three_same, pair, constraints, cache, previous_context)
    if three_same > 0:
        return _find_group_and_recurse(find_three_of_a_kind(tiles, constraints),
                                       sequence, three_same - 1, pair, constraints, cache, previous_context)
    return []
