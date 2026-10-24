"""Animals action: play animal cards from hand (or from the display on side II) into enclosures."""
from .. import abilities, cards, effects as E, sponsor_rules as SR, tables as T
from ..state import Option, pop, push, register_action, register_choice

ON_ANIMAL_PLAYED = []  # fn(state, player_idx, card_id), called after an animal is fully played
ON_ENCLOSURE_FILLED = []  # fn(state, player_idx, building): an empty standard enclosure received an animal

SPECIAL_KINDS = {"Reptile House": "reptile_house", "Large Bird Aviary": "aviary", "Petting Zoo": "petting_zoo"}


def _count(state, p, strength):
    return T.ANIMALS_TABLE[E.is_upgraded(state, p, "animals")][min(strength, 5) - 1]


def _num(v):
    return v if isinstance(v, int) else 0


def _cost(player, card_id):
    c = cards.card(card_id)
    discount = T.PARTNER_ZOO_DISCOUNT * sum(1 for k in cards.animal_continents(card_id) if k in player.partner_zoos)
    return max(0, c["cost"] - discount - SR.animal_cost_reduction(player, card_id))


def _terrain_ok(player, building, enc):
    return SR.ignores_terrain(player) or (player.zoo.adjacent_terrain(building.cells, "rock") >= _num(enc.get("rock"))
            and player.zoo.adjacent_terrain(building.cells, "water") >= _num(enc.get("water")))


def housings(player, card_id):
    """[(building id, spaces used)] where the animal could live; spaces is 0 for a standard enclosure."""
    enc = cards.card(card_id)["enclosure"]
    found = []
    size = enc.get("standard_size")
    if size is not None:
        for b in player.zoo.buildings:
            if b.kind == "enclosure" and not b.occupied and b.capacity >= size and _terrain_ok(player, b, enc):
                found.append((b.id, 0))
        # Flock Animal X: may instead join a herbivore in an occupied enclosure of size X or more.
        flock = next((a["value"] for a in cards.card(card_id)["abilities"] if a["keyword"] == "FLOCK_ANIMAL"), None)
        if flock is not None:
            for b in player.zoo.buildings:
                if (b.kind == "enclosure" and b.occupied and b.capacity >= flock and _terrain_ok(player, b, enc)
                        and any(home == b.id and "herbivore" in cards.card(other)["tags"]
                                for other, (home, _) in player.housing.items())):
                    found.append((b.id, 0))
    for entry in enc.get("special", []):
        kind = SPECIAL_KINDS.get(entry["type"])
        for b in player.zoo.buildings:
            if b.kind == kind and b.size - b.used >= entry["size"] and _terrain_ok(player, b, enc):
                found.append((b.id, entry["size"]))
    return found


def _plays(state, p, small_only=False):
    """[(key, card id, building id, spaces, total cost)] for every play available now."""
    player = state.players[p]
    sources = [(("play", c), c, 0) for c in player.hand]
    if E.is_upgraded(state, p, "animals"):
        sources += [(("play_display", i), state.display[i], i + 1) for i in E.cards_in_range(state, p)]
    plays = []
    for key, c, extra in sources:
        if cards.card(c)["type"] != "animal" or not SR.requirements_ok(player, c, state) \
                or not SR.animal_allowed(player, c) or (small_only and not cards.is_small(c)):
            continue
        cost = _cost(player, c) + extra
        if cost > player.money:
            continue
        for building_id, spaces in housings(player, c):
            plays.append(((key[0], key[1], building_id), c, building_id, spaces, cost))
    return plays


def feasible(state, p, strength):
    return _count(state, p, strength) > 0 and bool(_plays(state, p))


def start(state, p, strength):
    push(state, "act_animals", p, remaining=_count(state, p, strength), played=0, phase="play", all_small=True)
    if E.is_upgraded(state, p, "animals") and strength >= T.ANIMALS_II_REPUTATION_STRENGTH:
        E.gain(state, p, "reputation", 1)


def _small_in_display(state, p):
    return [i for i in E.cards_in_range(state, p)
            if cards.card(state.display[i])["type"] == "animal" and cards.is_small(state.display[i])]


def _advance(state, frame):
    """The current phase is over: go on to the next one, or leave the action.

    Phases: "play" (the action's own animals), then, with Waza Small Animals Program after only
    small animals, "bonus" (one further small animal) and "take" (one small animal from the display).
    """
    d = frame.data
    p = frame.player
    if d["phase"] == "play":
        if not (d["played"] and d["all_small"] and SR.has_small_program(state.players[p])):
            pop(state, frame)
            return
        d["phase"] = "bonus"
        if _plays(state, p, small_only=True):
            return
    if d["phase"] == "bonus":
        d["phase"] = "take"
        if _small_in_display(state, p):
            return
    pop(state, frame)


def _options(state, frame):
    d = frame.data
    p = frame.player
    if d["phase"] == "take":
        return [Option(("take_small", i), f"Take {cards.card(state.display[i])['name']} from folder {i + 1}")
                for i in _small_in_display(state, p)] or [Option(("done",), "Finish")]
    options = []
    for key, c, building_id, spaces, cost in _plays(state, p, small_only=d["phase"] == "bonus"):
        label = f"Play {cards.card(c)['name']} into building {building_id} for {cost}"
        options.append(Option(key, label))
    if d["played"] or not options or d["phase"] == "bonus":
        options.append(Option(("done",), "Finish"))
    return options


def _apply(state, frame, option):
    p = frame.player
    player = state.players[p]
    d = frame.data
    if option.key[0] == "done":
        if d["phase"] == "take":
            pop(state, frame)
        else:
            _advance(state, frame)
        return
    if option.key[0] == "take_small":
        pop(state, frame)
        E.to_hand(state, p, E.take_from_display(state, option.key[1]), True)  # display
        return
    match = next(m for m in _plays(state, p, small_only=d["phase"] == "bonus") if m[0] == option.key)
    _, card_id, building_id, spaces, cost = match
    player.money -= cost
    if option.key[0] == "play":
        player.hand.remove(card_id)
    else:
        E.take_from_display(state, option.key[1])
    building = player.zoo.buildings[building_id]
    filled = building.kind == "enclosure" and not building.occupied
    if building.kind == "enclosure":
        building.occupied = True
    else:
        building.used += spaces
    player.housing[card_id] = (building_id, spaces)
    icons_before = cards.icons(player)
    player.zoo_cards.append(card_id)
    d["remaining"] -= 1
    d["played"] += 1
    in_play_phase = d["phase"] == "play"
    d["all_small"] = d["all_small"] and cards.is_small(card_id)
    if not in_play_phase or d["remaining"] <= 0 or not _plays(state, p):
        _advance(state, frame)
    c = cards.card(card_id)
    for kind in ("appeal", "conservation", "reputation"):
        E.gain(state, p, kind, c[kind])
    SR.on_animal_played(state, p, card_id)
    for hook in ON_ANIMAL_PLAYED:
        hook(state, p, card_id)
    if filled:
        for hook in ON_ENCLOSURE_FILLED:
            hook(state, p, building)
    abilities.resolve(state, p, card_id)
    E.icons_played(state, p, cards.icons_of(card_id), icons_before)


def release_animal(state, p, card_id):
    player = state.players[p]
    player.zoo_cards.remove(card_id)
    building_id, spaces = player.housing.pop(card_id)
    player.appeal = max(0, player.appeal - cards.card(card_id)["appeal"])
    building = player.zoo.buildings[building_id]
    if building.kind == "enclosure":
        building.occupied = any(home == building_id for home, _ in player.housing.values())
    else:
        building.used -= spaces
    state.discard.append(card_id)


register_action("animals", feasible, start)
register_choice("act_animals", _options, _apply)
