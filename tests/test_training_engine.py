"""Non-regression tests for the ``training_engine`` public API.

The engine drives the interactive tenpai training game via small JSON-in /
JSON-out functions. Each public function is exercised over a set of
representative, deterministic inputs and its structured output is compared
against a golden snapshot stored in ``golden_training.json``.

Fixed seeds are used for ``new_game`` so the shuffled pool and the two winds are
fully reproducible.

To update the golden file after an intentional behaviour change, run:

    python tests/generate_golden_training.py
"""

import json
import os

import pytest

import training_engine as te
from tests.training_snapshot_util import (
    ANALYZE_CASES,
    EVALUATE_CASES,
    NEW_GAME_SEEDS,
    SCORE_CASES,
    analyze_turn_snapshot,
    evaluate_discard_snapshot,
    new_game_snapshot,
    score_winning_tiles_snapshot,
)

_GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_training.json")

with open(_GOLDEN_PATH, encoding="utf-8") as _golden_file:
    _GOLDEN = json.load(_golden_file)


# --- golden snapshot comparisons ----------------------------------------------
@pytest.mark.parametrize("seed", NEW_GAME_SEEDS)
def test_new_game_snapshot(seed):
    golden = _GOLDEN["new_game"][str(seed)]
    assert new_game_snapshot(seed) == golden


@pytest.mark.parametrize("name", sorted(ANALYZE_CASES))
def test_analyze_turn_snapshot(name):
    assert analyze_turn_snapshot(*ANALYZE_CASES[name]) == _GOLDEN["analyze_turn"][name]


@pytest.mark.parametrize("name", sorted(EVALUATE_CASES))
def test_evaluate_discard_snapshot(name):
    assert (
        evaluate_discard_snapshot(*EVALUATE_CASES[name])
        == _GOLDEN["evaluate_discard"][name]
    )


@pytest.mark.parametrize("name", sorted(SCORE_CASES))
def test_score_winning_tiles_snapshot(name):
    assert (
        score_winning_tiles_snapshot(*SCORE_CASES[name])
        == _GOLDEN["score_winning_tiles"][name]
    )


# --- direct behavioural invariants --------------------------------------------
def test_new_game_is_deterministic_for_a_given_seed():
    assert te.new_game(7) == te.new_game(7)


def test_new_game_different_seeds_differ():
    assert te.new_game(1) != te.new_game(2)


def test_new_game_pool_is_a_full_valid_wall():
    game = json.loads(te.new_game(0))
    pool = game["pool"]
    # 27 suited tiles * 4 + 7 honors * 4 = 136 tiles.
    assert len(pool) == 136
    assert len(set(pool)) == 34
    assert all(pool.count(tile) == 4 for tile in set(pool))
    assert 1 <= game["prevalent_wind"] <= 4
    assert 1 <= game["seat_wind"] <= 4
    assert game["seed"] == 0


def test_new_game_none_seed_generates_valid_seed():
    game = json.loads(te.new_game(None))
    assert isinstance(game["seed"], int)
    assert 0 <= game["seed"] <= 2**32 - 1
    assert len(game["pool"]) == 136


def test_analyze_turn_recommends_a_tile_in_the_hand():
    tiles = ANALYZE_CASES["pure_straight_pinzu_wait"][0]
    result = json.loads(
        te.analyze_turn(json.dumps(tiles), json.dumps([0] * 34))
    )
    assert result["engine_discard"] in tiles
    assert result["engine"]["away"] >= 0
    assert result["engine"]["number"] >= 0


def test_analyze_turn_rejects_a_complete_hand():
    # A completed 14-tile hand has no tile to discard.
    winning = [
        "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
        "1p", "2p", "3p", "1z", "1z",
    ]
    with pytest.raises(ValueError):
        te.analyze_turn(json.dumps(winning), json.dumps([0] * 34))


def test_evaluate_discard_removes_the_chosen_tile():
    tiles = [
        "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
        "1p", "2p", "3p", "4p", "5p",
    ]
    result = json.loads(
        te.evaluate_discard(json.dumps(tiles), "1p", json.dumps([0] * 34))
    )
    assert "1p" not in result["acceptance"]
    assert result["away"] >= 0
    assert result["number"] >= 0


def test_visible_vector_reduces_acceptance_number():
    from mahjong_objects import MahjongTile

    tiles = [
        "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
        "1p", "2p", "3p", "4p", "5p",
    ]
    none_visible = json.loads(
        te.analyze_turn(json.dumps(tiles), json.dumps([0] * 34))
    )
    visible = [0] * 34
    for accepted in none_visible["engine"]["acceptance"]:
        visible[MahjongTile(accepted).index] = 4  # all copies already seen
    some_visible = json.loads(
        te.analyze_turn(json.dumps(tiles), json.dumps(visible))
    )
    assert some_visible["engine"]["number"] < none_visible["engine"]["number"]


def test_score_winning_tiles_sorted_by_points_desc():
    result = score_winning_tiles_snapshot(*SCORE_CASES["two_sided_wait"])
    points = [entry["points"] for entry in result]
    assert points == sorted(points, reverse=True)
    acceptance = SCORE_CASES["two_sided_wait"][1]
    assert {entry["tile"] for entry in result} == set(acceptance)
    for entry in result:
        assert entry["points"] > 0
        assert entry["won_groups"]
