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


def _has_empty_group(groups):
    return any(len(group) == 0 for group in groups)


def _is_pair(group: MahjongGroup) -> bool:
    return len(group) == 2 and group[0] == group[1]

