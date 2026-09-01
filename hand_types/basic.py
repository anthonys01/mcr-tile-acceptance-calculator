from collections import Counter
from functools import cache, partial, reduce
from itertools import product

from group_finder import all_groups_for
from hand_scorer import get_best_yakus_for_won_hand, get_tenpai_acceptance
from mahjong_objects import MahjongHand, MahjongCombination, MahjongGroup, MahjongTile
from tiles_utils import parse_hand


def can_construct_hand(hand: MahjongHand, prevalent_wind=0, seat_wind=0, self_drawn=False):
    """Try to construct the fastest 8-point hand following basic acceptance

    Only return result hands when the final point count of the hand is 8 or more, for a basic hand at least 5-shanten
    :param hand: Mahjong hand
    :param prevalent_wind: prevalent wind (1-4) or 0 if unknown
    :param seat_wind: seat wind (1-4) or 0 if unknown
    :param self_drawn: score the candidate completions as self-draw wins (Fully
        Concealed Hand instead of Concealed Hand, +2 points for a closed hand).
        Some shapes only reach the 8-point minimum when self-drawn, so this
        widens the acceptance; see ``discard_ranking``.
    """
    acceptance = set()
    possible_hands = []
    kept_yakus = []
    for comb, added_tiles, yakus, won_hand in _get_all_possible_yakus(
        hand, prevalent_wind, seat_wind, self_drawn
    ):
        possible_hands.append(comb)
        kept_yakus.append((won_hand, yakus))
        acceptance.update(added_tiles)
    return possible_hands, acceptance, kept_yakus


def _compute_acceptance_for_winning_tile(
    won_hand, winning_tile: MahjongTile, declared_groups: tuple[MahjongGroup, ...] = ()
) -> set[MahjongTile]:
    """Derive the complete tenpai acceptance set of ``won_hand`` minus ``winning_tile``.

    The wait must be computed on the whole tenpai hand, not just on the group the
    winning tile belongs to: the very same tiles can often be re-parsed into other
    proto-groups accepting other tiles. Wait-shape yakus (edge/closed/single wait)
    only apply when the hand waits on a single tile overall.
    """
    remaining = list(declared_groups)
    free_tiles = []
    for group in won_hand:
        if group in remaining:
            remaining.remove(group)
            continue
        free_tiles.extend(group)
    if winning_tile not in free_tiles:
        return set()
    free_tiles.remove(winning_tile)
    return get_tenpai_acceptance(
        tuple(sorted(free_tiles)), 4 - len(declared_groups)
    )


_NO_YAKUS = object()


def _reachable_acceptance(added_tiles, scoring_tiles):
    """Tiles that can be drawn *now* without killing the 8-point plan.

    ``added_tiles`` is the whole multiset of tiles still missing from ``won_hand``;
    ``scoring_tiles`` are the ones that reach the 8-point minimum when they are the
    *winning* tile. Several yakus depend on which tile arrives last - wait shape
    above all - so the order of the draws matters and not every missing tile is
    real progress.

    ``13m 789m 123p 45p 99s`` needs both ``2m`` and ``6p``, but the hand only
    reaches 8 points by winning on ``2m`` (Closed Wait, +1). Drawing ``6p`` first
    leaves a single ``2m`` wait and is progress; drawing ``2m`` first leaves a
    two-sided ``3p``/``6p`` wait worth 7 points, i.e. an illegal hand. So ``6p``
    is acceptance for this plan and ``2m`` is not.

    A draw therefore counts when a scoring tile is still missing afterwards, or
    when it completes the hand itself.
    """
    if not scoring_tiles:
        return ()
    remaining = Counter(added_tiles)
    scoring = set(scoring_tiles)
    reachable = []
    for tile in remaining:
        remaining[tile] -= 1
        if sum(remaining.values()):
            still_reachable = any(remaining[scorer] for scorer in scoring)
        else:
            # last missing tile: drawing it wins, provided it is a scoring tile
            still_reachable = tile in scoring
        remaining[tile] += 1
        if still_reachable:
            reachable.append(tile)
    return tuple(reachable)


def _get_all_possible_yakus(hand: MahjongHand, prevalent_wind, seat_wind, self_drawn=False):
    fastest_hands = []
    best_shanten = 13
    declared_groups = hand.get_all_declared_groups()
    max_free_groups = 4 - len(declared_groups)
    free_tiles = hand.get_free_tiles()
    results = []
    for seq in range(max_free_groups + 1):
        free_groups: list[MahjongCombination] = all_groups_for(
            free_tiles, seq, max_free_groups - seq, 1
        )
        for g, residue in free_groups:
            if len(residue) > best_shanten:
                continue
            if len(residue) < best_shanten:
                best_shanten = len(residue)
                fastest_hands.clear()
            groups = declared_groups + list(g)
            fastest_hands.append((groups, residue))
    declared_tiles = hand.declared_tiles.copy()
    kongs = hand.kongs.copy()
    # The same (won_hand, winning tiles) is produced by many different free-group
    # decompositions; scoring only depends on those two, so cache it. Different
    # ``combination``/``residue`` are still emitted as separate results (they
    # matter for discard selection), only the expensive scoring is shared.
    scoring_cache: dict = {}
    acceptance_for_winning_tile = partial(
        _compute_acceptance_for_winning_tile, declared_groups=tuple(declared_groups)
    )
    for combination, residue in fastest_hands:
        if len(residue) > 5:
            continue
        for won_hand, added_tiles in _get_tenpai_hands_from(combination):
            cache_key = (won_hand, tuple(added_tiles))
            cached = scoring_cache.get(cache_key)
            if cached is None:
                complete_hand = MahjongHand(_get_flattened_tiles(won_hand))
                complete_hand.declared_tiles = declared_tiles
                complete_hand.kongs = kongs
                best_yakus, _, scoring_tiles = get_best_yakus_for_won_hand(
                    complete_hand,
                    won_hand,
                    list(added_tiles),
                    acceptance_for_winning_tile,
                    self_drawn=self_drawn,
                    prevalent_wind=prevalent_wind,
                    seat_wind=seat_wind,
                )
                reachable = _reachable_acceptance(added_tiles, scoring_tiles)
                cached = (best_yakus, reachable) if best_yakus else _NO_YAKUS
                scoring_cache[cache_key] = cached
            if cached is _NO_YAKUS:
                continue
            best_yakus, reachable = cached
            results.append(((combination, residue), reachable, best_yakus, won_hand))
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
        groups.extend(
            _complete_proto_group(to_complete[index])
            for index in range(len(to_complete))
            if index != pair_index
        )
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
        elif tile_1.family == tile_2.family and not tile_1.is_honor():
            # honors (and tiles of different families) have no sequence, so two
            # distinct such tiles can never be completed into a group
            smallest_tile = min(tile_1, tile_2)
            biggest_tile = max(tile_1, tile_2)
            if biggest_tile.number - smallest_tile.number == 2:
                # middle wait
                middle_tile = MahjongTile(
                    number=smallest_tile.number + 1, family=smallest_tile.family
                )
                results.append(
                    ([(smallest_tile, middle_tile, biggest_tile)], [middle_tile])
                )
            elif biggest_tile.number == 9 and smallest_tile.number == 8:
                # edge wait
                edge_tile = MahjongTile(number=7, family=smallest_tile.family)
                results.append(
                    ([(edge_tile, smallest_tile, biggest_tile)], [edge_tile])
                )
            elif smallest_tile.number == 1 and biggest_tile.number == 2:
                # edge wait
                edge_tile = MahjongTile(number=3, family=smallest_tile.family)
                results.append(
                    ([(smallest_tile, biggest_tile, edge_tile)], [edge_tile])
                )
            else:
                # double wait
                waiting_1 = MahjongTile(
                    number=smallest_tile.number - 1, family=smallest_tile.family
                )
                results.append(
                    ([(waiting_1, smallest_tile, biggest_tile)], [waiting_1])
                )
                waiting_2 = MahjongTile(
                    number=biggest_tile.number + 1, family=smallest_tile.family
                )
                results.append(
                    ([(smallest_tile, biggest_tile, waiting_2)], [waiting_2])
                )
    elif len(proto_group) == 1:
        minus_2 = None
        minus_1 = None
        plus_1 = None
        plus_2 = None
        tile = proto_group[0]
        if tile.is_honor():
            # no sequence with honors: the only completion is the triplet
            return [([(tile, tile, tile)], [tile, tile])]
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
        if minus_1 and plus_1:
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
        raise AttributeError("Invalid group")
    if len(proto_group) == 2:
        return [([proto_group], [])]
    elif len(proto_group) == 1:
        return [([(proto_group[0], proto_group[0])], [proto_group[0]])]
    return [[()], []]


if __name__ == "__main__":
    # print(can_construct_hand(parse_hand("256679s259m22378p")))
    print(can_construct_hand(parse_hand("13m588p344s124566z")))

