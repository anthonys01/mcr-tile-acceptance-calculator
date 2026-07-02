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
from tiles_utils import HONOR_TILES, ORPHAN_TILES


def _get_all_tenpai_forms(
    hand: MahjongHand,
) -> tuple[list[MahjongGroups], list[MahjongGroups]]:
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


def _get_acceptance(won_hand: MahjongHand):
    if not won_hand.needs_to_discard():
        return set()
    tenpai_hand = MahjongHand(won_hand.get_tiles_without_last())
    tenpai_hand.declared_tiles = set(won_hand.declared_tiles)
    tenpai_hand.kongs = set(won_hand.kongs)
    declared_groups = tenpai_hand.get_all_declared_groups()
    tenpai_forms, _ = _get_all_tenpai_forms(tenpai_hand)
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


def _get_context(
    hand: MahjongHand,
    won_hand: Iterable[MahjongGroup],
    acceptance: set[MahjongTile],
    self_drawn: bool,
    last_tile: bool,
    prevalent_wind: int,
    seat_wind: int,
) -> HandContext:
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


def _get_standard_hand_yakus(
    hand_context: HandContext,
) -> list[tuple[MahjongMCRYaku, int]]:
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
    base_context = _get_context(
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


def _get_yakus_compatible_with_seven_pairs(pairs, self_drawn, last_tile):
    compatible_yakus: list[tuple[MahjongMCRYaku, int]] = [
        (MahjongMCRYaku.SEVEN_PAIRS, 1)
    ]
    families = set()
    has_dragon = False
    has_winds = False
    has_terminals = False
    has_ordinary = False
    for pair in pairs:
        families.add(pair[0].family)
        if pair[0].family == Family.HONOR:
            if pair[0].is_dragon():
                has_dragon = True
            else:
                has_winds = True
        elif pair[0].is_terminal():
            has_terminals = True
        else:
            has_ordinary = True

    if all(pair[0].is_green() for pair in pairs):
        compatible_yakus.append((MahjongMCRYaku.ALL_GREEN, 1))

    if len(families) == 1:
        if has_winds or has_dragon:
            compatible_yakus.append((MahjongMCRYaku.ALL_HONORS, 1))
        else:
            sorted_nums = list(sorted(pair[0].number for pair in pairs))
            if len(set(sorted_nums)) == 7 and (
                sorted_nums[0] == 1
                and sorted_nums[-1] == 7
                or sorted_nums[0] == 2
                and sorted_nums[-1] == 8
                or sorted_nums[0] == 3
                and sorted_nums[-1] == 9
            ):
                compatible_yakus.clear()
                compatible_yakus.append((MahjongMCRYaku.SEVEN_SHIFTED_PAIRS, 1))
            else:
                compatible_yakus.append((MahjongMCRYaku.FULL_FLUSH, 1))
    elif len(families) == 2:
        if has_winds or has_dragon:
            compatible_yakus.append((MahjongMCRYaku.HALF_FLUSH, 1))
        else:
            compatible_yakus.append((MahjongMCRYaku.ONE_VOIDED_SUIT, 1))
            compatible_yakus.append((MahjongMCRYaku.NO_HONOR, 1))
    elif len(families) == 3 and (has_winds or has_dragon):
        compatible_yakus.append((MahjongMCRYaku.ONE_VOIDED_SUIT, 1))
    elif len(families) == 4 and has_dragon and has_winds:
        compatible_yakus.append((MahjongMCRYaku.ALL_TYPES, 1))

    if (has_dragon or has_winds) and has_terminals and not has_ordinary:
        compatible_yakus.append((MahjongMCRYaku.ALL_TERMINAL_AND_HONORS, 1))
    elif not has_dragon and not has_winds and has_terminals and not has_ordinary:
        compatible_yakus.append((MahjongMCRYaku.ALL_TERMINALS, 1))
    elif not has_dragon and not has_winds and not has_terminals and has_ordinary:
        compatible_yakus.append((MahjongMCRYaku.ALL_SIMPLE, 1))

    if all(p[0].number <= 3 for p in pairs):
        if (MahjongMCRYaku.NO_HONOR, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.NO_HONOR, 1))
        compatible_yakus.append((MahjongMCRYaku.LOWER_TILES, 1))
    elif all(p[0].number >= 7 for p in pairs):
        if (MahjongMCRYaku.NO_HONOR, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.NO_HONOR, 1))
        compatible_yakus.append((MahjongMCRYaku.UPPER_TILES, 1))
    elif all(4 <= p[0].number <= 6 for p in pairs):
        if (MahjongMCRYaku.NO_HONOR, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.NO_HONOR, 1))
        if (MahjongMCRYaku.ALL_SIMPLE, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.ALL_SIMPLE, 1))
        compatible_yakus.append((MahjongMCRYaku.MIDDLE_TILES, 1))
    elif all(p[0].number <= 4 for p in pairs):
        if (MahjongMCRYaku.NO_HONOR, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.NO_HONOR, 1))
        compatible_yakus.append((MahjongMCRYaku.LOWER_FOUR, 1))
    elif all(p[0].number >= 6 for p in pairs):
        if (MahjongMCRYaku.NO_HONOR, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.NO_HONOR, 1))
        compatible_yakus.append((MahjongMCRYaku.UPPER_FOUR, 1))

    if all(p[0].is_symmetric() for p in pairs):
        if (MahjongMCRYaku.ONE_VOIDED_SUIT, 1) in compatible_yakus:
            compatible_yakus.remove((MahjongMCRYaku.ONE_VOIDED_SUIT, 1))
        compatible_yakus.append((MahjongMCRYaku.REVERSIBLE_TILES, 1))

    unique_pairs = len(set(pairs))
    if unique_pairs < 7:
        compatible_yakus.append((MahjongMCRYaku.TILE_HOG, 7 - unique_pairs))

    if self_drawn:
        compatible_yakus.append((MahjongMCRYaku.FULLY_CONCEALED, 1))
    if last_tile:
        compatible_yakus.append((MahjongMCRYaku.LAST_TILE, 1))
    return compatible_yakus


def _is_thirteen_orphans(hand):
    for tile in ORPHAN_TILES:
        if tile not in hand.hand_tiles:
            return False
    for tile in hand.hand_tiles:
        if tile.is_ordinary():
            return False
    return True


def _get_orphans_acceptance(hand: MahjongHand):
    hand_tiles = hand.get_tiles_without_last()
    orphans_acceptance = set(ORPHAN_TILES).difference(hand_tiles)
    return orphans_acceptance if orphans_acceptance else set(ORPHAN_TILES)


def _check_knitted(hand: MahjongHand) -> MahjongGroups:
    honors_tiles = set(HONOR_TILES).intersection(hand.get_free_tiles())
    declared_groups = hand.get_all_declared_groups()
    if len(honors_tiles) >= 5 and hand.is_closed_hand():
        _, knitted_tiles = hand.get_missing_tiles_and_residue(honors_tiles)
        if _check_knitted_straight(knitted_tiles):
            return tuple(knitted_tiles), tuple(honors_tiles)
    if len(declared_groups) > 1:
        return ()
    elif hand.is_closed_hand():
        free_groups: list[MahjongCombination] = all_groups_for(
            hand.hand_tiles, 1, 0, 1
        ) + all_groups_for(hand.hand_tiles, 0, 1, 1)
        for groups, residue in free_groups:
            if (
                groups
                and len(groups[0]) == 2
                and len(groups[1]) == 3
                or len(groups[0]) == 3
                and len(groups[1]) == 2
            ):
                if _check_knitted_straight(residue):
                    return tuple(residue), groups[0], groups[1]
    else:
        group = declared_groups[0]
        for pairs, residue in all_groups_for(hand.get_free_tiles(), 0, 0, 1):
            if pairs and len(pairs[0]) == 2:
                if _check_knitted_straight(residue):
                    return tuple(residue), pairs[0], group
    return ()


def _check_knitted_straight(knitted_tiles: list[MahjongTile]) -> bool:
    limit = len(knitted_tiles)
    if limit < 7 or limit > 9:
        return False
    families: list[list[MahjongTile]] = [[], [], []]
    tiles_to_family = {
        1: families[0],
        2: families[1],
        3: families[2],
        4: families[0],
        5: families[1],
        6: families[2],
        7: families[0],
        8: families[1],
        9: families[2],
    }
    for tile in knitted_tiles:
        if tile.is_honor():
            continue
        tiles_to_family[tile.number].append(tile)

    all_families = set()
    for family in families:
        if not family:
            return False
        f = family[0].family
        all_families.add(f)
        for tile in family:
            if tile.family != f:
                return False

    if len(all_families) < 3:
        return False

    return sum(len(set(f)) for f in families) == limit


def _get_knitted_honors_acceptance(hand: MahjongHand, knitted):
    knitted_tiles = set()
    for tile in knitted[0]:
        knitted_tiles.add(tile)
        knitted_tiles.add(
            MahjongTile(number=((tile.number + 2) % 9) + 1, family=tile.family)
        )
        knitted_tiles.add(
            MahjongTile(number=((tile.number + 5) % 9) + 1, family=tile.family)
        )
    knitted_tiles.update(HONOR_TILES)
    return knitted_tiles.difference(hand.get_tiles_without_last())


def _get_knitted_straight_acceptance(hand, knitted):
    winning_tile = hand.drawn_tile
    for knitted_group in knitted[1:]:
        if winning_tile in knitted_group and knitted_group not in hand.declared_tiles:
            if len(knitted_group) == 2:
                # pair wait
                return {winning_tile}
            else:
                # concealed hand
                straight_acceptance = set()
                free_tiles = []
                free_tiles.extend(knitted[1])
                free_tiles.extend(knitted[2])
                free_tiles.remove(winning_tile)
                free_groups: list[MahjongCombination] = all_groups_for(
                    free_tiles, 1, 0, 1
                ) + all_groups_for(free_tiles, 0, 1, 1)
                for groups, residue in free_groups:
                    if residue:
                        continue
                    straight_acceptance.update(
                        get_tile_acceptance_of_groups(tuple(groups))
                    )
                return straight_acceptance
    # winning tile in the knitted straight group
    return {winning_tile}


def _get_yakus_compatible_with_knitted(
    hand, knitted, self_drawn, last_tile, prevalent_wind, seat_wind
):
    yakus = []
    if len(knitted) == 2:
        # with honors
        tile_acceptance = _get_knitted_honors_acceptance(hand, knitted)
        if len(knitted[1]) == 7:
            # greater
            yakus.append((MahjongMCRYaku.GREATER_HONORS_AND_KNITTED_TILES, 1))
        elif len(knitted[1]) == 5:
            yakus.append((MahjongMCRYaku.LESSER_HONORS_AND_KNITTED_TILES, 1))
            yakus.append((MahjongMCRYaku.KNITTED_STRAIGHT, 1))
        else:
            yakus.append((MahjongMCRYaku.LESSER_HONORS_AND_KNITTED_TILES, 1))
        if self_drawn:
            yakus.append((MahjongMCRYaku.FULLY_CONCEALED, 1))
        if last_tile:
            yakus.append((MahjongMCRYaku.LAST_TILE, 1))
    else:
        # standard hand
        yakus.append((MahjongMCRYaku.KNITTED_STRAIGHT, 1))
        tile_acceptance = _get_knitted_straight_acceptance(hand, knitted)
        context = _get_context(
            hand,
            knitted,
            tile_acceptance,
            self_drawn,
            last_tile,
            prevalent_wind,
            seat_wind,
        )
        yakus.extend(_get_standard_hand_yakus(context))
    return tile_acceptance, knitted, yakus


def print_yakus(yakus: list[tuple[MahjongMCRYaku, int]]) -> str:
    """
    Return a str with a formatted table of all the yakus, with the total
    """
    rows = []
    for yaku, count in sorted(yakus, key=lambda x: x[0].get_id()):
        name = yaku.name.replace("_", " ").title()
        if count > 1:
            name = f"{name} \u00d7{count}"
        rows.append((name, yaku.get_points() * count))
    total = sum(points for _, points in rows)
    name_width = max([len("Yaku")] + [len(name) for name, _ in rows])
    points_width = max(
        [len("Points")] + [len(str(points)) for _, points in rows] + [len(str(total))]
    )
    sep = f"+-{'-' * name_width}-+-{'-' * points_width}-+"
    result = [sep, f"| {'Yaku':<{name_width}} | {'Points':>{points_width}} |", sep]
    for name, points in rows:
        result.append(f"| {name:<{name_width}} | {points:>{points_width}} |")
    result.append(sep)
    result.append(f"| {'Total':<{name_width}} | {total:>{points_width}} |")
    result.append(sep)
    return "\n".join(result)


def get_total_points(yakus):
    return sum(times * yaku.get_points() for yaku, times in yakus)


def get_won_hand_yakus(
    hand,
    self_drawn: bool = False,
    last_tile: bool = False,
    prevalent_wind=0,
    seat_wind=0,
    accept_closed_chicken=False
) -> tuple[set[MahjongTile], MahjongGroups, list[tuple[MahjongMCRYaku, int]]]:
    """
    Compute the hand tenpai acceptance and yakus
    Only supports a complete hand
    :return: acceptance, won hand, yakus
    """
    if not hand.needs_to_discard():
        return set(), (), []
    won_hands_scores = []
    acceptance = set()
    if hand.is_closed_hand() and not hand.kongs:
        # check orphans (can return immediately)
        if _is_thirteen_orphans(hand):
            yakus: list[tuple[MahjongMCRYaku, int]] = [
                (MahjongMCRYaku.THIRTEEN_ORPHANS, 1)
            ]
            if self_drawn:
                yakus.append((MahjongMCRYaku.FULLY_CONCEALED, 1))
            if last_tile:
                yakus.append((MahjongMCRYaku.LAST_TILE, 1))
            return _get_orphans_acceptance(hand), tuple(hand.hand_tiles), yakus

        # check pairs
        pairs: list[MahjongCombination] = all_groups_for(hand.get_free_tiles(), 0, 0, 7)
        if pairs and not pairs[0][1]:
            won_hands_scores.append(
                (
                    pairs[0][0],
                    _get_yakus_compatible_with_seven_pairs(
                        pairs[0][0], self_drawn, last_tile
                    ),
                )
            )
            acceptance.add(hand.drawn_tile)

    # check knitted
    knitted = _check_knitted(hand)
    if knitted:
        return _get_yakus_compatible_with_knitted(
            hand, knitted, self_drawn, last_tile, prevalent_wind, seat_wind
        )

    acceptance.update(_get_acceptance(hand))
    _, regular_won_hands = _get_all_tenpai_forms(hand)
    if regular_won_hands:
        for won_hand in regular_won_hands:
            won_hands_scores.append(
                (
                    won_hand,
                    get_won_hand_yakus_for_basic_groups(
                        hand,
                        won_hand,
                        acceptance,
                        self_drawn,
                        last_tile,
                        prevalent_wind,
                        seat_wind,
                    ),
                )
            )
    best_pattern = max(
        won_hands_scores,
        key=lambda x: sum(times * yaku.get_points() for (yaku, times) in x[1]),
    )
    final_yakus = best_pattern[1]
    if accept_closed_chicken and len(final_yakus) == 1 and final_yakus[0][0] == MahjongMCRYaku.CONCEALED_HAND:
        final_yakus = [(MahjongMCRYaku.CHICKEN_HAND, 1)]
    return acceptance, best_pattern[0], final_yakus


def get_won_hand_yakus_for_basic_groups(
    hand,
    won_hand,
    acceptance=None,
    self_drawn: bool = False,
    last_tile: bool = False,
    prevalent_wind=0,
    seat_wind=0,
):
    if acceptance is None:
        acceptance = _get_acceptance(hand)
    context = _get_context(
        hand,
        won_hand,
        acceptance,
        self_drawn,
        last_tile,
        prevalent_wind,
        seat_wind,
    )
    return _get_standard_hand_yakus(context)


def get_ordinal_yakus(yakus):
    """Returns hashable comparable tuple of yakus"""
    return tuple(sorted(yakus, key=lambda x: x[0].get_id()))
