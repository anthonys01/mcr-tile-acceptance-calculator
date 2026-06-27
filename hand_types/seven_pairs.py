from group_finder import all_groups_for
from mahjong_objects import MahjongHand, MahjongCombination, MahjongTile


def can_construct_seven_pairs(
        hand: MahjongHand,
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    """Try to construct seven pairs

    Only return result hands when seven pairs is technically possible (closed hand, no concealed kong)
    :param hand: Mahjong hand
    """
    if not hand.is_closed_hand() or hand.kongs:
        return [], set()
    acceptance = set()
    all_groups = all_groups_for(hand.hand_tiles, 0, 0, 7)
    if all_groups:
        groups, residue = all_groups[0]
        acceptance.update(residue)
        for group in groups:
            if len(group) == 1:
                acceptance.add(group[0])
    return all_groups, acceptance

