"""
    mahjong objects and enum
"""
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import combinations, permutations

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

# count-vector indexing: 0-8 = 1m-9m, 9-17 = 1p-9p, 18-26 = 1s-9s, 27-33 = 1z-7z
_FAMILY_OFFSET = {"m": 0, "p": 9, "s": 18, "z": 27}
NB_TILE_INDICES = 34


class MahjongTile:
    """
        tile

        Tiles are interned (flyweight): two tiles with the same number and family
        are guaranteed to be the same object. This makes equality an identity check
        and lets us precompute the hash and all the boolean predicates once.
    """
    __slots__ = ("number", "family", "_str", "_hash", "index",
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
        # count-vector index (0..33); it also encodes the total order m<p<s<z
        # then ascending number, matching the original __lt__ semantics
        obj.index = _FAMILY_OFFSET[family.value] + number - 1

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

EAST = MahjongTile('1z')
SOUTH = MahjongTile('2z')
WEST = MahjongTile('3z')
NORTH = MahjongTile('4z')
WHITE_DRAGON = MahjongTile('5z')
GREEN_DRAGON = MahjongTile('6z')
RED_DRAGON = MahjongTile('7z')

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
    def __init__(self, hand_tiles: MahjongTiles=None, drawn_tile: MahjongTile=None):
        self.hand_tiles: MahjongTiles = hand_tiles
        self.drawn_tile: MahjongTile = drawn_tile
        self.declared_tiles: set[MahjongGroup] = set()
        self.kans: set[MahjongGroup] = set()

    def get_free_tiles(self) -> MahjongTiles:
        """
        get the tiles in hand that are not declared
        :return: the free tiles in hand
        """
        free_tiles = list(self.hand_tiles)
        for group in self.declared_tiles:
            for tile in group:
                free_tiles.remove(tile)
        return free_tiles

    def is_closed_hand(self) -> bool:
        return not self.declared_tiles

    def get_natural_size(self):
        return 13 + len(self.kans)

    def needs_to_discard(self):
        return len(self.hand_tiles) == self.get_natural_size() + 1

    def get_all_declared_groups(self) -> list[MahjongGroup]:
        return list(self.declared_tiles.union(self.kans))

    def get_missing_tiles_and_residue(self, tiles: MahjongTiles) -> tuple[MahjongTiles, MahjongTiles]:
        """
        get missing tiles in hand for given tiles, and residue after that
        :param tiles: tiles to find
        :return: the missing tiles in the hand for given tiles, and the residue
        """
        current_hand = self.get_free_tiles()
        not_found = []
        for tile in tiles:
            if tile in current_hand:
                current_hand.remove(tile)
            else:
                not_found.append(tile)
        return not_found, current_hand

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


@dataclass
class HandContext:
    all_tiles: list[MahjongTile]
    groups: tuple[MahjongGroup, ...]
    pair: MahjongGroup
    acceptance: set[MahjongTile]
    chows: list[MahjongGroup]
    pungs: list[MahjongGroup]
    kongs: list[MahjongGroup]
    open_chows: list[MahjongGroup]
    open_pungs: list[MahjongGroup]
    open_kongs: list[MahjongGroup]
    families: set[Family]
    is_drawn: bool
    winning_tile: MahjongTile
    prevalent_wind: int = 0   # 1-4 for East-North, 0 if unknown
    seat_wind: int = 0        # 1-4 for East-North, 0 if unknown
    is_last_tile: bool = False
    # Mutable pools consumed by group-combination yaku checks (highest value first).
    # Once a group is claimed for one combination, it is removed here so lower-value
    # checks cannot reuse those same groups.
    free_chows: list = field(init=False)
    free_pungs: list = field(init=False)          # combination pool (for Double Pungs etc.)
    free_pungs_single: list = field(init=False)   # single-group pool (for Dragon Pung, Winds, POTH)

    def __post_init__(self):
        self.free_chows = list(self.chows)
        self.free_pungs = list(self.pungs + self.kongs)
        self.free_pungs_single = list(self.pungs + self.kongs)


# ---------------------------------------------------------------------------
# Helper utilities used by check functions
# ---------------------------------------------------------------------------

def _concealed_pungs(h: "HandContext") -> list[MahjongGroup]:
    return [g for g in h.pungs if g not in h.open_pungs]


def _concealed_kongs(h: "HandContext") -> list[MahjongGroup]:
    return [g for g in h.kongs if g not in h.open_kongs]


def _chow_starts_for_family(h: "HandContext", family: Family) -> list[int]:
    return [g[0].number for g in h.chows if g[0].family is family]


def _pung_numbers_for_family(h: "HandContext", family: Family) -> list[int]:
    return [g[0].number for g in h.pungs + h.kongs if g[0].family is family]


# ---------------------------------------------------------------------------
# Free-pool helpers (group-exclusion principle)
# Each combination-yaku check draws from these pools and consumes the groups
# it matches so that lower-value checks cannot reuse the same groups.
# ---------------------------------------------------------------------------

def _free_chow_starts_for_family(h: "HandContext", family: Family) -> list[int]:
    return [g[0].number for g in h.free_chows if g[0].family is family]


def _free_pung_numbers_for_family(h: "HandContext", family: Family) -> list[int]:
    return [g[0].number for g in h.free_pungs if g[0].family is family]


def _has_free_chow(h: "HandContext", family: Family, start: int) -> bool:
    """Return True if at least one fresh copy of this chow is in the free pool."""
    return any(g[0].family is family and g[0].number == start for g in h.free_chows)


def _has_free_pung(h: "HandContext", family: Family, number: int) -> bool:
    """Return True if at least one fresh copy of this pung/kong is in the free pool."""
    return any(g[0].family is family and g[0].number == number for g in h.free_pungs)


def _take_free_chow(h: "HandContext", family: Family, start: int) -> None:
    """Remove the first matching chow from the free pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_chows):
        if g[0].family is family and g[0].number == start:
            h.free_chows.pop(i)
            return


def _take_free_pung(h: "HandContext", family: Family, number: int) -> None:
    """Remove the first matching pung/kong from the free pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_pungs):
        if g[0].family is family and g[0].number == number:
            h.free_pungs.pop(i)
            return


def _has_free_pung_single(h: "HandContext", family: Family, number: int) -> bool:
    """Return True if at least one fresh copy of this pung/kong is in the single-group pool."""
    return any(g[0].family is family and g[0].number == number for g in h.free_pungs_single)


def _take_free_pung_single(h: "HandContext", family: Family, number: int) -> None:
    """Remove the first matching pung/kong from the single-group pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_pungs_single):
        if g[0].family is family and g[0].number == number:
            h.free_pungs_single.pop(i)
            return


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def _check_big_four_winds(h: "HandContext") -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 4


def _check_big_three_dragons(h: "HandContext") -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) == 3


def _check_all_green(h: "HandContext") -> bool:
    return all(t.is_green() for t in h.all_tiles)


def _check_four_kongs(h: "HandContext") -> bool:
    return len(h.kongs) == 4


def _check_all_terminals(h: "HandContext") -> bool:
    return all(t.is_terminal() for t in h.all_tiles)


def _check_little_four_winds(h: "HandContext") -> bool:
    return (sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 3
            and h.pair[0].is_wind())


def _check_little_three_dragons(h: "HandContext") -> bool:
    return (sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) == 2
            and h.pair[0].is_dragon())


def _check_all_honors(h: "HandContext") -> bool:
    return all(t.is_honor() for t in h.all_tiles)


def _check_four_concealed_pungs(h: "HandContext") -> bool:
    return len(_concealed_pungs(h)) == 4


def _check_pure_terminal_chows(h: "HandContext") -> bool:
    """2×123 + 2×789 in the same suit, pair of 5 in the same suit."""
    if len(h.chows) != 4:
        return False
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        if h.pair[0].family is not family or h.pair[0].number != 5:
            continue
        all_starts = sorted(_chow_starts_for_family(h, family))
        if all_starts == [1, 1, 7, 7]:
            if _has_free_chow(h, family, 1) or _has_free_chow(h, family, 7):
                for s in [1, 1, 7, 7]:
                    _take_free_chow(h, family, s)
                return True
    return False


def _check_quadruple_chow(h: "HandContext") -> bool:
    c = Counter(h.chows)
    for chow, count in c.items():
        if count >= 4:
            family, start = chow[0].family, chow[0].number
            if _has_free_chow(h, family, start):
                for _ in range(4):
                    _take_free_chow(h, family, start)
                return True
    return False


def _check_four_pure_shifted_pungs(h: "HandContext") -> bool:
    """4 pungs/kongs in the same suit with consecutive numbers (step 1)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(_pung_numbers_for_family(h, family))
        for i in range(len(nums) - 3):
            sub = nums[i:i + 4]
            if sub[1]-sub[0] == 1 and sub[2]-sub[1] == 1 and sub[3]-sub[2] == 1:
                if any(_has_free_pung(h, family, n) for n in sub):
                    for n in sub:
                        _take_free_pung(h, family, n)
                    return True
    return False


def _check_four_pure_shifted_chows(h: "HandContext") -> bool:
    """4 chows in the same suit, each shifted by the same step (1 or 2)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(_chow_starts_for_family(h, family))
        for i in range(len(nums) - 3):
            sub = nums[i:i + 4]
            for step in (1, 2):
                if sub[1]-sub[0] == step and sub[2]-sub[1] == step and sub[3]-sub[2] == step:
                    if any(_has_free_chow(h, family, s) for s in sub):
                        for s in sub:
                            _take_free_chow(h, family, s)
                        return True
    return False


def _check_three_kongs(h: "HandContext") -> bool:
    return len(h.kongs) == 3


def _check_all_terminal_and_honors(h: "HandContext") -> bool:
    return all(t.is_terminal() or t.is_honor() for t in h.all_tiles)


def _check_all_even_pungs(h: "HandContext") -> bool:
    return (not h.chows
            and all(g[0].is_even() for g in h.pungs + h.kongs)
            and h.pair[0].is_even())


def _check_full_flush(h: "HandContext") -> bool:
    return len(h.families) == 1 and Family.HONOR not in h.families


def _check_pure_triple_chow(h: "HandContext") -> bool:
    c = Counter(h.chows)
    for chow, count in c.items():
        if count >= 3:
            family, start = chow[0].family, chow[0].number
            if _has_free_chow(h, family, start):
                for _ in range(3):
                    _take_free_chow(h, family, start)
                return True
    return False


def _check_pure_shifted_pungs(h: "HandContext") -> bool:
    """3 pungs/kongs in the same suit with consecutive numbers (step 1)."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(_pung_numbers_for_family(h, family))
        for i in range(len(nums) - 2):
            sub = nums[i:i + 3]
            if sub[1]-sub[0] == 1 and sub[2]-sub[1] == 1:
                if any(_has_free_pung(h, family, n) for n in sub):
                    for n in sub:
                        _take_free_pung(h, family, n)
                    return True
    return False


def _check_upper_tiles(h: "HandContext") -> bool:
    return all(not t.is_honor() and t.number >= 7 for t in h.all_tiles)


def _check_middle_tiles(h: "HandContext") -> bool:
    return all(not t.is_honor() and 4 <= t.number <= 6 for t in h.all_tiles)


def _check_lower_tiles(h: "HandContext") -> bool:
    return all(not t.is_honor() and t.number <= 3 for t in h.all_tiles)


def _check_pure_straight(h: "HandContext") -> bool:
    """123 + 456 + 789 in the same suit. Consumes those 3 chows from the free pool."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        starts = _chow_starts_for_family(h, family)
        if 1 in starts and 4 in starts and 7 in starts:
            if _has_free_chow(h, family, 1) or _has_free_chow(h, family, 4) or _has_free_chow(h, family, 7):
                _take_free_chow(h, family, 1)
                _take_free_chow(h, family, 4)
                _take_free_chow(h, family, 7)
                return True
    return False


def _check_three_suited_terminal_chows(h: "HandContext") -> bool:
    """123+789 in two suits, pair of 5 in the third suit."""
    if len(h.chows) != 4:
        return False
    for pair_fam in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        if h.pair[0].family is not pair_fam or h.pair[0].number != 5:
            continue
        other = [f for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER) if f is not pair_fam]
        fa, fb = other[0], other[1]
        all_starts_a = sorted(_chow_starts_for_family(h, fa))
        all_starts_b = sorted(_chow_starts_for_family(h, fb))
        if all_starts_a == [1, 7] and all_starts_b == [1, 7]:
            fresh = any(_has_free_chow(h, f, s) for f in (fa, fb) for s in (1, 7))
            if fresh:
                for s in [1, 7]:
                    _take_free_chow(h, fa, s)
                    _take_free_chow(h, fb, s)
                return True
    return False


def _check_pure_shifted_chows(h: "HandContext") -> bool:
    """3 chows in the same suit, each shifted by step 1 or 2. Consumes those 3 chows."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        nums = sorted(_chow_starts_for_family(h, family))
        for i in range(len(nums) - 2):
            sub = nums[i:i + 3]
            for step in (1, 2):
                if sub[1]-sub[0] == step and sub[2]-sub[1] == step:
                    if any(_has_free_chow(h, family, s) for s in sub):
                        for s in sub:
                            _take_free_chow(h, family, s)
                        return True
    return False


def _check_all_fives(h: "HandContext") -> bool:
    """Every group and the pair contains a 5."""
    return (any(t.number == 5 for t in h.pair)
            and all(any(t.number == 5 for t in g) for g in h.groups))


def _check_triple_pung(h: "HandContext") -> bool:
    """3 pungs/kongs of the same number in 3 different suits. Consumes those 3 groups."""
    by_num: dict[int, list] = {}
    for g in h.pungs + h.kongs:
        if not g[0].is_honor():
            by_num.setdefault(g[0].number, []).append(g)
    for num, groups in by_num.items():
        fams = {g[0].family for g in groups}
        if len(fams) >= 3:
            consumed = []
            used_fams: set = set()
            for g in groups:
                if g[0].family not in used_fams:
                    consumed.append(g)
                    used_fams.add(g[0].family)
                    if len(consumed) == 3:
                        break
            if any(_has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    _take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_three_concealed_pungs(h: "HandContext") -> bool:
    return len(_concealed_pungs(h)) >= 3


def _check_upper_four(h: "HandContext") -> bool:
    return all(not t.is_honor() and t.number >= 6 for t in h.all_tiles)


def _check_lower_four(h: "HandContext") -> bool:
    return all(not t.is_honor() and t.number <= 4 for t in h.all_tiles)


def _check_big_three_winds(h: "HandContext") -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_wind()) == 3


def _check_mixed_straight(h: "HandContext") -> bool:
    """123 + 456 + 789, one chow per suit (any assignment of numbers to suits)."""
    chow_by_fam: dict[Family, list[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, []).append(g[0].number)
    fams = [f for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER) if f in chow_by_fam]
    for f1, f2, f3 in permutations(fams, 3):
        if (1 in chow_by_fam[f1]
                and 4 in chow_by_fam[f2]
                and 7 in chow_by_fam[f3]):
            if _has_free_chow(h, f1, 1) or _has_free_chow(h, f2, 4) or _has_free_chow(h, f3, 7):
                _take_free_chow(h, f1, 1)
                _take_free_chow(h, f2, 4)
                _take_free_chow(h, f3, 7)
                return True
    return False


def _check_reversible_tiles(h: "HandContext") -> bool:
    return all(t.is_symmetric() for t in h.all_tiles)


def _check_mixed_triple_chow(h: "HandContext") -> bool:
    """Same starting number chow in each of the 3 suits. Consumes those 3 chows."""
    chow_by_fam: dict[Family, set[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, set()).add(g[0].number)
    for num in range(1, 8):
        if all(num in chow_by_fam.get(f, set())
               for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER)):
            if any(_has_free_chow(h, f, num) for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER)):
                for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
                    _take_free_chow(h, f, num)
                return True
    return False


def _check_mixed_shifted_pungs(h: "HandContext") -> bool:
    """3 pungs, one in each suit, with consecutive starting numbers. Consumes those 3 groups."""
    entries = [(g[0].number, g[0].family, g) for g in h.pungs + h.kongs if not g[0].is_honor()]
    for trio in combinations(range(len(entries)), 3):
        nums = sorted(entries[i][0] for i in trio)
        fams = {entries[i][1] for i in trio}
        if len(fams) == 3 and nums[1]-nums[0] == 1 and nums[2]-nums[1] == 1:
            consumed = [entries[i][2] for i in trio]
            if any(_has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    _take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_two_concealed_kongs(h: "HandContext") -> bool:
    return len(_concealed_kongs(h)) >= 2


def _check_all_pungs(h: "HandContext") -> bool:
    return not h.chows


def _check_half_flush(h: "HandContext") -> bool:
    return len(h.families) == 2 and Family.HONOR in h.families


def _check_mixed_shifted_chows(h: "HandContext") -> bool:
    """3 chows, one per suit, with consecutive starting numbers (any step 1 or 2). Consumes those 3 chows."""
    chow_by_fam: dict[Family, list[int]] = {}
    for g in h.chows:
        chow_by_fam.setdefault(g[0].family, []).append(g[0].number)
    fams = [f for f in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER) if f in chow_by_fam]
    if len(fams) < 3:
        return False
    for f1, f2, f3 in permutations(fams, 3):
        for na in chow_by_fam[f1]:
            for nb in chow_by_fam[f2]:
                for nc in chow_by_fam[f3]:
                    nums = sorted([na, nb, nc])
                    if nums[1]-nums[0] == 1 and nums[2]-nums[1] == 1:
                        if _has_free_chow(h, f1, na) or _has_free_chow(h, f2, nb) or _has_free_chow(h, f3, nc):
                            _take_free_chow(h, f1, na)
                            _take_free_chow(h, f2, nb)
                            _take_free_chow(h, f3, nc)
                            return True
    return False


def _check_all_types(h: "HandContext") -> bool:
    """Hand contains tiles from all 3 suits + honors, and has both chows and pungs."""
    return (bool(h.chows) and bool(h.pungs or h.kongs)
            and len(h.families) == 4)


def _check_melded_hand(h: "HandContext") -> bool:
    """All groups are open (melded), won by discard."""
    total_groups = len(h.chows) + len(h.pungs) + len(h.kongs)
    open_groups = len(h.open_chows) + len(h.open_pungs) + len(h.open_kongs)
    return not h.is_drawn and total_groups == open_groups


def _check_two_dragons_pungs(h: "HandContext") -> bool:
    return sum(1 for g in h.pungs + h.kongs if g[0].is_dragon()) >= 2


def _check_outside_hand(h: "HandContext") -> bool:
    """Every group and the pair contains at least one terminal or honor."""
    def _has_toh(group: MahjongGroup) -> bool:
        return any(t.is_terminal() or t.is_honor() for t in group)
    return _has_toh(h.pair) and all(_has_toh(g) for g in h.groups)


def _check_fully_concealed(h: "HandContext") -> bool:
    """All groups concealed, won by self-draw."""
    return (h.is_drawn
            and not h.open_chows and not h.open_pungs and not h.open_kongs)


def _check_two_melded_kongs(h: "HandContext") -> bool:
    return len(h.open_kongs) >= 2


def _check_last_tile(h: "HandContext") -> bool:
    return h.is_last_tile


def _check_dragon_pung(h: "HandContext") -> int:
    """1 or more dragon pungs/kongs. Consumes each from the single-group pool."""
    count = 0
    for g in h.pungs + h.kongs:
        if g[0].is_dragon():
            _take_free_pung_single(h, g[0].family, g[0].number)
            count += 1
    return count


def _check_prevalent_wind(h: "HandContext") -> bool:
    if h.prevalent_wind > 0:
        for g in h.pungs + h.kongs:
            if g[0].is_wind() and g[0].number == h.prevalent_wind:
                _take_free_pung_single(h, g[0].family, g[0].number)
                return True
    return False


def _check_seat_wind(h: "HandContext") -> bool:
    if h.seat_wind > 0:
        for g in h.pungs + h.kongs:
            if g[0].is_wind() and g[0].number == h.seat_wind:
                _take_free_pung_single(h, g[0].family, g[0].number)
                return True
    return False


def _check_concealed_hand(h: "HandContext") -> bool:
    """All groups concealed, won by discard."""
    return (not h.is_drawn
            and not h.open_chows and not h.open_pungs and not h.open_kongs)


def _check_all_chows(h: "HandContext") -> bool:
    return not h.pungs and not h.kongs


def _check_tile_hog(h: "HandContext") -> int:
    """Count tiles with 4 copies used without declaring a kong."""
    kong_tiles = {g[0] for g in h.kongs}
    c = Counter(h.all_tiles)
    return sum(1 for tile, v in c.items() if v == 4 and tile not in kong_tiles)


def _check_double_pungs(h: "HandContext") -> bool:
    """2 pungs of the same number in different suits. Consumes those 2 groups."""
    by_num: dict[int, list] = {}
    for g in h.pungs + h.kongs:
        if not g[0].is_honor():
            by_num.setdefault(g[0].number, []).append(g)
    for num, groups in by_num.items():
        fams = {g[0].family for g in groups}
        if len(fams) >= 2:
            consumed = []
            used_fams: set = set()
            for g in groups:
                if g[0].family not in used_fams:
                    consumed.append(g)
                    used_fams.add(g[0].family)
                    if len(consumed) == 2:
                        break
            if any(_has_free_pung(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    _take_free_pung(h, g[0].family, g[0].number)
                return True
    return False


def _check_two_concealed_pungs(h: "HandContext") -> bool:
    return len(_concealed_pungs(h)) >= 2


def _check_concealed_kong(h: "HandContext") -> bool:
    return len(_concealed_kongs(h)) >= 1


def _check_all_simple(h: "HandContext") -> bool:
    return all(t.is_ordinary() for t in h.all_tiles)


def _check_pure_double_chow(h: "HandContext") -> bool:
    c = Counter(h.chows)
    for chow, count in c.items():
        if count >= 2:
            family, start = chow[0].family, chow[0].number
            if _has_free_chow(h, family, start):
                _take_free_chow(h, family, start)
                _take_free_chow(h, family, start)
                return True
    return False


def _check_mixed_double_chow(h: "HandContext") -> bool:
    """2 chows of the same starting number in different suits. Consumes those 2 chows."""
    by_num: dict[int, list] = {}
    for g in h.chows:
        by_num.setdefault(g[0].number, []).append(g)
    for num, groups in by_num.items():
        fams = {g[0].family for g in groups}
        if len(fams) >= 2:
            consumed = []
            used_fams: set = set()
            for g in groups:
                if g[0].family not in used_fams:
                    consumed.append(g)
                    used_fams.add(g[0].family)
                    if len(consumed) == 2:
                        break
            if any(_has_free_chow(h, g[0].family, g[0].number) for g in consumed):
                for g in consumed:
                    _take_free_chow(h, g[0].family, g[0].number)
                return True
    return False


def _check_short_straight(h: "HandContext") -> bool:
    """2 consecutive chows in the same suit (e.g. 123+456 or 456+789). Consumes those 2 chows."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        starts = sorted(_chow_starts_for_family(h, family))
        for i in range(len(starts) - 1):
            s1, s2 = starts[i], starts[i + 1]
            if s2 - s1 == 3:
                if _has_free_chow(h, family, s1) or _has_free_chow(h, family, s2):
                    _take_free_chow(h, family, s1)
                    _take_free_chow(h, family, s2)
                    return True
    return False


def _check_two_terminal_chows(h: "HandContext") -> bool:
    """123 + 789 in the same suit. Consumes those 2 chows."""
    for family in (Family.BAMBOO, Family.CIRCLE, Family.CHARACTER):
        starts = _chow_starts_for_family(h, family)
        if 1 in starts and 7 in starts:
            if _has_free_chow(h, family, 1) or _has_free_chow(h, family, 7):
                _take_free_chow(h, family, 1)
                _take_free_chow(h, family, 7)
                return True
    return False


def _check_pung_of_terminals_or_honors(h: "HandContext") -> int:
    """Count pungs/kongs of terminals or honors that still have a fresh slot in the single-group pool."""
    count = 0
    for g in h.pungs + h.kongs:
        if (g[0].is_terminal() or g[0].is_honor()) and _has_free_pung_single(h, g[0].family, g[0].number):
            _take_free_pung_single(h, g[0].family, g[0].number)
            count += 1
    return count


def _check_melded_kong(h: "HandContext") -> bool:
    return len(h.open_kongs) >= 1


def _check_one_voided_suit(h: "HandContext") -> bool:
    """Tiles come from exactly 2 of the 3 number suits (honors don't count)."""
    return len(h.families - {Family.HONOR}) == 2


def _check_no_honor(h: "HandContext") -> bool:
    return Family.HONOR not in h.families


def _check_edge_wait(h: "HandContext") -> bool:
    """Winning tile is the 3 of a 12X chow, or the 7 of an X89 chow."""
    if len(h.acceptance) > 1:
        return False
    wt = h.winning_tile
    for g in h.chows:
        if wt in g:
            nums = sorted(t.number for t in g)
            if nums == [1, 2, 3] and wt.number == 3:
                return True
            if nums == [7, 8, 9] and wt.number == 7:
                return True
    return False


def _check_closed_wait(h: "HandContext") -> bool:
    """Winning tile is the middle tile of its chow (kanchan wait)."""
    if len(h.acceptance) > 1:
        return False
    wt = h.winning_tile
    for g in h.chows:
        if wt in g:
            nums = sorted(t.number for t in g)
            if nums[1] == wt.number:
                return True
    return False


def _check_single_wait(h: "HandContext") -> bool:
    """Winning tile completes the pair (tanki wait)."""
    return len(h.acceptance) == 1 and h.winning_tile in h.pair


def _check_self_drawn(h: "HandContext") -> bool:
    return h.is_drawn


# Placeholder for yakus that require full scoring context or are special hands
def _check_not_implemented(_h: "HandContext") -> bool:
    return False


class MahjongMCRYaku(Enum):
    BIG_FOUR_WIND            = (1,  88, [38, 49, 60, 61, 73], _check_big_four_winds)
    BIG_THREE_DRAGON         = (2,  88, [54, 59],             _check_big_three_dragons)
    ALL_GREEN                = (3,  88, [],                   _check_all_green)
    NINE_GATES               = (4,  88, [22, 62, 73],         _check_not_implemented)
    FOUR_KONGS               = (5,  88, [48, 57, 67, 74, 79], _check_four_kongs)
    SEVEN_SHIFTED_PAIRS      = (6,  88, [19, 22, 62, 79],     _check_not_implemented)
    THIRTEEN_ORPHANS         = (7,  88, [52, 62],             _check_not_implemented)
    ALL_TERMINALS            = (8,  64, [18, 49, 73, 76],     _check_all_terminals)
    LITTLE_FOUR_WINDS        = (9,  64, [38, 73],             _check_little_four_winds)
    LITTLE_THREE_DRAGONS     = (10, 64, [54, 59],             _check_little_three_dragons)
    ALL_HONORS               = (11, 64, [18, 49, 73],         _check_all_honors)
    FOUR_CONCEALED_PUNGS     = (12, 64, [33, 49, 62, 66],     _check_four_concealed_pungs)
    PURE_TERMINAL_CHOWS      = (13, 64, [22, 63, 69, 72],     _check_pure_terminal_chows)
    QUADRUPLE_CHOW           = (14, 48, [64, 69],             _check_quadruple_chow)
    FOUR_PURE_SHIFTED_PUNGS  = (15, 48, [49],                 _check_four_pure_shifted_pungs)
    FOUR_PURE_SHIFTED_CHOWS  = (16, 32, [71, 72],             _check_four_pure_shifted_chows)
    THREE_KONGS              = (17, 32, [48, 57, 67, 74],     _check_three_kongs)
    ALL_TERMINAL_AND_HONORS  = (18, 32, [49, 55, 73],         _check_all_terminal_and_honors)
    SEVEN_PAIRS              = (19, 24, [62, 79],             _check_not_implemented)
    GREATER_HONORS_AND_KNITTED_TILES = (20, 24, [52, 62],     _check_not_implemented)
    ALL_EVEN_PUNGS           = (21, 24, [49, 68],             _check_all_even_pungs)
    FULL_FLUSH               = (22, 24, [50, 76],             _check_full_flush)
    PURE_TRIPLE_CHOW         = (23, 24, [69],                 _check_pure_triple_chow)
    PURE_SHIFTED_PUNGS       = (24, 24, [],                   _check_pure_shifted_pungs)
    UPPER_TILES              = (25, 24, [76],                 _check_upper_tiles)
    MIDDLE_TILES             = (26, 24, [68, 76],             _check_middle_tiles)
    LOWER_TILES              = (27, 24, [76],                 _check_lower_tiles)
    PURE_STRAIGHT            = (28, 16, [],                   _check_pure_straight)
    THREE_SUITED_TERMINAL_CHOWS = (29, 16, [63, 69, 70, 72], _check_three_suited_terminal_chows)
    PURE_SHIFTED_CHOWS       = (30, 16, [],                   _check_pure_shifted_chows)
    ALL_FIVES                = (31, 16, [68],                 _check_all_fives)
    TRIPLE_PUNG              = (32, 16, [],                   _check_triple_pung)
    THREE_CONCEALED_PUNGS    = (33, 16, [66],                 _check_three_concealed_pungs)
    LESSER_HONORS_AND_KNITTED_TILES = (34, 12, [52, 62],      _check_not_implemented)
    KNITTED_STRAIGHT         = (35, 12, [],                   _check_not_implemented)
    UPPER_FOUR               = (36, 12, [76],                 _check_upper_four)
    LOWER_FOUR               = (37, 12, [76],                 _check_lower_four)
    BIG_THREE_WINDS          = (38, 12, [73],                 _check_big_three_winds)
    MIXED_STRAIGHT           = (39, 8,  [],                   _check_mixed_straight)
    REVERSIBLE_TILES         = (40, 8,  [75],                 _check_reversible_tiles)
    MIXED_TRIPLE_CHOW        = (41, 8,  [70],                 _check_mixed_triple_chow)
    MIXED_SHIFTED_PUNGS      = (42, 8,  [],                   _check_mixed_shifted_pungs)
    CHICKEN_HAND             = (43, 8,  [],                   _check_not_implemented)
    # 44, 45, 46, 47 situational
    TWO_CONCEALED_KONGS      = (48, 8,  [67],                 _check_two_concealed_kongs)
    ALL_PUNGS                = (49, 6,  [],                   _check_all_pungs)
    HALF_FLUSH               = (50, 6,  [75],                 _check_half_flush)
    MIXED_SHIFTED_CHOWS      = (51, 6,  [],                   _check_mixed_shifted_chows)
    ALL_TYPES                = (52, 6,  [],                   _check_all_types)
    MELDED_HAND              = (53, 6,  [79],                 _check_melded_hand)
    TWO_DRAGONS_PUNGS        = (54, 6,  [59],                 _check_two_dragons_pungs)
    OUTSIDE_HAND             = (55, 4,  [],                   _check_outside_hand)
    FULLY_CONCEALED          = (56, 4,  [62, 80],             _check_fully_concealed)
    TWO_MELDED_KONGS         = (57, 4,  [74],                 _check_two_melded_kongs)
    LAST_TILE                = (58, 4,  [],                   _check_last_tile)
    DRAGON_PUNG              = (59, 2,  [],                   _check_dragon_pung)
    PREVALENT_WIND           = (60, 2,  [],                   _check_prevalent_wind)
    SEAT_WIND                = (61, 2,  [],                   _check_seat_wind)
    CONCEALED_HAND           = (62, 2,  [],                   _check_concealed_hand)
    ALL_CHOWS                = (63, 2,  [76],                 _check_all_chows)
    TILE_HOG                 = (64, 2,  [],                   _check_tile_hog)
    DOUBLE_PUNGS             = (65, 2,  [],                   _check_double_pungs,      True)
    TWO_CONCEALED_PUNGS      = (66, 2,  [],                   _check_two_concealed_pungs)
    CONCEALED_KONG           = (67, 2,  [],                   _check_concealed_kong)
    ALL_SIMPLE               = (68, 2,  [76],                 _check_all_simple)
    PURE_DOUBLE_CHOW         = (69, 1,  [],                   _check_pure_double_chow,  True)
    MIXED_DOUBLE_CHOW        = (70, 1,  [],                   _check_mixed_double_chow, True)
    SHORT_STRAIGHT           = (71, 1,  [],                   _check_short_straight,    True)
    TWO_TERMINAL_CHOWS       = (72, 1,  [],                   _check_two_terminal_chows,True)
    PUNG_OF_TERMINALS_OR_HONORS = (73, 1, [],                 _check_pung_of_terminals_or_honors)
    MELDED_KONG              = (74, 1,  [],                   _check_melded_kong)
    ONE_VOIDED_SUIT          = (75, 1,  [],                   _check_one_voided_suit)
    NO_HONOR                 = (76, 1,  [],                   _check_no_honor)
    EDGE_WAIT                = (77, 1,  [],                   _check_edge_wait)
    CLOSED_WAIT              = (78, 1,  [],                   _check_closed_wait)
    SINGLE_WAIT              = (79, 1,  [],                   _check_single_wait)
    SELF_DRAWN               = (80, 1,  [],                   _check_self_drawn)
    # 81 flowers

    @staticmethod
    def get(yaku_id: int):
        for yaku in MahjongMCRYaku:
            if yaku.get_id() == yaku_id:
                return yaku
        raise ValueError(f"Yaku with id {yaku_id} not found")

    def check(self, hand: "HandContext") -> int:
        return self.value[3](hand)

    def is_multi(self) -> bool:
        return len(self.value) > 4 and bool(self.value[4])

    def get_points(self) -> int:
        return self.value[1]

    def get_exclusions(self) -> "set[MahjongMCRYaku]":
        return set([MahjongMCRYaku.get(yaku_id) for yaku_id in self.value[2]])

    def get_id(self) -> int:
        return self.value[0]
