"""
    functions to find all the best groups (that minimize the number of tiles away)
"""
from collections import Counter, defaultdict
from typing import Iterator

from mahjong_objects import MahjongGroup, Constraint, Family, MahjongTiles, MahjongTile, \
    MahjongGroups, MahjongCombination, MahjongGroupAndResidue, get_tiles_from_family
from tiles_utils import parse_tiles


def _get_group(numbers:list[int], family: Family) -> MahjongGroup:
    return tuple(MahjongTile(number=num, family=family) for num in numbers)


def _get_group_residue(group: MahjongGroup, tiles: MahjongTiles) -> MahjongTiles:
    leftover = list(tiles)
    for group_tile in group:
        leftover.remove(group_tile)
    return leftover


def find_simple_waits_for_two_tiles(group: MahjongGroup) -> set[MahjongTile]:
    """
    Find the waits of a two tiles group. If the group is smaller or greater, return an empty set
    :param group: two tiles group
    :return: the found waits
    """
    if len(group) != 2:
        return set()
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


# pylint: disable=too-many-branches
def _get_respected_constraints(group: MahjongGroup, constraints: list[Constraint]) -> list[Constraint]:
    if not constraints:
        return []

    respected_constraints = list(constraints)

    for constraint in constraints:
        match constraint:
            case Constraint.NONE:
                pass
            case Constraint.FLUSH_BAMBOO:
                if any(not tile.is_compatible_with_half_flush(Family.BAMBOO) for tile in group):
                    respected_constraints.remove(Constraint.FLUSH_BAMBOO)
            case Constraint.FLUSH_CIRCLE:
                if any(not tile.is_compatible_with_half_flush(Family.CIRCLE) for tile in group):
                    respected_constraints.remove(Constraint.FLUSH_CIRCLE)
            case Constraint.FLUSH_CHARACTER:
                if any(not tile.is_compatible_with_half_flush(Family.CHARACTER) for tile in group):
                    respected_constraints.remove(Constraint.FLUSH_CHARACTER)
            case Constraint.FIRST_FOUR:
                if any(tile.number > 4 or tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.FIRST_FOUR)
            case Constraint.LAST_FOUR:
                if any(tile.number < 6 or tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.LAST_FOUR)
            case Constraint.FIRST_THREE:
                if any(tile.number > 3 or tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.FIRST_THREE)
            case Constraint.MIDDLE_THREE:
                if any(not (4 <= tile.number <= 6) or tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.MIDDLE_THREE)
            case Constraint.LAST_THREE:
                if any(tile.number < 7 or tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.LAST_THREE)
            case Constraint.SYMMETRIC:
                if any(not tile.is_symmetric() for tile in group) or \
                        (waits := find_simple_waits_for_two_tiles(group)) and \
                        all(not tile.is_symmetric() for tile in waits):
                    respected_constraints.remove(Constraint.SYMMETRIC)
            case Constraint.FULL_TERMINALS_OR_HONORS:
                if any(not tile.is_honor() and not tile.is_terminal() for tile in group):
                    respected_constraints.remove(Constraint.FULL_TERMINALS_OR_HONORS)
            case Constraint.FULL_HONORS:
                if any(not tile.is_honor() for tile in group):
                    respected_constraints.remove(Constraint.FULL_HONORS)
            case Constraint.FULL_TERMINALS:
                if any(not tile.is_terminal() for tile in group):
                    respected_constraints.remove(Constraint.FULL_TERMINALS)
            case Constraint.EVEN:
                if any(not tile.is_even() for tile in group):
                    respected_constraints.remove(Constraint.EVEN)
            case Constraint.GREEN:
                if any(not tile.is_green() for tile in group):
                    respected_constraints.remove(Constraint.GREEN)
    return respected_constraints


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
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            if current_tile + 1 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 1], family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            if current_tile + 2 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 2], family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            new_group = _get_group([current_tile], family)
            respected_constraints = _get_respected_constraints(new_group, constraints)
            if respected_constraints:
                yield new_group, _get_group_residue(new_group, tiles), respected_constraints


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
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            if tile_count >= 2:
                new_group = _get_group([current_tile] * 2, family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            new_group = _get_group([current_tile], family)
            respected_constraints = _get_respected_constraints(new_group, constraints)
            if respected_constraints:
                yield new_group, _get_group_residue(new_group, tiles), respected_constraints


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
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            else:
                new_group = _get_group([current_tile], family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints


def all_groups_for(tiles: MahjongTiles,
                   sequence: int, three_same: int, pair: int) -> list[MahjongCombination]:
    """
    Find all combinations of groups respecting given conditions
    :param tiles: the tiles to use
    :param sequence: number of sequences to have
    :param three_same: number of three of a kind to have
    :param pair: number of pairs to have
    :return: list of all combinations matching the requirements, and their residue tiles
    """
    return _find_all_groups_for(tiles, sequence, three_same, pair,
                                [Constraint.NONE], set(), ())[Constraint.NONE]


def all_groups_for_with_constraints(tiles: MahjongTiles, sequence: int, three_same: int, pair: int,
                   constraints) -> dict[Constraint, list[MahjongCombination]]:
    """
    Find all combinations of groups respecting given conditions
    :param tiles: the tiles to use
    :param sequence: number of sequences to have
    :param three_same: number of three of a kind to have
    :param pair: number of pairs to have
    :param constraints: constraints to respect
    :return: list of all combinations matching the requirements, and their residue tiles
    """
    if not constraints:
        raise AttributeError("Constraints cannot be None or empty")
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
                            new_sequence, new_three_same, new_pair,
                            cache, previous_context):
    possible_combinations: dict[Constraint, list[MahjongCombination]] = defaultdict(list)
    smallest_leftovers: dict[Constraint, int] = defaultdict(lambda: 14)
    for found_group, residue, respected_constraints in found_groups:
        new_match = merge_group_tuple(previous_context, found_group)
        if new_match in cache:
            continue
        cache.add(new_match)

        if new_sequence == 0 and new_three_same == 0 and new_pair == 0:
            for constraint in respected_constraints:
                possible_combinations[constraint].append((tuple([found_group]), residue))
        else:
            for constraint, combinations in _find_all_groups_for(residue, new_sequence, new_three_same, new_pair,
                                                        respected_constraints, cache, new_match).items():
                for best_group, res in combinations:
                    residue_size = len(res)
                    if residue_size > smallest_leftovers[constraint]:
                        continue
                    if residue_size < smallest_leftovers[constraint]:
                        possible_combinations[constraint].clear()
                        smallest_leftovers[constraint] = residue_size
                    possible_combinations[constraint].append((merge_group_tuple(best_group, found_group), res))
    return dict(possible_combinations)


def _find_all_groups_for(tiles: MahjongTiles,
                         sequence: int, three_same: int, pair: int, constraints,
                         cache, previous_context) -> dict[Constraint, list[MahjongCombination]]:
    needed_tiles = 3 * (sequence + three_same) + 2 * pair
    if len(tiles) < needed_tiles - 1:
        raise AttributeError(f'Not enough tiles, need at least {needed_tiles - 1} tiles')

    if pair > 0:
        return _find_group_and_recurse(find_pair(tiles, constraints),
                                       sequence, three_same, pair - 1, cache, previous_context)
    if sequence > 0:
        return _find_group_and_recurse(find_sequences(tiles, constraints),
                                       sequence - 1, three_same, pair, cache, previous_context)
    if three_same > 0:
        return _find_group_and_recurse(find_three_of_a_kind(tiles, constraints),
                                       sequence, three_same - 1, pair, cache, previous_context)
    return {}


if __name__ == "__main__":
    print(all_groups_for(parse_tiles("134679s1222z"), 3, 0, 0))
    # print(all_groups_for(parse_tiles("123s"), 1, 0, 0))
