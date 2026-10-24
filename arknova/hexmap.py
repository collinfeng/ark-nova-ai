"""Hex geometry, map definition and per-player zoo state for Ark Nova."""
from dataclasses import dataclass, field

DIRS = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0)]  # N NE SE S SW NW


def neighbors(c):
    """The six axial neighbours of c."""
    return [(c[0] + dq, c[1] + dr) for dq, dr in DIRS]


def distance(a, b):
    """Hex distance between two axial cells."""
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


@dataclass
class Cell:
    terrain: str
    bonus: str | None = None
    build2_only: bool = False


@dataclass
class MapDef:
    name: str
    cells: dict = field(default_factory=dict)

    @staticmethod
    def from_columns(name, columns):
        """Build a map from column token lists (W, R, ., .:bonus, .:build2)."""
        cells = {}
        for col, toks in enumerate(columns):
            for row, t in enumerate(toks):
                c = (col, row - (col + 1) // 2)
                if t == 'W':
                    cells[c] = Cell('water')
                elif t == 'R':
                    cells[c] = Cell('rock')
                elif t == '.':
                    cells[c] = Cell('plain')
                elif t == '.:build2':
                    cells[c] = Cell('plain', None, True)
                elif t.startswith('.:'):
                    cells[c] = Cell('plain', t[2:])
                else:
                    raise ValueError(f"bad token {t!r}")
        return MapDef(name, cells)

    def is_border(self, c):
        return c in self.cells and any(n not in self.cells for n in neighbors(c))

    def buildable_cells(self):
        return {c for c, v in self.cells.items() if v.terrain == 'plain'}


def _cols(s):
    return [t for t in s.split()]


MAP0 = MapDef.from_columns("Map 0", [
    _cols("W W . . .:rep2 R"),
    _cols("W .:card . . . W R"),
    _cols("R . .:card W . ."),
    _cols("W R . . .:xtoken . .:card"),
    _cols(".:xtoken . .:money10 . . ."),
    _cols(". . W .:clever R .:xtoken R"),
    _cols(". R .:build2 . R R"),
    _cols(". .:money5 .:build2 . . .:rep2 W"),
    _cols(". . . .:money5 W W"),
])

SHAPES = {
    ('enclosure', 1): {(0, 0)}, ('enclosure', 2): {(0, 0), (1, 0)},
    ('enclosure', 3): {(0, 0), (1, 0), (0, 1)},
    ('enclosure', 4): {(0, 0), (1, -1), (1, 0), (2, -1)},
    ('enclosure', 5): {(0, 0), (1, -1), (1, 0), (2, -1), (2, 0)},
    ('kiosk', 1): {(0, 0)}, ('pavilion', 1): {(0, 0)},
    ('petting_zoo', 3): {(0, 0), (1, -1), (2, -1)},
    ('reptile_house', 5): {(0, 0), (-1, 0), (-1, 1), (1, -1), (1, 0)},
    ('aviary', 5): {(0, 0), (-1, 0), (1, -1), (-1, 1), (0, 1)},
}
SPECIAL = ('petting_zoo', 'reptile_house', 'aviary')


def _norm(cells):
    m = min(cells)
    return frozenset((q - m[0], r - m[1]) for q, r in cells)


def orientations(offsets):
    """Distinct rotations (60 degree steps) of a shape, normalised."""
    out, cur = [], set(offsets)
    for _ in range(6):
        n = _norm(cur)
        if n not in out:
            out.append(n)
        cur = {(-r, q + r) for q, r in cur}
    return out


@dataclass
class Building:
    id: int
    kind: str
    size: int
    cells: frozenset
    occupied: bool = False
    used: int = 0
    name: str | None = None
    extra_size: int = 0  # spaces added by a map rule (Map 2 outdoor area); see capacity

    @property
    def capacity(self):
        return self.size + self.extra_size


def _shape_positions(mapdef, base):
    """[(cells, frozenset, all plain, covers a Build II space, cells on the border, rock next to it,
    water next to it)] for each distinct position of the shape that lies on the map."""
    positions = mapdef.__dict__.setdefault("_positions", {})  # kept on the map: it never changes
    key = tuple(sorted(base))
    if key not in positions:
        cells, seen, out = mapdef.cells, set(), []
        for o in orientations(base):
            for (aq, ar) in cells:
                placed = tuple((aq + q, ar + r) for q, r in o)
                fs = frozenset(placed)
                if fs in seen or any(c not in cells for c in placed):
                    continue
                seen.add(fs)
                near = {n for c in placed for n in neighbors(c) if n not in fs and n in cells}
                out.append((placed, fs, all(cells[c].terrain == 'plain' for c in placed),
                            any(cells[c].build2_only for c in placed), sum(mapdef.is_border(c) for c in placed),
                            sum(cells[n].terrain == 'rock' for n in near),
                            sum(cells[n].terrain == 'water' for n in near)))
        positions[key] = out
    return positions[key]


class Zoo:
    """One player's map state."""

    def __init__(self, mapdef):
        self.mapdef = mapdef
        self.buildings = []
        self.cell_owner = {}
        self._placements = {}  # legal_placements results; they only change when a building is placed

    def __deepcopy__(self, memo):
        """Copy the buildings; share the map definition, which never changes."""
        import copy
        clone = Zoo(self.mapdef)
        clone.buildings = copy.deepcopy(self.buildings, memo)
        clone.cell_owner = dict(self.cell_owner)
        clone._placements = dict(self._placements)  # the cached lists are never mutated
        return clone

    def legal_placements(self, kind, size, build2=False, shape=None, need_rock=0, need_water=0,
                         min_border=0, adjacent=True, any_terrain=False):
        """Legal positions. `any_terrain` (Diversity Researcher) lets buildings cover water and rock
        spaces and drops need_rock / need_water."""
        if any_terrain:
            need_rock = need_water = 0
        if kind in SPECIAL and self.count(kind):
            return []
        cache_key = (kind, size, build2, None if shape is None else tuple(sorted(shape)), need_rock, need_water,
                     min_border, adjacent, any_terrain)
        if cache_key in self._placements:
            return self._placements[cache_key]
        base = shape if shape is not None else SHAPES[(kind, size)]
        owner = self.cell_owner
        kiosks = [c for b in self.buildings if b.kind == 'kiosk' for c in b.cells] if kind == 'kiosk' else ()
        occupied_adj = {n for c in owner for n in neighbors(c)}
        first = not self.buildings
        found = []
        for placed, fs, plain, has_build2, on_border, rock, water in _shape_positions(self.mapdef, base):
            if (not plain and not any_terrain) or (has_build2 and not build2) or on_border < min_border:
                continue
            if need_rock > rock or need_water > water:
                continue
            if any(c in owner for c in placed):
                continue
            if first:
                if not on_border:
                    continue
            elif adjacent and not any(c in occupied_adj for c in placed):
                continue
            if kiosks and any(distance(c, k) < 3 for c in placed for k in kiosks):
                continue
            found.append(fs)
        result = self._placements[cache_key] = sorted(found, key=lambda s: tuple(sorted(s)))
        return result

    def place(self, kind, size, cells, name=None):
        """Place a building; returns (building, bonuses on covered cells)."""
        cells = frozenset(cells)
        assert not any(c in self.cell_owner for c in cells), "cell already covered"
        b = Building(len(self.buildings), kind, size, cells, name=name)
        self.buildings.append(b)
        self._placements.clear()
        bonuses = []
        for c in sorted(cells):
            self.cell_owner[c] = b.id
            if self.mapdef.cells[c].bonus:
                bonuses.append(self.mapdef.cells[c].bonus)
        return b, bonuses

    def adjacent_terrain(self, cells, terrain):
        adj = {n for c in cells for n in neighbors(c)
               if n not in cells and n in self.mapdef.cells and self.mapdef.cells[n].terrain == terrain}
        return len(adj)

    def adjacent_buildings(self, b):
        ids = {self.cell_owner[n] for c in b.cells for n in neighbors(c)
               if n in self.cell_owner and self.cell_owner[n] != b.id}
        return [self.buildings[i] for i in sorted(ids)]

    def kiosk_income(self):
        total = 0
        for k in self.buildings:
            if k.kind != 'kiosk':
                continue
            for a in self.adjacent_buildings(k):
                if (a.kind in ('pavilion', 'unique') or a.kind in SPECIAL
                        or (a.kind == 'enclosure' and a.occupied)):
                    total += 1
        return total

    def is_fully_covered(self):
        return all(c in self.cell_owner for c in self.mapdef.buildable_cells())

    def count(self, kind):
        return sum(1 for b in self.buildings if b.kind == kind)
