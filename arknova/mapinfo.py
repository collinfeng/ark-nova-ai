"""Facts about a zoo map that card effects score: connected spaces and empty spaces.

A water, rock, border or placement-bonus space is "connected" when at least one
building is adjacent to it (UNVERIFIED reading of the glossary term).
"""
from .hexmap import neighbors


def next_to_building(zoo, cell):
    return any(n in zoo.cell_owner for n in neighbors(cell))


def terrain_cells(zoo, terrain):
    return [c for c, cell in zoo.mapdef.cells.items() if cell.terrain == terrain]


def connected_terrain(zoo, terrain):
    """(connected, unconnected) counts of water or rock spaces."""
    cells = terrain_cells(zoo, terrain)
    connected = sum(next_to_building(zoo, c) for c in cells)
    return connected, len(cells) - connected


def empty_spaces(zoo):
    """Building spaces (not water or rock) without a building."""
    return [c for c, cell in zoo.mapdef.cells.items() if cell.terrain == "plain" and c not in zoo.cell_owner]


def empty_border_spaces(zoo):
    return [c for c in empty_spaces(zoo) if zoo.mapdef.is_border(c)]


def connected_empty_border(zoo):
    return sum(next_to_building(zoo, c) for c in empty_border_spaces(zoo))


def all_border_connected(zoo):
    """Every border building space is covered or next to a building."""
    return all(next_to_building(zoo, c) for c in empty_border_spaces(zoo))


def bonus_spaces(zoo):
    """(connected, unconnected) counts of uncovered spaces that still show a placement bonus."""
    cells = [c for c in empty_spaces(zoo) if zoo.mapdef.cells[c].bonus]
    connected = sum(next_to_building(zoo, c) for c in cells)
    return connected, len(cells) - connected
