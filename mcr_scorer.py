
from group_finder import all_groups_for
from mahjong_objects import MahjongHand, MahjongCombination, MahjongTile, HandContext, MahjongGroups, EAST, \
    MahjongMCRYaku, Family
from tile_acceptance_calculator import get_tile_acceptance_of_groups
from tiles_utils import parse_tiles


ORPHANS = set(parse_tiles('19s19p19m1234567z'))

HONORS = set(parse_tiles('1234567z'))


def _get_all_tenpai_forms(hand: MahjongHand) -> tuple[list[MahjongGroups], list[MahjongGroups]]:
    tenpai_hands = []
    won_hands = []
    declared_groups = hand.get_all_declared_groups()
    max_free_groups = 4 - len(declared_groups)
    for seq in range(max_free_groups + 1):
        free_groups: list[MahjongCombination] = all_groups_for(hand.get_free_tiles(), seq, max_free_groups - seq, 1)
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


def _get_context(hand, won_hand, acceptance):
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

    return HandContext(hand.hand_tiles,
                       tuple(groups), pair, acceptance,
                       chows, pungs, kongs, open_chows, open_pungs, open_kongs,
                       families, False, hand.drawn_tile, EAST.number, EAST.number, knitted, False)


def _get_standard_hand_yakus(hand_context: HandContext) -> list[tuple[MahjongMCRYaku, int]]:
    exclusions = set()
    results: dict[MahjongMCRYaku, int] = {}

    # First pass: check every yaku once, accumulating counts
    for yaku in MahjongMCRYaku:
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
        for yaku in MahjongMCRYaku:
            if not yaku.is_multi() or yaku in exclusions:
                continue
            count = yaku.check(hand_context)
            if count:
                results[yaku] = results.get(yaku, 0) + count
                changed = True

    return list(results.items())


def _print_yakus(yakus: list[tuple[MahjongMCRYaku, int]]):
    rows = []
    for yaku, count in yakus:
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
    print(sep)
    print(f"| {'Yaku':<{name_width}} | {'Points':>{points_width}} |")
    print(sep)
    for name, points in rows:
        print(f"| {name:<{name_width}} | {points:>{points_width}} |")
    print(sep)
    print(f"| {'Total':<{name_width}} | {total:>{points_width}} |")
    print(sep)


def _get_yakus_compatible_with_seven_pairs(pairs, self_drawn):
    compatible_yakus: list[tuple[MahjongMCRYaku, int]] = [(MahjongMCRYaku.SEVEN_PAIRS, 1)]
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

    if len(families) == 1:
        if has_winds or has_dragon:
            compatible_yakus.append((MahjongMCRYaku.ALL_HONORS, 1))
        else:
            sorted_nums = list(sorted(pair[0].number for pair in pairs))
            if sorted_nums[0] == 1 and sorted_nums[-1] == 7 or\
                    sorted_nums[0] == 2 and sorted_nums[-1] == 8 or\
                    sorted_nums[0] == 3 and sorted_nums[-1] == 9:
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

    unique_pairs = len(set(pairs))
    if unique_pairs < 7:
        compatible_yakus.append((MahjongMCRYaku.TILE_HOG, 7 - unique_pairs))

    if self_drawn:
        compatible_yakus.append((MahjongMCRYaku.FULLY_CONCEALED, 1))
    return compatible_yakus


def _is_thirteen_orphans(hand):
    for tile in ORPHANS:
        if tile not in hand.hand_tiles:
            return False
    for tile in hand.hand_tiles:
        if tile.is_ordinary():
            return False
    return True


def _get_orphans_acceptance(hand: MahjongHand):
    hand_tiles = hand.get_tiles_without_last()
    orphans_acceptance = ORPHANS.difference(hand_tiles)
    return orphans_acceptance if orphans_acceptance else ORPHANS


def _check_knitted(hand: MahjongHand) -> MahjongGroups:
    honors_tiles = HONORS.intersection(hand.get_free_tiles())
    if len(honors_tiles) >= 5 and hand.is_closed_hand():
        _, knitted_tiles = hand.get_missing_tiles_and_residue(honors_tiles)
        if _check_knitted_straight(knitted_tiles):
            return tuple(knitted_tiles), tuple(honors_tiles)
    if len(hand.declared_tiles.union(hand.kongs)) > 1:
        return ()
    elif hand.is_closed_hand():
        free_groups: list[MahjongCombination] = all_groups_for(hand.hand_tiles, 1, 0, 1) +\
                                                all_groups_for(hand.hand_tiles, 0, 1, 1)
        for groups, residue in free_groups:
            if groups and len(groups[0]) == 2 and len(groups[1]) == 3 or len(groups[0]) == 3 and len(groups[1]) == 2:
                if _check_knitted_straight(residue):
                    return tuple(residue), groups[0], groups[1]
    else:
        group = list(hand.declared_tiles.union(hand.kongs))[0]
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
    tiles_to_family = {1: families[0], 2: families[1], 3: families[2],
                       4: families[0], 5: families[1], 6: families[2],
                       7: families[0], 8: families[1], 9: families[2]}
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
        knitted_tiles.add(MahjongTile(number=((tile.number + 2) % 9) + 1, family=tile.family))
        knitted_tiles.add(MahjongTile(number=((tile.number + 5) % 9) + 1, family=tile.family))
    knitted_tiles.update(HONORS)
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
                free_groups: list[MahjongCombination] = all_groups_for(free_tiles, 1, 0, 1) + \
                                                        all_groups_for(free_tiles, 0, 1, 1)
                for groups, residue in free_groups:
                    if residue:
                        continue
                    straight_acceptance.update(get_tile_acceptance_of_groups(tuple(groups)))
                return straight_acceptance
    # winning tile in the knitted straight group
    return {winning_tile}


def _get_yakus_compatible_with_knitted(hand, knitted, self_drawn, last_tile=False):
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
        context = _get_context(hand, knitted, tile_acceptance)
        yakus.extend(_get_standard_hand_yakus(context))
    return tile_acceptance, knitted, yakus


def get_won_hand_yakus(hand, self_drawn: bool = False) -> tuple[set[MahjongTile], MahjongGroups, list[tuple[MahjongMCRYaku, int]]]:
    if not hand.needs_to_discard():
        return set(), (), []
    won_hands_scores = []
    if hand.is_closed_hand() and not hand.kongs:
        # check orphans (can return immediately)
        if _is_thirteen_orphans(hand):
            # last tile not taken into account
            yakus: list[tuple[MahjongMCRYaku, int]] = [(MahjongMCRYaku.THIRTEEN_ORPHANS, 1)]
            if self_drawn:
                yakus.append((MahjongMCRYaku.FULLY_CONCEALED, 1))
            return _get_orphans_acceptance(hand), tuple(hand.hand_tiles), yakus

        # check pairs
        pairs: list[MahjongCombination] = all_groups_for(hand.get_free_tiles(), 0, 0, 7)
        if pairs and not pairs[0][1]:
            won_hands_scores.append(
                (pairs[0][0], _get_yakus_compatible_with_seven_pairs(pairs[0][0], self_drawn)))

    # check knitted
    knitted = _check_knitted(hand)
    if knitted:
        return _get_yakus_compatible_with_knitted(hand, knitted, self_drawn)

    acceptance = _get_acceptance(hand)
    tenpai_hands, regular_won_hands = _get_all_tenpai_forms(hand)
    if regular_won_hands:
        for won_hand in regular_won_hands:
            context = _get_context(hand, won_hand, acceptance)
            won_hands_scores.append((won_hand, _get_standard_hand_yakus(context)))
    best_pattern = max(won_hands_scores, key=lambda x: sum(times * yaku.get_points() for (yaku, times) in x[1]))
    return acceptance, best_pattern[0], best_pattern[1]


def _test_scorer():
    # hand = MahjongHand(parse_tiles("123456789p22333m"), MahjongTile("2m"))
    #
    # hand = MahjongHand(parse_tiles("123789p123m789s77z"), MahjongTile("7p"))
    # # should be Outside Hand, Concealed Hand, Mixed Double Chow x 2, Two Terminal Chows, Edge Wait
    #
    # hand = MahjongHand(parse_tiles("11133p999s111777z"), MahjongTile("3p"))
    # hand.declared_tiles.add((MahjongTile('1p'), MahjongTile('1p'), MahjongTile('1p')))
    # hand.declared_tiles.add((MahjongTile('9s'), MahjongTile('9s'), MahjongTile('9s')))
    # # should be All Pungs, Dragon Pung, Prevalent Wind, Seat Wind, Two Concealed Pungs, Pung Of Terminal Or Honors x2, One Voided Suit, Single Wait
    #
    # hand = MahjongHand(parse_tiles("11133p111999s777z"), MahjongTile("3p"))
    # hand.declared_tiles.add((MahjongTile('1p'), MahjongTile('1p'), MahjongTile('1p')))
    # hand.declared_tiles.add((MahjongTile('9s'), MahjongTile('9s'), MahjongTile('9s')))
    # # should be All Pungs, Dragon Pung, Double Pungs, Two Concealed Pungs, Pung Of Terminal Or Honors x 3, One voided Suit, Single Wait
    #
    # hand = MahjongHand(parse_tiles("222234444p23455s"), MahjongTile("2s"))
    # # should be Concealed Hand, Tile Hog x 2, Two Concealed Pungs, All Simple, Mixed Double Chow, One Voided Suit
    #
    # hand = MahjongHand(parse_tiles("22334455667788s"), MahjongTile("2s"))
    # # should be Seven Shifted Pairs, All Simple
    #
    # hand = MahjongHand(parse_tiles("22223333444499s"), MahjongTile("2s"))
    # # should be Quadruple Chow, Full Flush, Concealed Hand, All Chows
    #
    # hand = MahjongHand(parse_tiles("11122345678999s"), MahjongTile("2s"))
    # # should be Nine Gates, Two Concealed Pungs, Short Straight
    #
    # hand = MahjongHand(parse_tiles("199s19p19m1234567z"), MahjongTile("1s"))
    # # should be Thirteen Orphans
    #
    # hand = MahjongHand(parse_tiles("147s258m369p789s11p"), MahjongTile("7s"))
    # # should be Knitted Straight, Concealed Hand, All Chows, Edge Wait
    #
    # hand = MahjongHand(parse_tiles("147s258m369p789s11p"), MahjongTile("7s"))
    # hand.declared_tiles.add((MahjongTile('7s'), MahjongTile('8s'), MahjongTile('9s')))
    # # should be Knitted Straight, All Chows
    #
    # hand = MahjongHand(parse_tiles("147s258m369p22277z"), MahjongTile("2z"))
    # # should be Knitted Straight, All Types, Concealed Hand, Pung of Terminal or Honor
    #
    # hand = MahjongHand(parse_tiles("147s258m369p12457z"), MahjongTile("2z"))
    # # should be Knitted Straight, Lesser honors and knitted
    #
    # hand = MahjongHand(parse_tiles("1s258m369p1234567z"), MahjongTile("2z"))
    # # should be greater honors and knitted
    #
    # hand = MahjongHand(parse_tiles("1111p22s9999m1166z"), MahjongTile("1z"))
    # # should be Seven Pairs, All Types, Tile Hog x 2
    #
    # hand = MahjongHand(parse_tiles("222p345m234789s11z"), MahjongTile("2s"))
    # hand.declared_tiles.add((MahjongTile('2p'), MahjongTile('2p'), MahjongTile('2p')))
    # # should be Chicken Hand
    #
    # hand = MahjongHand(parse_tiles("1111s111p222278999m"), MahjongTile("9m"))
    # hand.declared_tiles.add((MahjongTile('2m'), MahjongTile('2m'), MahjongTile('2m'), MahjongTile('2m')))
    # hand.kongs.add((MahjongTile('2m'), MahjongTile('2m'), MahjongTile('2m'), MahjongTile('2m')))
    # hand.kongs.add((MahjongTile('1s'), MahjongTile('1s'), MahjongTile('1s'), MahjongTile('1s')))
    # # should be Outside Hand, Two Melded Kongs + Concealed Kong + Pung of Terminals or Honors x 2 + Double Pung + No Honor
    #
    # hand = MahjongHand(parse_tiles("1111s111p111155m555z"), MahjongTile("5z"))
    # hand.kongs.add((MahjongTile('1m'), MahjongTile('1m'), MahjongTile('1m'), MahjongTile('1m')))
    # hand.kongs.add((MahjongTile('1s'), MahjongTile('1s'), MahjongTile('1s'), MahjongTile('1s')))
    # # should be Three Concealed Pungs + All Pungs + Two Concealed Kongs + Triple Pung + Pung of Terminals or Honors x 3 + Concealed Hand + Dragon Pung

    hand = MahjongHand(parse_tiles("2222s3333p555577m555z"), MahjongTile("7m"))
    hand.kongs.add((MahjongTile('5m'), MahjongTile('5m'), MahjongTile('5m'), MahjongTile('5m')))
    hand.kongs.add((MahjongTile('2s'), MahjongTile('2s'), MahjongTile('2s'), MahjongTile('2s')))
    hand.kongs.add((MahjongTile('3p'), MahjongTile('3p'), MahjongTile('3p'), MahjongTile('3p')))
    # should be Four Concealed Pungs + Three Kongs + Dragon Pung + Single Wait

    acceptance, won, yakus = get_won_hand_yakus(hand)
    print(won, acceptance)
    _print_yakus(yakus)


if __name__ == '__main__':
    _test_scorer()
