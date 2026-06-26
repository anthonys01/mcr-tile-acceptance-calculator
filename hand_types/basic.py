from functools import cache, reduce
from itertools import product

from group_finder import all_groups_for
from mahjong_objects import MahjongHand, MahjongCombination, MahjongGroup, MahjongTile
from mcr_scorer import get_won_hand_yakus_for_basic_groups, get_total_points
from tiles_utils import parse_hand


def can_construct_hand(hand: MahjongHand):
    acceptance = set()
    possible_hands = []
    kept_yakus = []
    for comb, added_tiles, yakus, won_hand in get_all_possible_yakus(hand):
        possible_hands.append(comb)
        kept_yakus.append((won_hand, yakus))
        acceptance.update(added_tiles)
    return possible_hands, acceptance, kept_yakus


def get_all_possible_yakus(hand: MahjongHand):
    fastest_hands = []
    best_shanten = 13
    declared_groups = hand.get_all_declared_groups()
    max_free_groups = 4 - len(declared_groups)
    results = []
    for seq in range(max_free_groups + 1):
        free_groups: list[MahjongCombination] = all_groups_for(
            hand.get_free_tiles(), seq, max_free_groups - seq, 1
        )
        for g, residue in free_groups:
            if len(residue) > best_shanten:
                continue
            if len(residue) < best_shanten:
                best_shanten = len(residue)
                fastest_hands.clear()
            groups = declared_groups + list(g)
            fastest_hands.append((groups, residue))
    for combination, residue in fastest_hands:
        for won_hand, added_tiles in _get_tenpai_hands_from(combination):
            complete_hand = hand.clone()
            complete_hand.hand_tiles = _get_flattened_tiles(won_hand)
            best_yakus = None
            best_points = 7
            for winning_tile in added_tiles:
                complete_hand.drawn_tile = winning_tile
                yakus = get_won_hand_yakus_for_basic_groups(complete_hand, won_hand)
                points = get_total_points(yakus)
                if points > best_points:
                    best_yakus = yakus
                    best_points = points
                if best_yakus:
                    results.append(((combination, residue), added_tiles, best_yakus, won_hand))
    return results


def _get_flattened_tiles(combination):
    tiles = []
    for group in combination:
        tiles.extend(group)
    return tiles


def _get_tenpai_hands_from(groups):
    completed_groups = []
    to_complete = []
    for group in groups:
        if len(group) >= 3:
            completed_groups.append(group)
        elif not group:
            # do not support empty groups
            return
        else:
            to_complete.append(group)
    for pair_index in range(len(to_complete)):
        if not _can_be_pair(to_complete[pair_index]):
            continue
        groups = [_complete_pair(to_complete[pair_index])]
        groups.extend(_complete_proto_group(to_complete[index]) for index in range(len(to_complete)) if index != pair_index)
        for group_tuples in product(*groups):
            new_groups, added_tiles = reduce(_aggregate_group_tuples, group_tuples)
            yield tuple(completed_groups + new_groups), added_tiles


def _aggregate_group_tuples(tuple_1, tuple_2):
    return tuple_1[0] + tuple_2[0], tuple_1[1] + tuple_2[1]


@cache
def _complete_proto_group(proto_group: MahjongGroup):
    # TODO verify tile count before generating
    results = []
    if len(proto_group) == 2:
        tile_1, tile_2 = proto_group
        if tile_1 == tile_2:
            results.append(([(tile_1, tile_1, tile_1)], [tile_1]))
        else:
            smallest_tile = min(tile_1, tile_2)
            biggest_tile = max(tile_1, tile_2)
            if biggest_tile.number - smallest_tile.number == 2:
                # middle wait
                middle_tile = MahjongTile(number=smallest_tile.number + 1, family=smallest_tile.family)
                results.append(([(smallest_tile, middle_tile, biggest_tile)], [middle_tile]))
            elif biggest_tile.number == 9 and smallest_tile.number == 8:
                # edge wait
                edge_tile = MahjongTile(number=7, family=smallest_tile.family)
                results.append(([(smallest_tile, edge_tile, biggest_tile)], [edge_tile]))
            elif smallest_tile.number == 1 and biggest_tile.number == 2:
                # edge wait
                edge_tile = MahjongTile(number=3, family=smallest_tile.family)
                results.append(([(smallest_tile, edge_tile, biggest_tile)], [edge_tile]))
            else:
                # double wait
                waiting_1 = MahjongTile(number=smallest_tile.number - 1, family=smallest_tile.family)
                results.append(([(waiting_1, smallest_tile, biggest_tile)], [waiting_1]))
                waiting_2 = MahjongTile(number=biggest_tile.number + 1, family=smallest_tile.family)
                results.append(([(smallest_tile, biggest_tile, waiting_2)], [waiting_2]))
    elif len(proto_group) == 1:
        minus_2 = None
        minus_1 = None
        plus_1 = None
        plus_2 = None
        tile = proto_group[0]
        if tile.number >= 2:
            minus_1 = MahjongTile(number=tile.number - 1, family=tile.family)
        if tile.number >= 3:
            minus_2 = MahjongTile(number=tile.number - 2, family=tile.family)
        if tile.number <= 7:
            plus_2 = MahjongTile(number=tile.number + 2, family=tile.family)
        if tile.number <= 8:
            plus_1 = MahjongTile(number=tile.number + 1, family=tile.family)
        if minus_2:
            results.append(([(minus_2, minus_1, tile)], [minus_2, minus_1]))
        if minus_1:
            results.append(([(minus_1, tile, plus_1)], [minus_1, plus_1]))
        if plus_2:
            results.append(([(tile, plus_1, plus_2)], [plus_1, plus_2]))
        results.append(([(tile, tile, tile)], [tile, tile]))
    return results


def _can_be_pair(group: MahjongGroup):
    return len(group) <= 1 or len(group) == 2 and group[0] == group[1]


@cache
def _complete_pair(proto_group: MahjongGroup):
    # TODO verify tile count before generating
    if not _can_be_pair(proto_group):
        raise AttributeError('Invalid group')
    if len(proto_group) == 2:
        return [([proto_group], [])]
    elif len(proto_group) == 1:
        return [([(proto_group[0], proto_group[0])], [proto_group[0]])]
    # TODO empty proto group
    return [[()], []]


if __name__ == '__main__':
    print(can_construct_hand(parse_hand('(123)678m667p223s11z')))