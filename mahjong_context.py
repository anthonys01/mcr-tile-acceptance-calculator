"""
HandContext and helper utilities for yaku analysis
"""
from dataclasses import dataclass, field

from mahjong_core import MahjongTile, MahjongGroup, Family

@dataclass
class HandContext:
    """
    Mahjong hand precomputed context for yaku analysis
    """

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
    prevalent_wind: int = 0  # 1-4 for East-North, 0 if unknown
    seat_wind: int = 0  # 1-4 for East-North, 0 if unknown
    has_knitted_straight: bool = False
    is_last_tile: bool = False
    # Mutable pools consumed by group-combination yaku checks (highest value first).
    # Once a group is claimed for one combination, it is removed here so lower-value
    # checks cannot reuse those same groups.
    free_chows: list = field(init=False)
    free_pungs: list = field(init=False)  # combination pool (for Double Pungs etc.)
    free_pungs_single: list = field(
        init=False
    )  # single-group pool (for Dragon Pung, Winds, POTH)
    # Cached optimal plan for the low-tier chow-combination yakus
    # (pure/mixed double chow, short straight, two terminal chows). Computed
    # lazily the first time one of those checks runs.
    chow_combo_plan: dict | None = field(init=False)

    def __post_init__(self):
        self.free_chows = list(self.chows)
        self.free_pungs = list(self.pungs + self.kongs)
        self.free_pungs_single = list(self.pungs + self.kongs)
        self.chow_combo_plan = None


# ---------------------------------------------------------------------------
# Helper utilities used by check functions
# ---------------------------------------------------------------------------


def concealed_pungs(h: HandContext) -> list[MahjongGroup]:
    """Return all concealed pungs and concealed kongs in the hand.

    A pung is concealed when it is not in the open pungs list and either the hand
    was self-drawn or the winning tile is not that pung's tile (so it was not won
    by calling that pung).
    """
    return [
        g
        for g in h.pungs
        if g not in h.open_pungs and (h.is_drawn or h.winning_tile != g[0])
    ] + concealed_kongs(h)


def concealed_kongs(h: HandContext) -> list[MahjongGroup]:
    """Return all kongs that were not declared open (added via a claimed discard)."""
    return [g for g in h.kongs if g not in h.open_kongs]


def chow_starts_for_family(h: HandContext, family: Family) -> list[int]:
    """Return the starting tile numbers of all chows belonging to the given family."""
    return [g[0].number for g in h.chows if g[0].family is family]


def pung_numbers_for_family(h: HandContext, family: Family) -> list[int]:
    """Return the tile numbers of all pungs and kongs belonging to the given family."""
    return [g[0].number for g in h.pungs + h.kongs if g[0].family is family]


# ---------------------------------------------------------------------------
# Free-pool helpers (group-exclusion principle)
# Each combination-yaku check draws from these pools and consumes the groups
# it matches so that lower-value checks cannot reuse the same groups.
# ---------------------------------------------------------------------------


def has_free_chow(h: HandContext, family: Family, start: int) -> bool:
    """Return True if at least one fresh copy of this chow is in the free pool."""
    return any(g[0].family is family and g[0].number == start for g in h.free_chows)


def has_free_pung(h: HandContext, family: Family, number: int) -> bool:
    """Return True if at least one fresh copy of this pung/kong is in the free pool."""
    return any(g[0].family is family and g[0].number == number for g in h.free_pungs)


def take_free_chow(h: HandContext, family: Family, start: int) -> None:
    """Remove the first matching chow from the free pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_chows):
        if g[0].family is family and g[0].number == start:
            h.free_chows.pop(i)
            return


def take_free_pung(h: HandContext, family: Family, number: int) -> None:
    """Remove the first matching pung/kong from the free pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_pungs):
        if g[0].family is family and g[0].number == number:
            h.free_pungs.pop(i)
            return


def has_free_pung_single(h: HandContext, family: Family, number: int) -> bool:
    """Return True if at least one fresh copy of this pung/kong is in the single-group pool."""
    return any(
        g[0].family is family and g[0].number == number for g in h.free_pungs_single
    )


def take_free_pung_single(h: HandContext, family: Family, number: int) -> None:
    """Remove the first matching pung/kong from the single-group pool (no-op if already depleted)."""
    for i, g in enumerate(h.free_pungs_single):
        if g[0].family is family and g[0].number == number:
            h.free_pungs_single.pop(i)
            return

