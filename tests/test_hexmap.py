import copy
from collections import Counter

from arknova.hexmap import (DIRS, MAP0, SHAPES, Cell, MapDef, Zoo, distance,
                            neighbors, orientations)


def small(cols):
    return MapDef.from_columns("s", cols)


def test_map0_counts():
    cs = MAP0.cells.values()
    assert len(MAP0.cells) == 58
    t = Counter(c.terrain for c in cs)
    assert (t['water'], t['rock'], t['plain']) == (10, 9, 39)
    assert sum(c.build2_only for c in cs) == 2
    assert Counter(c.bonus for c in cs if c.bonus) == {
        'xtoken': 3, 'card': 3, 'money5': 2, 'money10': 1, 'rep2': 2, 'clever': 1}


def test_coordinates_and_neighbors():
    assert (1, -1 + 0) in neighbors((0, 0))  # NE of (0,0)
    # col1,row0 -> (1, 0 - 1) = (1,-1) is NE of col0,row0 -> (0,0)
    assert (1, -1) in MAP0.cells and neighbors((0, 0))[1] == (1, -1)
    assert MAP0.cells[(1, -1)].terrain == 'water'
    assert len(DIRS) == 6 and distance((0, 0), (2, -1)) == 2 and distance((0, 0), (3, 0)) == 3


def test_orientation_counts():
    exp = {('enclosure', 1): 1, ('enclosure', 2): 3, ('enclosure', 3): 2, ('enclosure', 4): 3,
           ('enclosure', 5): 6, ('petting_zoo', 3): 6, ('reptile_house', 5): 3, ('aviary', 5): 6}
    for k, n in exp.items():
        assert len(orientations(SHAPES[k])) == n, k


def test_border_and_adjacency():
    z = Zoo(MAP0)
    ps = z.legal_placements('enclosure', 1)
    assert ps and all(MAP0.is_border(next(iter(p))) for p in ps)
    assert frozenset({(4, 0 - 2)}) not in ps or MAP0.is_border((4, -2))
    b, _ = z.place('enclosure', 1, ps[0])
    occ = {n for n in neighbors(next(iter(b.cells)))}
    for p in z.legal_placements('enclosure', 1):
        assert next(iter(p)) in occ


def test_excluded_terrain_and_build2():
    z = Zoo(MAP0)
    allp = {c for p in z.legal_placements('pavilion', 1) for c in p}
    for c in allp:
        assert MAP0.cells[c].terrain == 'plain' and not MAP0.cells[c].build2_only
    b2 = (6, 2 - 3)
    assert MAP0.cells[b2].build2_only
    m = small([['.:build2', '.']])
    z = Zoo(m)
    assert frozenset({(0, 0)}) not in z.legal_placements('pavilion', 1)
    assert frozenset({(0, 0)}) in z.legal_placements('pavilion', 1, build2=True)


def test_covered_cells_excluded():
    m = small([['.', '.']])
    z = Zoo(m)
    z.place('pavilion', 1, [(0, 0)])
    assert z.legal_placements('pavilion', 1) == [frozenset({(0, 1)})]


def test_kiosk_distance():
    m = small([['.'] * 6])
    z = Zoo(m)
    z.place('kiosk', 1, [(0, 0)])
    # adjacent building needed, but kiosk needs distance >= 3: none adjacent qualifies
    assert z.legal_placements('kiosk', 1) == []
    z.place('pavilion', 1, [(0, 1)])
    z.place('pavilion', 1, [(0, 2)])
    assert z.legal_placements('kiosk', 1) == [frozenset({(0, 3)})]


def test_special_one_per_zoo():
    m = small([['.'] * 8, ['.'] * 8, ['.'] * 8])
    for kind, size in [('petting_zoo', 3), ('reptile_house', 5), ('aviary', 5)]:
        z = Zoo(m)
        assert z.legal_placements(kind, size)
        z.place(kind, size, z.legal_placements(kind, size)[0])
        assert z.legal_placements(kind, size) == []
        assert z.count(kind) == 1


def test_place_bonuses():
    m = small([['.:card', '.:money5', '.']])
    z = Zoo(m)
    b, bon = z.place('enclosure', 2, [(0, 0), (0, 1)])
    assert bon == ['card', 'money5'] and b.id == 0
    assert z.place('pavilion', 1, [(0, 2)])[1] == []


def test_need_rock_water():
    m = small([['.', 'R', '.', 'W', '.']])
    z = Zoo(m)
    ps = z.legal_placements('pavilion', 1, need_rock=1)
    assert ps == [frozenset({(0, 0)}), frozenset({(0, 2)})]
    assert z.legal_placements('pavilion', 1, need_water=1) == [frozenset({(0, 2)}), frozenset({(0, 4)})]
    assert z.legal_placements('pavilion', 1, need_rock=1, need_water=1) == [frozenset({(0, 2)})]
    assert z.adjacent_terrain({(0, 2)}, 'rock') == 1
    assert z.adjacent_terrain({(0, 2)}, 'water') == 1
    assert z.legal_placements('pavilion', 1, need_rock=2) == []


def test_kiosk_income():
    m = small([['.'] * 9])
    z = Zoo(m)
    k, _ = z.place('kiosk', 1, [(0, 4)])
    assert z.kiosk_income() == 0
    e, _ = z.place('enclosure', 1, [(0, 3)])
    z.place('kiosk', 1, [(0, 5)])  # other kiosk gives nothing
    assert z.kiosk_income() == 0
    e.occupied = True
    assert z.kiosk_income() == 1
    z.place('pavilion', 1, [(0, 6)])  # adjacent to the second kiosk
    assert z.kiosk_income() == 2
    z.place('unique', 1, [(0, 2)], name='x')
    z.place('petting_zoo', 1, [(0, 7)])  # not adjacent to a kiosk
    assert z.kiosk_income() == 2
    assert z.adjacent_buildings(k) == [z.buildings[1], z.buildings[2]]


def test_empty_special_counts_for_kiosk():
    m = small([['.'] * 3])
    z = Zoo(m)
    z.place('aviary', 1, [(0, 0)])
    z.place('kiosk', 1, [(0, 1)])
    assert z.kiosk_income() == 1


def test_fully_covered():
    m = small([['.', 'W', '.']])
    z = Zoo(m)
    assert not z.is_fully_covered()
    z.place('pavilion', 1, [(0, 0)])
    assert not z.is_fully_covered()
    z.place('pavilion', 1, [(0, 2)])
    assert z.is_fully_covered()


def test_deepcopy_independence():
    m = small([['.'] * 4])
    z = Zoo(m)
    z.place('pavilion', 1, [(0, 0)])
    z2 = copy.deepcopy(z)
    z2.place('pavilion', 1, [(0, 1)])
    z2.buildings[0].occupied = True
    assert len(z.buildings) == 1 and not z.buildings[0].occupied
    assert (0, 1) not in z.cell_owner
