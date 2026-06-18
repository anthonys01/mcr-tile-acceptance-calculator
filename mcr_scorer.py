
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
        print(seq)
        print(groups)
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


def _get_hand_yakus(hand_context: HandContext):
    exclusions = set()
    valid_yakus = []
    for yaku in MahjongMCRYaku:
        if yaku in exclusions:
            continue
        if yaku.check(hand_context):
            valid_yakus.append(yaku)
            exclusions.update(yaku.get_exclusions())
    return valid_yakus


def _print_yakus(yakus: list[MahjongMCRYaku]):
    rows = [
        (yaku.name.replace("_", " ").title(), yaku.get_points())
        for yaku in yakus
    ]
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
    # normal hand types
    tenpai_hands, won_hands = _get_all_tenpai_forms(hand)
    if won_hands:
        for won_hand in won_hands:
            context = _get_context(hand, won_hand)
            yakus = _get_hand_yakus(context)
            _print_yakus(yakus)
