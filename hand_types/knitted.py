from hand_types.common import can_construct_one_group_one_pair, can_construct_one_pair, get_read_groups_from_combi_tiles
from mahjong_objects import MahjongHand, MahjongCombination, MahjongTile, MahjongGroup, MahjongTiles, Family, \
    get_tiles_from_family
from pattern_generator import pattern_generator
from tiles_utils import parse_tiles, HONOR_TILES


def can_construct_knitted(
        hand: MahjongHand,
        cache: dict
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    best_shanten: int = 13
    best_result: list[MahjongCombination] = []
    best_combi: list[MahjongGroup] = []
    best_acceptance: MahjongTiles = []

    declared_groups = hand.get_all_declared_groups()
    if len(declared_groups) > 1:
        # impossible to build knitted
        return [], set()

    for pattern in pattern_generator("147a258b369c"):
        orig_combi = parse_tiles(pattern)
        orig_combi_groups = (
            tuple(orig_combi[:3]),
            tuple(orig_combi[3:6]),
            tuple(orig_combi[6:]),
        )
        combi = list(orig_combi)
        missing, tiles = hand.get_missing_tiles_and_residue(combi)
        for tile in missing:
            combi.remove(tile)
        if not declared_groups:
            # can build knitted with honors
            usable_honor_tiles = set(get_tiles_from_family(tiles, Family.HONOR))
            leftover = list(tiles)
            for tile in usable_honor_tiles:
                leftover.remove(tile)
            shanten = len(leftover)
            if shanten < best_shanten:
                best_shanten = shanten
                best_combi = get_read_groups_from_combi_tiles(combi, orig_combi_groups)
                best_result = [((tuple(usable_honor_tiles),), leftover)]
                best_acceptance = missing + list(set(HONOR_TILES) - set(usable_honor_tiles))
            # and also knitted straight
            shanten, result = can_construct_one_group_one_pair(tiles, cache)
            if shanten < best_shanten:
                best_shanten = shanten
                best_combi = get_read_groups_from_combi_tiles(
                    combi, orig_combi_groups
                ) + list(declared_groups)
                best_result = result
                best_acceptance = missing
        else:
            # can only build knitted straight
            shanten, result = can_construct_one_pair(tiles, cache)
            if shanten < best_shanten:
                best_shanten = shanten
                best_combi = get_read_groups_from_combi_tiles(
                    combi, orig_combi_groups
                ) + list(declared_groups)
                best_result = result
                best_acceptance = missing
    acceptance: set[MahjongTile] = set(best_acceptance)
    result_to_return: list[MahjongCombination] = []
    for groups, res in best_result:
        result_to_return.append((tuple(best_combi + list(groups)), res))
    return result_to_return, acceptance

