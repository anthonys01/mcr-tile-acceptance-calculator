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
from acceptance import _knitted_waits
from hand_types.basic import _reachable_acceptance
from tests.snapshot_util import SNAPSHOT_HANDS, snapshot_for_hand
from tile_acceptance_calculator import (
    analyze_hand,
    analyze_hand_structured,
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


def test_knitted_discards_report_their_acceptance():
    """147m28899s334566p: knitted discards must not show an empty acceptance.

    The combination is (1m4m7m)(2s8s)(3p6p)(3p4p5p)(9s9s) with 8s and 6p left
    over. The leading groups are knitted proto-groups - the tiles held out of a
    {n, n+3, n+6} triple - which the standard wait finder cannot read: it sees
    (2s, 8s) as a two-tile group with no simple wait and credits it nothing. All
    three knitted discards were therefore displayed as accepting 0 tiles.
    """
    hand = parse_hand("147m28899s334566p")
    results, acceptance, best_results, _away, yakus = analyze_hand(hand)
    assert best_results == ["Knitted"]
    assert {str(tile) for tile in acceptance["Knitted"]} == {"5s", "9p"}

    choices = get_discard_choices(best_results, results, acceptance, hand, yakus)
    by_tile = {str(choice[0]): choice for choice in choices}
    for tile in ("3p", "6p", "8s"):
        assert {str(t) for t in by_tile[tile][1]} == {"5s", "9p"}, tile
        assert by_tile[tile][2] == 8, tile


def test_knitted_waits_completes_the_triple():
    """A partial knitted group accepts exactly the tiles missing from its triple."""
    two_sou, five_sou, eight_sou = parse_hand("258s").get_free_tiles()
    assert _knitted_waits((two_sou, eight_sou)) == {five_sou}
    assert _knitted_waits((five_sou,)) == {two_sou, eight_sou}
    assert _knitted_waits((two_sou, five_sou, eight_sou)) == set()
    # an empty group carries no family, so it cannot name any tile
    assert _knitted_waits(()) == set()


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


def test_reported_distance_is_that_of_the_recommended_discard():
    """134789m12345p599s: the pick stays 2 away although 1 away is reachable.

    ``4m``/``5s`` reach 1 away with 4 tiles of acceptance, but the ranking prefers
    ``1m`` (2 away, 27 tiles). The reported distance must be the one the
    recommended discard actually leaves, not the best reachable one - otherwise
    the UI claims a shanten the engine did not take, and the training page flags
    its own recommendation as suboptimal.
    """
    data = analyze_hand_structured("134789m12345p599s")

    recommended = [d for d in data["discards"] if d["recommended"]]
    assert [d["tile"] for d in recommended] == ["1m"]
    assert data["recommended_away_after_discard"] == recommended[0]["away_after_discard"]
    assert data["recommended_away_after_discard"] == 2
    # A closer discard exists and is still reported, so the UI can show both.
    assert data["away_after_discard"] == 1
    assert min(d["away_after_discard"] for d in data["discards"]) == 1


def test_reported_distance_matches_the_best_one_when_nothing_is_given_up():
    data = analyze_hand_structured("5m456899p2345679s")
    assert data["recommended_away_after_discard"] == data["away_after_discard"]


def test_pattern_hand_type_keeps_every_equally_close_instance():
    """46789m34s3444567p is two away from two different Mixed Shifted Chows.

    234s 345p 456m (missing 2s, 5m) and 345s 456m 567p (missing 5s, 5m) are
    equally close. Only the first one used to be kept, so discarding 3p or 4p
    (which only the second one allows) showed acceptance tiles with no hand type.
    """
    data = analyze_hand_structured("46789m34s3444567p")
    mixed_shifted = next(
        hand_type for hand_type in data["hand_types"]
        if hand_type["name"] == "Mixed Shifted"
    )
    residues = {tuple(combo["residue"]) for combo in mixed_shifted["combos"]}
    assert residues == {("6p", "7p"), ("3p", "4p")}
    assert set(mixed_shifted["acceptance"]) == {"2s", "5m", "5s"}

    by_tile = {discard["tile"]: discard for discard in data["discards"]}
    for tile in ("3p", "4p"):
        # 2s only helps the other instance, it must not leak into this discard
        assert by_tile[tile]["by_type"] == {"Mixed Shifted": ["5m", "5s"]}, tile
        assert by_tile[tile]["acceptance"] == ["5m", "5s"], tile
    for tile in ("6p", "7p"):
        assert by_tile[tile]["by_type"] == {"Mixed Shifted": ["2s", "5m"]}, tile


def test_every_discard_acceptance_is_attributed_to_a_hand_type():
    data = analyze_hand_structured("46789m34s3444567p")
    for discard in data["discards"]:
        attributed = set().union(*map(set, discard["by_type"].values()))
        assert attributed == set(discard["acceptance"]), discard["tile"]
