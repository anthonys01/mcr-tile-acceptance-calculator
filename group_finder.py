"""
    functions to find all the best groups (that minimize the number of tiles away)
"""
from collections import Counter
from typing import Iterator

from mahjong_objects import MahjongGroup, Constraint, Family, MahjongTiles, get_tiles_from_family, MahjongTile


def _get_group(numbers:list[int], family: Family) -> MahjongGroup:
    return tuple(MahjongTile(number=num, family=family) for num in numbers)

def _get_group_residue(group: MahjongGroup, tiles: MahjongTiles) -> MahjongTiles:
    leftover = list(tiles)
    for group_tile in group:
        leftover.remove(group_tile)
    return leftover

def are_constraints_respected(group: MahjongGroup, constraints: list[Constraint]):
    if not constraints:
        return True

    for constraint in constraints:
        if constraint == Constraint.FLUSH_BAMBOO:
            for tile in group:
                if not tile.is_compatible_with_half_flush(Family.BAMBOO):
                    return False
        elif constraint == Constraint.FLUSH_CIRCLE:
            for tile in group:
                if not tile.is_compatible_with_half_flush(Family.CIRCLE):
                    return False
        elif constraint == Constraint.FLUSH_CHARACTER:
            for tile in group:
                if not tile.is_compatible_with_half_flush(Family.CHARACTER):
                    return False
    return True

def find_sequences(tiles: MahjongTiles,
                   constraints: list[Constraint]=None) -> Iterator[tuple[MahjongGroup, MahjongTiles]]:
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        family_tiles = get_tiles_from_family(tiles, family)
        family_tiles_num = list(sorted(tile.number for tile in family_tiles))
        for current_tile in family_tiles_num:
            if current_tile > 7:
                break
            if current_tile + 1 in family_tiles_num and current_tile + 2 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 1, current_tile + 2], family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if current_tile + 1 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 1], family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if current_tile + 2 in family_tiles_num:
                new_group = _get_group([current_tile, current_tile + 2], family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            new_group = _get_group([current_tile], family)
            if are_constraints_respected(new_group, constraints):
                yield new_group, _get_group_residue(new_group, tiles)

def find_three_of_a_kind(tiles: MahjongTiles,
                         constraints: list[Constraint]=None) -> Iterator[tuple[MahjongGroup, MahjongTiles]]:
    for family in Family:
        family_tiles = get_tiles_from_family(tiles, family)
        count = Counter(tile.number for tile in family_tiles)
        for current_tile, tile_count in count.items():
            if tile_count >= 3:
                new_group = _get_group([current_tile] * 3, family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            if tile_count >= 2:
                new_group = _get_group([current_tile] * 2, family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            new_group = _get_group([current_tile], family)
            if are_constraints_respected(new_group, constraints):
                yield new_group, _get_group_residue(new_group, tiles)

def find_pair(tiles: MahjongTiles,
              constraints: list[Constraint]=None) -> Iterator[tuple[MahjongGroup, MahjongTiles]]:
    for family in Family:
        family_tiles = get_tiles_from_family(tiles, family)
        count = Counter(tile.number for tile in family_tiles)
        for current_tile, tile_count in count.items():
            if tile_count >= 2:
                new_group = _get_group([current_tile] * 2, family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)
            else:
                new_group = _get_group([current_tile], family)
                if are_constraints_respected(new_group, constraints):
                    yield new_group, _get_group_residue(new_group, tiles)

def all_groups_for(tiles: MahjongTiles, sequence: int, three_same: int, pair: int,
                   constraints=None) -> list[tuple[tuple[MahjongGroup, ...], MahjongTiles]]:
    return _find_all_groups_for(tiles, sequence, three_same, pair, constraints, set(), ())

def merge_group_tuple(group_tuple: tuple[MahjongGroup, ...], new_group: MahjongGroup) -> tuple[MahjongGroup, ...]:
    return tuple(sorted(list(group_tuple) + [new_group]))

def _find_group_and_recurse(found_groups: Iterator[tuple[MahjongGroup, MahjongTiles]],
                            new_sequence, new_three_same, new_pair, constraints,
                            cache, previous_context):
    possible_groups_residue_pair: list[tuple[tuple[MahjongGroup, ...], MahjongTiles]] = []
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
                         cache, previous_context) -> list[tuple[tuple[MahjongGroup, ...], MahjongTiles]]:
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

