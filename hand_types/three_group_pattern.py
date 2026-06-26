from acceptance import get_tile_acceptance_of_groups
from hand_types.common import (
    get_read_groups_from_combi_tiles,
    can_construct_one_group_one_pair,
    can_construct_one_pair,
)
from mahjong_objects import (
    MahjongHand,
    MahjongCombination,
    MahjongTile,
    MahjongGroup,
    MahjongTiles,
)
from pattern_generator import pattern_generator
from tiles_utils import parse_tiles


def can_construct_with_3_group_pattern(
    hand: MahjongHand, input_pattern: str, cache: dict
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    best_shanten: int = 13
    best_result: list[MahjongCombination] = []
    best_combi: list[MahjongGroup] = []
    best_acceptance: MahjongTiles = []

    for pattern in pattern_generator(input_pattern):
        orig_combi = parse_tiles(pattern)
        orig_combi_groups = (
            tuple(orig_combi[:3]),
            tuple(orig_combi[3:6]),
            tuple(orig_combi[6:]),
        )
        other_declared_groups = set(hand.get_all_declared_groups()).difference(
            set(orig_combi_groups)
        )
        if len(other_declared_groups) > 1:
            # combi impossible
            continue
        combi = list(orig_combi)
        to_search = list(orig_combi)
        for original_group in orig_combi_groups:
            if original_group in hand.get_all_declared_groups():
                for tile in original_group:
                    to_search.remove(tile)
        missing, tiles = hand.get_missing_tiles_and_residue(to_search)
        for tile in missing:
            combi.remove(tile)
        if len(other_declared_groups) == 1:
            shanten, result = can_construct_one_pair(tiles, cache)
        else:
            shanten, result = can_construct_one_group_one_pair(tiles, cache)
        if shanten < best_shanten:
            best_shanten = shanten
            best_combi = get_read_groups_from_combi_tiles(
                combi, orig_combi_groups
            ) + list(other_declared_groups)
            best_result = result
            best_acceptance = missing
    acceptance: set[MahjongTile] = set(best_acceptance)
    result_to_return: list[MahjongCombination] = []
    for groups, res in best_result:
        acceptance.update(get_tile_acceptance_of_groups(groups))
        result_to_return.append((tuple(best_combi + list(groups)), res))
    return result_to_return, acceptance
