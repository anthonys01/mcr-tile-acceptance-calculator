"""
    functions and constants to get/generate tiles
"""
from random import sample

from mahjong_objects import MahjongTiles, Family, MahjongTile, MahjongHand


def generate_tile_pool(honor_tiles_multiplier=4) -> MahjongTiles:
    """
    generate the game tile pool
    :param honor_tiles_multiplier: honor tile multiplier, 4 tiles is the default
    :return: list of all tiles
    """
    pool = []
    for number in range(1, 10):
        pool += [MahjongTile(number=number, family=Family.BAMBOO)] * 4
        pool += [MahjongTile(number=number, family=Family.CIRCLE)] * 4
        pool += [MahjongTile(number=number, family=Family.CHARACTER)] * 4
    for number in range(1, 8):
        pool += [MahjongTile(number=number, family=Family.HONOR)] * honor_tiles_multiplier
    return pool

def generate_random_closed_hand(honor_tiles_multiplier=4):
    """
    generate a random hand
    :return: hand
    """
    pool = generate_tile_pool(honor_tiles_multiplier)
    return MahjongHand(sample(pool, 13))

def parse_tiles(tiles: str) -> MahjongTiles:
    """
    parse tile pattern and return a list of mahjong tiles
    :param tiles: tiles pattern
    :return: list of tiles
    """
    current_numbers: list[int] = []
    parsed: MahjongTiles = []
    for char in tiles:
        if char in "123456789":
            current_numbers.append(int(char))
        elif char in Family:
            family = Family(char)
            parsed += [MahjongTile(number=num, family=family) for num in current_numbers]
            current_numbers.clear()
        else:
            raise AttributeError(f'Unknown character {char}')
    if current_numbers:
        raise AttributeError(f'Missing family denomination for {"".join(str(num) for num in current_numbers)}')
    return parsed

SYMMETRIC_TILES = parse_tiles("5z1234589p245689s")
WINDS_TILES = parse_tiles("1234z")
DRAGONS_TILES = parse_tiles("567z")
HONOR_TILES = WINDS_TILES + DRAGONS_TILES
FIRST_FOUR_TILES = parse_tiles("1234s1234p1234m")
LAST_FOUR_TILES = parse_tiles("6789s6789p6789m")
FAMILY_TILES = {
    Family.CHARACTER: parse_tiles("123456789m"),
    Family.BAMBOO: parse_tiles("123456789s"),
    Family.CIRCLE: parse_tiles("123456789p"),
    Family.HONOR: HONOR_TILES
}
