"""
MahjongHand and related utilities
"""
from collections import defaultdict
from typing import Iterable

from mahjong_core import MahjongTile, MahjongTiles, MahjongGroup, Family

class MahjongHand:
    """
    mahjong hand
    """

    def __init__(self, hand_tiles: MahjongTiles, drawn_tile: MahjongTile | None = None):
        self.hand_tiles: MahjongTiles = hand_tiles
        self.drawn_tile: MahjongTile | None = drawn_tile
        self.declared_tiles: set[MahjongGroup] = set()
        self.kongs: set[MahjongGroup] = set()

    def get_free_tiles(self) -> MahjongTiles:
        """
        get the tiles in hand that are not declared
        :return: the free tiles in hand
        """
        free_tiles = list(self.hand_tiles)
        for group in self.get_all_declared_groups():
            for tile in group:
                free_tiles.remove(tile)
        return free_tiles

    def is_closed_hand(self) -> bool:
        return not self.declared_tiles

    def get_natural_size(self):
        return 13 + len(self.kongs)

    def needs_to_discard(self):
        return len(self.hand_tiles) == self.get_natural_size() + 1

    def get_all_declared_groups(self) -> list[MahjongGroup]:
        return list(self.declared_tiles.union(self.kongs))

    def get_tiles_without_last(self):
        tiles = list(self.hand_tiles)
        if self.drawn_tile:
            tiles.remove(self.drawn_tile)
        return tiles

    def get_missing_tiles_and_residue(
        self, tiles: Iterable[MahjongTile]
    ) -> tuple[MahjongTiles, MahjongTiles]:
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
        self.drawn_tile = draw_tile

    def discard(self, to_discard: MahjongTile):
        """
        remove tile from hand
        :param to_discard: tile to remove
        """
        self.hand_tiles.remove(to_discard)

    def clone(self):
        """
        create a copy of this hand
        """
        copied = MahjongHand(self.hand_tiles.copy(), self.drawn_tile)
        copied.declared_tiles = self.declared_tiles.copy()
        copied.kongs = self.kongs.copy()
        return copied

    def __str__(self):
        rep = ""
        groups_by_family = defaultdict(list)
        for group in self.declared_tiles:
            groups_by_family[group[0].family].append('(' + "".join(str(t.number) for t in group) + ')')
        for group in self.kongs:
            if group in self.declared_tiles:
                continue
            groups_by_family[group[0].family].append('[' + "".join(str(t.number) for t in group) + ']')
        for family in Family:
            tiles: list[int] = [
                tile.number for tile in get_tiles_from_family(self.get_free_tiles(), family)
            ]
            declared = groups_by_family[family]
            if declared:
                rep += "".join(sorted(declared))
            if tiles:
                rep += "".join(str(t) for t in sorted(tiles))
            if declared or tiles:
                rep += family.value
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
