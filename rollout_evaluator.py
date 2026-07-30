"""Rollout-based evaluation of discard choices.

Given a 14-tile hand and a set of candidate discards, this estimates the
**win rate** (reaching a legal MCR win worth >= 8 points) of each candidate by
Monte-Carlo simulation:

    for each candidate discard d:
        repeat N times:
            discard d, then play out random draws from the unseen wall,
            choosing every subsequent discard with a *playout policy*,
            until a legal >= 8 win or a turn budget is reached
        win rate(d) = wins / N

The default playout policy is the project's own value-aware discarder
(``get_tile_to_discard_from``), so the estimate reflects how the hand actually
plays out under the current strategy - directly answering "which discard gives
the best chance of a real win". The expensive >= 8 scorer is only invoked when
the fast ``shanten_oracle`` reports a structurally complete hand, and rollouts
are parallelised across CPU cores, keeping a few-hundred-rollout evaluation
within minutes.

A faster, lower-fidelity ``playout="oracle"`` mode is also provided (a cheap
shanten-free heuristic); it is much quicker but, being value-blind, materially
underestimates win rates and should only be used for rough ranking.
"""
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from random import Random

from mahjong_objects import MahjongHand, MahjongTile
from shanten_oracle import (
    counts_from_tiles,
    standard_shanten,
    seven_pairs_shanten,
    kokushi_shanten,
    honors_knitted_shanten,
)
from tile_acceptance_calculator import get_tile_to_discard_from
from discard_policy import (
    _INDEX_TO_TILE,
    _legal_win_points,
    _legal_points_cached,
    _terminally_complete,
    _playout_discard,
)
from tiles_utils import parse_hand, parse_tiles

DEFAULT_ROLLOUTS = int(os.environ.get("MCR_EVAL_ROLLOUTS", "30"))
DEFAULT_BUDGET = int(os.environ.get("MCR_EVAL_BUDGET", "22"))
# When True, skip the expensive value-aware discarder on drawn tiles that neither
# advance shanten nor improve acceptance (tsumogiri fast-path). See _greedy_rollout.
FASTPATH = os.environ.get("MCR_EVAL_FASTPATH", "1") != "0"

# Measured amortized wall-clock cost of one greedy-playout rollout across cores
# with the tsumogiri fast-path on (~2-2.5 s each on a 12-core box; ~4.8 s with
# MCR_EVAL_FASTPATH=0). Used only for the pre-flight runtime estimate, not for
# correctness.
_SECONDS_PER_ROLLOUT = float(os.environ.get("MCR_EVAL_SEC_PER_ROLLOUT", "2.5"))


@dataclass
class ChoiceStats:
    """Aggregated rollout outcome for one candidate discard."""

    tile: MahjongTile
    rollouts: int
    wins: int
    win_rate: float
    ci_low: float          # 95% Wilson lower bound on win_rate
    ci_high: float         # 95% Wilson upper bound on win_rate
    prob_best: float       # paired-bootstrap P(this discard is the true argmax)
    avg_points: float | None
    avg_turns_to_win: float | None
    ev: float  # win_rate * avg_points (0 if no wins)


def _wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion (robust at small n)."""
    if n == 0:
        return 0.0, 1.0
    phat = wins / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * ((phat * (1 - phat) + z * z / (4 * n)) / n) ** 0.5) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _prob_best_bootstrap(win_matrix, resamples: int, seed: int) -> list[float]:
    """Paired bootstrap over the shared rollout index -> P(each choice is best).

    ``win_matrix[c][r]`` is 1 if choice ``c`` won on wall ``r`` (Common Random
    Numbers make column ``r`` the *same* wall for every choice). Resampling whole
    columns keeps the pairing, so this measures confidence in the *ranking*, not
    just each marginal win rate.
    """
    n_choices = len(win_matrix)
    if n_choices == 0:
        return []
    n = len(win_matrix[0])
    if n == 0:
        return [0.0] * n_choices
    rng = Random(seed)
    best_counts = [0] * n_choices
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        sums = [0] * n_choices
        for c in range(n_choices):
            row = win_matrix[c]
            s = 0
            for i in idx:
                s += row[i]
            sums[c] = s
        top = max(sums)
        winners = [c for c in range(n_choices) if sums[c] == top]
        share = 1.0 / len(winners)
        for c in winners:
            best_counts[c] += share
    return [bc / resamples for bc in best_counts]


def _wall_from_unseen(unseen_counts, rng: Random) -> list:
    """Build and shuffle a determinized wall from the unseen-tile counts."""
    wall = []
    for idx, copies in enumerate(unseen_counts):
        if copies:
            wall.extend([_INDEX_TO_TILE[idx]] * copies)
    rng.shuffle(wall)
    return wall


_TERMINALS_HONORS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


@lru_cache(maxsize=None)
def _fast_shapes(counts_t):
    """(standard, seven_pairs, kokushi, honors_knitted) shanten - memoized.

    Excludes the costly knitted *straight* (see ``_terminally_complete``); rollouts
    never assemble one, so keeping it would only slow every turn."""
    counts = list(counts_t)
    return (
        standard_shanten(counts),
        seven_pairs_shanten(counts),
        kokushi_shanten(counts),
        honors_knitted_shanten(counts),
    )


def _fast_shanten(counts) -> int:
    """Minimum shanten over the cheap shapes (memoized)."""
    return min(_fast_shapes(tuple(counts)))


def _standard_relevant(counts) -> set:
    """Superset of tiles whose addition can reduce *standard*-shape shanten: any
    present tile (forms a pair/triplet) and every same-suit neighbour within 2 of a
    present tile (forms/extends a run). Tiles outside this set are provably useless
    to the standard shape, so probing them is skipped with no loss of accuracy."""
    rel = set()
    for idx in range(34):
        if counts[idx] == 0:
            continue
        rel.add(idx)
        if idx < 27:
            num = idx % 9
            base = idx - num
            for dn in (num - 2, num - 1, num + 1, num + 2):
                if 0 <= dn <= 8:
                    rel.add(base + dn)
    return rel


def _fast_ukeire(counts):
    """(shanten, {advancing_tile: unseen_copies}) over the cheap shapes.

    Only tiles that can advance a shape *currently at the minimum shanten* are
    probed - an exact reduction of the naive all-34 scan (a tile can lower the min
    only by dropping a shape that is already at the min). Falls back to the full
    scan for the rare kokushi/honors-knitted-governed hands."""
    std, sp, ko, hk = _fast_shapes(tuple(counts))
    cur = min(std, sp, ko, hk)
    if ko == cur or hk == cur:
        candidates = range(34)  # rare in rollouts; stay exact without extra bookkeeping
    else:
        candidates = set()
        if std == cur:
            candidates |= _standard_relevant(counts)
        if sp == cur:
            candidates |= {i for i in range(34) if counts[i] == 1}  # 7 pairs: pair a single
    advancing = {}
    for idx in candidates:
        if counts[idx] >= 4:
            continue
        counts[idx] += 1
        if min(_fast_shapes(tuple(counts))) < cur:
            advancing[idx] = 4 - (counts[idx] - 1)
        counts[idx] -= 1
    return cur, advancing


@lru_cache(maxsize=None)
def _fast_acceptance_cached(counts_t) -> int:
    return sum(_fast_ukeire(list(counts_t))[1].values())


def _fast_acceptance(counts) -> int:
    """Total unseen tiles that reduce shanten (breadth), cheap shapes only (memoized)."""
    return _fast_acceptance_cached(tuple(counts))


def _connected(counts14, t) -> bool:
    """Cheap necessary condition for the drawn tile ``t`` to *possibly* improve
    acceptance if kept. Isolated middle-suit draws fail this in O(1) and are
    classified Type C without the (relatively costly) discard scan.

    Conservative: honours and terminals always pass (they can feed the kokushi /
    honors-knitted shapes), so a genuinely useful special-shape tile is never
    mis-skipped."""
    if counts14[t] >= 2:
        return True  # duplicates an existing tile -> pair (standard / seven pairs)
    if t >= 27:
        return True  # honour: may advance kokushi / honors-knitted
    num = t % 9
    if num == 0 or num == 8:
        return True  # terminal: kokushi / honors-knitted relevant
    base = t - num
    for dn in (num - 2, num - 1, num + 1, num + 2):
        if 0 <= dn <= 8 and counts14[base + dn] >= 1:
            return True  # a same-suit neighbour within 2 -> can form/upgrade a run
    return False


def _keeping_improves_acceptance(counts14, drawn, s13, acc13) -> bool:
    """Does *keeping* the drawn tile (discarding something else) beat tsumogiri?

    Tsumogiri (discard ``drawn``) restores the pre-draw 13-hand: shanten ``s13``,
    acceptance ``acc13``. The draw is worth keeping only if some *other* discard
    ``d`` yields a 13-hand with the same shanten but strictly greater acceptance.
    Returns ``True`` as soon as such a ``d`` is found (Type B); ``False`` means the
    draw is useless (Type C) and can be discarded without the costly value policy.

    Only *distinct* discard candidates that keep shanten at ``s13`` are scored, and
    the acceptance is memoized, so the scan stays cheap.
    """
    if not _connected(counts14, drawn):
        return False
    seen = set()
    for d in range(34):
        if counts14[d] == 0 or d == drawn or d in seen:
            continue  # discarding the draw itself is the tsumogiri baseline
        seen.add(d)
        counts14[d] -= 1
        try:
            if _fast_shanten(counts14) == s13 and _fast_acceptance(counts14) > acc13:
                return True
        finally:
            counts14[d] += 1
    return False


def _value_discard_index(counts14, drawn, pw, sw) -> int:
    """Call the project's value-aware discarder on the 14-tile hand; return its
    tile index. Falls back to tsumogiri on any scorer/analyser hiccup."""
    tiles = []
    for idx, copies in enumerate(counts14):
        take = copies - 1 if idx == drawn else copies
        if take:
            tiles.extend([_INDEX_TO_TILE[idx]] * take)
    hand = MahjongHand(tiles)
    hand.draw(_INDEX_TO_TILE[drawn])
    try:
        return get_tile_to_discard_from(hand, pw, sw)[0][0].index
    except (AttributeError, ValueError, IndexError):
        return drawn


def _greedy_rollout(hand13_counts, unseen_counts, seed, budget, pw, sw):
    """Play out with the project's value-aware discarder; return (won, turns, points).

    A tsumogiri fast-path (enabled by ``FASTPATH``) skips the expensive
    ``get_tile_to_discard_from`` whenever the fast oracle proves the drawn tile
    neither advances shanten (Type A) nor improves acceptance (Type B) - which,
    especially as the hand nears tenpai, is the large majority of draws (Type C).
    The advancing set and acceptance of the current 13-hand are computed once per
    *real* discard and reused across the run of skipped (tsumogiri) draws.
    """
    rng = Random(seed)
    counts = list(hand13_counts)  # 13-tile count vector; kept in sync in-place
    wall = _wall_from_unseen(unseen_counts, rng)

    s13, advancing = _fast_ukeire(counts)
    acc13 = sum(advancing.values())

    for turn in range(1, budget + 1):
        if not wall:
            break
        drawn = wall.pop().index
        counts[drawn] += 1  # now a 14-tile vector

        if _terminally_complete(counts):
            points = _legal_points_cached(tuple(counts), drawn)
            if points >= 0:
                return True, turn, points

        if FASTPATH:
            if drawn in advancing:
                discard = _value_discard_index(counts, drawn, pw, sw)  # Type A
            elif _keeping_improves_acceptance(counts, drawn, s13, acc13):
                discard = _value_discard_index(counts, drawn, pw, sw)  # Type B
            else:
                discard = drawn  # Type C: useless draw -> tsumogiri, skip policy
        else:
            discard = _value_discard_index(counts, drawn, pw, sw)

        counts[discard] -= 1  # back to 13 tiles
        if discard != drawn:
            # the 13-hand changed; refresh the cached advancing set / acceptance
            s13, advancing = _fast_ukeire(counts)
            acc13 = sum(advancing.values())
    return False, 0, 0


def _oracle_rollout(hand13_counts, unseen_counts, seed, budget, pw, sw):
    """Play out with the cheap shanten-free heuristic; return (won, turns, points)."""
    from discard_policy import _legal_points_cached, _weighted_draw

    rng = Random(seed)
    counts = list(hand13_counts)
    rem = list(unseen_counts)
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
                return True, turn, points
        discard = _playout_discard(counts)
        counts[discard] -= 1
    return False, 0, 0


def _rollout_task(args):
    """Top-level worker (must be importable for ProcessPoolExecutor on Windows)."""
    (choice_index, rollout_index, hand13_counts, unseen_counts,
     seed, budget, pw, sw, playout) = args
    run = _greedy_rollout if playout == "greedy" else _oracle_rollout
    won, turns, points = run(hand13_counts, unseen_counts, seed, budget, pw, sw)
    return choice_index, rollout_index, won, turns, points


def _coerce_choices(choices, hand: MahjongHand) -> list:
    """Accept choices as MahjongTile objects or integer tile indices (0-33)."""
    coerced = []
    for c in choices:
        if isinstance(c, MahjongTile):
            coerced.append(c)
        elif isinstance(c, int):
            coerced.append(_INDEX_TO_TILE[c])
        else:
            raise TypeError(
                f"choice {c!r} must be a MahjongTile or int tile index (0-33)."
            )
    return coerced


def _default_choices(hand: MahjongHand) -> list:
    """All distinct tiles currently in the hand (any of them could be discarded)."""
    seen = {}
    for tile in hand.get_free_tiles():
        seen[tile.index] = tile
    return [seen[idx] for idx in sorted(seen)]


def _execute(tasks, parallel):
    """Run rollout tasks (parallel across cores or serially); yield raw results."""
    if parallel:
        # chunksize=1 (round-robin) balances load best: rollouts vary widely in
        # cost (early wins ~6 s vs full-budget losers ~15 s) and the transposition
        # cache is keyed by full hand, so grouping same-choice tasks gives little
        # reuse but risks piling slow tasks on one worker.
        n_workers = os.cpu_count() or 1
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            for result in executor.map(_rollout_task, tasks):
                yield result
    else:
        for task in tasks:
            yield _rollout_task(task)


def _crn_seed(base_seed, r):
    """Common-Random-Numbers seed: depends only on the rollout index, so every
    candidate faces the same wall for rollout ``r`` (see evaluate_discard_choices)."""
    return (base_seed ^ (r * 2654435761)) & 0xFFFFFFFF


def _build_stats(choices, wins, points_sum, turns_sum, n_by_choice, prob_best):
    """Assemble sorted ChoiceStats from accumulated per-choice tallies."""
    stats = []
    for ci, tile in enumerate(choices):
        w = wins[ci]
        n = n_by_choice[ci]
        avg_points = points_sum[ci] / w if w else None
        avg_turns = turns_sum[ci] / w if w else None
        win_rate = w / n if n else 0.0
        ci_low, ci_high = _wilson_ci(w, n)
        stats.append(
            ChoiceStats(
                tile=tile,
                rollouts=n,
                wins=w,
                win_rate=win_rate,
                ci_low=ci_low,
                ci_high=ci_high,
                prob_best=prob_best[ci],
                avg_points=avg_points,
                avg_turns_to_win=avg_turns,
                ev=win_rate * (avg_points or 0.0),
            )
        )
    stats.sort(key=lambda s: (s.prob_best, s.win_rate, s.ev), reverse=True)
    return stats


def evaluate_discard_choices(
    hand: MahjongHand,
    choices: list | None = None,
    rollouts: int = DEFAULT_ROLLOUTS,
    budget: int = DEFAULT_BUDGET,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    playout: str = "greedy",
    parallel: bool = True,
    base_seed: int = 0xC0FFEE,
    verbose: bool = True,
) -> list[ChoiceStats]:
    """Estimate each candidate discard's win rate by Monte-Carlo rollouts.

    :param hand: a 14-tile :class:`MahjongHand` (a hand that needs to discard).
    :param choices: candidate discards as :class:`MahjongTile` objects or integer
        tile indices (0-33); defaults to every distinct hand tile. Prefer passing
        a *shortlist* (e.g. the top few greedy candidates) - runtime is linear in
        ``len(choices) * rollouts``.
    :param rollouts: simulations per candidate (accuracy vs. time).
    :param budget: max draws simulated per rollout before giving up.
    :param playout: ``"greedy"`` (value-aware, slow, realistic) or ``"oracle"``
        (cheap, fast, value-blind - rough ranking only).
    :param parallel: distribute rollouts across CPU cores.
    :param verbose: print a runtime pre-estimate before running.
    :return: :class:`ChoiceStats` per candidate, sorted by win rate (desc).
    """
    if not hand.needs_to_discard():
        raise AttributeError(
            f"Hand must have a tile to discard (got {len(hand.hand_tiles)} tiles)."
        )
    counts14 = counts_from_tiles(hand.get_free_tiles())
    if choices is None:
        choices = _default_choices(hand)
    else:
        choices = _coerce_choices(choices, hand)
    unseen_counts = tuple(4 - counts14[idx] for idx in range(34))

    if verbose and playout == "greedy":
        total = len(choices) * rollouts
        # _SECONDS_PER_ROLLOUT is already the parallel-amortized per-rollout cost.
        n_workers = (os.cpu_count() or 1)
        est = total * _SECONDS_PER_ROLLOUT
        if not parallel:
            est *= n_workers
        print(
            f"[rollout_evaluator] {len(choices)} choices x {rollouts} rollouts "
            f"(budget {budget}, playout={playout}, parallel={parallel}) "
            f"~= {est/60:.1f} min estimated."
        )
        if est > 600:
            print(
                "[rollout_evaluator] WARNING: estimate exceeds 10 min; "
                "reduce rollouts or the number of choices."
            )

    tasks = []
    for choice_index, tile in enumerate(choices):
        hand13 = list(counts14)
        hand13[tile.index] -= 1
        hand13 = tuple(hand13)
        for r in range(rollouts):
            # Common Random Numbers: the seed depends ONLY on the rollout index r,
            # not on the discarded tile, so every candidate faces the *same* wall
            # for rollout r (the unseen pool is identical across choices). This
            # pairs the comparison and sharply reduces the variance of the ranking.
            tasks.append(
                (
                    choice_index,
                    r,
                    hand13,
                    unseen_counts,
                    _crn_seed(base_seed, r),
                    budget,
                    prevalent_wind,
                    seat_wind,
                    playout,
                )
            )

    # Per-choice, per-rollout win indicators (paired across choices via CRN).
    win_matrix = [[0] * rollouts for _ in choices]
    wins = defaultdict(int)
    points_sum = defaultdict(int)
    turns_sum = defaultdict(int)

    for choice_index, rollout_index, won, turns, points in _execute(tasks, parallel):
        if won:
            win_matrix[choice_index][rollout_index] = 1
            wins[choice_index] += 1
            points_sum[choice_index] += points
            turns_sum[choice_index] += turns

    prob_best = _prob_best_bootstrap(win_matrix, resamples=5000, seed=base_seed)
    n_by_choice = {ci: rollouts for ci in range(len(choices))}
    return _build_stats(choices, wins, points_sum, turns_sum, n_by_choice, prob_best)


def evaluate_discard_choices_adaptive(
    hand: MahjongHand,
    choices: list | None = None,
    budget: int = DEFAULT_BUDGET,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    playout: str = "greedy",
    parallel: bool = True,
    initial_rollouts: int = 12,
    batch: int = 8,
    max_rollouts: int = 64,
    target_prob: float = 0.90,
    prune: bool = True,
    base_seed: int = 0xC0FFEE,
    verbose: bool = True,
) -> list[ChoiceStats]:
    """Like :func:`evaluate_discard_choices`, but keep adding rollouts until the
    leader is confident (``P(best) >= target_prob``) or ``max_rollouts`` is hit -
    so you don't have to guess the rollout count.

    Rollouts are added in waves under Common Random Numbers (every surviving choice
    shares wall ``r``). Between waves, choices that are statistically out of the
    race are pruned (``prune``): a choice is dropped when its 95% CI upper bound is
    below the current leader's CI lower bound, so the remaining budget concentrates
    on the genuinely close contenders. The leader is never pruned.

    :param initial_rollouts: rollouts in the first wave (all choices).
    :param batch: rollouts added per subsequent wave (surviving choices).
    :param max_rollouts: hard cap on rollouts for any single choice.
    :param target_prob: stop once the leader's paired-bootstrap P(best) reaches this.
    :return: :class:`ChoiceStats` per candidate, sorted by P(best) then win rate.
    """
    if not hand.needs_to_discard():
        raise AttributeError(
            f"Hand must have a tile to discard (got {len(hand.hand_tiles)} tiles)."
        )
    counts14 = counts_from_tiles(hand.get_free_tiles())
    if choices is None:
        choices = _default_choices(hand)
    else:
        choices = _coerce_choices(choices, hand)
    unseen_counts = tuple(4 - counts14[idx] for idx in range(34))
    hand13_by_choice = []
    for tile in choices:
        h = list(counts14)
        h[tile.index] -= 1
        hand13_by_choice.append(tuple(h))

    n_choices = len(choices)
    # win_rows[ci][r] = 1 if choice ci won on wall r (grows as waves are added).
    win_rows = [dict() for _ in range(n_choices)]
    wins = defaultdict(int)
    points_sum = defaultdict(int)
    turns_sum = defaultdict(int)
    n_by_choice = {ci: 0 for ci in range(n_choices)}
    active = set(range(n_choices))
    prob_best = [0.0] * n_choices

    done = 0  # rollout indices [0, done) have been sampled for all still-active choices
    wave = 0
    while True:
        want = initial_rollouts if wave == 0 else batch
        want = min(want, max_rollouts - done)
        if want <= 0:
            break

        tasks = []
        for ci in sorted(active):
            for r in range(done, done + want):
                tasks.append(
                    (
                        ci,
                        r,
                        hand13_by_choice[ci],
                        unseen_counts,
                        _crn_seed(base_seed, r),
                        budget,
                        prevalent_wind,
                        seat_wind,
                        playout,
                    )
                )
        if verbose and playout == "greedy":
            est = len(tasks) * _SECONDS_PER_ROLLOUT
            print(
                f"[adaptive] wave {wave}: {len(active)} active x {want} rollouts "
                f"(total so far -> {done + want}/choice max) ~= {est/60:.1f} min."
            )

        for ci, r, won, turns, points in _execute(tasks, parallel):
            if won:
                win_rows[ci][r] = 1
                wins[ci] += 1
                points_sum[ci] += points
                turns_sum[ci] += turns
            else:
                win_rows[ci].setdefault(r, 0)
        done += want
        for ci in active:
            n_by_choice[ci] = done
        wave += 1

        # Paired bootstrap over the shared columns [0, done) among active choices.
        active_ids = sorted(active)
        active_matrix = [[win_rows[ci].get(r, 0) for r in range(done)] for ci in active_ids]
        active_prob = _prob_best_bootstrap(active_matrix, resamples=5000, seed=base_seed)
        prob_best = [0.0] * n_choices
        for k, ci in enumerate(active_ids):
            prob_best[ci] = active_prob[k]

        leader = max(active_ids, key=lambda ci: prob_best[ci])
        leader_prob = prob_best[leader]
        if verbose:
            print(
                f"[adaptive]   leader {choices[leader]} P(best)={leader_prob:.0%} "
                f"(win {wins[leader]}/{done})"
            )

        if leader_prob >= target_prob or done >= max_rollouts:
            break

        if prune and len(active) > 2:
            lead_lo, _ = _wilson_ci(wins[leader], done)
            dropped = set()
            for ci in active_ids:
                if ci == leader:
                    continue
                _, hi = _wilson_ci(wins[ci], done)
                if hi < lead_lo:
                    dropped.add(ci)
            if dropped and len(active) - len(dropped) >= 2:
                active -= dropped
                if verbose:
                    names = ", ".join(str(choices[ci]) for ci in sorted(dropped))
                    print(f"[adaptive]   pruned (out of race): {names}")

    return _build_stats(choices, wins, points_sum, turns_sum, n_by_choice, prob_best)


def print_choice_stats(stats: list[ChoiceStats]) -> None:
    """Pretty-print a ranked table of discard evaluations with uncertainty."""
    print(
        f"{'discard':>8} {'win%':>6} {'95% CI':>13} {'P(best)':>8} "
        f"{'avg_pts':>8} {'avg_turns':>10} {'EV':>6}"
    )
    for s in stats:
        pts = f"{s.avg_points:.1f}" if s.avg_points is not None else "-"
        trn = f"{s.avg_turns_to_win:.1f}" if s.avg_turns_to_win is not None else "-"
        ci = f"{s.ci_low:.0%}-{s.ci_high:.0%}"
        print(
            f"{str(s.tile):>8} {s.win_rate:>6.1%} {ci:>13} {s.prob_best:>8.0%} "
            f"{pts:>8} {trn:>10} {s.ev:>6.2f}"
        )
    if len(stats) >= 2:
        top, second = stats[0], stats[1]
        if top.prob_best < 0.90:
            print(
                f"\nNote: top choice {top.tile} is only P(best)={top.prob_best:.0%} "
                f"(next: {second.tile} at {second.prob_best:.0%}). Increase "
                f"`rollouts` for a confident pick."
            )


def _demo() -> None:
    """Small self-contained demo: evaluate a few discards on a random hand."""
    from random import Random

    from tiles_utils import generate_tile_pool

    rng = Random(7)
    pool = generate_tile_pool()
    rng.shuffle(pool)
    hand = MahjongHand(pool[:13])
    hand.draw(pool[13])
    print("hand:", " ".join(str(t) for t in _default_choices(hand)))
    choices = _default_choices(hand)[:4]
    stats = evaluate_discard_choices(hand, choices=choices, rollouts=30, budget=22)
    print_choice_stats(stats)


def _test() -> None:
    hand = parse_hand('13m35679s24567p55z')
    choices = parse_tiles('6s2p7p3s')
    stats = evaluate_discard_choices_adaptive(hand, choices=choices, budget=22,
                                              initial_rollouts=30, max_rollouts=150, target_prob=0.8)
    print_choice_stats(stats)


if __name__ == "__main__":
    _test()
