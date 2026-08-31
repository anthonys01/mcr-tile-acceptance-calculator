"""Non-regression tests for tile_acceptance_calculator public functions.

``analyze_hand`` and ``get_tile_to_discard_from`` are exercised over a set of
representative hands (every hand from the module ``__main__`` block plus a few
extra hand types). Their structured output is compared against a golden
snapshot stored in ``golden_acceptance.json``.

To update the golden file after an intentional behaviour change, run:

    python tests/generate_golden.py
"""

import json
import os

import pytest

from mahjong_objects import MahjongHand
from hand_types.basic import _reachable_acceptance
from tests.snapshot_util import SNAPSHOT_HANDS, snapshot_for_hand
from tile_acceptance_calculator import (
    analyze_hand,
    get_discard_choices,
    get_tile_to_discard_from,
)
from tiles_utils import parse_hand

_GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_acceptance.json")

with open(_GOLDEN_PATH, encoding="utf-8") as _golden_file:
    _GOLDEN = json.load(_golden_file)


@pytest.mark.parametrize("hand_str", SNAPSHOT_HANDS)
def test_analyze_and_discard_snapshot(hand_str):
    assert hand_str in _GOLDEN, (
        f"No golden snapshot for {hand_str!r}. Run tests/generate_golden.py."
    )
    assert snapshot_for_hand(hand_str) == _GOLDEN[hand_str]


def test_analyze_hand_rejects_too_few_tiles():
    hand = MahjongHand(parse_hand("123m").hand_tiles)
    with pytest.raises(AttributeError):
        analyze_hand(hand)


def test_get_tile_to_discard_rejects_non_discardable_hand():
    # 13-tile hand does not need a discard.
    hand = parse_hand("45s13447m135799p")
    assert not hand.needs_to_discard()
    with pytest.raises(AttributeError):
        get_tile_to_discard_from(hand)


def test_wait_yakus_require_a_single_winning_tile():
    """4568999p234567s waits on both 7p and 8p, so no wait yaku applies.

    Counting Edge Wait on the 789p / 99p parsing used to push this hand to a
    bogus 8 points, while 8p (pairing 88p next to the 999p pung) is an equally
    valid winning tile.
    """
    _results, acceptance, _best, _away, _yakus = analyze_hand(
        parse_hand("4568999p234567s")
    )
    assert not acceptance.get("Basic")


def test_discard_ranking_prefers_value_over_raw_acceptance():
    """5m456899p2345679s: raw acceptance says 5m, the better discard is 8p.

    Discarding 5m accepts 22 tiles against 19 for 8p, but every 5m route tops out
    at exactly 8 points, while keeping 5m (i.e. discarding 8p) keeps Mixed Shifted
    Chows and Triple Chows reachable and opens manzu chows that are legal 8-point
    hands on a self-draw. Monte-Carlo rollouts agree with 8p.
    """
    hand = parse_hand("5m456899p2345679s")
    results, acceptance, best_results, _away, yakus = analyze_hand(hand)
    choices = get_discard_choices(best_results, results, acceptance, hand, yakus)

    by_tile = {str(tile): choice for choice in choices for tile in [choice[0]]}
    assert by_tile["5m"][2] > by_tile["8p"][2], "5m must still win on raw acceptance"
    assert by_tile["8p"][5] > by_tile["5m"][5], "8p must win on the composite score"
    assert str(choices[0][0]) == "8p"
    assert choices[0][4] is True


def test_discard_ranking_keeps_completed_group():
    """13m35679s24567p55z: raw acceptance says 6s, the better discard is 7p.

    Discarding 6s accepts 16 tiles against 15 for 7p, but no MCR blueprint uses
    the completed 567s chow, so breaking it looks free to them while it collapses
    the general-purpose ukeire from 52 tiles to 20. Monte-Carlo rollouts rank 7p
    first (28.7% win rate against 24.0% for 6s).
    """
    hand = parse_hand("13m35679s24567p55z")
    results, acceptance, best_results, _away, yakus = analyze_hand(hand)
    choices = get_discard_choices(best_results, results, acceptance, hand, yakus)

    by_tile = {str(tile): choice for choice in choices for tile in [choice[0]]}
    assert by_tile["6s"][2] > by_tile["7p"][2], "6s must still win on raw acceptance"
    assert by_tile["7p"][5] > by_tile["6s"][5], "7p must win on the composite score"
    assert str(choices[0][0]) == "7p"
    assert choices[0][4] is True


def test_acceptance_excludes_tiles_that_break_the_winning_wait():
    """134789m12345p599s: 2m is not acceptance even though the plan needs it.

    Discarding 4m leaves 13m 789m 123p 45p 99s, two tiles away from
    123m 789m 123p 456p 99s. That hand only reaches 8 points when 2m is the
    *winning* tile (Closed Wait, +1): drawing 6p first leaves a lone 2m wait and
    wins, while drawing 2m first leaves a two-sided 3p/6p wait worth 7 points,
    i.e. an illegal hand. Only 6p is real progress.
    """
    hand = parse_hand("134789m12345p599s")
    results, acceptance, best_results, _away, yakus = analyze_hand(hand)
    assert best_results == ["Basic"]
    assert {str(tile) for tile in acceptance["Basic"]} == {"6p"}

    choices = get_discard_choices(best_results, results, acceptance, hand, yakus)
    by_tile = {str(choice[0]): choice for choice in choices}
    for tile in ("4m", "5s"):
        assert {str(t) for t in by_tile[tile][1]} == {"6p"}


def test_reachable_acceptance_keeps_single_missing_tile():
    """A one-tile-away plan always accepts that tile - it is the winning draw."""
    two_man, six_pin = parse_hand("2m6p").get_free_tiles()
    assert _reachable_acceptance([two_man], (two_man,)) == (two_man,)
    # 2m is the only scoring winning tile, so it must not be drawn first
    assert _reachable_acceptance([two_man, six_pin], (two_man,)) == (six_pin,)
    # both orders legal -> both tiles are acceptance
    reachable = _reachable_acceptance([two_man, six_pin], (two_man, six_pin))
    assert set(reachable) == {two_man, six_pin}
    # a duplicate scoring tile can be drawn first, the second copy still wins
    assert _reachable_acceptance([two_man, two_man], (two_man,)) == (two_man,)
    assert _reachable_acceptance([two_man, six_pin], ()) == ()
