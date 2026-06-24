from group_finder import all_groups_for
from mahjong_objects import MahjongTiles, MahjongCombination, MahjongGroups, MahjongGroup


def _get_best_groups(
        best_groups: list[MahjongCombination],
) -> tuple[int, list[MahjongCombination]]:
    real_shanten = min(len(residue) for _, residue in best_groups)
    groups_to_return: list[MahjongCombination] = []
    for best_group, residue in best_groups:
        if len(residue) == real_shanten:
            groups_to_return.append((best_group, residue))
    return real_shanten, groups_to_return

def _can_construct_one_pair(
        tiles: MahjongTiles,
) -> tuple[int, list[MahjongCombination]]:
    return _get_best_groups(all_groups_for(tiles, 0, 0, 1))


def can_construct_one_pair(
        tiles: MahjongTiles, cache: dict
) -> tuple[int, list[MahjongCombination]]:
    key = tuple(sorted(t.index for t in tiles))
    if key not in cache:
        cache[key] = _can_construct_one_pair(tiles)
    return cache[key]


def _can_construct_one_group_one_pair(
        tiles: MahjongTiles,
) -> tuple[int, list[MahjongCombination]]:
    best_groups: list[MahjongCombination] = all_groups_for(tiles, 0, 1, 1)
    best_groups += all_groups_for(tiles, 1, 0, 1)
    return _get_best_groups(best_groups)


def can_construct_one_group_one_pair(
        tiles: MahjongTiles, cache: dict
) -> tuple[int, list[MahjongCombination]]:
    key = tuple(sorted(t.index for t in tiles))
    if key not in cache:
        cache[key] = _can_construct_one_group_one_pair(tiles)
    return cache[key]


def get_read_groups_from_combi_tiles(
        hand_tiles: MahjongTiles, full_combination: MahjongGroups
) -> list[MahjongGroup]:
    return _get_read_groups_from_full_groups(hand_tiles, full_combination)


def _get_read_groups_from_full_groups(
        hand_tiles: MahjongTiles, groups: MahjongGroups
) -> list[MahjongGroup]:
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

