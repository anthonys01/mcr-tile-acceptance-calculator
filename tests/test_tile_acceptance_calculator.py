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
from tests.snapshot_util import SNAPSHOT_HANDS, snapshot_for_hand
from tile_acceptance_calculator import analyze_hand, get_tile_to_discard_from
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
