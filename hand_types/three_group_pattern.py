from acceptance import CombinationAcceptance, get_tile_acceptance_of_groups
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
    """Try to construct the given three groups pattern

    Only return result hands when the pattern is technically possible (at most one declared group that does not belong to the pattern)
    :param hand: Mahjong hand
    :param input_pattern: the input pattern, see pattern_generator for the format
    :param cache: global cache for the leftover pair or element + pair
    """
    best_shanten: int = 13
    # every pattern instance reaching the best shanten is kept: a hand can be
    # equally close to several instances (e.g. 234s 345p 456m and 345s 456m 567p)
    best_candidates: list[
        tuple[list[MahjongGroup], list[MahjongCombination], MahjongTiles]
    ] = []

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
        if shanten > best_shanten:
            continue
        if shanten < best_shanten:
            best_shanten = shanten
            best_candidates = []
        best_combi = get_read_groups_from_combi_tiles(
            combi, orig_combi_groups
        ) + list(other_declared_groups)
        best_candidates.append((best_combi, result, missing))
    result_to_return: list[MahjongCombination] = []
    per_combination: dict = {}
    seen: set = set()
    for best_combi, best_result, best_acceptance in best_candidates:
        pattern_acceptance: set[MahjongTile] = set(best_acceptance)
        for groups, _res in best_result:
            pattern_acceptance.update(get_tile_acceptance_of_groups(groups))
        for groups, res in best_result:
            combination = (tuple(best_combi + list(groups)), res)
            per_combination.setdefault(combination[0], set()).update(
                pattern_acceptance
            )
            key = (combination[0], tuple(sorted(t.index for t in res)))
            if key in seen:
                continue
            seen.add(key)
            result_to_return.append(combination)
    return result_to_return, CombinationAcceptance(per_combination)
