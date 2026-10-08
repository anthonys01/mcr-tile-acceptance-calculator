from group_finder import find_simple_waits_for_two_tiles
from mahjong_objects import MahjongTiles, MahjongCombination, MahjongTile, get_tiles_from_family, Family, MahjongGroups, \
    MahjongGroup


def get_full_tile_acceptance(
        tiles_in_hand: MahjongTiles,
        combinations: list[MahjongCombination],
        other_acceptance: set[MahjongTile] | None = None,
        allowed_tiles: MahjongTiles | None = None,
):
    """
    get tile acceptance of all proto-groups, and if there is an empty group, add all allowed tiles as acceptance
    :param tiles_in_hand: tiles in hand
    :param combinations: combinations to compute acceptance from
    :param other_acceptance: previously calculated acceptance (i.e. from a main combination)
    :param allowed_tiles: allowed tiles for empty group acceptance
    :return: tile acceptance set
    """
    acceptance = set()
    has_empty_group = False
    for groups, _ in combinations:
        acceptance.update(get_tile_acceptance_of_groups(groups))
        if _has_empty_group(groups):
            has_empty_group = True
    if allowed_tiles and has_empty_group:
        honor_tiles = get_tiles_from_family(allowed_tiles, Family.HONOR)
        for tile in honor_tiles:
            if tile not in acceptance and tiles_in_hand.count(tile) < 2:
                acceptance.add(tile)
        for tile in set(allowed_tiles) - set(honor_tiles):
            if tile not in acceptance and tiles_in_hand.count(tile) < 4:
                acceptance.add(tile)
    if allowed_tiles:
        acceptance.intersection_update(allowed_tiles)
    if other_acceptance:
        acceptance.update(other_acceptance)
    return acceptance


class CombinationAcceptance(set):
    """Acceptance pool of a hand type (the union over all its combinations) that
    also remembers the narrower pool each combination was built from.

    A hand type may reach its best distance through several pattern instances
    (e.g. two different Mixed Shifted Chows). Intersecting a combination's group
    acceptance with the union pool would then credit it with tiles only useful to
    another instance, so consumers should go through ``useful_acceptance_of``.
    """

    def __init__(self, per_combination: dict):
        super().__init__()
        self.per_combination = per_combination
        for pool in per_combination.values():
            self.update(pool)

    def pool_for(self, groups) -> set:
        return self.per_combination.get(tuple(groups), self)

    def __reduce__(self):
        return CombinationAcceptance, (self.per_combination,)


def useful_acceptance_of(groups, acceptance_pool) -> set[MahjongTile]:
    """Tiles of ``acceptance_pool`` that improve the given combination groups."""
    if isinstance(acceptance_pool, CombinationAcceptance):
        acceptance_pool = acceptance_pool.pool_for(groups)
    return get_tile_acceptance_of_groups(groups).intersection(acceptance_pool)


def get_tile_acceptance_of_groups(groups: MahjongGroups) -> set[MahjongTile]:
    acceptance = set()
    number_of_pairs = sum(_is_pair(group) for group in groups)
    for group in groups:
        if len(group) == 3:
            continue
        if len(group) == 2:
            if _is_pair(group) and number_of_pairs == 1:
                continue
            acceptance.update(find_simple_waits_for_two_tiles(group))
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
                        acceptance.add(
                            MahjongTile(
                                number=tile_value + neighbour, family=tile_family
                            )
                        )
        else:
            acceptance.add(group[0])
    return acceptance


KNITTED_GROUP_COUNT = 3


def get_tile_acceptance_of_knitted_groups(
        groups: MahjongGroups, knitted_group_count: int = KNITTED_GROUP_COUNT
) -> set[MahjongTile]:
    """Tile acceptance of a knitted-straight combination.

    The first ``knitted_group_count`` groups of such a combination are knitted
    proto-groups: the tiles held out of one ``{n, n+3, n+6}`` triple of a single
    family. :func:`get_tile_acceptance_of_groups` only understands *standard*
    shapes, so it reads ``(2s, 8s)`` as a two-tile group with no simple wait and
    credits it nothing - which is why knitted discards were displayed with an
    empty acceptance. Here each incomplete triple accepts the tiles it still
    misses.

    The remaining groups are ordinary - the chow and the pair completing the
    knitted straight, plus any declared group - and keep the standard treatment.
    Knitted proto-groups are never pairs, so splitting them off does not perturb
    the pair bookkeeping of the standard pass.
    """
    acceptance = set()
    for group in groups[:knitted_group_count]:
        acceptance.update(_knitted_waits(group))
    acceptance.update(get_tile_acceptance_of_groups(groups[knitted_group_count:]))
    return acceptance


def _knitted_waits(group: MahjongGroup) -> set[MahjongTile]:
    """Tiles missing from the knitted triple ``group`` belongs to.

    A tile's number identifies its triple unambiguously (``1/4/7``, ``2/5/8`` or
    ``3/6/9``), so a partial group of any size determines the tiles it still
    needs. An empty group carries no family and accepts nothing;
    :func:`get_full_tile_acceptance` covers that case through ``allowed_tiles``.
    """
    if not group:
        return set()
    family = group[0].family
    start = (group[0].number - 1) % 3 + 1
    held = {tile.number for tile in group}
    return {
        MahjongTile(number=number, family=family)
        for number in (start, start + 3, start + 6)
        if number not in held
    }


def _has_empty_group(groups):
    return any(len(group) == 0 for group in groups)


def _is_pair(group: MahjongGroup) -> bool:
    return len(group) == 2 and group[0] == group[1]

