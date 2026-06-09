"""
    mahjong objects and enum
"""
from enum import Enum, auto


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



_SYMMETRIC_STR = {"5z", "1p", "2p", "3p", "4p", "5p", "8p", "9p", "2s", "4s", "5s", "6s", "8s", "9s"}
_GREEN_STR = {"6z", "2s", "3s", "4s", "6s", "8s"}


class MahjongTile:
    """
        tile

        Tiles are interned (flyweight): two tiles with the same number and family
        are guaranteed to be the same object. This makes equality an identity check
        and lets us precompute the hash and all the boolean predicates once.
    """
    __slots__ = ("number", "family", "_str", "_hash", "_order",
                 "_is_honor", "_is_wind", "_is_dragon",
                 "_is_symmetric", "_is_green", "_is_even",
                 "_is_terminal", "_is_ordinary")

    _cache: dict = {}

    def __new__(cls, tile: str=None, *, number: int=-1, family: Family=None):
        if tile:
            number = int(tile[0])
            family = Family(tile[1])
        key = (number, family)
        existing = cls._cache.get(key)
        if existing is not None:
            return existing

        obj = super().__new__(cls)
        obj.number = number
        obj.family = family
        obj._str = f"{number}{family.value}"
        obj._hash = hash(key)
        # precomputed total-order key: family char then number, matching the
        # original __lt__ semantics, but without touching the (slow) Enum API
        obj._order = ord(family.value) * 10 + number

        is_honor = family == Family.HONOR
        obj._is_honor = is_honor
        obj._is_wind = is_honor and 1 <= number <= 4
        obj._is_dragon = is_honor and 5 <= number <= 7
        obj._is_symmetric = obj._str in _SYMMETRIC_STR
        obj._is_green = obj._str in _GREEN_STR
        obj._is_even = not is_honor and number % 2 == 0
        obj._is_terminal = not is_honor and number in (1, 9)
        obj._is_ordinary = not is_honor and 2 <= number <= 8

        cls._cache[key] = obj
        return obj

    def is_wind(self) -> bool:
        """
        is wind tile
        :return: true if wind
        """
        return self._is_wind

    def is_dragon(self) -> bool:
        """
        is dragon tile
        :return: true if dragon
        """
        return self._is_dragon

    def is_honor(self):
        """
        is an honor tile
        :return: True if honor tile
        """
        return self._is_honor

    def is_compatible_with_half_flush(self, family: Family):
        """
        can be a half flush tile
        :param family: half flush family
        :return: true is compatible
        """
        return self.family is family or self._is_honor

    def is_symmetric(self):
        """
        is a symmetric tile
        :return: True if symmetric
        """
        return self._is_symmetric

    def is_green(self):
        """
        is a green tile
        :return: True if green
        """
        return self._is_green

    def is_even(self):
        """
        is an even tile
        :return: True if even
        """
        return self._is_even

    def is_terminal(self):
        """
        is a terminal tile
        :return: True if terminal
        """
        return self._is_terminal

    def is_ordinary(self):
        """
        is an ordinary tile
        :return: True if ordinary
        """
        return self._is_ordinary

    def __eq__(self, other):
        # tiles are interned, so identity is equivalent to equality
        return self is other

    def __hash__(self):
        return self._hash

    def __str__(self):
        return self._str

    def __repr__(self):
        return self._str

    def __lt__(self, other):
        return self._order < other._order


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

    def draw(self, draw_tile: MahjongTile):
        """
        add tile to hand
        :param draw_tile: tile to add
        """
        self.hand_tiles.append(draw_tile)

    def discard(self, to_discard: MahjongTile):
        """
        remove tile from hand
        :param to_discard: tile to remove
        """
        self.hand_tiles.remove(to_discard)

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
