"""JSON-in / JSON-out bridge that runs :mod:`rollout_evaluator` client-side.

Pyodide has no ``multiprocessing`` / ``ProcessPoolExecutor``, so the CPython
parallelism (rollouts fanned out across CPU cores) is reproduced in the browser
by a **pool of Web Workers**, each hosting its own Pyodide instance. The unit of
parallel work is the pure function :func:`rollout_evaluator._rollout_task`, which
maps one ``(choice, rollout)`` pair to ``(won, turns, points)``.

This module exposes three small JSON functions that the JS orchestrator calls:

* :func:`prepare`   - resolve the candidate discards and pre-compute the shared
  context (per-choice 13-tile counts, the unseen wall, run parameters). Called
  once, on any worker.
* :func:`run_chunk` - the worker hot path: run a batch of ``(choice, rollout)``
  pairs and return their raw outcomes. Called many times, spread across workers.
* :func:`aggregate` - fold all raw outcomes back into the exact same statistics
  the desktop tool produces (Wilson CI + paired-bootstrap ``P(best)``), so the
  browser ranking is identical to :func:`rollout_evaluator.evaluate_discard_choices`.

**Common Random Numbers across workers.** ``_crn_seed(base_seed, r)`` depends only
on the rollout index ``r`` (and the unseen pool, which is identical for every
choice). So it does not matter which worker computes a given ``(choice, r)`` pair
- rollout ``r`` faces the same determinized wall everywhere. Reassembling the full
``win_matrix[choice][r]`` in :func:`aggregate` therefore yields byte-for-byte the
same paired bootstrap as the single-process desktop run.
"""
import json

from mahjong_objects import MahjongHand
from tiles_utils import parse_hand, parse_tiles
from shanten_oracle import counts_from_tiles
from discard_policy import _INDEX_TO_TILE
from rollout_evaluator import (
    _rollout_task,
    _crn_seed,
    _prob_best_bootstrap,
    _build_stats,
    _default_choices,
    _coerce_choices,
    DEFAULT_ROLLOUTS,
    DEFAULT_BUDGET,
)

DEFAULT_BASE_SEED = 0xC0FFEE
BOOTSTRAP_RESAMPLES = 5000


def _resolve_choices(hand: MahjongHand, choices_str: str):
    """Return the candidate discard tiles: an explicit shortlist, or all distinct
    hand tiles when ``choices_str`` is empty."""
    choices_str = (choices_str or "").strip()
    if not choices_str:
        return _default_choices(hand)
    return _coerce_choices(parse_tiles(choices_str), hand)


def prepare(
    hand_str: str,
    choices_str: str = "",
    rollouts: int = DEFAULT_ROLLOUTS,
    budget: int = DEFAULT_BUDGET,
    prevalent_wind: int = 0,
    seat_wind: int = 0,
    playout: str = "greedy",
    base_seed: int = DEFAULT_BASE_SEED,
) -> str:
    """Resolve the candidate discards and build the shared rollout context.

    :param hand_str: a 14-tile hand in the usual notation, e.g. ``13m35679s24567p55z``.
    :param choices_str: optional shortlist of discards (e.g. ``6s2p7p3s``); empty
        means "evaluate every distinct tile in the hand".
    :return: a JSON context object consumed by :func:`run_chunk` / :func:`aggregate`
        and echoed back to JS to drive the worker pool (it lists the candidates and
        the total rollout count so the UI can build the task list and a progress bar).
    """
    hand = parse_hand(hand_str)
    if not hand.needs_to_discard():
        raise ValueError(
            f"Hand must have 14 tiles (a tile to discard); got {len(hand.hand_tiles)}."
        )
    counts14 = counts_from_tiles(hand.get_free_tiles())
    choices = _resolve_choices(hand, choices_str)

    unseen = [4 - counts14[idx] for idx in range(34)]
    hand13 = []
    for tile in choices:
        h = list(counts14)
        h[tile.index] -= 1
        hand13.append(h)

    ctx = {
        "choices": [{"index": t.index, "name": str(t)} for t in choices],
        "hand13": hand13,
        "unseen": unseen,
        "rollouts": int(rollouts),
        "budget": int(budget),
        "pw": int(prevalent_wind),
        "sw": int(seat_wind),
        "playout": playout,
        "base_seed": int(base_seed),
    }
    return json.dumps(ctx)


def run_chunk(ctx_json: str, pairs_json: str) -> str:
    """Worker hot path: run a batch of ``(choice_index, rollout_index)`` pairs.

    :param ctx_json: the context object produced by :func:`prepare`.
    :param pairs_json: a JSON list of ``[choice_index, rollout_index]`` pairs.
    :return: a JSON list of ``[choice_index, rollout_index, won(0/1), turns, points]``.
    """
    ctx = json.loads(ctx_json)
    pairs = json.loads(pairs_json)
    hand13 = ctx["hand13"]
    unseen = tuple(ctx["unseen"])
    budget = ctx["budget"]
    pw = ctx["pw"]
    sw = ctx["sw"]
    playout = ctx["playout"]
    base_seed = ctx["base_seed"]

    out = []
    for ci, r in pairs:
        args = (
            ci,
            r,
            tuple(hand13[ci]),
            unseen,
            _crn_seed(base_seed, r),
            budget,
            pw,
            sw,
            playout,
        )
        c_i, r_i, won, turns, points = _rollout_task(args)
        out.append([c_i, r_i, 1 if won else 0, turns, points])
    return json.dumps(out)


def aggregate(ctx_json: str, results_json: str) -> str:
    """Fold all raw rollout outcomes into the ranked ChoiceStats table.

    Reconstructs the paired ``win_matrix[choice][rollout]`` from the (possibly
    out-of-order, concatenated-from-many-workers) results, then applies the exact
    Wilson-CI + paired-bootstrap ``P(best)`` statistics used by the desktop tool.

    :param results_json: a JSON list of ``[ci, r, won, turns, points]`` rows.
    :return: a JSON list of per-choice result dicts, ranked best-first.
    """
    ctx = json.loads(ctx_json)
    results = json.loads(results_json)
    choices_meta = ctx["choices"]
    n_choices = len(choices_meta)
    rollouts = ctx["rollouts"]
    base_seed = ctx["base_seed"]

    win_matrix = [[0] * rollouts for _ in range(n_choices)]
    wins = {ci: 0 for ci in range(n_choices)}
    points_sum = {ci: 0 for ci in range(n_choices)}
    turns_sum = {ci: 0 for ci in range(n_choices)}

    for ci, r, won, turns, points in results:
        if won:
            win_matrix[ci][r] = 1
            wins[ci] += 1
            points_sum[ci] += points
            turns_sum[ci] += turns

    prob_best = _prob_best_bootstrap(
        win_matrix, resamples=BOOTSTRAP_RESAMPLES, seed=base_seed
    )
    choices_tiles = [_INDEX_TO_TILE[c["index"]] for c in choices_meta]
    n_by_choice = {ci: rollouts for ci in range(n_choices)}
    stats = _build_stats(
        choices_tiles, wins, points_sum, turns_sum, n_by_choice, prob_best
    )

    table = [
        {
            "tile": str(s.tile),
            "rollouts": s.rollouts,
            "wins": s.wins,
            "win_rate": s.win_rate,
            "ci_low": s.ci_low,
            "ci_high": s.ci_high,
            "prob_best": s.prob_best,
            "avg_points": s.avg_points,
            "avg_turns_to_win": s.avg_turns_to_win,
            "ev": s.ev,
        }
        for s in stats
    ]
    return json.dumps(table)
