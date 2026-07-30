"""
Discard policies (Phase 2).

`get_value_weighted_discard` upgrades the greedy immediate-acceptance policy
(`tile_acceptance_calculator.get_tile_to_discard_from`) into a **value-weighted,
multi-hand-type** acceptance score, while still needing only a single
`analyze_hand` call per decision (same cost class as the baseline).

For every candidate discard `d` (a residue tile of some analysed hand type) the
score is::

    score(d) = sum over hand types T of
                 value(T)^ALPHA * DECAY^(away_T - min_away) * ukeire(d, T)

- ``value(T)``   achievable MCR points of the hand type (BASIC uses the actual
                 computed yaku total; structural types use their guaranteed base).
- ``away_T``     structural shanten of T; the ``DECAY`` term keeps close types
                 dominant while still crediting slightly-further, high-value types
                 (a cheap look-ahead that avoids over-committing to a fast but
                 low-value shape).
- ``ukeire(d,T)`` number of live tiles (accounting for copies already held) that
                 advance T after discarding ``d``.

Unlike the baseline, all analysed hand types contribute (not just the closest
ones), and the contribution is weighted by hand value -> the policy is value
aware, which matters because MCR requires a >= 8 point hand.
"""
import os
from collections import defaultdict
from functools import lru_cache

from acceptance import get_tile_acceptance_of_groups
from hand_scorer import get_total_points
from mahjong_hand import MahjongHand
from mahjong_objects import Family, MahjongTile
from tile_acceptance_calculator import (
    HandType,
    analyze_hand,
    evaluate_hand_fast,
    get_simple_acceptance,
    _get_acceptance_tile_number,
    _get_most_useless_tile_from,
)

# Guaranteed base MCR point value of each structural hand type (the minimum the
# type is worth; completed hands often score more via extra yakus).
HAND_TYPE_POINTS: dict[str, int] = {
    HandType.MIXED_STRAIGHT.value: 8,
    HandType.MIXED_SHIFTED.value: 6,
    HandType.PURE_STRAIGHT.value: 16,
    HandType.PURE_SHIFTED.value: 16,
    HandType.TRIPLE_CHOWS.value: 8,   # mixed triple chow (pure triple chow is 24)
    HandType.ALL_PUNGS.value: 6,
    HandType.SEVEN_PAIRS.value: 24,
    HandType.HALF_FLUSH.value: 6,     # half flush (full flush is 24)
    HandType.ALL_TYPES.value: 6,
    HandType.KNITTED.value: 12,
    HandType.FIRST_OR_LAST_N_TILES.value: 12,  # upper/lower four (tiles is 24)
    HandType.SYMMETRY.value: 8,
}

# How strongly hand value influences the score (0 = pure efficiency, 1 = linear).
ALPHA = float(os.environ.get("MCR_ALPHA", "0.5"))
# Per-extra-tile-away discount applied to a hand type's contribution (proxy for
# completion probability from that distance).
DECAY = float(os.environ.get("MCR_DECAY", "0.3"))
# Value saturation: aiming above ~CAP points rarely improves EV because a legal
# MCR win only needs 8 points, so extra value is capped before weighting.
VALUE_CAP = float(os.environ.get("MCR_VALUE_CAP", "10"))


def _useful_acceptance_for_tile(
    hand_type: str, combi, acceptance_pool: set, tile: MahjongTile
) -> set:
    """Acceptance tiles credited to discarding ``tile`` while pursuing ``combi``.

    Mirrors the special cases of ``_get_best_discard_choice`` so the value-weighted
    policy stays consistent with the existing acceptance semantics.
    """
    if hand_type == HandType.SEVEN_PAIRS.value:
        useful = set(acceptance_pool)
        useful.discard(tile)
        return useful
    if hand_type == HandType.KNITTED.value:
        # Knitted-with-honors combos expose the whole pool; length-4 group set.
        return set(acceptance_pool)
    return get_tile_acceptance_of_groups(combi).intersection(acceptance_pool)


def get_value_weighted_discard(
    hand: MahjongHand, prevalent_wind: int = 0, seat_wind: int = 0
) -> MahjongTile:
    """Choose a discard maximising the value-weighted multi-type acceptance score."""
    results, acceptance, best_results, _away, basic_yakus = analyze_hand(
        hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )

    away_by_type: dict[str, int] = {}
    for hand_type, hand_results in results.items():
        if hand_results and hand_results[0]:
            away_by_type[hand_type] = len(hand_results[0][1])
    if not away_by_type:
        raise ValueError("No hand type to evaluate for discard")
    min_away = min(away_by_type.values())

    # Safe candidate discards: only tiles that sit in the residue of one of the
    # closest hand types. This mirrors the greedy policy and guarantees we never
    # discard a tile that is a productive (in-group) tile of the most developed
    # shape. Value re-ranking then happens *within* this safe pool.
    safe_candidates: set[MahjongTile] = set()
    for hand_type in best_results:
        for _combi, residue in results[hand_type]:
            safe_candidates.update(residue)

    # d -> {hand_type -> union of useful acceptance tiles}
    per_tile_type_acc: dict[MahjongTile, dict[str, set]] = defaultdict(
        lambda: defaultdict(set)
    )
    per_tile_types: dict[MahjongTile, set] = defaultdict(set)
    # d -> best achieved BASIC point value among combos that keep d as residue
    per_tile_basic_value: dict[MahjongTile, int] = defaultdict(int)

    for hand_type, hand_results in results.items():
        acceptance_pool = acceptance[hand_type]
        for combo_index, (combi, residue) in enumerate(hand_results):
            basic_value = 0
            if hand_type == HandType.BASIC.value and basic_yakus:
                basic_value = get_total_points(basic_yakus[combo_index][1])
            for tile in set(residue):
                if tile not in safe_candidates:
                    continue
                useful = _useful_acceptance_for_tile(
                    hand_type, combi, acceptance_pool, tile
                )
                if not useful:
                    continue
                per_tile_type_acc[tile][hand_type].update(useful)
                per_tile_types[tile].add(hand_type)
                if hand_type == HandType.BASIC.value:
                    per_tile_basic_value[tile] = max(
                        per_tile_basic_value[tile], basic_value
                    )

    if not per_tile_type_acc:
        raise ValueError("No tile to discard")

    scores: dict[MahjongTile, float] = {}
    for tile, type_accs in per_tile_type_acc.items():
        score = 0.0
        for hand_type, acc in type_accs.items():
            if hand_type == HandType.BASIC.value:
                value = per_tile_basic_value[tile] or 8
            else:
                value = HAND_TYPE_POINTS.get(hand_type, 8)
            value = min(value, VALUE_CAP)
            proximity = DECAY ** (away_by_type[hand_type] - min_away)
            score += (value ** ALPHA) * proximity * _get_acceptance_tile_number(
                hand, acc
            )
        scores[tile] = score

    best_score = max(scores.values())
    best_tiles = [tile for tile, score in scores.items() if score == best_score]
    return _get_most_useless_tile_from(best_tiles, per_tile_types)


# ---------------------------------------------------------------------------
# Phase 3: depth-1 expectimax (one-ply draw look-ahead)
# ---------------------------------------------------------------------------
# Unlike the static Phase-2 heuristic, this policy actually *re-evaluates* the
# hands that result from each candidate discard followed by each plausible draw.
# That second-order information (a draw opening new hand types, or reducing
# shanten across several types at once, or completing a legal win) is exactly
# what immediate acceptance cannot see.
#
# Because ``analyze_hand`` is expensive we prune hard: only the top ``K``
# candidate discards (by immediate acceptance) and, per discard, only the top
# ``BRANCHES`` most-available useful draws are expanded. Everything else is
# folded into a single "blank draw" outcome (hand unchanged, one turn spent).

# Reward added to a leaf that is already a legal (>= 8 pt) win, on top of points,
# so completing dominates mere progress.
WIN_BONUS = float(os.environ.get("MCR_WIN_BONUS", "100"))
# Distance discount for the (non-winning) leaf heuristic value.
LEAF_DECAY = float(os.environ.get("MCR_LEAF_DECAY", "0.5"))
# Search width.
EXPECTIMAX_K = int(os.environ.get("MCR_EXPECTIMAX_K", "2"))
EXPECTIMAX_BRANCHES = int(os.environ.get("MCR_EXPECTIMAX_BRANCHES", "4"))

_FULL_COPIES = 4


def _remaining_copies(hand: MahjongHand, tile: MahjongTile) -> int:
    """How many copies of ``tile`` are still unseen (single-player: only our hand
    is visible)."""
    return max(0, _FULL_COPIES - hand.hand_tiles.count(tile))


def _legal_win_points(hand: MahjongHand) -> int | None:
    """Points if ``hand`` (14 tiles) is a legal MCR win (>= 8), else ``None``."""
    from mcr_scorer import get_won_hand_yakus

    if not hand.needs_to_discard():
        return None
    try:
        _acc, _groups, yakus = get_won_hand_yakus(hand, self_drawn=True)
    except (ValueError, AttributeError):
        return None
    if not yakus:
        return None
    points = get_total_points(yakus)
    return points if points >= 8 else None


def _achievable_value(best_results) -> float:
    """Best guaranteed point value among the closest structural hand types."""
    values = [HAND_TYPE_POINTS.get(t, 8) for t in best_results]
    return min(max(values, default=8), VALUE_CAP)


def _leaf_value(hand: MahjongHand, prevalent_wind: int, seat_wind: int) -> float:
    """Value-aware heuristic value of a leaf hand (13 or 14 tiles).

    A completed legal hand is worth ``WIN_BONUS + points``. Otherwise the value is
    the achievable hand value discounted by structural distance, computed on the
    *actual* post-draw hand via the fast (BASIC-free) evaluator.
    """
    win_points = _legal_win_points(hand)
    if win_points is not None:
        return WIN_BONUS + win_points
    away, best_results, _acc = evaluate_hand_fast(
        hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )
    value = _achievable_value(best_results)
    return value * (LEAF_DECAY ** away)


def _candidate_acceptance(hand: MahjongHand, prevalent_wind: int, seat_wind: int):
    """Return (candidates, per_tile_types) where ``candidates`` maps each safe
    discard tile to the set of useful draws credited to it (as in the greedy
    policy), restricted to the closest hand types."""
    results, acceptance, best_results, _away, _basic = analyze_hand(
        hand, prevalent_wind=prevalent_wind, seat_wind=seat_wind
    )
    candidate_acc: dict[MahjongTile, set] = defaultdict(set)
    per_tile_types: dict[MahjongTile, set] = defaultdict(set)
    for hand_type in best_results:
        acceptance_pool = acceptance[hand_type]
        for combi, residue in results[hand_type]:
            for tile in set(residue):
                useful = _useful_acceptance_for_tile(
                    hand_type, combi, acceptance_pool, tile
                )
                candidate_acc[tile].update(useful)
                per_tile_types[tile].add(hand_type)
    return candidate_acc, per_tile_types


def get_expectimax_discard(
    hand: MahjongHand,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    k: int = EXPECTIMAX_K,
    branches: int = EXPECTIMAX_BRANCHES,
) -> MahjongTile:
    """Choose a discard by one-ply expectimax over the next draw.

    For each of the top ``k`` candidate discards, expand the ``branches`` most
    available useful draws, evaluate each resulting hand with :func:`_leaf_value`,
    and pick the discard maximising the probability-weighted leaf value.
    """
    candidate_acc, per_tile_types = _candidate_acceptance(
        hand, prevalent_wind, seat_wind
    )
    if not candidate_acc:
        raise ValueError("No tile to discard")

    # Prune candidate discards to the top-k by immediate acceptance count.
    ranked = sorted(
        candidate_acc.items(),
        key=lambda item: _get_acceptance_tile_number(hand, item[1]),
        reverse=True,
    )
    candidates = [tile for tile, _acc in ranked[:k]]

    unseen_total = sum(
        _remaining_copies(hand, MahjongTile(number=n, family=fam))
        for fam in Family
        for n in (range(1, 8) if fam == Family.HONOR else range(1, 10))
    )
    if unseen_total <= 0:
        return _get_most_useless_tile_from(candidates, per_tile_types)

    best_tile = None
    best_ev = float("-inf")
    for discard in candidates:
        hand13 = hand.clone()
        hand13.discard(discard)

        draws = sorted(
            candidate_acc[discard],
            key=lambda t: _remaining_copies(hand, t),
            reverse=True,
        )[:branches]

        ev = 0.0
        covered_p = 0.0
        for draw_tile in draws:
            copies = _remaining_copies(hand, draw_tile)
            if copies <= 0:
                continue
            p = copies / unseen_total
            leaf = hand13.clone()
            leaf.draw(draw_tile)
            ev += p * _leaf_value(leaf, prevalent_wind, seat_wind)
            covered_p += p

        # Blank draw: nothing useful drawn, hand effectively unchanged.
        blank_value = _leaf_value(hand13, prevalent_wind, seat_wind)
        ev += (1.0 - covered_p) * blank_value

        if ev > best_ev:
            best_ev = ev
            best_tile = discard

    return best_tile


# ---------------------------------------------------------------------------
# Phase 4 (prototype): oracle-guided Monte-Carlo rollouts
# ---------------------------------------------------------------------------
# The user's original proposal: simulate many draw orders after each candidate
# discard and keep the discard that reaches a *legal* win (>= 8 pts) fastest on
# average. This became feasible only with the fast ``shanten_oracle`` - a full
# ``analyze_hand`` per rollout step would cost minutes per decision.
#
# Design:
# - Candidate discards are the value-aware "safe candidates" of the closest hand
#   types (one ``analyze_hand`` call), i.e. exactly the set greedy chooses among.
#   The rollouts decide *which* of them is best. This is a controlled A/B: same
#   candidates, greedy ranks by immediate acceptance, this ranks by simulated
#   time-to-legal-win.
# - Each rollout plays out with a cheap *shape-value-weighted* oracle policy
#   (below) entirely in count-vector space; the expensive real scorer is called
#   only when the oracle reports a structurally complete hand, to confirm >= 8.
# - Reward is ``GAMMA ** turns_to_win`` (0 if no legal win within the budget), so
#   faster legal wins score higher.

from random import Random  # noqa: E402

from shanten_oracle import (  # noqa: E402
    counts_from_tiles,
    standard_shanten,
    seven_pairs_shanten,
    kokushi_shanten,
    honors_knitted_shanten,
)

ROLLOUTS = int(os.environ.get("MCR_ROLLOUTS", "24"))
ROLLOUT_BUDGET = int(os.environ.get("MCR_ROLLOUT_BUDGET", "14"))
ROLLOUT_K = int(os.environ.get("MCR_ROLLOUT_K", "3"))
ROLLOUT_GAMMA = float(os.environ.get("MCR_ROLLOUT_GAMMA", "0.85"))


def _build_index_to_tile():
    from mahjong_objects import Family, MahjongTile

    families = (
        (Family.CHARACTER, 0),
        (Family.CIRCLE, 9),
        (Family.BAMBOO, 18),
    )
    table: list = [None] * 34
    for family, base in families:
        for number in range(1, 10):
            table[base + number - 1] = MahjongTile(number=number, family=family)
    for number in range(1, 8):
        table[27 + number - 1] = MahjongTile(number=number, family=Family.HONOR)
    return table


_INDEX_TO_TILE = _build_index_to_tile()


def _playout_discard(counts14: list[int]) -> int:
    """Cheap, shanten-free in-rollout discard heuristic.

    Keeps pairs/triplets and sequence-connected suit tiles; discards the least
    connected tile (lone honours first, then isolated terminals). This is a
    deliberately light efficiency policy - the expensive per-candidate shanten
    evaluation dominated rollout cost, and the terminal >= 8 filter is what
    actually enforces value, not the playout.
    """
    worst_idx = -1
    worst_score = float("inf")
    for idx in range(34):
        c = counts14[idx]
        if c == 0:
            continue
        if c >= 2:
            score = 10.0 + c  # pairs / triplets are valuable, keep them
        elif idx >= 27:
            score = 0.0  # lone honour: discard first
        else:
            v = idx % 9
            conn = 0.0
            if v >= 1 and counts14[idx - 1]:
                conn += 1.0
            if v <= 7 and counts14[idx + 1]:
                conn += 1.0
            if v >= 2 and counts14[idx - 2]:
                conn += 0.5
            if v <= 6 and counts14[idx + 2]:
                conn += 0.5
            score = 1.0 + conn * 2.0
        if score < worst_score:
            worst_score = score
            worst_idx = idx
    return worst_idx


@lru_cache(maxsize=None)
def _legal_points_cached(counts_t: tuple, drawn: int) -> int:
    """Cached MCR points of a complete 14-tile hand (or -1 if not a legal >= 8 win).

    Keyed by the count vector and the drawn tile so repeated completions across
    rollouts pay the expensive scorer only once.
    """
    from mahjong_objects import MahjongHand

    tiles = []
    for idx, copies in enumerate(counts_t):
        take = copies - 1 if idx == drawn else copies
        if take:
            tiles.extend([_INDEX_TO_TILE[idx]] * take)
    hand = MahjongHand(tiles)
    hand.draw(_INDEX_TO_TILE[drawn])
    try:
        points = _legal_win_points(hand)
    except AttributeError:
        return -1
    return points if points is not None else -1


def _weighted_draw(rem: list[int], rng: Random, unseen: int) -> int:
    """Sample an unseen tile index proportional to remaining copies."""
    target = rng.random() * unseen
    cumulative = 0
    for idx in range(34):
        cumulative += rem[idx]
        if cumulative > target:
            return idx
    return 33


def _terminally_complete(counts: list[int]) -> bool:
    """Cheap structural-completion test used inside rollouts.

    Uses the four inexpensive shapes; the knitted straight is omitted because its
    shanten is comparatively costly and the value-blind playout essentially never
    assembles one, so including it only slows every simulated turn.
    """
    return (
        standard_shanten(counts) == -1
        or seven_pairs_shanten(counts) == -1
        or kokushi_shanten(counts) == -1
        or honors_knitted_shanten(counts) == -1
    )


def _rollout(
    counts13: list[int],
    rem: list[int],
    rng: Random,
    budget: int,
) -> tuple[int, int]:
    """Play out draws until a legal win or the budget expires.

    :return: ``(turns_to_win, points)`` for the first legal >= 8 win, or
             ``(0, 0)`` if none is reached within the budget.
    """
    counts = list(counts13)
    rem = list(rem)
    unseen = sum(rem)
    for turn in range(1, budget + 1):
        if unseen <= 0:
            break
        drawn = _weighted_draw(rem, rng, unseen)
        counts[drawn] += 1
        rem[drawn] -= 1
        unseen -= 1
        if _terminally_complete(counts):
            points = _legal_points_cached(tuple(counts), drawn)
            if points >= 0:
                return turn, points
        discard = _playout_discard(counts)
        counts[discard] -= 1
    return 0, 0


def get_oracle_rollout_discard(
    hand: MahjongHand,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    rollouts: int = ROLLOUTS,
    budget: int = ROLLOUT_BUDGET,
    k: int = ROLLOUT_K,
) -> MahjongTile:
    """Choose the discard whose rollouts reach a legal win fastest on average."""
    candidate_acc, per_tile_types = _candidate_acceptance(
        hand, prevalent_wind, seat_wind
    )
    if not candidate_acc:
        raise ValueError("No tile to discard")

    ranked = sorted(
        candidate_acc.items(),
        key=lambda item: _get_acceptance_tile_number(hand, item[1]),
        reverse=True,
    )
    candidates = [tile for tile, _acc in ranked[:k]]
    if len(candidates) == 1:
        return candidates[0]

    counts14 = counts_from_tiles(hand.get_free_tiles())
    rem = [4 - counts14[idx] for idx in range(34)]
    # Deterministic per-hand seed so runs are reproducible.
    base_seed = hash(tuple(counts14)) & 0xFFFFFFFF

    best_tile = None
    best_reward = float("-inf")
    for candidate in candidates:
        counts13 = list(counts14)
        counts13[candidate.index] -= 1
        total = 0.0
        for r in range(rollouts):
            rng = Random(base_seed ^ (candidate.index << 8) ^ r)
            turns, points = _rollout(counts13, rem, rng, budget)
            if turns:
                # Reward faster, higher-value legal wins.
                total += points * (ROLLOUT_GAMMA ** turns)
        avg = total / rollouts
        if avg > best_reward:
            best_reward = avg
            best_tile = candidate

    if best_reward <= 0:
        # No candidate reached a legal win in any rollout: fall back to greedy pick.
        return candidates[0]
    return best_tile
