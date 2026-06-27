from group_finder import all_groups_for
from mahjong_objects import MahjongHand


def can_construct_all_pungs(hand: MahjongHand):
    """Try to construct all pungs

    Only return result hands when all pungs is technically possible (no chow declared)
    :param hand: Mahjong hand
    """
    if not hand.is_closed_hand():
        for meld in hand.declared_tiles:
            if len(set(meld)) != 1:
                return [], set()
    acceptance = set()
    declared_groups = hand.get_all_declared_groups()
    all_groups = all_groups_for(hand.get_free_tiles(), 0, 4 - len(declared_groups), 1)
    if all_groups:
        groups, residue = all_groups[0]
        has_lone_group = False
        for group in groups:
            if len(group) == 3:
                continue
            if len(group) == 2:
                acceptance.add(group[0])
            elif len(group) == 1:
                has_lone_group = True
                acceptance.add(group[0])
        if has_lone_group:
            acceptance.update(residue)
    extended_all_groups = []
    for groups, residue in all_groups:
        extended_all_groups.append(
            (tuple(list(groups) + list(declared_groups)), residue)
        )
    return extended_all_groups, acceptance
