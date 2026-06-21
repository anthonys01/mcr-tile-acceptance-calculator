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
        pool += [
            MahjongTile(number=number, family=Family.HONOR)
        ] * honor_tiles_multiplier
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
            parsed += [
                MahjongTile(number=num, family=family) for num in current_numbers
            ]
            current_numbers.clear()
        else:
            raise AttributeError(f"Unknown character {char}")
    if current_numbers:
        raise AttributeError(
            f"Missing family denomination for {''.join(str(num) for num in current_numbers)}"
        )
    return parsed


def parse_hand(tiles: str) -> MahjongHand:
    current_numbers: list[int] = []
    parsed: MahjongTiles = []
    reading_declared_group = False
    reading_concealed_kong = False
    declared_group = []
    declared_group_nums = []
    concealed_kong = []
    concealed_kong_nums = []
    winning_tile_number = None
    winning_tile = None
    declared_groups = set()
    kongs = set()
    for char in tiles:
        if char in "123456789":
            current_numbers.append(int(char))
            if reading_declared_group:
                declared_group.append(int(char))
            elif reading_concealed_kong:
                concealed_kong.append(int(char))
        elif char in Family:
            family = Family(char)
            if not current_numbers:
                raise AttributeError("No number before family denomination")
            if reading_concealed_kong or reading_declared_group:
                raise AttributeError(
                    "Cannot designate family inside declared group or concealed kong"
                )
            if winning_tile_number:
                winning_tile = MahjongTile(number=winning_tile_number, family=family)
                winning_tile_number = None
            parsed += [
                MahjongTile(number=num, family=family) for num in current_numbers
            ]
            for kong_num in concealed_kong_nums:
                kong = [MahjongTile(number=num, family=family) for num in kong_num]
                kongs.add(tuple(kong))
            for declared_num in declared_group_nums:
                declared = [
                    MahjongTile(number=num, family=family) for num in declared_num
                ]
                declared_groups.add(tuple(declared))
                if len(declared) == 4:
                    kongs.add(tuple(declared))
            concealed_kong_nums.clear()
            declared_group_nums.clear()
            current_numbers.clear()
        elif char == "!":
            if reading_declared_group or reading_concealed_kong:
                raise AttributeError(
                    "Winning tile cannot be in a declared group or kong"
                )
            if not current_numbers:
                raise AttributeError("Missing current numbers for winning tile")
            if winning_tile or winning_tile_number:
                raise AttributeError("Wining tile already set")
            winning_tile_number = current_numbers[-1]
        elif char in "([":
            if reading_declared_group or reading_concealed_kong:
                raise AttributeError("Cannot nest declared groups or concealed kongs")
            if char == "(":
                reading_declared_group = True
            elif char == "[":
                reading_concealed_kong = True
        elif char == ")":
            if not reading_declared_group:
                raise AttributeError("Closing parenthesis without opening parenthesis")
            reading_declared_group = False
            if not (3 <= len(declared_group) <= 4):
                raise AttributeError(
                    f"Declared group must be 3 or 4 tiles, got {declared_group}"
                )
            nums = list(sorted(declared_group))
            if len(nums) == 4 and len(set(nums)) != 1:
                raise AttributeError(
                    f"Exposed kong must be 4 identical tiles, got {nums}"
                )
            if len(set(nums)) == 1 or (
                len(nums) == 3 and nums[2] - nums[1] == 1 and nums[1] - nums[0] == 1
            ):
                declared_group_nums.append(declared_group[:])
                declared_group.clear()
            else:
                raise AttributeError(f"Invalid group {nums}")
        elif char == "]":
            if not reading_concealed_kong:
                raise AttributeError("Closing bracket without opening bracket")
            reading_concealed_kong = False
            if len(concealed_kong) != 4 or len(set(concealed_kong)) != 1:
                raise AttributeError(
                    f"Concealed kong must be 4 identical tiles, got {concealed_kong}"
                )
            concealed_kong_nums.append(concealed_kong[:])
            concealed_kong.clear()
        else:
            raise AttributeError(f"Unknown character {char}")
    if current_numbers:
        raise AttributeError(
            'Missing family denomination for {"".join(str(num) for num in current_numbers)}'
        )
    if reading_concealed_kong:
        raise AttributeError("Missing closing bracket for concealed kong")
    if reading_declared_group:
        raise AttributeError("Missing closing parenthesis for declared group")
    hand = MahjongHand(parsed)
    hand.declared_tiles = declared_groups
    hand.kongs = kongs
    if not winning_tile:
        winning_tile = parsed[-1]
    hand.drawn_tile = winning_tile
    return hand


SYMMETRIC_TILES = parse_tiles("5z1234589p245689s")
WINDS_TILES = parse_tiles("1234z")
DRAGONS_TILES = parse_tiles("567z")
HONOR_TILES = WINDS_TILES + DRAGONS_TILES
FIRST_FOUR_TILES = parse_tiles("1234s1234p1234m")
LAST_FOUR_TILES = parse_tiles("6789s6789p6789m")
ORPHAN_TILES = parse_tiles("19s19p19m") + HONOR_TILES
FAMILY_TILES = {
    Family.CHARACTER: parse_tiles("123456789m"),
    Family.BAMBOO: parse_tiles("123456789s"),
    Family.CIRCLE: parse_tiles("123456789p"),
    Family.HONOR: HONOR_TILES,
}


if __name__ == "__main__":
    hand = parse_hand("[1111]s111p(2222)(789)99!m")
    print(hand.hand_tiles)
    print(hand.declared_tiles)
    print(hand.kongs)
