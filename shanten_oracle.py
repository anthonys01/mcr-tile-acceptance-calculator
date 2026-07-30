"""
Fast shanten + ukeire oracle (prototype).

A count-vector oracle over the 34 tile indices (see ``mahjong_core``: 0-8 = 1m-9m,
9-17 = 1p-9p, 18-26 = 1s-9s, 27-33 = honors). It computes, in well under a
millisecond, the classical *shanten* (tiles-away distance) and *ukeire* (advancing
tiles) for all five MCR-relevant winning shapes:

- standard              : 4 melds + 1 pair
- seven pairs
- thirteen orphans (kokushi)
- honors & knitted tiles: 14 distinct singles from honours + a knitted straight
- knitted straight       : the nine 147/258/369-across-suits tiles + 1 meld + 1 pair

Unlike ``tile_acceptance_calculator.analyze_hand`` it performs **no yaku
enumeration** - it answers only "how far, and what advances it". That is exactly
the primitive tree search needs at every node; the (expensive) value / >= 8 point
check is left to the existing scorer, which only has to run at genuine tenpai /
win leaves.

Shanten convention: ``-1`` complete, ``0`` tenpai, ``k`` = k tiles from tenpai.

Validation:
- standard / seven pairs / kokushi: 0 mismatches vs the independent ``mahjong``
  library (``Shanten``) over 40,000 random 13- and 14-tile hands.
- honors & knitted / knitted straight: 0 mismatches vs an independent
  max-overlap brute force (enumerating every valid complete knitted hand) over
  1,000 biased+random hands each. See ``_knitted_validate.py`` history.

Performance: ``standard_shanten`` and ``knitted_straight_shanten`` are memoized
(``lru_cache``). Warm ``shanten`` ~30 us, warm ``ukeire`` ~1.7 ms - which is what
a state-revisiting search sees. Cold ``shanten`` ~1.1 ms; a first-visit
``ukeire`` pays 34 cold probes (~80 ms), dominated by the knitted-straight
meld+pair search. If cold ukeire becomes a bottleneck, precompute per-suit
decomposition tables for the standard shape and cache the knitted meld+pair scan.

Modelling notes:
- The knitted shapes are only considered for fully concealed hands
  (``melds_declared == 0``). The scorer additionally allows a Knitted Straight
  with a single declared group; that case is not modelled here and falls back to
  the standard-shape distance.
- The exhaustive value / >= 8 point check still runs on the real scorer at
  candidate tenpai / win leaves, so any residual modelling gap only affects
  heuristic ordering, never win legality.
"""
from functools import lru_cache

from mahjong_core import NB_TILE_INDICES

INF = 99
_TERMINALS_HONORS = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
_HONORS = [27, 28, 29, 30, 31, 32, 33]

# Knitted straight: the three arithmetic value-classes {1,4,7}, {2,5,8}, {3,6,9}
# each live in a *distinct* suit. Enumerate the 6 ways to assign the three
# classes to the three suit bases (m=0, p=9, s=18); each yields the 9 knitted
# tile indices for that assignment.
_SUIT_BASES = (0, 9, 18)
_KNITTED_CLASS_OFFSETS = ((0, 3, 6), (1, 4, 7), (2, 5, 8))  # 147 / 258 / 369


def _build_knitted_assignments():
    from itertools import permutations
    assignments = []
    for bases in permutations(_SUIT_BASES):
        tiles = []
        for base, offsets in zip(bases, _KNITTED_CLASS_OFFSETS):
            tiles.extend(base + off for off in offsets)
        assignments.append(tuple(tiles))
    return tuple(assignments)


_KNITTED_ASSIGNMENTS = _build_knitted_assignments()


def counts_from_tiles(tiles) -> list[int]:
    """Build a 34-length count vector from an iterable of tiles."""
    counts = [0] * NB_TILE_INDICES
    for tile in tiles:
        counts[tile.index] += 1
    return counts


def _shanten_from(melds: int, partials: int, has_pair: bool) -> int:
    """Standard-form shanten from a block decomposition.

    At most ``4 - melds`` partial sets are useful toward the four melds; the pair
    is counted separately via ``has_pair``.
    """
    if partials > 4 - melds:
        partials = 4 - melds
    shanten = 8 - 2 * melds - partials
    if has_pair:
        shanten -= 1
    return shanten


def _decompose(counts: list[int], i: int, melds: int, partials: int,
                has_pair: bool, best: list[int]) -> None:
    """DFS enumerating meld / partial / pair extractions, updating ``best[0]``."""
    while i < NB_TILE_INDICES and counts[i] == 0:
        i += 1
    if i >= NB_TILE_INDICES:
        value = _shanten_from(melds, partials, has_pair)
        if value < best[0]:
            best[0] = value
        return

    c = counts[i]
    is_suit = i < 27
    seq_ok = is_suit and (i % 9) <= 6

    if c >= 3:
        counts[i] -= 3
        _decompose(counts, i, melds + 1, partials, has_pair, best)
        counts[i] += 3

    if seq_ok and counts[i + 1] > 0 and counts[i + 2] > 0:
        counts[i] -= 1; counts[i + 1] -= 1; counts[i + 2] -= 1
        _decompose(counts, i, melds + 1, partials, has_pair, best)
        counts[i] += 1; counts[i + 1] += 1; counts[i + 2] += 1

    if c >= 2:
        if not has_pair:
            counts[i] -= 2
            _decompose(counts, i, melds, partials, True, best)
            counts[i] += 2
        counts[i] -= 2
        _decompose(counts, i, melds, partials + 1, has_pair, best)
        counts[i] += 2

    if is_suit and (i % 9) <= 7 and counts[i + 1] > 0:
        counts[i] -= 1; counts[i + 1] -= 1
        _decompose(counts, i, melds, partials + 1, has_pair, best)
        counts[i] += 1; counts[i + 1] += 1

    if is_suit and (i % 9) <= 6 and counts[i + 2] > 0:
        counts[i] -= 1; counts[i + 2] -= 1
        _decompose(counts, i, melds, partials + 1, has_pair, best)
        counts[i] += 1; counts[i + 2] += 1

    # Leave one tile floating.
    counts[i] -= 1
    _decompose(counts, i, melds, partials, has_pair, best)
    counts[i] += 1


def standard_shanten(counts: list[int], melds_declared: int = 0) -> int:
    """Shanten toward 4 melds + 1 pair (``melds_declared`` melds already set)."""
    return _standard_shanten_cached(tuple(counts), melds_declared)


@lru_cache(maxsize=None)
def _standard_shanten_cached(counts_t: tuple, melds_declared: int) -> int:
    best = [INF]
    work = list(counts_t)
    _decompose(work, 0, melds_declared, 0, False, best)
    return best[0]


def seven_pairs_shanten(counts: list[int]) -> int:
    """Shanten toward seven distinct pairs (14-tile shape)."""
    pairs = sum(1 for c in counts if c >= 2)
    kinds = sum(1 for c in counts if c >= 1)
    shanten = 6 - pairs
    if kinds < 7:
        shanten += 7 - kinds
    return shanten


def kokushi_shanten(counts: list[int]) -> int:
    """Shanten toward thirteen orphans."""
    kinds = sum(1 for idx in _TERMINALS_HONORS if counts[idx] >= 1)
    has_pair = any(counts[idx] >= 2 for idx in _TERMINALS_HONORS)
    return 13 - kinds - (1 if has_pair else 0)


def honors_knitted_shanten(counts: list[int]) -> int:
    """Shanten toward Honors & Knitted Tiles (14 distinct singles).

    Target = up to 14 distinct tiles drawn from the 7 honours plus the 9 knitted
    tiles of a single suit-assignment (no meld, no pair). Shanten is
    ``13 - overlap`` where ``overlap`` is the number of distinct target tiles
    already held for the best assignment.
    """
    honor_distinct = sum(1 for idx in _HONORS if counts[idx] >= 1)
    best = INF
    for knit in _KNITTED_ASSIGNMENTS:
        knit_distinct = sum(1 for idx in knit if counts[idx] >= 1)
        overlap = min(14, honor_distinct + knit_distinct)
        value = 13 - overlap
        if value < best:
            best = value
    return best


def _best_meld_pair_overlap(rem: list[int]) -> int:
    """Max tiles matched by a single meld + single pair drawn from ``rem``.

    ``rem`` holds available copies after the knitted tiles have been reserved.
    Enumerates every pung / chow (meld) and pairs it with the best compatible
    pair. Pair values are precomputed once; a pung and pair on the same tile is
    disallowed (would need 5 copies in the target hand).
    """
    # Precompute pair overlap per tile, and the top-4 (value, tile) so a meld can
    # pick the best pair that does not conflict with its own tiles.
    pair_val = [c if c <= 2 else 2 for c in rem]
    ranked = sorted(range(NB_TILE_INDICES), key=lambda t: pair_val[t], reverse=True)
    top = [(pair_val[t], t) for t in ranked[:4]]

    def best_pair_excluding(excluded: set) -> int:
        for val, tile in top:
            if tile not in excluded:
                return val
        return 0

    best = 0
    for mt in range(NB_TILE_INDICES):
        # Pung meld on mt (pair must be a different tile).
        pung_use = rem[mt] if rem[mt] <= 3 else 3
        total = pung_use + best_pair_excluding({mt})
        if total > best:
            best = total

        # Chow meld anchored at mt (suits, values 1-7).
        if mt < 27 and (mt % 9) <= 6:
            chow = (mt, mt + 1, mt + 2)
            chow_use = sum(1 for x in chow if rem[x])
            # A pair reusing a chow tile has one fewer copy available.
            pair_best = best_pair_excluding(set(chow))
            for x in chow:
                avail = rem[x] - 1
                if avail > 0:
                    adj = avail if avail <= 2 else 2
                    if adj > pair_best:
                        pair_best = adj
            total = chow_use + pair_best
            if total > best:
                best = total
    return best


def knitted_straight_shanten(counts: list[int]) -> int:
    """Shanten toward a Knitted Straight (9 knitted tiles + one meld + one pair).

    For each suit-assignment the 9 knitted tiles are mandatory singles; the
    remaining five tiles must form one meld and one pair. Shanten is
    ``13 - overlap`` maximised over assignments, where ``overlap`` counts held
    knitted singles plus the best meld+pair match on the leftover copies.
    """
    best = INF
    for knit in _KNITTED_ASSIGNMENTS:
        rem = list(counts)
        knit_overlap = 0
        for idx in knit:
            if rem[idx] >= 1:
                knit_overlap += 1
                rem[idx] -= 1
        overlap = knit_overlap + _best_meld_pair_overlap(rem)
        value = 13 - overlap
        if value < best:
            best = value
    return best


def shanten(counts: list[int], melds_declared: int = 0) -> int:
    """Best (minimum) shanten across all supported winning shapes.

    Seven pairs, kokushi and the two knitted shapes only apply to fully
    concealed 13/14-tile hands, so they are skipped when melds are declared.
    (The codebase allows a Knitted Straight with a single declared group; that
    nuance is not modelled here - see module docstring.)
    """
    best = standard_shanten(counts, melds_declared)
    if melds_declared == 0:
        best = min(
            best,
            seven_pairs_shanten(counts),
            kokushi_shanten(counts),
            honors_knitted_shanten(counts),
            _knitted_straight_cached(tuple(counts)),
        )
    return best


@lru_cache(maxsize=None)
def _knitted_straight_cached(counts_t: tuple) -> int:
    return knitted_straight_shanten(list(counts_t))


def ukeire(counts: list[int], melds_declared: int = 0):
    """Tiles (as indices) that strictly reduce shanten, with their live count.

    :return: (current_shanten, {tile_index: remaining_copies})
    """
    current = shanten(counts, melds_declared)
    advancing: dict[int, int] = {}
    for idx in range(NB_TILE_INDICES):
        if counts[idx] >= 4:
            continue
        counts[idx] += 1
        if shanten(counts, melds_declared) < current:
            advancing[idx] = 4 - (counts[idx] - 1)
        counts[idx] -= 1
    return current, advancing


def hand_shanten(hand, use_declared: bool = True) -> int:
    """Convenience: shanten of a :class:`MahjongHand` from its free tiles."""
    counts = counts_from_tiles(hand.get_free_tiles())
    melds = len(hand.get_all_declared_groups()) if use_declared else 0
    return shanten(counts, melds)


def hand_ukeire(hand, use_declared: bool = True):
    """Convenience: ``ukeire`` for a :class:`MahjongHand`."""
    counts = counts_from_tiles(hand.get_free_tiles())
    melds = len(hand.get_all_declared_groups()) if use_declared else 0
    return ukeire(counts, melds)
