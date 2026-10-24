"""Build action: side I builds one building (size <= strength); side II several different ones
(total size <= strength). Each space costs tables.BUILD_COST_PER_SPACE."""
from .. import effects as E
from .. import sponsor_rules as SR
from .. import tables as T
from ..state import Option, pop, push, register_action, register_choice

SIDE_I = [("kiosk", 1), ("pavilion", 1)] + [("enclosure", s) for s in range(1, 6)] + [("petting_zoo", 3)]
SIDE_II_EXTRA = [("reptile_house", 5), ("aviary", 5)]


def _candidates(state, p, budget, built):
    """Yield (kind, size, placements) for every building that can be built right now."""
    player = state.players[p]
    upgraded = E.is_upgraded(state, p, "build")
    kinds = SIDE_I + (SIDE_II_EXTRA if upgraded else [])
    for kind, size in kinds:
        if size > budget or (kind, size) in built:
            continue
        if T.BUILD_COST_PER_SPACE * size > player.money:
            continue
        placements = player.zoo.legal_placements(kind, size, build2=upgraded, any_terrain=SR.ignores_terrain(player))
        if placements:
            yield kind, size, placements


def feasible(state, p, strength):
    return any(True for _ in _candidates(state, p, strength, ()))


def start(state, p, strength):
    push(state, "act_build", p, budget=strength, built=[], upgraded=E.is_upgraded(state, p, "build"),
         normal_done=False, engineer_used=False)


def _normal_open(state, p, d):
    """Whether the action's own building budget still allows another building."""
    if d["normal_done"] or d["budget"] <= 0:
        return False
    return any(True for _ in _candidates(state, p, d["budget"], d["built"]))


def _engineer_candidates(state, p, d):
    """Engineer: once per action, one more building of the kind and size just built (no special
    enclosures), at the normal cost, regardless of the budget or the no-identical rule."""
    player = state.players[p]
    if d["engineer_used"] or not SR.has_engineer(player):
        return
    for kind, size in d["built"]:
        if kind not in SR.ENGINEER_KINDS or T.BUILD_COST_PER_SPACE * size > player.money:
            continue
        placements = player.zoo.legal_placements(kind, size, build2=d["upgraded"],
                                                 any_terrain=SR.ignores_terrain(player))
        if placements:
            yield kind, size, placements


def _options(state, frame):
    d = frame.data
    p = frame.player
    options = []
    if not d["normal_done"]:
        for kind, size, placements in _candidates(state, p, d["budget"], d["built"]):
            cost = T.BUILD_COST_PER_SPACE * size
            for cells in placements:
                key = E.cells_key(cells)
                options.append(Option(("build", kind, size, key), f"Build {kind} {size} at {key} for {cost}"))
    for kind, size, placements in _engineer_candidates(state, p, d):
        cost = T.BUILD_COST_PER_SPACE * size
        for cells in placements:
            key = E.cells_key(cells)
            options.append(Option(("engineer", kind, size, key),
                                  f"Engineer: build another {kind} {size} at {key} for {cost}"))
    if d["built"]:
        options.append(Option(("done",), "Done building"))
    elif not options:
        options.append(E.SKIP)  # defensive: not reachable when start() follows feasible()
    return options


def _apply(state, frame, option):
    if option.key[0] not in ("build", "engineer"):
        pop(state, frame)
        return
    kind_of_build, kind, size, cells = option.key
    d = frame.data
    p = frame.player
    state.players[p].money -= T.BUILD_COST_PER_SPACE * size
    if kind_of_build == "engineer":
        d["engineer_used"] = True
    else:
        d["budget"] -= size
        d["built"].append((kind, size))
        if not d["upgraded"] or d["budget"] <= 0:
            d["normal_done"] = True
    # Engineer may still offer a building afterwards; only leave early when it cannot.
    engineer_possible = SR.has_engineer(state.players[p]) and not d["engineer_used"]
    finished = d["normal_done"] and not engineer_possible
    if finished:
        pop(state, frame)
    E.place_building(state, p, kind, size, frozenset(cells))
    if not finished and not _normal_open(state, p, d) and not any(True for _ in _engineer_candidates(state, p, d)):
        pop(state, frame)  # nothing more to build (money from bonuses was already counted)


register_action("build", feasible, start)
register_choice("act_build", _options, _apply)
