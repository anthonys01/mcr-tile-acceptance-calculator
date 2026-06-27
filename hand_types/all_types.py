from itertools import chain

from acceptance import get_full_tile_acceptance
from group_finder import find_sequences, find_three_of_a_kind, merge_group_tuple
from mahjong_objects import MahjongHand, Family, Constraint, get_tiles_from_family
from tiles_utils import FAMILY_TILES, WINDS_TILES, DRAGONS_TILES


def can_construct_all_types(hand: MahjongHand):
    """Try to construct all types

    Only return result hands when all types is technically possible (at most one declared group per type)
    :param hand: Mahjong hand
    """
    concatenated_results = []
    have_family = [False] * 5
    declared_groups = hand.get_all_declared_groups()
    tile_check = [
        lambda t: t.family == Family.CIRCLE,
        lambda t: t.family == Family.CHARACTER,
        lambda t: t.family == Family.BAMBOO,
        lambda t: t.is_wind(),
        lambda t: t.is_dragon(),
    ]

    groups = []
    useless_tiles = set()
    for family_index in range(5):
        for group in declared_groups:
            if tile_check[family_index](group[0]):
                if have_family[family_index]:
                    # too many groups for all types
                    return [], set()
                compatible_group = group
                have_family[family_index] = True
                useless_tiles.update([tile for tile in hand.get_free_tiles() if tile_check[family_index](tile)])
                groups.append(compatible_group)

    if groups:
        concatenated_results = [(tuple(groups), list(useless_tiles))]

    for family_index, family in enumerate([Family.CIRCLE, Family.CHARACTER, Family.BAMBOO]):
        if have_family[family_index]:
            continue
        concatenated_results = _find_groups_and_concatenate(
            get_tiles_from_family(hand.get_free_tiles(), family),
            concatenated_results,
            FAMILY_TILES[family],
        )

    tiles = get_tiles_from_family(hand.get_free_tiles(), Family.HONOR)
    if not have_family[3]:
        concatenated_results = _find_groups_and_concatenate(
            [tile for tile in tiles if tile.is_wind()],
            concatenated_results,
            WINDS_TILES,
        )
    if not have_family[4]:
        concatenated_results = _find_groups_and_concatenate(
            [tile for tile in tiles if tile.is_dragon()],
            concatenated_results,
            DRAGONS_TILES,
        )

    return concatenated_results, get_full_tile_acceptance(hand.hand_tiles, concatenated_results)


def _find_groups_and_concatenate(
        tiles, concatenated_results, all_valid_tiles
):
    good_groups = []
    if not tiles:
        good_groups = [(((),), tiles)]
    else:
        smallest_residue_length = 13
        for group, residue, _ in chain(
                find_sequences(tiles, [Constraint.NONE]),
                find_three_of_a_kind(tiles, [Constraint.NONE]),
        ):
            residue_length = len(residue)
            if residue_length > smallest_residue_length:
                continue
            if residue_length < smallest_residue_length:
                smallest_residue_length = len(residue)
                good_groups.clear()
            good_groups.append(((group,), residue))
    if not concatenated_results:
        return good_groups

    new_concatenated_results = []
    for found_groups, found_residue in good_groups:
        new_group = found_groups[0]
        for groups, residue in concatenated_results:
            new_concatenated_results.append(
                (merge_group_tuple(groups, new_group), residue + found_residue)
            )
    return new_concatenated_results

