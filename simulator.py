"""
    simulate a game
"""
from random import shuffle
from statistics import median, mean

from mahjong_objects import MahjongHand
from tile_acceptance_calculator import get_tile_to_discard_from
from tiles_utils import generate_tile_pool


def play_a_game() -> int:
    """
    Simulate a single player playing by the recommendations of the program
    :return: the number of turns taken
    """
    game_tiles = generate_tile_pool()
    shuffle(game_tiles)
    hand_tiles = game_tiles[:13]
    game_tiles = game_tiles[13:]
    hand = MahjongHand(hand_tiles)
    print(f"Starting hand : {hand}")
    nb_away = 14
    turn = 0
    while nb_away > 0:
        turn += 1
        print(f"Turn {turn}")
        draw_tile = game_tiles.pop()
        hand.draw(draw_tile)
        print(f"Draw {draw_tile} : {hand}")

        to_discard, nb_away = get_tile_to_discard_from(hand)
        print(f"Discard {to_discard}, {nb_away} away")
        hand.discard(to_discard)

    print(f"Final hand: {hand}")
    return turn


if __name__ == "__main__":
    turns_taken = []
    for _ in range(100):
        turns_taken.append(play_a_game())
    print(f"100 tries : min {min(turns_taken)} turns, max {max(turns_taken)} turns,"
          f" {mean(turns_taken)} turns average, {median(turns_taken)} turn median")
