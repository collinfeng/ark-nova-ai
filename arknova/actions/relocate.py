"""Moving animals into a newly built Reptile House or Large Bird Aviary (allowed only when it is built)."""
from .. import cards, effects as E
from ..state import Option, pop, push, register_choice
from . import animals


def _movable(state, p, building):
    """[(card id, spaces)] for animals in standard enclosures that fit the special enclosure."""
    player = state.players[p]
    found = []
    for card_id, (home, _) in player.housing.items():
        if player.zoo.buildings[home].kind != "enclosure":
            continue
        enc = cards.card(card_id)["enclosure"]
        for entry in enc.get("special", []):
            if (animals.SPECIAL_KINDS.get(entry["type"]) == building.kind
                    and building.size - building.used >= entry["size"]
                    and animals._terrain_ok(player, building, enc)):
                found.append((card_id, entry["size"]))
    return found


def after_special_built(state, p, building):
    if building.kind in ("reptile_house", "aviary") and _movable(state, p, building):
        push(state, "move_animals", p, building=building.id)


def _options(state, frame):
    building = state.players[frame.player].zoo.buildings[frame.data["building"]]
    return [Option(("move", c), f"Move {cards.card(c)['name']} into the new {building.kind}")
            for c, _ in _movable(state, frame.player, building)] + [Option(("done",), "Finish moving animals")]


def _apply(state, frame, option):
    if option.key[0] == "done":
        pop(state, frame)
        return
    player = state.players[frame.player]
    building = player.zoo.buildings[frame.data["building"]]
    card_id = option.key[1]
    spaces = dict(_movable(state, frame.player, building))[card_id]
    player.zoo.buildings[player.housing[card_id][0]].occupied = False
    building.used += spaces
    player.housing[card_id] = (building.id, spaces)
    if not _movable(state, frame.player, building):
        pop(state, frame)


E.AFTER_BUILD_HOOKS.append(after_special_built)
register_choice("move_animals", _options, _apply)
