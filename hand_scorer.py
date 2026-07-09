from typing import Iterable

from acceptance import get_tile_acceptance_of_groups
from group_finder import all_groups_for
from mahjong_objects import (
    MahjongGroup,
    MahjongHand,
    MahjongCombination,
    MahjongTile,
    HandContext,
    MahjongGroups,
    MahjongMCRYaku,
    Family,
)

def get_all_tenpai_forms(
    hand: MahjongHand,
) -> tuple[list[MahjongGroups], list[MahjongGroups]]:
    """Return all tenpai and winning group arrangements for the given hand.

    :param hand: the hand to analyse
    :return: (tenpai_forms, won_forms) where each form is a list of group lists
    """
    tenpai_hands = []
    won_hands = []
    declared_groups = hand.get_all_declared_groups()
    max_free_groups = 4 - len(declared_groups)
    for seq in range(max_free_groups + 1):
        free_groups: list[MahjongCombination] = all_groups_for(
            hand.get_free_tiles(), seq, max_free_groups - seq, 1
        )
        for g, residue in free_groups:
            groups = declared_groups + list(g)
            if hand.needs_to_discard():
                if len(residue) == 0:
                    won_hands.append(groups)
                elif len(residue) == 1:
                    tenpai_hands.append(groups)
            elif len(residue) == 0:
                tenpai_hands.append(groups)
    return tenpai_hands, won_hands


def get_acceptance(won_hand: MahjongHand) -> set[MahjongTile]:
    """Compute the full tenpai acceptance set for a hand that needs to discard.

    :param won_hand: hand holding one tile more than the natural size
    :return: set of tiles that the hand can win on
    """
    if not won_hand.needs_to_discard():
        return set()
    tenpai_hand = MahjongHand(won_hand.get_tiles_without_last())
    tenpai_hand.declared_tiles = set(won_hand.declared_tiles)
    tenpai_hand.kongs = set(won_hand.kongs)
    declared_groups = tenpai_hand.get_all_declared_groups()
    tenpai_forms, _ = get_all_tenpai_forms(tenpai_hand)
    acceptance = set()
    for groups in tenpai_forms:
        free_groups = set(groups).difference(declared_groups)
        acceptance.update(get_tile_acceptance_of_groups(tuple(free_groups)))
    return acceptance


def _context_from_base(
    base: HandContext, acceptance: set[MahjongTile], winning_tile: MahjongTile
) -> HandContext:
    """Build a context for another winning tile of the same won_hand.

    The group classification (chows/pungs/kongs/families/...) depends only on
    the won_hand, so it is reused from ``base``; only ``acceptance`` and the
    ``winning_tile`` differ. The mutable combination pools are freshly rebuilt by
    ``HandContext.__post_init__``. Equivalent to re-running ``_get_context`` but
    without re-classifying the groups on every winning tile.
    """
    return HandContext(
        base.all_tiles,
        base.groups,
        base.pair,
        acceptance,
        base.chows,
        base.pungs,
        base.kongs,
        base.open_chows,
        base.open_pungs,
        base.open_kongs,
        base.families,
        base.is_drawn,
        winning_tile,
        base.prevalent_wind,
        base.seat_wind,
        base.has_knitted_straight,
        base.is_last_tile,
    )


def get_context(
    hand: MahjongHand,
    won_hand: Iterable[MahjongGroup],
    acceptance: set[MahjongTile],
    self_drawn: bool,
    last_tile: bool,
    prevalent_wind: int,
    seat_wind: int,
) -> HandContext:
    """Build a HandContext from a complete winning hand arrangement.

    Classifies each group as chow/pung/kong/pair, identifies open groups, and
    collects the families present, then wraps everything in a HandContext ready
    for yaku analysis.

    :param hand: the MahjongHand (used for declared-group membership)
    :param won_hand: the winning group arrangement (iterable of groups + pair)
    :param acceptance: pre-computed acceptance set for the winning tile
    :param self_drawn: True if the winning tile was self-drawn
    :param last_tile: True if this is the last tile in the wall
    :param prevalent_wind: 1-4 for East-North, 0 if unknown
    :param seat_wind: 1-4 for East-North, 0 if unknown
    :return: a fully populated HandContext
    """
    groups = []
    pair = None
    chows = []
    pungs = []
    kongs = []
    open_chows = []
    open_pungs = []
    open_kongs = []
    families = set()
    knitted = False
    for group in won_hand:
        group_length = len(group)
        if group_length == 4:
            kongs.append(group)
            if group in hand.declared_tiles:
                open_kongs.append(group)
        elif group_length == 2:
            pair = group
        elif group_length == 3:
            groups.append(group)
            if group[0] == group[1]:
                pungs.append(group)
                if group in hand.declared_tiles:
                    open_pungs.append(group)
            else:
                chows.append(group)
                if group in hand.declared_tiles:
                    open_chows.append(group)
        else:
            # knitted straight group
            knitted = True
            families.add(Family.BAMBOO)
            families.add(Family.CHARACTER)
            families.add(Family.CIRCLE)
        families.add(group[0].family)

    if pair is None or hand.drawn_tile is None:
        raise AttributeError("not all conditions are OK for hand value analysis")

    return HandContext(
        hand.hand_tiles,
        tuple(groups),
        pair,
        acceptance,
        chows,
        pungs,
        kongs,
        open_chows,
        open_pungs,
        open_kongs,
        families,
        self_drawn,
        hand.drawn_tile,
        prevalent_wind,
        seat_wind,
        knitted,
        last_tile,
    )


def get_standard_hand_yakus(
    hand_context: HandContext,
) -> list[tuple[MahjongMCRYaku, int]]:
    """Evaluate all standard yakus for a hand context and return the scored list.

    Runs the full yaku-check pipeline: one pass over all yakus with exclusion
    tracking, then a fixed-point loop for multi-occurrence yakus.  Returns
    [(CHICKEN_HAND, 1)] when nothing fires.

    :param hand_context: pre-built HandContext for the winning arrangement
    :return: list of (yaku, count) pairs
    """
    exclusions = set()
    results: dict[MahjongMCRYaku, int] = {}

    # First pass: check every yaku once, accumulating counts
    for yaku in _ALL_YAKUS:
        if yaku in exclusions:
            continue
        count = yaku.check(hand_context)
        if count:
            results[yaku] = count
            exclusions.update(yaku.get_exclusions())

    if not results:
        return [(MahjongMCRYaku.CHICKEN_HAND, 1)]

    # Fixed-point loop: re-check multi-occurrence yakus until no new firings
    changed = True
    while changed:
        changed = False
        for yaku in _MULTI_YAKUS:
            if yaku in exclusions:
                continue
            count = yaku.check(hand_context)
            if count:
                results[yaku] = results.get(yaku, 0) + count
                changed = True

    return list(results.items())


_TILE_DEPENDENT_YAKUS = frozenset(
    {
        MahjongMCRYaku.NINE_GATES,
        MahjongMCRYaku.FOUR_CONCEALED_PUNGS,
        MahjongMCRYaku.THREE_CONCEALED_PUNGS,
        MahjongMCRYaku.TWO_CONCEALED_PUNGS,
        MahjongMCRYaku.EDGE_WAIT,
        MahjongMCRYaku.CLOSED_WAIT,
        MahjongMCRYaku.SINGLE_WAIT,
    }
)

# Precomputed yaku iteration orders. The scorer loops run millions of times
# during hand analysis; iterating ``MahjongMCRYaku`` directly goes through the
# Enum iterator on every pass and forces per-iteration ``is_multi()`` /
# membership filtering. These tuples preserve enum definition order (so results
# are unchanged) while turning each loop into a tight iteration over exactly the
# members it needs.
_ALL_YAKUS = tuple(MahjongMCRYaku)
_MULTI_YAKUS = tuple(y for y in _ALL_YAKUS if y.is_multi())
_TILE_INDEPENDENT_YAKUS = tuple(
    y for y in _ALL_YAKUS if y not in _TILE_DEPENDENT_YAKUS
)
_TILE_INDEPENDENT_MULTI_YAKUS = tuple(
    y for y in _TILE_INDEPENDENT_YAKUS if y.is_multi()
)
_TILE_DEPENDENT_YAKUS_ORDERED = tuple(
    y for y in _ALL_YAKUS if y in _TILE_DEPENDENT_YAKUS
)


def _get_tile_independent_yakus_and_exclusions(
    context: HandContext,
) -> tuple[dict, set]:
    """Compute all yakus that do not depend on winning_tile or acceptance (once per won_hand).
    Returns (results dict, exclusions set)."""
    exclusions = set()
    results: dict = {}

    for yaku in _TILE_INDEPENDENT_YAKUS:
        if yaku in exclusions:
            continue
        count = yaku.check(context)
        if count:
            results[yaku] = count
            exclusions.update(yaku.get_exclusions())

    # Fixed-point loop for multi-occurrence yakus (all non-dependent)
    changed = True
    while changed:
        changed = False
        for yaku in _TILE_INDEPENDENT_MULTI_YAKUS:
            if yaku in exclusions:
                continue
            count = yaku.check(context)
            if count:
                results[yaku] = results.get(yaku, 0) + count
                changed = True

    return results, exclusions


def _get_tile_dependent_yakus(context: HandContext, base_exclusions: set) -> dict:
    """Compute only the winning-tile-dependent yakus.  Returns results dict.

    Iterates in enum order to respect intra-dependent exclusion chains
    (e.g. FOUR_CONCEALED_PUNGS excluding THREE and TWO_CONCEALED_PUNGS).
    """
    results: dict = {}
    exclusions = set(base_exclusions)
    for yaku in _TILE_DEPENDENT_YAKUS_ORDERED:
        if yaku in exclusions:
            continue
        count = yaku.check(context)
        if count:
            results[yaku] = count
            exclusions.update(yaku.get_exclusions())
    return results


def _merge_winning_tile_yakus(
    base_results: dict, dep_results: dict
) -> list[tuple[MahjongMCRYaku, int]]:
    """Merge tile-independent and tile-dependent results.
    Exclusions triggered by dependent yakus override independent results."""
    dep_exclusions: set = set()
    for yaku in dep_results:
        dep_exclusions.update(yaku.get_exclusions())

    merged = {y: c for y, c in base_results.items() if y not in dep_exclusions}
    merged.update(dep_results)

    if not merged:
        return [(MahjongMCRYaku.CHICKEN_HAND, 1)]
    return list(merged.items())


def get_best_yakus_for_won_hand(
    hand: MahjongHand,
    won_hand,
    winning_tiles,
    compute_acceptance,
    self_drawn: bool = False,
    last_tile: bool = False,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
) -> tuple[list | None, int]:
    """Compute the best-scoring yakus across all winning tiles for a given won_hand.

    Optimises by computing tile-independent yakus only once, then merging with
    per-tile dependent yakus (wait type, concealed pungs) for each winning tile.
    Returns (best_yakus, best_points); best_yakus is None when no yaku scores above 7.
    """
    if not winning_tiles:
        return None, 0

    # Use the first winning tile to build the base context for the independent pass.
    # Independent yakus don't consult winning_tile, so the choice is arbitrary.
    first_tile = winning_tiles[0]
    hand.drawn_tile = first_tile
    base_context = get_context(
        hand, won_hand, set(), self_drawn, last_tile, prevalent_wind, seat_wind
    )
    base_results, base_exclusions = _get_tile_independent_yakus_and_exclusions(
        base_context
    )

    best_yakus = None
    best_points = 7

    for winning_tile in winning_tiles:
        acceptance = compute_acceptance(won_hand, winning_tile)
        dep_context = _context_from_base(base_context, acceptance, winning_tile)
        dep_results = _get_tile_dependent_yakus(dep_context, base_exclusions)
        yakus = _merge_winning_tile_yakus(base_results, dep_results)
        yakus = _replace_with_chicken_when_relevant(yakus)
        points = get_total_points(yakus)
        if points > best_points:
            best_yakus = yakus
            best_points = points

    return best_yakus, best_points

def _replace_with_chicken_when_relevant(yakus):
    """If the basic hand only has CONCEALED_HAND, CHICKEN_HAND is possible just with calling one random group"""
    if len(yakus) == 1:
        yaku_val = yakus[0][0]
        if yaku_val == MahjongMCRYaku.CONCEALED_HAND:
            return [(MahjongMCRYaku.CHICKEN_HAND, 1)]
    return yakus

def get_total_points(yakus) -> int:
    """Return the total point value of a list of (yaku, count) pairs."""
    return sum(times * yaku.get_points() for yaku, times in yakus)
