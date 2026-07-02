"""Non-regression tests for mcr_scorer.get_won_hand_yakus.

Ported from the former ``mcr_scorer._test_scorer`` helper. Each case is a hand
string mapped to the exact set of yakus (with counts) the scorer is expected to
return for the winning hand.
"""

import pytest

from mahjong_objects import MahjongMCRYaku
from mcr_scorer import get_ordinal_yakus, get_won_hand_yakus
from tiles_utils import parse_hand

Y = MahjongMCRYaku

# hand string -> expected list of (yaku, count)
SCORER_CASES = {
    "123456789p22!333m": [
        (Y.PURE_STRAIGHT, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.ONE_VOIDED_SUIT, 1),
        (Y.NO_HONOR, 1),
    ],
    "123!789p123m789s77z": [
        (Y.OUTSIDE_HAND, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.MIXED_DOUBLE_CHOW, 2),
        (Y.TWO_TERMINAL_CHOWS, 1),
        (Y.EDGE_WAIT, 1),
    ],
    "(111)33!p(999)s111777z": [
        (Y.ALL_PUNGS, 1),
        (Y.DRAGON_PUNG, 1),
        (Y.TWO_CONCEALED_PUNGS, 1),
        (Y.PUNG_OF_TERMINALS_OR_HONORS, 3),
        (Y.ONE_VOIDED_SUIT, 1),
        (Y.SINGLE_WAIT, 1),
    ],
    "(111)33!p111(999)s777z": [
        (Y.ALL_PUNGS, 1),
        (Y.DRAGON_PUNG, 1),
        (Y.DOUBLE_PUNGS, 1),
        (Y.TWO_CONCEALED_PUNGS, 1),
        (Y.PUNG_OF_TERMINALS_OR_HONORS, 3),
        (Y.ONE_VOIDED_SUIT, 1),
        (Y.SINGLE_WAIT, 1),
    ],
    "222234444p2!3455s": [
        (Y.CONCEALED_HAND, 1),
        (Y.TILE_HOG, 2),
        (Y.TWO_CONCEALED_PUNGS, 1),
        (Y.ALL_SIMPLE, 1),
        (Y.MIXED_DOUBLE_CHOW, 1),
        (Y.ONE_VOIDED_SUIT, 1),
    ],
    "2!2334455667788s": [
        (Y.SEVEN_SHIFTED_PAIRS, 1),
        (Y.ALL_SIMPLE, 1),
    ],
    "2!2223333444499s": [
        (Y.QUADRUPLE_CHOW, 1),
        (Y.FULL_FLUSH, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.ALL_CHOWS, 1),
    ],
    "1112!2345678999s": [
        (Y.NINE_GATES, 1),
        (Y.TWO_CONCEALED_PUNGS, 1),
        (Y.SHORT_STRAIGHT, 1),
    ],
    "1!99s19p19m1234567z": [
        (Y.THIRTEEN_ORPHANS, 1),
    ],
    "147s258m369p7!89s11p": [
        (Y.KNITTED_STRAIGHT, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.ALL_CHOWS, 1),
        (Y.EDGE_WAIT, 1),
    ],
    "147!s258m369p11p(789)s": [
        (Y.KNITTED_STRAIGHT, 1),
        (Y.ALL_CHOWS, 1),
    ],
    "147s258m369p2!2277z": [
        (Y.KNITTED_STRAIGHT, 1),
        (Y.ALL_TYPES, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.PUNG_OF_TERMINALS_OR_HONORS, 1),
    ],
    "147s258m369p12!457z": [
        (Y.KNITTED_STRAIGHT, 1),
        (Y.LESSER_HONORS_AND_KNITTED_TILES, 1),
    ],
    "1s258m369p12!34567z": [
        (Y.GREATER_HONORS_AND_KNITTED_TILES, 1),
    ],
    "1111p22s9999m1!166z": [
        (Y.SEVEN_PAIRS, 1),
        (Y.ALL_TYPES, 1),
        (Y.TILE_HOG, 2),
    ],
    "222p(345)m2!34789s11z": [
        (Y.CHICKEN_HAND, 1),
    ],
    "[1111]s111p(2222)78999!m": [
        (Y.OUTSIDE_HAND, 1),
        (Y.CONCEALED_KONG, 1),
        (Y.TWO_CONCEALED_PUNGS, 1),
        (Y.TWO_MELDED_KONGS, 1),
        (Y.DOUBLE_PUNGS, 1),
        (Y.PUNG_OF_TERMINALS_OR_HONORS, 2),
        (Y.NO_HONOR, 1),
    ],
    "[1111]s111p[1111]55m555!z": [
        (Y.THREE_CONCEALED_PUNGS, 1),
        (Y.TRIPLE_PUNG, 1),
        (Y.TWO_CONCEALED_KONGS, 1),
        (Y.ALL_PUNGS, 1),
        (Y.DRAGON_PUNG, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.PUNG_OF_TERMINALS_OR_HONORS, 3),
    ],
    "[2222]s[3333]p[5555]77!m555z": [
        (Y.FOUR_CONCEALED_PUNGS, 1),
        (Y.THREE_KONGS, 1),
        (Y.DRAGON_PUNG, 1),
        (Y.SINGLE_WAIT, 1),
    ],
    "11112222!334444p": [
        (Y.SEVEN_PAIRS, 1),
        (Y.FULL_FLUSH, 1),
        (Y.LOWER_FOUR, 1),
        (Y.REVERSIBLE_TILES, 1),
        (Y.TILE_HOG, 3),
    ],
    "22224444668888s": [
        (Y.ALL_GREEN, 1),
        (Y.SEVEN_PAIRS, 1),
        (Y.FULL_FLUSH, 1),
        (Y.REVERSIBLE_TILES, 1),
        (Y.TILE_HOG, 3),
        (Y.ALL_SIMPLE, 1),
    ],
    "11112222333344s": [
        (Y.QUADRUPLE_CHOW, 1),
        (Y.FULL_FLUSH, 1),
        (Y.LOWER_FOUR, 1),
        (Y.ALL_CHOWS, 1),
        (Y.CONCEALED_HAND, 1),
    ],
    "1223!34m234p11666z": [
        (Y.DRAGON_PUNG, 1),
        (Y.MIXED_DOUBLE_CHOW, 1),
        (Y.ONE_VOIDED_SUIT, 1),
        (Y.EDGE_WAIT, 1),
        (Y.CONCEALED_HAND, 1),
    ],
    "12355789789m1!23s": [
        (Y.ALL_CHOWS, 1),
        (Y.PURE_DOUBLE_CHOW, 1),
        (Y.ONE_VOIDED_SUIT, 1),
        (Y.MIXED_DOUBLE_CHOW, 1),
        (Y.TWO_TERMINAL_CHOWS, 1),
        (Y.CONCEALED_HAND, 1),
    ],
    "123s789m123789p77!z": [
        (Y.OUTSIDE_HAND, 1),
        (Y.MIXED_DOUBLE_CHOW, 2),
        (Y.TWO_TERMINAL_CHOWS, 1),
        (Y.CONCEALED_HAND, 1),
        (Y.SINGLE_WAIT, 1),
    ],
}


@pytest.mark.parametrize("hand_str, expected", list(SCORER_CASES.items()))
def test_get_won_hand_yakus(hand_str, expected):
    _acceptance, _won, yakus = get_won_hand_yakus(parse_hand(hand_str))
    assert get_ordinal_yakus(yakus) == get_ordinal_yakus(expected)
