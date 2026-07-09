from collections import Counter
from enum import Enum
from itertools import combinations, permutations

from mahjong_core import MahjongGroup, Family
from mahjong_context import (
    HandContext,
    concealed_pungs,
    concealed_kongs,
    chow_starts_for_family,
    pung_numbers_for_family,
    has_free_chow,
    has_free_pung,
    take_free_chow,
    take_free_pung,
    has_free_pung_single,
    take_free_pung_single,
)

# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _check_big_four_winds(h: HandContext) -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 4


def _check_big_three_dragons(h: HandContext) -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) == 3


def _check_all_green(h: HandContext) -> bool:
    return all(t.is_green() for t in h.all_tiles)


def _check_nine_gates(h: HandContext) -> bool:
    return len(h.acceptance) == 9


def _check_four_kongs(h: HandContext) -> bool:
    return len(h.kongs) == 4


def _check_all_terminals(h: HandContext) -> bool:
    return all(t.is_terminal() for t in h.all_tiles)


def _check_little_four_winds(h: HandContext) -> bool:
    return (
        sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 3 and h.pair[0].is_wind()
    )


def _check_little_three_dragons(h: HandContext) -> bool:
    return (
        sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) == 2
        and h.pair[0].is_dragon()
    )


def _check_all_honors(h: HandContext) -> bool:
    return all(t.is_honor() for t in h.all_tiles)


def _check_four_concealed_pungs(h: HandContext) -> bool:
    return len(concealed_pungs(h)) == 4


def _check_pure_terminal_chows(h: HandContext) -> bool:
    """2×123 + 2×789 in the same suit, pair of 5 in the same suit."""
    if len(h.chows) != 4:
        return False
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        if h.pair[0].family is not family or h.pair[0].number != 5:
            continue
        all_starts = sorted(chow_starts_for_family(h, family))
        if all_starts == [1, 1, 7, 7]:
            if has_free_chow(h, family, 1) or has_free_chow(h, family, 7):
                for s in [1, 1, 7, 7]:
                    take_free_chow(h, family, s)
                return True
    return False


def _check_quadruple_chow(h: HandContext) -> bool:
    c = Counter(h.chows)
    for chow, count in c.items():
        if count >= 4:
            family, start = chow[0].family, chow[0].number
            if has_free_chow(h, family, start):
                for _ in range(4):
                    take_free_chow(h, family, start)
                return True
    return False


def _check_four_pure_shifted_pungs(h: HandContext) -> bool:
    """4 pungs/kongs in the same suit with consecutive numbers (step 1)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(pung_numbers_for_family(h, family))
        for i in range(len(nums) - 3):
            sub = nums[i : i + 4]
            if sub[1] - sub[0] == 1 and sub[2] - sub[1] == 1 and sub[3] - sub[2] == 1:
                if any(has_free_pung(h, family, n) for n in sub):
                    for n in sub:
                        take_free_pung(h, family, n)
                    return True
    return False


def _check_four_pure_shifted_chows(h: HandContext) -> bool:
    """4 chows in the same suit, each shifted by the same step (1 or 2)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(chow_starts_for_family(h, family))
        for i in range(len(nums) - 3):
            sub = nums[i : i + 4]
            for step in (1, 2):
                if (
                    sub[1] - sub[0] == step
                    and sub[2] - sub[1] == step
                    and sub[3] - sub[2] == step
                ):
                    if any(has_free_chow(h, family, s) for s in sub):
                        for s in sub:
                            take_free_chow(h, family, s)
                        return True
    return False


def _check_three_kongs(h: HandContext) -> bool:
    return len(h.kongs) == 3


def _check_all_terminal_and_honors(h: HandContext) -> bool:
    return all(t.is_terminal() or t.is_honor() for t in h.all_tiles)


def _check_all_even_pungs(h: HandContext) -> bool:
    return (
        not h.chows
        and all(g[0].is_even() for g in h.pungs + h.kongs)
        and h.pair[0].is_even()
    )


def _check_full_flush(h: HandContext) -> bool:
    return len(h.families) == 1 and Family.HONOR not in h.families


def _check_pure_triple_chow(h: HandContext) -> bool:
    c = Counter(h.chows)
    for chow, count in c.items():
        if count >= 3:
            family, start = chow[0].family, chow[0].number
            if has_free_chow(h, family, start):
                for _ in range(3):
                    take_free_chow(h, family, start)
                return True
    return False


def _check_pure_shifted_pungs(h: HandContext) -> bool:
    """3 pungs/kongs in the same suit with consecutive numbers (step 1)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(pung_numbers_for_family(h, family))
        for i in range(len(nums) - 2):
            sub = nums[i : i + 3]
            if sub[1] - sub[0] == 1 and sub[2] - sub[1] == 1:
                if any(has_free_pung(h, family, n) for n in sub):
                    for n in sub:
                        take_free_pung(h, family, n)
                    return True
    return False


def _check_upper_tiles(h: HandContext) -> bool:
    return all(not t.is_honor() and t.number >= 7 for t in h.all_tiles)


def _check_middle_tiles(h: HandContext) -> bool:
    return all(not t.is_honor() and 4 <= t.number <= 6 for t in h.all_tiles)


def _check_lower_tiles(h: HandContext) -> bool:
    return all(not t.is_honor() and t.number <= 3 for t in h.all_tiles)


def _check_pure_straight(h: HandContext) -> bool:
    """123 + 456 + 789 in the same suit. Consumes those 3 chows from the free pool."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        starts = chow_starts_for_family(h, family)
        if 1 in starts and 4 in starts and 7 in starts:
            if (
                has_free_chow(h, family, 1)
                or has_free_chow(h, family, 4)
                or has_free_chow(h, family, 7)
            ):
                take_free_chow(h, family, 1)
                take_free_chow(h, family, 4)
                take_free_chow(h, family, 7)
                return True
    return False


def _check_three_suited_terminal_chows(h: HandContext) -> bool:
    """123+789 in two suits, pair of 5 in the third suit."""
    if len(h.chows) != 4:
        return False
    for pair_fam in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        if h.pair[0].family is not pair_fam or h.pair[0].number != 5:
            continue
        other = [
            f
            for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER)
            if f is not pair_fam
        ]
        fa, fb = other[0], other[1]
        all_starts_a = sorted(chow_starts_for_family(h, fa))
        all_starts_b = sorted(chow_starts_for_family(h, fb))
        if all_starts_a == [1, 7] and all_starts_b == [1, 7]:
            fresh = any(has_free_chow(h, f, s) for f in (fa, fb) for s in (1, 7))
            if fresh:
                for s in [1, 7]:
                    take_free_chow(h, fa, s)
                    take_free_chow(h, fb, s)
                return True
    return False


def _check_pure_shifted_chows(h: HandContext) -> bool:
    """3 chows in the same suit, each shifted by step 1 or 2. Consumes those 3 chows."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(chow_starts_for_family(h, family))
        for i in range(len(nums) - 2):
            sub = nums[i : i + 3]
            for step in (1, 2):
                if sub[1] - sub[0] == step and sub[2] - sub[1] == step:
                    if any(has_free_chow(h, family, s) for s in sub):
                        for s in sub:
                            take_free_chow(h, family, s)
                        return True
    return False


def _check_all_fives(h: HandContext) -> bool:
    """Every group and the pair contains a 5."""
    return any(t.number == 5 for t in h.pair) and all(
        any(t.number == 5 for t in g) for g in h.groups
    )


def _check_triple_pung(h: HandContext) -> bool:
    """3 pungs/kongs of the same number in 3 different suits. Consumes those 3 groups."""
    by_num: dict[int, list] = {}
    for g in h.pungs + h.kongs:
        if not g[0].is_honor():
            by_num.setdefault(g[0].number, []).append(g)
    for _, groups in by_num.items():
        fams = {g[0].family for g in groups}
        if len(fams) >= 3:
            consumed = []
            used_fams: set = set()
            for g in groups:
                if g[0].family not in used_fams:
                    consumed.append(g)
                    used_fams.add(g[0].family)
                    if len(consumed) == 3:
                        break
            if any(has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_three_concealed_pungs(h: HandContext) -> bool:
    return len(concealed_pungs(h)) >= 3


def _check_upper_four(h: HandContext) -> bool:
    return all(not t.is_honor() and t.number >= 6 for t in h.all_tiles)


def _check_lower_four(h: HandContext) -> bool:
    return all(not t.is_honor() and t.number <= 4 for t in h.all_tiles)


def _check_big_three_winds(h: HandContext) -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 3


def _check_mixed_straight(h: HandContext) -> bool:
    """123 + 456 + 789, one chow per suit (any assignment of numbers to suits)."""
    chow_by_fam: dict[Family, list[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, []).append(g[0].number)
    fams = [
        f for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER) if f in chow_by_fam
    ]
    for f1, f2, f3 in permutations(fams, 3):
        if 1 in chow_by_fam[f1] and 4 in chow_by_fam[f2] and 7 in chow_by_fam[f3]:
            if (
                has_free_chow(h, f1, 1)
                or has_free_chow(h, f2, 4)
                or has_free_chow(h, f3, 7)
            ):
                take_free_chow(h, f1, 1)
                take_free_chow(h, f2, 4)
                take_free_chow(h, f3, 7)
                return True
    return False


def _check_reversible_tiles(h: HandContext) -> bool:
    return all(t.is_symmetric() for t in h.all_tiles)


def _check_mixed_triple_chow(h: HandContext) -> bool:
    """Same starting number chow in each of the 3 suits. Consumes those 3 chows."""
    chow_by_fam: dict[Family, set[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, set()).add(g[0].number)
    for num in range(1, 8):
        if all(
            num in chow_by_fam.get(f, set())
            for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER)
        ):
            if any(
                has_free_chow(h, f, num)
                for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER)
            ):
                for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
                    take_free_chow(h, f, num)
                return True
    return False


def _check_mixed_shifted_pungs(h: HandContext) -> bool:
    """3 pungs, one in each suit, with consecutive starting numbers. Consumes those 3 groups."""
    entries = [
        (g[0].number, g[0].family, g) for g in h.pungs + h.kongs if not g[0].is_honor()
    ]
    for trio in combinations(range(len(entries)), 3):
        nums = sorted(entries[i][0] for i in trio)
        fams = {entries[i][1] for i in trio}
        if len(fams) == 3 and nums[1] - nums[0] == 1 and nums[2] - nums[1] == 1:
            consumed = [entries[i][2] for i in trio]
            if any(has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_two_concealed_kongs(h: HandContext) -> bool:
    return len(concealed_kongs(h)) >= 2


def _check_all_pungs(h: HandContext) -> bool:
    return not h.has_knitted_straight and not h.chows


def _check_half_flush(h: HandContext) -> bool:
    return len(h.families) == 2 and Family.HONOR in h.families


def _check_mixed_shifted_chows(h: HandContext) -> bool:
    """3 chows, one per suit, with consecutive starting numbers (any step 1 or 2). Consumes those 3 chows."""
    chow_by_fam: dict[Family, list[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, []).append(g[0].number)
    fams = [
        f for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER) if f in chow_by_fam
    ]
    if len(fams) < 3:
        return False
    for f1, f2, f3 in permutations(fams, 3):
        for na in chow_by_fam[f1]:
            for nb in chow_by_fam[f2]:
                for nc in chow_by_fam[f3]:
                    nums = sorted([na, nb, nc])
                    if nums[1] - nums[0] == 1 and nums[2] - nums[1] == 1:
                        if (
                            has_free_chow(h, f1, na)
                            or has_free_chow(h, f2, nb)
                            or has_free_chow(h, f3, nc)
                        ):
                            take_free_chow(h, f1, na)
                            take_free_chow(h, f2, nb)
                            take_free_chow(h, f3, nc)
                            return True
    return False


def _check_all_types(h: HandContext) -> bool:
    """Hand contains tiles from all 3 suits + winds + dragons."""
    has_wind = False
    has_dragon = False
    for tile in h.all_tiles:
        if tile.is_wind():
            has_wind = True
        elif tile.is_dragon():
            has_dragon = True
    return len(h.families) == 4 and has_wind and has_dragon


def _check_melded_hand(h: HandContext) -> bool:
    """All groups are open (melded), won by discard."""
    open_groups = len(h.open_chows) + len(h.open_pungs) + len(h.open_kongs)
    return not h.is_drawn and open_groups == 4


def _check_two_dragons_pungs(h: HandContext) -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) >= 2


def _check_outside_hand(h: HandContext) -> bool:
    """Every group and the pair contains at least one terminal or honor."""

    def _has_toh(group: MahjongGroup) -> bool:
        return any(t.is_terminal() or t.is_honor() for t in group)

    return (
        not h.has_knitted_straight
        and _has_toh(h.pair)
        and all(_has_toh(g) for g in h.groups)
    )


def _check_fully_concealed(h: HandContext) -> bool:
    """All groups concealed, won by self-draw."""
    return h.is_drawn and not h.open_chows and not h.open_pungs and not h.open_kongs


def _check_two_melded_kongs(h: HandContext) -> bool:
    return len(h.kongs) >= 2


def _check_last_tile(h: HandContext) -> bool:
    return h.is_last_tile


def _check_dragon_pung(h: HandContext) -> int:
    """1 or more dragon pungs/kongs. Consumes each from the single-group pool."""
    count = 0
    for g in h.pungs + h.kongs:
        if g[0].is_dragon():
            take_free_pung_single(h, g[0].family, g[0].number)
            count += 1
    return count


def _check_prevalent_wind(h: HandContext) -> bool:
    if h.prevalent_wind > 0:
        for g in h.pungs + h.kongs:
            if g[0].is_wind() and g[0].number == h.prevalent_wind:
                take_free_pung_single(h, g[0].family, g[0].number)
                return True
    return False


def _check_seat_wind(h: HandContext) -> bool:
    if h.seat_wind > 0:
        for g in h.pungs + h.kongs:
            if g[0].is_wind() and g[0].number == h.seat_wind:
                take_free_pung_single(h, g[0].family, g[0].number)
                return True
    return False


def _check_concealed_hand(h: HandContext) -> bool:
    """All groups concealed, won by discard."""
    return not h.is_drawn and not h.open_chows and not h.open_pungs and not h.open_kongs


def _check_all_chows(h: HandContext) -> bool:
    return not h.pungs and not h.kongs and not h.pair[0].is_honor()


def _check_tile_hog(h: HandContext) -> int:
    """Count tiles with 4 copies used without declaring a kong."""
    kong_tiles = {g[0] for g in h.kongs}
    c = Counter(h.all_tiles)
    return sum(1 for tile, v in c.items() if v == 4 and tile not in kong_tiles)


def _check_double_pungs(h: HandContext) -> bool:
    """2 pungs of the same number in different suits. Consumes those 2 groups."""
    by_num: dict[int, list] = {}
    for g in h.pungs + h.kongs:
        if not g[0].is_honor():
            by_num.setdefault(g[0].number, []).append(g)
    for _, groups in by_num.items():
        fams = {g[0].family for g in groups}
        if len(fams) >= 2:
            consumed = []
            used_fams: set = set()
            for g in groups:
                if g[0].family not in used_fams:
                    consumed.append(g)
                    used_fams.add(g[0].family)
                    if len(consumed) == 2:
                        break
            if any(has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_two_concealed_pungs(h: HandContext) -> bool:
    return len(concealed_pungs(h)) >= 2


def _check_concealed_kong(h: HandContext) -> bool:
    return len(concealed_kongs(h)) >= 1


def _check_all_simple(h: HandContext) -> bool:
    return all(t.is_ordinary() for t in h.all_tiles)


# ---------------------------------------------------------------------------
# Low-tier chow-combination yakus (pure/mixed double chow, short straight,
# two terminal chows). These four share the leftover ``free_chows`` pool and
# can legally share melds with one another, so a fixed-priority greedy
# consumption order can miss feasible assignments (it may consume every free
# chow on the higher-priority combos and leave none for a lower-priority one
# that could otherwise still be scored). We instead compute, once per context,
# the optimal joint assignment via a small backtracking search and have each
# check draw its committed count from that plan.
# ---------------------------------------------------------------------------

# All four low-tier chow combinations are worth 1 point each.
_LOW_CHOW_POINTS = {69: 1, 70: 1, 71: 1, 72: 1}


def _low_chow_combo_instances(h: HandContext) -> list[tuple[int, list]]:
    """Enumerate every candidate low-tier chow combination as
    ``(yaku_id, [token, token])`` where each token is a ``(family, start)`` chow
    slot the combination would consume.  Patterns are detected over *all* chows
    (``h.chows``); fireability against the free pool is handled by the solver."""
    starts_by_fam: dict = {}
    for g in h.chows:
        starts_by_fam.setdefault(g[0].family, Counter())[g[0].number] += 1

    instances: list = []
    # Pure double chow: two identical chows in the same suit.
    for fam, counts in starts_by_fam.items():
        for start, count in counts.items():
            if count >= 2:
                instances.append((MahjongMCRYaku.PURE_DOUBLE_CHOW.get_id(), [(fam, start), (fam, start)]))
    # Mixed double chow: same start in two different suits.
    fams_by_start: dict = {}
    for fam, counts in starts_by_fam.items():
        for start in counts:
            fams_by_start.setdefault(start, []).append(fam)
    for start, fams in fams_by_start.items():
        ufams = list(dict.fromkeys(fams))
        for i in range(len(ufams)):
            for j in range(i + 1, len(ufams)):
                instances.append((MahjongMCRYaku.MIXED_DOUBLE_CHOW.get_id(), [(ufams[i], start), (ufams[j], start)]))
    # Short straight: two chows in one suit shifted by 3 (e.g. 123 + 456).
    for fam, counts in starts_by_fam.items():
        for start in counts:
            if (start + 3) in counts:
                instances.append((MahjongMCRYaku.SHORT_STRAIGHT.get_id(), [(fam, start), (fam, start + 3)]))
    # Two terminal chows: 123 + 789 in the same suit.
    for fam, counts in starts_by_fam.items():
        if 1 in counts and 7 in counts:
            instances.append((MahjongMCRYaku.TWO_TERMINAL_CHOWS.get_id(), [(fam, 1), (fam, 7)]))
    return instances


def _plan_is_better(a: tuple, b: tuple) -> bool:
    """True if plan ``a`` (tuple of yaku ids) beats plan ``b``: higher total
    points first, then – at equal points – the combination of higher-priority
    (lower-id) yakus, matching the engine's high-value-first principle."""
    pa = sum(_LOW_CHOW_POINTS[i] for i in a)
    pb = sum(_LOW_CHOW_POINTS[i] for i in b)
    if pa != pb:
        return pa > pb
    return tuple(sorted(a)) < tuple(sorted(b))


def _compute_low_chow_combo_plan(h: HandContext) -> Counter[int]:
    """Find the optimal set of low-tier chow combinations awardable from the
    current free-chow pool, returning a ``Counter`` of ``yaku_id -> count``.

    A combination may be awarded while at least one of its two chow slots is
    still free; awarding it consumes (up to) one free copy of each slot. Because
    different combination types may share a meld, the achievable set depends on
    ordering, so we search all orderings and keep the best plan."""
    tokens = Counter((g[0].family, g[0].number) for g in h.free_chows)
    instances = _low_chow_combo_instances(h)

    memo: dict[tuple, tuple] = {}

    def dfs(state: Counter) -> tuple:
        key = tuple(sorted((repr(k), v) for k, v in state.items() if v > 0))
        cached = memo.get(key)
        if cached is not None:
            return cached
        best: tuple = ()
        for yaku_id, slots in instances:
            if not any(state.get(t, 0) > 0 for t in slots):
                continue
            nxt = state.copy()
            for t in slots:
                if nxt.get(t, 0) > 0:
                    nxt[t] -= 1
            candidate = (yaku_id,) + dfs(nxt)
            if _plan_is_better(candidate, best):
                best = candidate
        memo[key] = best
        return best

    return Counter(dfs(tokens))


def _take_chow_combo(h: HandContext, yaku_id: int) -> int:
    """Draw one unit of the given low-tier chow-combination yaku from the
    context's cached optimal plan (computing the plan on first access)."""
    if h.chow_combo_plan is None:
        h.chow_combo_plan = _compute_low_chow_combo_plan(h)
    if h.chow_combo_plan.get(yaku_id, 0) > 0:
        h.chow_combo_plan[yaku_id] -= 1
        return 1
    return 0


def _check_pure_double_chow(h: HandContext) -> int:
    return _take_chow_combo(h, MahjongMCRYaku.PURE_DOUBLE_CHOW.get_id())


def _check_mixed_double_chow(h: HandContext) -> int:
    return _take_chow_combo(h, MahjongMCRYaku.MIXED_DOUBLE_CHOW.get_id())


def _check_short_straight(h: HandContext) -> int:
    return _take_chow_combo(h,  MahjongMCRYaku.SHORT_STRAIGHT.get_id())


def _check_two_terminal_chows(h: HandContext) -> int:
    return _take_chow_combo(h, MahjongMCRYaku.TWO_TERMINAL_CHOWS.get_id())


def _check_pung_of_terminals_or_honors(h: HandContext) -> int:
    """Count pungs/kongs of terminals or honors that still have a fresh slot in the single-group pool."""
    count = 0
    for g in h.pungs + h.kongs:
        if (g[0].is_terminal() or g[0].is_honor()) and has_free_pung_single(
            h, g[0].family, g[0].number
        ):
            take_free_pung_single(h, g[0].family, g[0].number)
            count += 1
    return count


def _check_melded_kong(h: HandContext) -> bool:
    return len(h.open_kongs) >= 1


def _check_one_voided_suit(h: HandContext) -> bool:
    """Tiles come from exactly 2 of the 3 number suits (honors don't count)."""
    return len(h.families - {Family.HONOR}) == 2


def _check_no_honor(h: HandContext) -> bool:
    return Family.HONOR not in h.families


def _check_edge_wait(h: HandContext) -> bool:
    """Winning tile is the 3 of a 12X chow, or the 7 of an X89 chow."""
    if len(h.acceptance) > 1:
        return False
    wt = h.winning_tile
    for g in h.chows:
        if g in h.open_chows:
            continue
        if wt in g:
            nums = sorted(t.number for t in g)
            if nums == [1, 2, 3] and wt.number == 3:
                return True
            if nums == [7, 8, 9] and wt.number == 7:
                return True
    return False


def _check_closed_wait(h: HandContext) -> bool:
    """Winning tile is the middle tile of its chow (kanchan wait)."""
    if len(h.acceptance) > 1:
        return False
    wt = h.winning_tile
    for g in h.chows:
        if g in h.open_chows:
            continue
        if wt in g:
            nums = sorted(t.number for t in g)
            if nums[1] == wt.number:
                return True
    return False


def _check_single_wait(h: HandContext) -> bool:
    """Winning tile completes the pair (tanki wait)."""
    return len(h.acceptance) == 1 and h.winning_tile in h.pair


def _check_self_drawn(h: HandContext) -> bool:
    return h.is_drawn


# Placeholder for yakus that require full scoring context or are special hands
def _check_not_implemented(_: HandContext) -> bool:
    return False


# fmt: off
class MahjongMCRYaku(Enum):
    BIG_FOUR_WIND            = (1,  88, [38, 49, 60, 61, 73], _check_big_four_winds)
    BIG_THREE_DRAGON         = (2,  88, [54, 59],             _check_big_three_dragons)
    ALL_GREEN                = (3,  88, [],                   _check_all_green)
    NINE_GATES               = (4,  88, [22, 62, 73, 76],     _check_nine_gates)
    FOUR_KONGS               = (5,  88, [48, 57, 67, 74, 79], _check_four_kongs)
    SEVEN_SHIFTED_PAIRS      = (6,  88, [19, 22, 62, 79],     _check_not_implemented)
    THIRTEEN_ORPHANS         = (7,  88, [52, 62],             _check_not_implemented)
    ALL_TERMINALS            = (8,  64, [18, 49, 73, 76],     _check_all_terminals)
    LITTLE_FOUR_WINDS        = (9,  64, [38, 73],             _check_little_four_winds)
    LITTLE_THREE_DRAGONS     = (10, 64, [54, 59],             _check_little_three_dragons)
    ALL_HONORS               = (11, 64, [18, 49, 73],         _check_all_honors)
    FOUR_CONCEALED_PUNGS     = (12, 64, [33, 49, 62, 66],     _check_four_concealed_pungs)
    PURE_TERMINAL_CHOWS      = (13, 64, [22, 63, 69, 72],     _check_pure_terminal_chows)
    QUADRUPLE_CHOW           = (14, 48, [64, 69],             _check_quadruple_chow)
    FOUR_PURE_SHIFTED_PUNGS  = (15, 48, [49],                 _check_four_pure_shifted_pungs)
    FOUR_PURE_SHIFTED_CHOWS  = (16, 32, [71, 72],             _check_four_pure_shifted_chows)
    THREE_KONGS              = (17, 32, [48, 57, 67, 74],     _check_three_kongs)
    ALL_TERMINAL_AND_HONORS  = (18, 32, [49, 55, 73],         _check_all_terminal_and_honors)
    SEVEN_PAIRS              = (19, 24, [62, 79],             _check_not_implemented)
    GREATER_HONORS_AND_KNITTED_TILES = (20, 24, [52, 62],     _check_not_implemented)
    ALL_EVEN_PUNGS           = (21, 24, [49, 68],             _check_all_even_pungs)
    FULL_FLUSH               = (22, 24, [50, 76],             _check_full_flush)
    PURE_TRIPLE_CHOW         = (23, 24, [69],                 _check_pure_triple_chow)
    PURE_SHIFTED_PUNGS       = (24, 24, [],                   _check_pure_shifted_pungs)
    UPPER_TILES              = (25, 24, [76],                 _check_upper_tiles)
    MIDDLE_TILES             = (26, 24, [68, 76],             _check_middle_tiles)
    LOWER_TILES              = (27, 24, [76],                 _check_lower_tiles)
    PURE_STRAIGHT            = (28, 16, [],                   _check_pure_straight)
    THREE_SUITED_TERMINAL_CHOWS = (29, 16, [63, 69, 70, 72],  _check_three_suited_terminal_chows)
    PURE_SHIFTED_CHOWS       = (30, 16, [],                   _check_pure_shifted_chows)
    ALL_FIVES                = (31, 16, [68],                 _check_all_fives)
    TRIPLE_PUNG              = (32, 16, [],                   _check_triple_pung)
    THREE_CONCEALED_PUNGS    = (33, 16, [66],                 _check_three_concealed_pungs)
    LESSER_HONORS_AND_KNITTED_TILES = (34, 12, [52, 62],      _check_not_implemented)
    KNITTED_STRAIGHT         = (35, 12, [],                   _check_not_implemented)
    UPPER_FOUR               = (36, 12, [76],                 _check_upper_four)
    LOWER_FOUR               = (37, 12, [76],                 _check_lower_four)
    BIG_THREE_WINDS          = (38, 12, [73],                 _check_big_three_winds)
    MIXED_STRAIGHT           = (39, 8,  [],                   _check_mixed_straight)
    REVERSIBLE_TILES         = (40, 8,  [75],                 _check_reversible_tiles)
    MIXED_TRIPLE_CHOW        = (41, 8,  [70],                 _check_mixed_triple_chow)
    MIXED_SHIFTED_PUNGS      = (42, 8,  [],                   _check_mixed_shifted_pungs)
    CHICKEN_HAND             = (43, 8,  [],                   _check_not_implemented)
    # 44, 45, 46, 47 situational
    TWO_CONCEALED_KONGS      = (48, 8,  [57, 67],             _check_two_concealed_kongs)
    ALL_PUNGS                = (49, 6,  [],                   _check_all_pungs)
    HALF_FLUSH               = (50, 6,  [75],                 _check_half_flush)
    MIXED_SHIFTED_CHOWS      = (51, 6,  [],                   _check_mixed_shifted_chows)
    ALL_TYPES                = (52, 6,  [],                   _check_all_types)
    MELDED_HAND              = (53, 6,  [79],                 _check_melded_hand)
    TWO_DRAGONS_PUNGS        = (54, 6,  [59],                 _check_two_dragons_pungs)
    OUTSIDE_HAND             = (55, 4,  [],                   _check_outside_hand)
    FULLY_CONCEALED          = (56, 4,  [62, 80],             _check_fully_concealed)
    TWO_MELDED_KONGS         = (57, 4,  [74],                 _check_two_melded_kongs)
    LAST_TILE                = (58, 4,  [],                   _check_last_tile)
    DRAGON_PUNG              = (59, 2,  [],                   _check_dragon_pung)
    PREVALENT_WIND           = (60, 2,  [],                   _check_prevalent_wind)
    SEAT_WIND                = (61, 2,  [],                   _check_seat_wind)
    CONCEALED_HAND           = (62, 2,  [],                   _check_concealed_hand)
    ALL_CHOWS                = (63, 2,  [76],                 _check_all_chows)
    TILE_HOG                 = (64, 2,  [],                   _check_tile_hog)
    DOUBLE_PUNGS             = (65, 2,  [],                   _check_double_pungs,      True)
    TWO_CONCEALED_PUNGS      = (66, 2,  [],                   _check_two_concealed_pungs)
    CONCEALED_KONG           = (67, 2,  [],                   _check_concealed_kong)
    ALL_SIMPLE               = (68, 2,  [76],                 _check_all_simple)
    PURE_DOUBLE_CHOW         = (69, 1,  [],                   _check_pure_double_chow,  True)
    MIXED_DOUBLE_CHOW        = (70, 1,  [],                   _check_mixed_double_chow, True)
    SHORT_STRAIGHT           = (71, 1,  [],                   _check_short_straight,    True)
    TWO_TERMINAL_CHOWS       = (72, 1,  [],                   _check_two_terminal_chows,True)
    PUNG_OF_TERMINALS_OR_HONORS = (73, 1, [],                 _check_pung_of_terminals_or_honors)
    MELDED_KONG              = (74, 1,  [],                   _check_melded_kong)
    ONE_VOIDED_SUIT          = (75, 1,  [],                   _check_one_voided_suit)
    NO_HONOR                 = (76, 1,  [],                   _check_no_honor)
    EDGE_WAIT                = (77, 1,  [78, 79],             _check_edge_wait)
    CLOSED_WAIT              = (78, 1,  [79],                 _check_closed_wait)
    SINGLE_WAIT              = (79, 1,  [],                   _check_single_wait)
    SELF_DRAWN               = (80, 1,  [],                   _check_self_drawn)
    # 81 flowers
    # fmt: off

    def __init__(self, yaku_id, points, exclusion_ids, check_fn, is_multi=False):
        # Unpack the definition tuple once into plain attributes. Accessing
        # ``self.value[i]`` on every call goes through the (slow) Enum value
        # descriptor; these hot accessors are called millions of times during
        # hand analysis, so caching the fields as attributes is a large win.
        self._id = yaku_id
        self._points = points
        self._exclusion_ids = exclusion_ids
        self._check_fn = check_fn
        self._is_multi = bool(is_multi)
        self._exclusions = None  # resolved lazily once all members exist

    def __hash__(self):
        # Stable, cheap hash (default Enum hash re-hashes the name string on
        # every set/dict operation, of which there are millions here).
        return self._id

    @staticmethod
    def get(yaku_id: int):
        return _YAKU_BY_ID[yaku_id]

    def check(self, hand: HandContext) -> int:
        return self._check_fn(hand)

    def is_multi(self) -> bool:
        return self._is_multi

    def get_points(self) -> int:
        return self._points

    def get_exclusions(self) -> "frozenset[MahjongMCRYaku]":
        if self._exclusions is None:
            self._exclusions = frozenset(
                _YAKU_BY_ID[yaku_id] for yaku_id in self._exclusion_ids
            )
        return self._exclusions

    def get_id(self) -> int:
        return self._id


_YAKU_BY_ID = {yaku.get_id(): yaku for yaku in MahjongMCRYaku}
