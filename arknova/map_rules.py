"""Special rules of zoo maps 1-8 (Map 0, 3 and A have none beyond their layout).

Every rule checks state.map_name, so other maps (and Map 0) are unaffected. The rules attach to
generic hooks: effects.AFTER_BUILD_HOOKS and BREAK_INCOME_HOOKS, CONDITION_ALLOWANCE, SPONSOR_LEVEL_DELTA,
animals.ON_ENCLOSURE_FILLED and engine.EXTRA_OPTIONS / EXTRA_APPLY (the harbour).
The special cells come from tables.MAPS[map]["special"] (axial coordinates).
"""
from . import cards, effects as E, engine, sponsor_rules as SR, tables as T
from .actions import animals
from .hexmap import neighbors
from .state import Option, pop

HARBOR_MONEY = 3


def cells_of(state, name):
    return state.map["special"].get(name, [])


def _covered(player, cell):
    return cell in player.zoo.cell_owner


def _adjacent(cells, target):
    return any(n in target for c in cells for n in neighbors(c))


# ---- Map 1: observation tower -------------------------------------------------------------

OBSERVATION_APPEAL = 2


def _tower(state, p, building):
    if state.map_name == "plan1" and _adjacent(building.cells, cells_of(state, "observation_tower")):
        E.gain(state, p, "appeal", OBSERVATION_APPEAL)


# ---- Map 2: outdoor area ------------------------------------------------------------------

OUTDOOR_EXTRA_SIZE = 2


def _outdoor(state, p, building):
    if (state.map_name == "plan2" and building.kind == "enclosure"
            and _adjacent(building.cells, cells_of(state, "outdoor_area"))):
        building.extra_size = OUTDOOR_EXTRA_SIZE


# ---- Map 4: commercial harbour ------------------------------------------------------------

def harbor_active(state, p):
    return state.map_name == "plan4" and any(_covered(state.players[p], c)
                                             for c in cells_of(state, "harbor_connecting_building_space"))


def _harbor_options(state, frame):
    p = frame.player
    if (not harbor_active(state, p) or p != state.current or state.turn_flags.get("harbor")
            or any(f.kind in ("break", "setup_keep", "final_scoring") for f in state.stack)):
        return []
    return [Option(("harbor", c), f"Harbour: discard {cards.card(c)['name']} for {HARBOR_MONEY} money")
            for c in sorted(set(state.players[p].hand)) if _harbor_leaves_options(state, frame, c)]


def _mentions(key, card_id):
    return any(k == card_id or (isinstance(k, tuple) and _mentions(k, card_id)) for k in key)


def _harbor_leaves_options(state, frame, card_id):
    """Discarding `card_id` must not leave the pending decision with nothing to choose: in the middle of an
    action that plays a hand card (say, an association action whose only options play this card), discarding
    that card would. A hand discard is exempt (_harbor_apply ends it once satisfied). Only cards that the
    pending options name are checked, by computing the options without the card."""
    if frame.kind == "discard_hand":
        return True
    options = engine.legal_options(state, extras=False)
    if not any(_mentions(o.key, card_id) for o in options):
        return True
    hand = state.players[frame.player].hand
    i = hand.index(card_id)
    hand.pop(i)
    cached, state.cached_options = state.cached_options, None
    use_cache, state.cache_options = state.cache_options, False
    try:
        return bool(engine.CHOICES[frame.kind][0](state, frame))
    finally:
        hand.insert(i, card_id)
        state.cached_options, state.cache_options = cached, use_cache


def _harbor_apply(state, frame, option):
    player = state.players[frame.player]
    player.hand.remove(option.key[1])
    state.discard.append(option.key[1])
    state.turn_flags["harbor"] = True
    E.gain(state, frame.player, "money", HARBOR_MONEY)
    # The decision stays pending; if it is a hand discard that this discard has satisfied (hand empty, or down to
    # the hand limit at a break), it ends here: otherwise it would offer nothing (a crash) or force discards
    # below the limit.
    top = state.stack[-1]
    if top.kind == "discard_hand" and top.player == frame.player:
        limit = top.data.get("limit")
        if not player.hand or (limit is not None and len(player.hand) <= limit):
            pop(state, top)


# ---- Map 5: park restaurant ---------------------------------------------------------------

def _restaurant_income(state, p):
    if state.map_name != "plan5":
        return
    player = state.players[p]
    n = sum(1 for r in cells_of(state, "park_restaurant") for c in neighbors(r)
            if c in player.zoo.mapdef.cells and _covered(player, c))
    E.gain(state, p, "money", n)


# ---- Map 6: research institute -------------------------------------------------------------

def _institute(state, player, card_id):
    if state.map_name == "plan6" and any(_covered(player, c)
                                         for c in cells_of(state, "institute_connecting_building_space")):
        return 1
    return 0


# ---- Map 7: ice cream parlours ------------------------------------------------------------

def _ice_cream(state, p):
    if state.map_name != "plan7":
        return
    player = state.players[p]
    if all(_covered(player, c) for c in cells_of(state, "kiosk_bonus")):
        E.gain(state, p, "money", player.zoo.count("kiosk"))


# ---- Map 8: Hollywood Hills ---------------------------------------------------------------

def _is_sponsor(card_id):
    return cards.card(card_id)["type"] == "sponsor"


def _hollywood(state, p, building):
    if state.map_name != "plan8":
        return
    for _ in range(sum(1 for c in building.cells if c in cells_of(state, "H"))):
        SR.reveal_until(state, p, _is_sponsor)


def _hollywood_level(state, p, card_id):
    player = state.players[p]
    if state.map_name == "plan8" and all(_covered(player, c) for c in cells_of(state, "H")):
        return -1
    return 0


def register():
    E.AFTER_BUILD_HOOKS.extend([_outdoor, _hollywood])
    animals.ON_ENCLOSURE_FILLED.append(_tower)
    E.BREAK_INCOME_HOOKS.extend([_restaurant_income, _ice_cream])
    E.CONDITION_ALLOWANCE.append(_institute)
    E.SPONSOR_LEVEL_DELTA.append(_hollywood_level)
    engine.EXTRA_OPTIONS.append(_harbor_options)
    engine.EXTRA_APPLY["harbor"] = _harbor_apply


register()
