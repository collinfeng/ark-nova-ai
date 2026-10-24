"""Sponsor card effects: passives (icon triggers, build hooks), immediate, income and endgame effects.

Cards are registered in the effects.py tables by card id. Cards whose rules change other
parts of the engine (action costs, projects, unique building placement, ...) live elsewhere.
Cards 205, 223, 255 and 256 only have printed points and icons and register nothing here.
"""
from . import abilities_basic as AB, cards, effects as E, mapinfo, tables as T
from .hexmap import neighbors
from .state import push

CATEGORY_CARD = {"231": "primate", "232": "reptile", "233": "bird", "234": "predator", "235": "herbivore"}
MONEY_ANY_ZOO = {"236": "primate", "237": "reptile", "238": "bird", "239": "predator", "240": "herbivore"}
APPEAL_OWN_ZOO = {"243": "herbivore", "244": "bird", "245": "water", "246": "rock", "247": "primate"}
INCOME_THRESHOLDS = [(5, 9), (3, 6), (1, 3)]  # (icons needed, money), best first
EXPLORER_ICONS = set(T.CONTINENTS) | set(T.ANIMAL_CATEGORIES)


def _icons(state, p):
    return cards.icons(state.players[p])


def _distinct(state, p, kinds):
    have = _icons(state, p)
    return sum(1 for k in kinds if have.get(k, 0) > 0)


def _others(state, p):
    return [q for q in range(state.n) if q != p]


def _give_others_money(state, p, conservation, amount=2):
    for q in _others(state, p):
        E.gain(state, q, "money", amount * conservation)


# ---- icon triggers: own zoo --------------------------------------------------

def _own_icon_gain(card_ids_to_icon, kind, amount):
    def make(icon):
        def trigger(state, owner, player, icons, new_icons):
            if player == owner:
                E.gain(state, owner, kind, amount * icons.get(icon, 0))
        return trigger
    for card_id, icon in card_ids_to_icon.items():
        E.ICON_TRIGGERS[card_id] = make(icon)


_own_icon_gain({"202": "science"}, "reputation", 1)
_own_icon_gain({"204": "science"}, "conservation", 1)
_own_icon_gain(APPEAL_OWN_ZOO, "appeal", 2)
_own_icon_gain({"248": "primate"}, "xtoken", 1)


def _free_build_trigger(card_id, icon, kind, size):
    def trigger(state, owner, player, icons, new_icons):
        if player != owner:
            return
        zoo = state.players[owner].zoo
        for _ in range(icons.get(icon, 0)):
            if zoo.legal_placements(kind, size, build2="build" in state.players[owner].upgraded,
                                    any_terrain="219" in state.players[owner].zoo_cards):  # Diversity Researcher
                push(state, "free_build", owner, kinds=[(kind, size)])
    E.ICON_TRIGGERS[card_id] = trigger


_free_build_trigger("210", "americas", "kiosk", 1)
_free_build_trigger("211", "europe", "enclosure", 1)
_free_build_trigger("213", "asia", "pavilion", 1)


@E.register(E.ICON_TRIGGERS, "212")
def expert_australia(state, owner, player, icons, new_icons):
    if player == owner:
        for _ in range(icons.get("australia", 0)):
            if state.players[owner].hand:
                push(state, "ab_pouch", owner, left=1)


@E.register(E.ICON_TRIGGERS, "214")
def expert_africa(state, owner, player, icons, new_icons):
    if player == owner:
        for _ in range(icons.get("africa", 0)):
            push(state, "clever", owner)


@E.register(E.ICON_TRIGGERS, "249")
def barred_owl_hut(state, owner, player, icons, new_icons):
    """Perception 2 per bird icon: draw 2, keep 1."""
    if player == owner:
        for _ in range(icons.get("bird", 0)):
            AB._offer_pick(state, owner, [E.draw_from_deck(state) for _ in range(2)], 1)


@E.register(E.ICON_TRIGGERS, "250")
def sea_turtle_tank(state, owner, player, icons, new_icons):
    """Sunbathing 2 per reptile icon."""
    if player == owner:
        for _ in range(icons.get("reptile", 0)):
            if state.players[owner].hand:
                push(state, "ab_sun", owner, left=2)


@E.register(E.ICON_TRIGGERS, "252")
def hyena_compound(state, owner, player, icons, new_icons):
    """Hunter X per predator icon, X = predator icons in the owner's zoo."""
    if player != owner:
        return
    for _ in range(icons.get("predator", 0)):
        x = _icons(state, owner).get("predator", 0)
        AB.hunter(state, owner, "252", x)


@E.register(E.ICON_TRIGGERS, "262")
def explorer(state, owner, player, icons, new_icons):
    if player == owner:
        n = sum(1 for i in new_icons if i in EXPLORER_ICONS)
        E.gain(state, owner, "appeal", n)
        E.gain(state, owner, "money", 2 * n)


# ---- icon triggers: any zoo (the owner gains) ----------------------------------

def _any_icon_gain(card_ids_to_icon, kind, amount):
    def make(icon):
        def trigger(state, owner, player, icons, new_icons):
            E.gain(state, owner, kind, amount * icons.get(icon, 0))
        return trigger
    for card_id, icon in card_ids_to_icon.items():
        E.ICON_TRIGGERS[card_id] = make(icon)


_any_icon_gain({"208": "science"}, "money", 2)
_any_icon_gain(MONEY_ANY_ZOO, "money", 3)
_any_icon_gain({"251": "bear"}, "appeal", 2)


# ---- immediate -----------------------------------------------------------------

@E.register(E.IMMEDIATE, "201", "254")
def take_card(state, p):
    E.gain(state, p, "card", 1)


@E.register(E.IMMEDIATE, "216")
def talented_communicator(state, p):
    E.gain(state, p, "worker", 1)


@E.register(E.IMMEDIATE, "207")
def basic_research(state, p):
    n = _distinct(state, p, T.CONTINENTS + T.ANIMAL_CATEGORIES) // 2
    _give_others_money(state, p, n)
    E.gain(state, p, "conservation", n)


@E.register(E.IMMEDIATE, "222")
def release_of_patents(state, p):
    n = min(3, _icons(state, p).get("science", 0))
    _give_others_money(state, p, n)
    E.gain(state, p, "conservation", n)


def _appeal_per_icon(card_ids_to_icon):
    def make(icon):
        return lambda state, p: E.gain(state, p, "appeal", _icons(state, p).get(icon, 0))
    for card_id, icon in card_ids_to_icon.items():
        E.IMMEDIATE[card_id] = make(icon)


_appeal_per_icon({"208": "science", "241": "water", **{c: i for c, i in CATEGORY_CARD.items()}})


@E.register(E.IMMEDIATE, "242")
def geologist_immediate(state, p):
    E.gain(state, p, "appeal", 3 * (_icons(state, p).get("rock", 0) // 2))


@E.register(E.IMMEDIATE, "258")
def native_seabirds_immediate(state, p):
    E.gain(state, p, "appeal", mapinfo.connected_terrain(state.players[p].zoo, "water")[0])


@E.register(E.IMMEDIATE, "259")
def native_lizards_immediate(state, p):
    E.gain(state, p, "appeal", mapinfo.connected_terrain(state.players[p].zoo, "rock")[0])


@E.register(E.IMMEDIATE, "260")
def native_farm_animals_immediate(state, p):
    E.gain(state, p, "appeal", mapinfo.connected_empty_border(state.players[p].zoo))


@E.register(E.IMMEDIATE, "264")
def new_world_monkeys_immediate(state, p):
    E.gain(state, p, "appeal", mapinfo.bonus_spaces(state.players[p].zoo)[0])


@E.register(E.IMMEDIATE, "262")
def explorer_immediate(state, p):
    E.gain(state, p, "money", 2 * _distinct(state, p, T.CONTINENTS + T.ANIMAL_CATEGORIES))


# ---- income ----------------------------------------------------------------------

@E.register(E.INCOME, "201")
def science_lab_income(state, p):
    E.gain(state, p, "card", 1)


@E.register(E.INCOME, "206")
def medical_breakthrough_income(state, p):
    E.gain(state, p, "conservation", 1)


@E.register(E.INCOME, "209")
def technology_institute_income(state, p):
    E.gain(state, p, "xtoken", 1)


@E.register(E.INCOME, "220")
def federal_grants_income(state, p):
    E.gain(state, p, "money", 3)


def _sponsorship_income(icon):
    def income(state, p):
        n = _icons(state, p).get(icon, 0)
        E.gain(state, p, "money", next((money for need, money in INCOME_THRESHOLDS if n >= need), 0))
    return income


for _card_id, _icon in CATEGORY_CARD.items():
    E.INCOME[_card_id] = _sponsorship_income(_icon)


@E.register(E.INCOME, "257")
def side_entrance_income(state, p):
    zoo = state.players[p].zoo
    entrance = next((b for b in zoo.buildings if b.name == "257"), None)
    if entrance is None:
        return
    n = sum(1 for b in zoo.adjacent_buildings(entrance) if not (b.kind == "enclosure" and not b.occupied))
    E.gain(state, p, "money", 2 * n)


# ---- build hooks ---------------------------------------------------------------------

def _covered_next_to(zoo, building, terrain):
    return sum(1 for c in building.cells
               if any(n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == terrain for n in neighbors(c)))


def _terrain_build_hook(state, p, building):
    player = state.players[p]
    for card_id, terrain in (("241", "water"), ("242", "rock")):
        if card_id in player.zoo_cards:
            E.gain(state, p, "money", _covered_next_to(player.zoo, building, terrain))


if _terrain_build_hook not in E.AFTER_BUILD_HOOKS:
    E.AFTER_BUILD_HOOKS.append(_terrain_build_hook)


# ---- endgame ---------------------------------------------------------------------------

def _score_threshold(icon, steps):
    """steps: [(icons needed, conservation)] best first; the best one reached counts."""
    def endgame(state, p):
        n = _icons(state, p).get(icon, 0)
        E.score(state, p, "conservation", next((c for need, c in steps if n >= need), 0))
    return endgame


E.ENDGAME["201"] = _score_threshold("science", [(6, 2), (3, 1)])
E.ENDGAME["251"] = _score_threshold("bear", [(6, 2), (3, 1)])
for _card_id, _icon in APPEAL_OWN_ZOO.items():
    E.ENDGAME[_card_id] = _score_threshold(_icon, [(6, 1)])


@E.register(E.ENDGAME, "208", "261")
def five_categories(state, p):
    if _distinct(state, p, T.ANIMAL_CATEGORIES) >= 5:
        E.score(state, p, "conservation", 1)


@E.register(E.ENDGAME, "225", "226")
def five_continents(state, p):
    if _distinct(state, p, T.CONTINENTS) >= 5:
        E.score(state, p, "conservation", 1)


@E.register(E.ENDGAME, "241")
def hydrologist_endgame(state, p):
    if mapinfo.connected_terrain(state.players[p].zoo, "water")[1] == 0:
        E.score(state, p, "conservation", 1)


@E.register(E.ENDGAME, "242")
def geologist_endgame(state, p):
    if mapinfo.connected_terrain(state.players[p].zoo, "rock")[1] == 0:
        E.score(state, p, "conservation", 1)


@E.register(E.ENDGAME, "257")
def side_entrance_endgame(state, p):
    if state.players[p].zoo.is_fully_covered():
        E.score(state, p, "appeal", 5)


@E.register(E.ENDGAME, "258")
def native_seabirds_endgame(state, p):
    E.score(state, p, "conservation", mapinfo.connected_terrain(state.players[p].zoo, "water")[1] // 2)


@E.register(E.ENDGAME, "259")
def native_lizards_endgame(state, p):
    E.score(state, p, "conservation", mapinfo.connected_terrain(state.players[p].zoo, "rock")[1] // 2)


@E.register(E.ENDGAME, "260")
def native_farm_animals_endgame(state, p):
    E.score(state, p, "conservation", len(mapinfo.empty_spaces(state.players[p].zoo)) // 6)


@E.register(E.ENDGAME, "264")
def new_world_monkeys_endgame(state, p):
    E.score(state, p, "conservation", mapinfo.bonus_spaces(state.players[p].zoo)[1] // 2)
