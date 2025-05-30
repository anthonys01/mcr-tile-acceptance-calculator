"""
    simulate a game
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from random import shuffle
from statistics import median, mean

from mahjong_objects import MahjongHand
from tile_acceptance_calculator import get_tile_to_discard_from
from tiles_utils import generate_tile_pool


def play_a_game(stop_at_nb_away=0):
    """
    Simulate a single player playing by the recommendations of the program
    :return: the number of turns taken, and the hand type(s)
    """
    game_tiles = generate_tile_pool()
    shuffle(game_tiles)
    hand_tiles = game_tiles[:13]
    game_tiles = game_tiles[13:]
    hand = MahjongHand(hand_tiles)
    # print(f"Starting hand : {hand}")
    nb_away = 14
    turn = 0
    hand_types = []
    while nb_away > stop_at_nb_away:
        turn += 1
        # print(f"Turn {turn}")
        draw_tile = game_tiles.pop()
        hand.draw(draw_tile)
        #print(f"Draw {draw_tile} : {hand}")

        to_discard, nb_away, hand_types = get_tile_to_discard_from(hand)
        # print(f"Discard {to_discard}, {nb_away} away")
        hand.discard(to_discard)

    # print(f"Final hand: {hand}")
    # print(f"Hand type : {hand_types}")
    return turn, hand_types


if __name__ == "__main__":
    TRIES = 100
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(play_a_game, [0] * TRIES))
    turns_taken = []
    hand_types_count = Counter()
    for turns, hand_type in results:
        turns_taken.append(turns)
        hand_types_count.update(hand_type)
    print(f"{TRIES} tries : min {min(turns_taken)} turns, max {max(turns_taken)} turns,"
          f" {mean(turns_taken)} turns average, {median(turns_taken)} turn median")
    print(hand_types_count)
