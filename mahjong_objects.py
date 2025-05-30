"""
    mahjong objects and enum
"""
from enum import Enum, auto
from random import sample


class Family(Enum):
    """
        tile families
    """
    BAMBOO = "s"
    CHARACTER = "m"
    CIRCLE = "p"
    HONOR = "z"

class Constraint(Enum):
    """
        tile group constraints
    """
    NONE = auto()
    ORDINARY = auto()
    NO_HONOR = auto()
    FULL_TERMINALS = auto()
    FULL_HONORS = auto()
    FULL_TERMINALS_OR_HONORS = auto()
    CONTAINS_TERMINALS_OR_HONORS = auto()
    FIRST_FOUR = auto()
    LAST_FOUR = auto()
    FIRST_THREE = auto()
    MIDDLE_THREE = auto()
    LAST_THREE = auto()
    EVEN = auto()
    SYMMETRIC = auto()
    GREEN = auto()
    CONTAINS_FIVE = auto()
    FLUSH_BAMBOO = auto()
    FLUSH_CIRCLE = auto()
    FLUSH_CHARACTER = auto()


class MahjongTile:
    """
        tile
    """
    def __init__(self, tile: str=None, *, number: int=-1, family: Family=None):
        if tile:
            self.number = int(tile[0])
            self.family = Family(tile[1])
        else:
            self.number = number
            self.family: Family = family

    def is_wind(self) -> bool:
        """
        is wind tile
        :return: true if wind
        """
        return self.family == Family.HONOR and 1 <= self.number <= 4

    def is_dragon(self) -> bool:
        """
        is dragon tile
        :return: true if dragon
        """
        return self.family == Family.HONOR and  5 <= self.number <= 7

    def is_honor(self):
        """
        is an honor tile
        :return: True if honor tile
        """
        return self.family == Family.HONOR

    def is_compatible_with_half_flush(self, family: Family):
        """
        can be a half flush tile
        :param family: half flush family
        :return: true is compatible
        """
        return self.family in (family, Family.HONOR)

    def is_symmetric(self):
        """
        is a symmetric tile
        :return: True if symmetric
        """
        return str(self) in {"5z", "1p", "2p", "3p", "4p", "5p", "8p", "9p", "2s", "4s", "5s", "6s", "8s", "9s"}

    def is_green(self):
        """
        is a green tile
        :return: True if green
        """
        return str(self) in {"6z", "2s", "3s", "4s", "6s", "8s"}

    def is_even(self):
        """
        is an even tile
        :return: True if even
        """
        return self.family != Family.HONOR and self.number % 2 == 0

    def is_terminal(self):
        """
        is a terminal tile
        :return: True if terminal
        """
        return self.family != Family.HONOR and self.number in (1, 9)

    def is_ordinary(self):
        """
        is an ordinary tile
        :return: True if ordinary
        """
        return self.family != Family.HONOR and 2 <= self.number <= 8

    def __eq__(self, other):
        if isinstance(other, MahjongTile):
            return self.number == other.number and self.family == other.family
        return False

    def __hash__(self):
        return hash((self.number, self.family))

    def __str__(self):
        return f"{self.number}{self.family.value}"

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return self.family.value < other.family.value or self.family == other.family and self.number < other.number


MahjongTiles = list[MahjongTile]
MahjongGroup = tuple[MahjongTile, ...]
MahjongGroups = tuple[MahjongGroup, ...]
MahjongCombination = tuple[MahjongGroups, MahjongTiles]
MahjongGroupAndResidue = tuple[MahjongGroup, MahjongTiles, list[Constraint]]

class MahjongGroupInstance:
    """
        represent a mahjong proto-group
    """
    def __init__(self, group: tuple):
        self.group = group
        self.possible_full_groups: dict[Constraint, list[MahjongGroup]] = {}

    def __str__(self):
        return str(self.group)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return isinstance(other, MahjongGroupInstance) and other.group == self.group

    def __hash__(self):
        return hash(self.group)

    def __lt__(self, other):
        return self.group < other.group

class MahjongHand:
    """
        mahjong hand
    """
    def __init__(self, hand_tiles: MahjongTiles=None):
        self.hand_tiles: MahjongTiles = hand_tiles
        self.declared_tiles = []


    def get_missing_tiles(self, tiles: MahjongTiles) -> MahjongTiles:
        """
        get missing tiles in hand for given tiles
        :param tiles: tiles to find
        :return: the missing tiles in the hand for given tiles
        """
        current_hand = list(self.hand_tiles)
        not_found = []
        for tile in tiles:
            if tile in current_hand:
                current_hand.remove(tile)
            else:
                not_found.append(tile)
        return not_found

    def get_residue_after(self, tiles: MahjongTiles) -> MahjongTiles:
        """
        get the rest of the tiles after removing given tiles
        :param tiles: tiles to remove
        :return: the rest of the tiles
        """
        current_hand = list(self.hand_tiles)
        for tile in tiles:
            if tile in current_hand:
                current_hand.remove(tile)
        return current_hand

    def __str__(self):
        rep = ""
        for family in Family:
            tiles: list[int] = [tile.number for tile in get_tiles_from_family(self.hand_tiles, family)]
            if tiles:
                rep += "".join(str(t) for t in sorted(tiles)) + family.value
        return rep

    def __repr__(self):
        return str(self)

def get_tiles_from_family(tiles: MahjongTiles, family: Family):
    """
    filter given tiles and return only the one matching family
    :param tiles: tiles to filter
    :param family: family
    :return: the tiles matching given family
    """
    found: MahjongTiles = []
    for tile in tiles:
        if tile.family == family:
            found.append(tile)
    return found

def _generate_tile_pool(honor_tiles_multiplier=4) -> MahjongTiles:
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
    pool = _generate_tile_pool(honor_tiles_multiplier)
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
