
from group_finder import all_groups_for
from mahjong_objects import MahjongHand, MahjongCombination, MahjongTile
from tiles_utils import parse_tiles


def get_all_tenpai_forms(hand: MahjongHand):
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


if __name__ == '__main__':
    hand = MahjongHand(parse_tiles("123456789p22333m"), MahjongTile("8p"))
    tenpai_hands, won_hands = get_all_tenpai_forms(hand)
    if won_hands:
        ...
