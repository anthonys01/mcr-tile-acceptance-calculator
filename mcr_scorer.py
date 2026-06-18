
from group_finder import all_groups_for
from mahjong_objects import MahjongHand, MahjongCombination, MahjongTile, HandContext, MahjongGroups, EAST, \
    MahjongMCRYaku
from tiles_utils import parse_tiles


def _get_all_tenpai_forms(hand: MahjongHand) -> tuple[list[MahjongGroups], list[MahjongGroups]]:
    hand_size = len(hand.hand_tiles)
    tenpai_hands = []
    won_hands = []
    for seq in range(5):
        groups: list[MahjongCombination] = all_groups_for(hand.hand_tiles, seq, 4 - seq, 1)
        for g, residue in groups:
            if hand_size == 14:
                if len(residue) == 0:
                    won_hands.append(g)
                elif len(residue) == 1:
                    tenpai_hands.append(g)
            elif len(residue) == 0:
                tenpai_hands.append(g)
    return tenpai_hands, won_hands


def _get_context(hand, won_hand):
    groups = []
    pair = None
    chows = []
    pungs = []
    kongs = []
    open_chows = []
    open_pungs = []
    open_kongs = []
    families = set()
    for group in won_hand:
        group_length = len(group)
        if group_length == 4:
            kongs.append(group)
            if group in hand.declared_tiles:
                open_kongs.append(group)
        elif group_length == 2:
            pair = group
        else:
            groups.append(group)
            if group[0] == group[1]:
                pungs.append(group)
                if group in hand.declared_tiles:
                    open_pungs.append(group)
            else:
                chows.append(group)
                if group in hand.declared_tiles:
                    open_chows.append(group)
        families.add(group[0].family)

    return HandContext(hand.hand_tiles,
                       tuple(groups), pair, chows, pungs, kongs, open_chows, open_pungs, open_kongs,
                       families, False, hand.drawn_tile, EAST.number, EAST.number, False)


def _get_hand_yakus(hand_context: HandContext) -> list[tuple[MahjongMCRYaku, int]]:
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


if __name__ == '__main__':
    hand = MahjongHand(parse_tiles("123456789p22333m"), MahjongTile("8p"))
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            # should be Pure Straight, Concealed Hand, No Honor, Closed Wait
            _print_yakus(yakus)


    hand = MahjongHand(parse_tiles("123789p123m789s77z"), MahjongTile("7p"))
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            # should be Outside Hand, Concealed Hand, Mixed Double Chow x 2, Two Terminal Chows, Edge Wait
            _print_yakus(yakus)

    hand = MahjongHand(parse_tiles("11133p999s111777z"), MahjongTile("3p"))
    hand.declared_tiles.add((MahjongTile('1p'), MahjongTile('1p'), MahjongTile('1p')))
    hand.declared_tiles.add((MahjongTile('9s'), MahjongTile('9s'), MahjongTile('9s')))
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            # should be All Pungs, Dragon Pung, Prevalent Wind, Seat Wind, Two Concealed Pungs, Pung Of Terminal Or Honors x2, One Voided Suit, Single Wait
            _print_yakus(yakus)

    hand = MahjongHand(parse_tiles("11133p111999s777z"), MahjongTile("3p"))
    hand.declared_tiles.add((MahjongTile('1p'), MahjongTile('1p'), MahjongTile('1p')))
    hand.declared_tiles.add((MahjongTile('9s'), MahjongTile('9s'), MahjongTile('9s')))
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            # should be All Pungs, Dragon Pung, Double Pungs, Two Concealed Pungs, Pung Of Terminal Or Honors x 3, One voided Suit, Single Wait
            _print_yakus(yakus)

    hand = MahjongHand(parse_tiles("222234444p23455s"), MahjongTile("2s"))
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            # should be Concealed Hand, Tile Hog x 2, Two Concealed Pungs, All Simple, Mixed Double Chow, One Voided Suit
            _print_yakus(yakus)
