"""Discard ranking metrics that go beyond raw immediate acceptance.

Motivation
----------
The historical ranking (``tile_acceptance_calculator._get_best_discard_choice``)
orders discards by the *size of the immediate acceptance set*: the number of live
tiles that bring the hand one step closer to one of the **closest** MCR hand
types. That metric disagrees with Monte-Carlo rollouts on hands such as
``5m456899p2345679s`` (immediate acceptance recommends ``5m`` with 22 tiles,
rollouts and human intuition recommend ``8p`` with 19 tiles).

Four effects explain the gap:

1. **Win-mode asymmetry.** ``hand_types.basic`` scores candidate completions as
   *discard* wins (Concealed Hand, 2 pts). A rollout only ever wins by self-draw
   (Fully Concealed Hand, 4 pts). Shapes worth 6-7 points on a ron are perfectly
   legal 8+ point self-draw wins, so the analyser credits them with nothing while
   the rollout counts them fully. On the reference hand this is the dominant
   effect: keeping ``5m`` only pays off through manzu chows that are worth 6-7
   points on a ron.
2. **The 8-point cliff has no margin.** Every acceptance tile is worth 1,
   whether it leads to an exactly-8-point hand or to a 24-point hand. Hands
   sitting exactly on the legality threshold are fragile: any deviation makes
   them unwinnable.
3. **Only the closest hand types are counted.** Discarding ``8p`` keeps *Mixed
   Shifted Chows* (2 away) and *Triple Chows* (3 away) alive; discarding ``5m``
   kills them. Optionality is invisible to a union over the closest types only.
4. **Depth-1 blindness.** Acceptance measures "tiles that reach tenpai", not how
   wide or how valuable the resulting tenpai is.

Scoring
-------
For a candidate discard ``d``::

    score(d) = SUM over hand types T of
                   value_weight(T, d) * DECAY^(away_T - min_away) * ukeire(d, T)
             + TSUMO_WEIGHT * value_weight_tsumo * ukeire_self_draw_only(d)

- ``ukeire(d, T)``   live tiles credited to ``d`` for hand type ``T`` (the exact
  same acceptance semantics as the legacy ranking, so the numbers displayed to
  the user stay meaningful).
- ``value_weight``   ``min(points, VALUE_CAP) ** ALPHA`` - a *soft* preference
  for valuable routes that saturates (a legal MCR win only needs 8 points, so
  being worth 40 is not five times better than being worth 8). Addresses (2).
- ``DECAY^(away_T - min_away)``  every analysed hand type contributes, not just
  the closest ones, discounted by how far it is. Addresses (3) and, indirectly,
  (4): a discard that keeps several routes alive scores higher than one that
  funnels the hand into a single fragile shape.
- ``ukeire_self_draw_only(d)``  tiles that only reach the 8-point minimum when
  self-drawn, discounted by ``TSUMO_WEIGHT`` because they cannot be ronned.
  Addresses (1).

Two further corrections, prompted by ``13m35679s24567p55z`` (raw acceptance
recommends ``6s`` with 16 tiles, rollouts and humans recommend ``7p`` with 15):

5. **The acceptance union is counted with diminishing returns.** Summing
   ``ukeire(d, T)`` over ``T`` counts a tile once *per hand type it serves*: on
   that hand ``6s`` collected ``2m`` and ``4s`` twice (Mixed Straight *and* Mixed
   Shifted) and scored far above its real 16-tile acceptance. An accepted tile
   serving several routes *is* worth more than one serving a single route, but
   not proportionally - the routes all still need the *same* tile. Each accepted
   tile is therefore credited at its best weight, plus its other routes'
   weights geometrically damped by ``ROUTE_DECAY``.
6. **Shape flexibility.** MCR blueprints only describe the tiles they *use*, so
   whatever the blueprint does not need looks free to discard: on that hand
   ``6s`` is unused by both blueprints, yet discarding it destroys the made
   ``567s`` chow and collapses the general-purpose ukeire from 52 to 20 tiles.
   The score is therefore multiplied by a factor derived from the *yaku-agnostic*
   ukeire of the 13 tiles left behind, which measures how many ways the hand can
   still improve regardless of which MCR pattern it eventually lands on. This is
   what distinguishes ``8p`` on the first hand (38 tiles vs 33 for ``5m``) and
   ``7p`` on the second (52 tiles vs 20 for ``6s``). The raw ukeire is discounted
   by ``SHAPE_STEP`` per standard shanten, otherwise the factor would reward
   stepping *backwards*: a 2-shanten hand mechanically accepts far more tiles
   than a 1-shanten one.
"""

import os
from collections import defaultdict
from functools import lru_cache

from acceptance import (
    get_tile_acceptance_of_groups,
    get_tile_acceptance_of_knitted_groups,
)
from hand_scorer import get_total_points
from hand_types.basic import can_construct_hand
from mahjong_objects import MahjongHand, MahjongTile
from shanten_oracle import counts_from_tiles, standard_shanten

# Guaranteed base MCR point value of each structural hand type (the minimum the
# type is worth; completed hands often score more through extra yakus).
HAND_TYPE_POINTS: dict[str, int] = {
    "Mixed Straight": 8,
    "Mixed Shifted": 6,
    "Pure Straight": 16,
    "Pure Shifted": 16,
    "Triple Chows": 8,  # mixed triple chow (pure triple chow is 24)
    "All Pungs": 6,
    "Seven Pairs": 24,
    "Half Flush": 6,  # half flush (full flush is 24)
    "All Types": 6,
    "Knitted": 12,
    "First or Last n tiles": 12,  # upper/lower four (upper/lower tiles is 24)
    "Symmetry": 8,
}

_BASIC = "Basic"
_SEVEN_PAIRS = "Seven Pairs"
_KNITTED = "Knitted"

# How strongly hand value influences the score (0 = pure efficiency, 1 = linear).
ALPHA = float(os.environ.get("MCR_RANK_ALPHA", "0.5"))
# Per-extra-tile-away discount applied to a hand type's contribution (proxy for
# the probability of ever completing that type from this distance).
DECAY = float(os.environ.get("MCR_RANK_DECAY", "0.15"))
# Value saturation: a legal MCR win only needs 8 points, so extra value is capped
# before weighting.
VALUE_CAP = float(os.environ.get("MCR_RANK_VALUE_CAP", "12"))
# Credit given to acceptance tiles that only reach 8 points when self-drawn.
# Below 1 because those routes cannot be ronned, but not much below: a self-draw
# is how most concealed MCR hands actually finish.
TSUMO_WEIGHT = float(os.environ.get("MCR_RANK_TSUMO_WEIGHT", "0.8"))
# Point value attributed to a self-draw-only route (it is, by construction, below
# the 8-point ron threshold).
TSUMO_ONLY_VALUE = 8.0
# Relative margin by which the composite score must beat the score of the
# acceptance-maximising tile before the recommendation is changed. Raw acceptance
# is a well-understood, low-variance signal; the extra terms (value, optionality,
# self-draw routes) are estimates, so they only override it on a clear win. This
# keeps near-ties (symmetric waits, equivalent discards) on the legacy answer.
SCORE_MARGIN = float(os.environ.get("MCR_RANK_MARGIN", "0.15"))
# Geometric damping applied to the 2nd, 3rd, ... hand type that credits the same
# acceptance tile. 0 would de-duplicate strictly, 1 would double-count.
ROUTE_DECAY = float(os.environ.get("MCR_RANK_ROUTE_DECAY", "0.45"))
# Exponent of the shape factor (yaku-agnostic ukeire of the remaining 13 tiles).
# 0 disables the shape correction.
SHAPE_GAMMA = float(os.environ.get("MCR_RANK_SHAPE_GAMMA", "0.3"))
# Per-shanten discount applied to the raw ukeire before it is used as a shape
# factor. Raw ukeire grows with the distance to a win - a 2-shanten hand simply
# has more improving tiles than a 1-shanten one - so comparing it directly would
# reward being *further* from completing. Roughly the fraction of that width that
# survives one more step.
SHAPE_STEP = float(os.environ.get("MCR_RANK_SHAPE_STEP", "0.5"))
# Ukeire of a good 1-shanten hand: the reference the shape factor is measured
# against. Only sets the scale of the factor (a common multiplier cannot change
# the ranking), so it needs no tuning.
SHAPE_REF_UKEIRE = 40.0

_FULL_COPIES = 4


def _live_copies(hand: MahjongHand, tiles) -> int:
    """Number of unseen copies of ``tiles`` (only our own hand is visible)."""
    return sum(_FULL_COPIES - hand.hand_tiles.count(tile) for tile in tiles)


def useful_acceptance_for_tile(
    hand_type: str, combi, acceptance_pool: set, tile: MahjongTile, results
) -> set:
    """Acceptance tiles credited to discarding ``tile`` while pursuing ``combi``.

    Mirrors the special cases of
    ``tile_acceptance_calculator._build_discard_candidates`` so the ranking stays
    consistent with the acceptance numbers shown to the user.
    """
    if hand_type == _SEVEN_PAIRS:
        useful = set(acceptance_pool)
        useful.discard(tile)
        return useful
    if hand_type == _KNITTED and len(results[0][0]) == 4:
        # knitted-with-honors combos expose the whole pool
        return set(acceptance_pool)
    if hand_type == _KNITTED:
        return get_tile_acceptance_of_knitted_groups(combi).intersection(
            acceptance_pool
        )
    return get_tile_acceptance_of_groups(combi).intersection(acceptance_pool)


def _value_weight(points: float) -> float:
    return min(points, VALUE_CAP) ** ALPHA


@lru_cache(maxsize=None)
def _shape_ukeire(counts_t: tuple) -> tuple:
    """Yaku-agnostic shape of a 13-tile multiset, as ``(shanten, ukeire)``.

    ``ukeire`` is the number of live tiles that lower the *standard* shanten,
    ignoring MCR legality entirely. It measures how many ways the hand can still
    improve whatever pattern it ends up in, which is exactly the flexibility the
    MCR blueprints cannot express: a blueprint only describes the tiles it uses,
    so a complete chow it happens not to need looks free to break.
    """
    counts = list(counts_t)
    reference = standard_shanten(counts)
    total = 0
    for index in range(34):
        seen = counts[index]
        if seen >= _FULL_COPIES:
            continue
        counts[index] = seen + 1
        if standard_shanten(counts) < reference:
            total += _FULL_COPIES - seen
        counts[index] = seen
    return reference, total


def _shape_factor(hand: MahjongHand, tile: MahjongTile) -> float:
    """Shape flexibility left behind by discarding ``tile``, as a multiplier.

    The raw ukeire is discounted by ``SHAPE_STEP`` per shanten, because a hand
    further from a win mechanically accepts more tiles; without that correction
    the factor would reward stepping *backwards*. The result depends only on the
    candidate itself, so adding candidates to the pool never changes the score of
    the existing ones.
    """
    if not SHAPE_GAMMA:
        return 1.0
    counts = counts_from_tiles(hand.get_free_tiles())
    if counts[tile.index]:
        counts[tile.index] -= 1
    shanten, ukeire = _shape_ukeire(tuple(counts))
    reference = SHAPE_REF_UKEIRE * SHAPE_STEP
    score = ukeire * SHAPE_STEP**shanten
    return (score / reference) ** SHAPE_GAMMA


def _self_draw_only_acceptance(
    hand: MahjongHand,
    candidates: set,
    ron_basic_acceptance: dict,
    prevalent_wind: int,
    seat_wind: int,
) -> dict:
    """Per-candidate acceptance tiles that are legal only as a self-draw win.

    Re-runs the Basic hand-type construction with self-draw scoring (Fully
    Concealed Hand instead of Concealed Hand) and returns, for each candidate
    discard, the acceptance tiles that this widened pass credits but the regular
    ron-scored pass does not.
    """
    try:
        results, pool, _yakus = can_construct_hand(
            hand, prevalent_wind, seat_wind, self_drawn=True
        )
    except (ValueError, AttributeError):
        return {}
    if not results:
        return {}

    extra: dict[MahjongTile, set] = defaultdict(set)
    for combi, residue in results:
        for tile in set(residue):
            if tile not in candidates:
                continue
            useful = get_tile_acceptance_of_groups(combi).intersection(pool)
            extra[tile].update(useful)
    for tile, tiles in extra.items():
        tiles.difference_update(ron_basic_acceptance.get(tile, ()))
    return {tile: tiles for tile, tiles in extra.items() if tiles}


def score_discards(
    hand: MahjongHand,
    results: dict,
    acceptance: dict,
    best_results,
    basic_yakus=None,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    candidates=None,
) -> tuple[dict, dict]:
    """Composite score of every candidate discard.

    :param hand: the 14-tile hand being analysed
    :param results: ``analyze_hand`` combinations, keyed by hand type
    :param acceptance: ``analyze_hand`` acceptance pools, keyed by hand type
    :param best_results: labels of the closest hand types
    :param basic_yakus: ``analyze_hand`` Basic yakus, aligned with ``results``
    :param candidates: restrict scoring to these discard candidates; defaults to
        the residue tiles of the closest hand types (same safe pool as the legacy
        ranking, so the new metric only *re-orders* previously legal choices)
    :return: ``(scores, breakdown)`` where ``scores`` maps a tile to its float
        score and ``breakdown`` maps a tile to ``{component: contribution}``
    """
    away_by_type = {
        hand_type: len(hand_results[0][1])
        for hand_type, hand_results in results.items()
        if hand_results and hand_results[0]
    }
    if not away_by_type:
        return {}, {}
    min_away = min(away_by_type.values())

    if candidates is None:
        candidates = set()
        for hand_type in best_results:
            for _combi, residue in results[hand_type]:
                candidates.update(residue)
    candidates = set(candidates)
    if not candidates:
        return {}, {}

    # tile -> hand type -> union of credited acceptance tiles
    per_tile_acc: dict[MahjongTile, dict[str, set]] = defaultdict(
        lambda: defaultdict(set)
    )
    # tile -> best Basic point total among the combos that keep it in the residue
    per_tile_basic_points: dict[MahjongTile, int] = defaultdict(int)

    for hand_type, hand_results in results.items():
        acceptance_pool = acceptance[hand_type]
        for combo_index, (combi, residue) in enumerate(hand_results):
            basic_points = 0
            if hand_type == _BASIC and basic_yakus:
                basic_points = get_total_points(basic_yakus[combo_index][1])
            for tile in set(residue):
                if tile not in candidates:
                    continue
                useful = useful_acceptance_for_tile(
                    hand_type, combi, acceptance_pool, tile, hand_results
                )
                if not useful:
                    continue
                per_tile_acc[tile][hand_type].update(useful)
                if hand_type == _BASIC:
                    per_tile_basic_points[tile] = max(
                        per_tile_basic_points[tile], basic_points
                    )

    self_draw_only = _self_draw_only_acceptance(
        hand,
        candidates,
        {tile: accs.get(_BASIC, set()) for tile, accs in per_tile_acc.items()},
        prevalent_wind,
        seat_wind,
    )

    scores: dict[MahjongTile, float] = {}
    breakdown: dict[MahjongTile, dict[str, float]] = {}
    shape_by_tile = {tile: _shape_factor(hand, tile) for tile in candidates}

    for tile in candidates:
        # Acceptance tiles are pooled across hand types with diminishing returns:
        # a tile credited by several blueprints is worth more than one credited by
        # a single blueprint, but the routes all need the *same* tile, so the
        # extra routes are damped instead of simply summed.
        routes: dict[MahjongTile, list[tuple[float, str]]] = defaultdict(list)
        for hand_type, acc in per_tile_acc.get(tile, {}).items():
            if hand_type == _BASIC:
                points = per_tile_basic_points[tile] or 8
            else:
                points = HAND_TYPE_POINTS.get(hand_type, 8)
            weight = _value_weight(points) * DECAY ** (
                away_by_type[hand_type] - min_away
            )
            for accepted in acc:
                routes[accepted].append((weight, hand_type))

        components: dict[str, float] = defaultdict(float)
        for accepted, entries in routes.items():
            entries.sort(reverse=True)
            live = _live_copies(hand, (accepted,))
            for rank, (weight, hand_type) in enumerate(entries):
                contribution = weight * live * ROUTE_DECAY**rank
                if contribution:
                    components[hand_type] += contribution
        extra = self_draw_only.get(tile)
        if extra:
            components["Basic (self-draw only)"] = (
                TSUMO_WEIGHT
                * _value_weight(TSUMO_ONLY_VALUE)
                * _live_copies(hand, extra)
            )
        if not components:
            continue
        # Shape flexibility of the 13 tiles left behind. Invisible to the
        # blueprints, which never account for the tiles they do not use.
        shape_factor = shape_by_tile[tile]
        scores[tile] = sum(components.values()) * shape_factor
        breakdown[tile] = dict(components)
        if shape_factor != 1:
            breakdown[tile]["(shape factor)"] = round(shape_factor, 3)
    return scores, breakdown
