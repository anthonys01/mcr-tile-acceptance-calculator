"""
    functions to find all the best groups (that minimize the number of tiles away)
"""
from bisect import insort
from collections import Counter, defaultdict
from typing import Iterator

from mahjong_objects import MahjongGroup, Constraint, Family, MahjongTiles, MahjongTile, \
    MahjongGroups, MahjongCombination, MahjongGroupAndResidue, get_tiles_from_family, \
    INDEX_TO_TILE, NB_TILE_INDICES
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

    # fast path for the very common unconstrained case
    if len(constraints) == 1 and constraints[0] is Constraint.NONE:
        return constraints

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
        if not family_tiles:
            continue
        family_tiles_num = sorted(tile.number for tile in family_tiles)
        present = set(family_tiles_num)
        for current_tile in family_tiles_num:
            if current_tile > 7:
                break
            has_plus_one = current_tile + 1 in present
            has_plus_two = current_tile + 2 in present
            if has_plus_one and has_plus_two:
                new_group = _get_group([current_tile, current_tile + 1, current_tile + 2], family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            if has_plus_one:
                new_group = _get_group([current_tile, current_tile + 1], family)
                respected_constraints = _get_respected_constraints(new_group, constraints)
                if respected_constraints:
                    yield new_group, _get_group_residue(new_group, tiles), respected_constraints
            if has_plus_two:
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
    count = Counter(tiles)
    for current_tile, tile_count in count.items():
        if tile_count >= 3:
            new_group = (current_tile, current_tile, current_tile)
            respected_constraints = _get_respected_constraints(new_group, constraints)
            if respected_constraints:
                yield new_group, _get_group_residue(new_group, tiles), respected_constraints
        if tile_count >= 2:
            new_group = (current_tile, current_tile)
            respected_constraints = _get_respected_constraints(new_group, constraints)
            if respected_constraints:
                yield new_group, _get_group_residue(new_group, tiles), respected_constraints
        new_group = (current_tile,)
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
    count = Counter(tiles)
    for current_tile, tile_count in count.items():
        if tile_count >= 2:
            new_group = (current_tile, current_tile)
            respected_constraints = _get_respected_constraints(new_group, constraints)
            if respected_constraints:
                yield new_group, _get_group_residue(new_group, tiles), respected_constraints
        else:
            new_group = (current_tile,)
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
    counts, order, total = _prepare_counts(tiles)
    raw = _recurse_none(counts, total, order, sequence, three_same, pair, set(), ())
    return _finalize_combinations(tiles, counts, raw)


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
    counts, order, total = _prepare_counts(tiles)
    raw = _recurse_counts(counts, total, order,
                          sequence, three_same, pair, constraints, set(), ())
    return {constraint: _finalize_combinations(tiles, counts, combinations)
            for constraint, combinations in raw.items()}


def merge_group_tuple(group_tuple: MahjongGroups, new_group: MahjongGroup) -> MahjongGroups:
    """
    merge a new group into a sortable tuple of groups
    :param group_tuple: previous mahjong groups
    :param new_group: new group
    :return: sortable tuple of groups
    """
    sorted_groups = list(group_tuple)
    insort(sorted_groups, new_group)
    return tuple(sorted_groups)


def _encode_group_id(indices: tuple[int, ...]) -> int:
    """Encode a proto-group (its ascending tile indices) into a unique small int.

    Used as a cheap, order-independent dedup key for the set of chosen groups,
    avoiding the cost of building/hashing tuples of tile tuples."""
    value = 0
    for index in indices:
        value = value * 34 + index + 1
    return value


def _insort_id(context_ids: tuple[int, ...], group_id: int) -> tuple[int, ...]:
    """Insert a group id into a sorted tuple of ids (canonical set key)."""
    ids = list(context_ids)
    insort(ids, group_id)
    return tuple(ids)


# families ordered as in the original find_sequences (bamboo, circle, character);
# value is the count-vector offset of number 1 for that family
_SEQUENCE_FAMILY_OFFSETS = (18, 9, 0)


def _prepare_counts(tiles: MahjongTiles) -> tuple[list[int], list[int], int]:
    """Build the count vector and the first-occurrence order of distinct tile indices."""
    counts = [0] * NB_TILE_INDICES
    order: list[int] = []
    for tile in tiles:
        index = tile.index
        if counts[index] == 0:
            order.append(index)
        counts[index] += 1
    return counts, order, len(tiles)


def _materialize_residue(original_tiles: MahjongTiles, counts: list[int]) -> MahjongTiles:
    """Rebuild the residue tile list in the original tile order from a count vector.

    This reproduces exactly the list obtained by repeatedly removing group tiles
    while preserving order (the previous list.remove based behaviour)."""
    budget = list(counts)
    residue: MahjongTiles = []
    for tile in original_tiles:
        index = tile.index
        if budget[index] > 0:
            budget[index] -= 1
            residue.append(tile)
    return residue


def _finalize_combinations(original_tiles: MahjongTiles, counts: list[int],
                           raw: list[tuple[MahjongGroups, int]]) -> list[MahjongCombination]:
    """Turn (groups, residue_size) combinations into (groups, residue_tiles).

    The residue is rebuilt only for the kept combinations, instead of at every leaf
    of the search. ``counts`` is the full hand count vector (restored after the
    search), temporarily mutated here to recover each residue in original order."""
    result: list[MahjongCombination] = []
    for groups, _residue_size in raw:
        for group in groups:
            for tile in group:
                counts[tile.index] -= 1
        result.append((groups, _materialize_residue(original_tiles, counts)))
        for group in groups:
            for tile in group:
                counts[tile.index] += 1
    return result


def _iter_sequence_groups(counts: list[int]) -> Iterator[tuple[tuple[int, ...], MahjongGroup]]:
    """Yield sequence-type proto-groups (3-run, partial runs, single) as (indices, group).

    Mirrors find_sequences: families in (bamboo, circle, character) order, ascending
    numbers 1..7, yielding the full run, the two partial runs then the single tile."""
    for offset in _SEQUENCE_FAMILY_OFFSETS:
        for base in range(offset, offset + 7):  # numbers 1..7
            if counts[base] == 0:
                continue
            has_plus_one = counts[base + 1] > 0
            has_plus_two = counts[base + 2] > 0
            if has_plus_one and has_plus_two:
                indices = (base, base + 1, base + 2)
                yield indices, (INDEX_TO_TILE[base], INDEX_TO_TILE[base + 1], INDEX_TO_TILE[base + 2])
            if has_plus_one:
                yield (base, base + 1), (INDEX_TO_TILE[base], INDEX_TO_TILE[base + 1])
            if has_plus_two:
                yield (base, base + 2), (INDEX_TO_TILE[base], INDEX_TO_TILE[base + 2])
            yield (base,), (INDEX_TO_TILE[base],)


def _iter_three_of_a_kind_groups(counts: list[int],
                                 order: list[int]) -> Iterator[tuple[tuple[int, ...], MahjongGroup]]:
    """Yield triplet/pair/single proto-groups, in first-occurrence order (like Counter)."""
    for index in order:
        count = counts[index]
        if count == 0:
            continue
        tile = INDEX_TO_TILE[index]
        if count >= 3:
            yield (index, index, index), (tile, tile, tile)
        if count >= 2:
            yield (index, index), (tile, tile)
        yield (index,), (tile,)


def _iter_pair_groups(counts: list[int],
                      order: list[int]) -> Iterator[tuple[tuple[int, ...], MahjongGroup]]:
    """Yield pair/single proto-groups, in first-occurrence order (like Counter)."""
    for index in order:
        count = counts[index]
        if count == 0:
            continue
        tile = INDEX_TO_TILE[index]
        if count >= 2:
            yield (index, index), (tile, tile)
        else:
            yield (index,), (tile,)


def _recurse_none(counts: list[int], total: int, order: list[int],
                  sequence: int, three_same: int, pair: int,
                  cache: set, context_ids: tuple[int, ...]) -> list[tuple[MahjongGroups, int]]:
    """Unconstrained variant of _recurse_counts.

    Since the only constraint is Constraint.NONE (always respected), this skips the
    per-group constraint check and the constraint-keyed dictionaries entirely, which
    is the bulk of the workload (all pungs, seven pairs, chow patterns...).

    Combinations carry the residue *size* only; the residue tile list is rebuilt
    later by _finalize_combinations for the kept results."""
    needed_tiles = 3 * (sequence + three_same) + 2 * pair
    if total < needed_tiles - 1:
        raise AttributeError(f'Not enough tiles, need at least {needed_tiles - 1} tiles')

    if pair > 0:
        iterator = _iter_pair_groups(counts, order)
        new_sequence, new_three_same, new_pair = sequence, three_same, pair - 1
    elif sequence > 0:
        iterator = _iter_sequence_groups(counts)
        new_sequence, new_three_same, new_pair = sequence - 1, three_same, pair
    elif three_same > 0:
        iterator = _iter_three_of_a_kind_groups(counts, order)
        new_sequence, new_three_same, new_pair = sequence, three_same - 1, pair
    else:
        return []

    is_leaf = new_sequence == 0 and new_three_same == 0 and new_pair == 0
    combinations: list[tuple[MahjongGroups, int]] = []
    smallest_leftover = 14

    for indices, found_group in iterator:
        new_ids = _insort_id(context_ids, _encode_group_id(indices))
        if new_ids in cache:
            continue
        cache.add(new_ids)

        for index in indices:
            counts[index] -= 1

        if is_leaf:
            combinations.append(((found_group,), total - len(indices)))
        else:
            child = _recurse_none(counts, total - len(indices), order,
                                  new_sequence, new_three_same, new_pair, cache, new_ids)
            for best_group, residue_size in child:
                if residue_size > smallest_leftover:
                    continue
                if residue_size < smallest_leftover:
                    combinations.clear()
                    smallest_leftover = residue_size
                combinations.append((merge_group_tuple(best_group, found_group), residue_size))

        for index in indices:
            counts[index] += 1

    return combinations


def _recurse_counts(counts: list[int], total: int, order: list[int],
                    sequence: int, three_same: int, pair: int, constraints,
                    cache: set, context_ids: tuple[int, ...]) -> dict[Constraint, list[tuple[MahjongGroups, int]]]:
    needed_tiles = 3 * (sequence + three_same) + 2 * pair
    if total < needed_tiles - 1:
        raise AttributeError(f'Not enough tiles, need at least {needed_tiles - 1} tiles')

    # pick the next group kind to expand, matching the original priority order
    if pair > 0:
        iterator = _iter_pair_groups(counts, order)
        new_sequence, new_three_same, new_pair = sequence, three_same, pair - 1
    elif sequence > 0:
        iterator = _iter_sequence_groups(counts)
        new_sequence, new_three_same, new_pair = sequence - 1, three_same, pair
    elif three_same > 0:
        iterator = _iter_three_of_a_kind_groups(counts, order)
        new_sequence, new_three_same, new_pair = sequence, three_same - 1, pair
    else:
        return {}

    is_leaf = new_sequence == 0 and new_three_same == 0 and new_pair == 0
    possible_combinations: dict[Constraint, list[tuple[MahjongGroups, int]]] = defaultdict(list)
    smallest_leftovers: dict[Constraint, int] = defaultdict(lambda: 14)

    for indices, found_group in iterator:
        respected_constraints = _get_respected_constraints(found_group, constraints)
        if not respected_constraints:
            continue
        new_ids = _insort_id(context_ids, _encode_group_id(indices))
        if new_ids in cache:
            continue
        cache.add(new_ids)

        for index in indices:
            counts[index] -= 1

        if is_leaf:
            residue_size = total - len(indices)
            for constraint in respected_constraints:
                possible_combinations[constraint].append(((found_group,), residue_size))
        else:
            child = _recurse_counts(counts, total - len(indices), order,
                                    new_sequence, new_three_same, new_pair,
                                    respected_constraints, cache, new_ids)
            for constraint, combinations in child.items():
                for best_group, residue_size in combinations:
                    if residue_size > smallest_leftovers[constraint]:
                        continue
                    if residue_size < smallest_leftovers[constraint]:
                        possible_combinations[constraint].clear()
                        smallest_leftovers[constraint] = residue_size
                    possible_combinations[constraint].append(
                        (merge_group_tuple(best_group, found_group), residue_size))

        for index in indices:
            counts[index] += 1

    return dict(possible_combinations)




if __name__ == "__main__":
    print(all_groups_for(parse_tiles("134679s1222z"), 3, 0, 0))
    # print(all_groups_for(parse_tiles("123s"), 1, 0, 0))
