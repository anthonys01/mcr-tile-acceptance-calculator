from acceptance import get_full_tile_acceptance
from group_finder import all_groups_for_with_constraints
from mahjong_objects import Constraint, MahjongCombination, Family, MahjongHand, MahjongTile
from tiles_utils import FAMILY_TILES, HONOR_TILES, FIRST_FOUR_TILES, LAST_FOUR_TILES, SYMMETRIC_TILES


def precompute_constraints(hand):
    constraints = [
        Constraint.FLUSH_CHARACTER,
        Constraint.FLUSH_CIRCLE,
        Constraint.FLUSH_BAMBOO,
        Constraint.FIRST_FOUR,
        Constraint.LAST_FOUR,
        Constraint.SYMMETRIC,
    ]
    best_combinations: dict[Constraint, list[MahjongCombination]] = {
        constraint: [] for constraint in constraints
    }
    declared_groups = hand.get_all_declared_groups()
    free_groups = 4 - len(declared_groups)
    incompatible_constraints = set()
    for group in declared_groups:
        if any(tile.number > 4 for tile in group):
            incompatible_constraints.add(Constraint.FIRST_FOUR)
        if any(tile.number < 6 for tile in group):
            incompatible_constraints.add(Constraint.LAST_FOUR)
        if any(not tile.is_symmetric() for tile in group):
            incompatible_constraints.add(Constraint.SYMMETRIC)
        if any(not tile.is_compatible_with_half_flush(Family.BAMBOO) for tile in group):
            incompatible_constraints.add(Constraint.FLUSH_BAMBOO)
        if any(not tile.is_compatible_with_half_flush(Family.CIRCLE) for tile in group):
            incompatible_constraints.add(Constraint.FLUSH_CIRCLE)
        if any(
                not tile.is_compatible_with_half_flush(Family.CHARACTER) for tile in group
        ):
            incompatible_constraints.add(Constraint.FLUSH_CHARACTER)
    constraints = [c for c in constraints if c not in incompatible_constraints]
    if constraints:
        for nb_seq in range(free_groups + 1):
            for constraint, combinations in all_groups_for_with_constraints(
                    hand.get_free_tiles(), nb_seq, free_groups - nb_seq, 1, constraints
            ).items():
                extended_combinations = []
                for combination in combinations:
                    extended_combinations.append(
                        (
                            tuple(list(combination[0]) + list(declared_groups)),
                            combination[1],
                        )
                    )
                best_combinations[constraint] += extended_combinations
    return dict(best_combinations)


def can_construct_half_flush_from_precomputed(
        hand: MahjongHand, precomputed: dict[Constraint, list[MahjongCombination]]
):
    best_groups = _get_best_groups_from_multiple_constraints(
        [Constraint.FLUSH_CHARACTER, Constraint.FLUSH_CIRCLE, Constraint.FLUSH_BAMBOO],
        precomputed,
    )

    if not best_groups:
        return [], []

    family = _find_example_tile(best_groups[0]).family
    return best_groups, get_full_tile_acceptance(
        hand.hand_tiles, best_groups, allowed_tiles=FAMILY_TILES[family] + HONOR_TILES
    )


def _get_best_groups_from_multiple_constraints(constraints, precomputed):
    best_combinations = {
        constraint: precomputed[constraint] for constraint in constraints
    }

    best_groups = []
    best_shanten = 14
    for _, combinations in best_combinations.items():
        if not combinations:
            continue
        real_shanten = min(len(residue) for _, residue in combinations)
        if real_shanten > best_shanten:
            continue
        if real_shanten < best_shanten:
            best_groups.clear()
            best_shanten = real_shanten
        best_groups += [
            (groups, residue)
            for groups, residue in combinations
            if len(residue) == best_shanten
        ]
    return best_groups


def _find_example_tile(combination: MahjongCombination) -> MahjongTile:
    groups, _ = combination
    for group in groups:
        if group:
            return group[0]
    raise ValueError("All groups are empty")


def _get_first_last_tile_acceptance(hand, best_groups):
    if _find_example_tile(best_groups[0]) in FIRST_FOUR_TILES:
        return get_full_tile_acceptance(
            hand.hand_tiles, best_groups, allowed_tiles=FIRST_FOUR_TILES
        )
    if _find_example_tile(best_groups[0]) in LAST_FOUR_TILES:
        return get_full_tile_acceptance(
            hand.hand_tiles, best_groups, allowed_tiles=LAST_FOUR_TILES
        )
    return set()


def can_construct_first_last_hand_from_precomputed(
        hand: MahjongHand, precomputed: dict[Constraint, list[MahjongCombination]]
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    best_groups = _get_best_groups_from_multiple_constraints(
        [Constraint.FIRST_FOUR, Constraint.LAST_FOUR], precomputed
    )

    if not best_groups:
        return [], set()

    return best_groups, _get_first_last_tile_acceptance(hand, best_groups)


def can_construct_symmetry_from_precomputed(
        hand: MahjongHand, precomputed: dict[Constraint, list[MahjongCombination]]
) -> tuple[list[MahjongCombination], set[MahjongTile]]:
    best_groups = _get_best_groups_from_multiple_constraints(
        [Constraint.SYMMETRIC], precomputed
    )

    if not best_groups:
        return [], set()

    return best_groups, get_full_tile_acceptance(
        hand.hand_tiles, best_groups, allowed_tiles=SYMMETRIC_TILES
    )

