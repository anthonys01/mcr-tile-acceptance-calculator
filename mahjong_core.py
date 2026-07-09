"""
mahjong objects and enum
"""

from enum import Enum, auto

# count-vector indexing: 0-8 = 1m-9m, 9-17 = 1p-9p, 18-26 = 1s-9s, 27-33 = 1z-7z
_FAMILY_OFFSET = {"m": 0, "p": 9, "s": 18, "z": 27}
NB_TILE_INDICES = 34


class Family(Enum):
    """
    tile families
    """

    BAMBOO = "s"
    CHARACTER = "m"
    CIRCLE = "p"
    HONOR = "z"

    def __init__(self, val_str):
        self._hash = _FAMILY_OFFSET[val_str]

    def __hash__(self):
        # Deterministic across processes and cheap: the default Enum hash is
        # identity based (randomised per run), and ``self.value`` goes through a
        # descriptor. ``_value_`` is a plain attribute (unlike the ``value`` descriptor).
        return self._hash


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

    def __hash__(self):
        # Deterministic across processes (see Family.__hash__); ``_value_`` is a
        # plain attribute (unlike the ``value`` descriptor).
        return self._value_


_SYMMETRIC_STR = frozenset({
    "5z",
    "1p",
    "2p",
    "3p",
    "4p",
    "5p",
    "8p",
    "9p",
    "2s",
    "4s",
    "5s",
    "6s",
    "8s",
    "9s",
})
_GREEN_STR = frozenset({"6z", "2s", "3s", "4s", "6s", "8s"})


class MahjongTile:
    """
    tile

    Tiles are interned (flyweight): two tiles with the same number and family
    are guaranteed to be the same object. This makes equality an identity check
    and lets us precompute the hash and all the boolean predicates once.
    """

    __slots__ = (
        "number",
        "family",
        "_str",
        "_hash",
        "index",
        "_is_honor",
        "_is_wind",
        "_is_dragon",
        "_is_symmetric",
        "_is_green",
        "_is_even",
        "_is_terminal",
        "_is_ordinary",
    )

    _cache: dict = {}

    def __new__(
        cls, tile: str | None = None, *, number: int = -1, family: Family | None = None
    ):
        if tile:
            number = int(tile[0])
            family = Family(tile[1])
        if number is None or family is None:
            raise AttributeError(
                "either input a valid string or number and family attribute"
            )
        key = (number, family)
        existing = cls._cache.get(key)
        if existing is not None:
            return existing

        obj = super().__new__(cls)
        obj.number = number
        obj.family = family
        obj._str = f"{number}{family.value}"
        # count-vector index (0..33); it also encodes the total order m<p<s<z
        # then ascending number, matching the original __lt__ semantics
        obj.index = _FAMILY_OFFSET[family.value] + number - 1
        # hash from the stable index (not hash(key)): tiles are interned so
        # equality is identity, and Family enum members hash per-process, which
        # would otherwise make set/dict iteration order non-deterministic.
        obj._hash = obj.index

        _is_honor = family == Family.HONOR
        obj._is_honor = _is_honor
        obj._is_wind = _is_honor and 1 <= number <= 4
        obj._is_dragon = _is_honor and 5 <= number <= 7
        obj._is_symmetric = obj._str in _SYMMETRIC_STR
        obj._is_green = obj._str in _GREEN_STR
        obj._is_even = not _is_honor and number % 2 == 0
        obj._is_terminal = not _is_honor and number in (1, 9)
        obj._is_ordinary = not _is_honor and 2 <= number <= 8

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
        return self.index < other.index


EAST = MahjongTile("1z")
SOUTH = MahjongTile("2z")
WEST = MahjongTile("3z")
NORTH = MahjongTile("4z")
WHITE_DRAGON = MahjongTile("5z")
GREEN_DRAGON = MahjongTile("6z")
RED_DRAGON = MahjongTile("7z")

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

def _build_index_table() -> tuple:
    table = []
    for index in range(NB_TILE_INDICES):
        if index < 27:
            family = (Family.CHARACTER, Family.CIRCLE, Family.BAMBOO)[index // 9]
            number = index % 9 + 1
        else:
            family = Family.HONOR
            number = index - 27 + 1
        table.append(MahjongTile(number=number, family=family))
    return tuple(table)


# index (0..33) -> interned MahjongTile
INDEX_TO_TILE: tuple = _build_index_table()
