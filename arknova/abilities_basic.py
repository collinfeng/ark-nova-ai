"""Basic animal abilities: card draws, display and discard manipulation, and simple icon-count gains."""
from . import cards, effects
from .abilities import ability
from .state import Option, pop, push, register_choice

DONE = Option(("done",), "Done")
SUN_BATHING_PRICE = 4
POUCH_APPEAL = 2


def _draw_into_hand(state, p, n):
    for _ in range(n):
        c = effects.draw_from_deck(state)
        if c is not None:
            effects.to_hand(state, p, c, False)  # drawn face down from the deck


def _icons_everywhere(state, icon):
    return sum(cards.icons(pl).get(icon, 0) for pl in state.players)


# ---- simple gains -----------------------------------------------------------

@ability("SPRINT")
def sprint(state, p, card_id, value):
    _draw_into_hand(state, p, value)


@ability("JUMPING")
def jumping(state, p, card_id, value):
    effects.advance_break(state, p, value)
    effects.gain(state, p, "money", value)


@ability("INVENTIVE")
def inventive(state, p, card_id, value):
    effects.gain(state, p, "xtoken", 1)


@ability("INVENTIVE_BEAR")
def inventive_bear(state, p, card_id, value):
    effects.gain(state, p, "xtoken", min(3, _icons_everywhere(state, "bear")))


@ability("INVENTIVE_PRIMARY")
def inventive_primary(state, p, card_id, value):
    n = cards.icons(state.players[p]).get("primate", 0)
    effects.gain(state, p, "xtoken", 3 if n >= 5 else 2 if n >= 3 else 1 if n >= 1 else 0)


@ability("PACK")
def pack(state, p, card_id, value):
    effects.gain(state, p, "appeal", cards.icons(state.players[p]).get("predator", 0))


@ability("PETTING_ZOO_ANIMAL")
def petting_zoo_animal(state, p, card_id, value):
    effects.gain(state, p, "appeal", 3 * cards.icons(state.players[p]).get("pet", 0))


@ability("ICONIC_ANIMAL")
def iconic_animal(state, p, card_id, value):
    effects.gain(state, p, "appeal", min(8, _icons_everywhere(state, str(value).lower())))


@ability("FULL_THROATED")
def full_throated(state, p, card_id, value):
    effects.gain(state, p, "worker", 1)


# ---- pick N from a revealed set (Perception, Scavenging) ---------------------

def _pick_options(state, frame):
    return [Option(("pick", c), f"Keep {cards.card(c)['name']}") for c in frame.data["cards"]]


def _pick_apply(state, frame, option):
    d = frame.data
    d["cards"].remove(option.key[1])
    # Perception / Scavenging draw cards (not "reveal"): only the owner sees them
    effects.to_hand(state, frame.player, option.key[1], False)
    d["count"] -= 1
    if d["count"] <= 0 or not d["cards"]:
        state.discard.extend(d["cards"])
        pop(state, frame)


def _offer_pick(state, p, revealed, keep):
    revealed = [c for c in revealed if c is not None]
    if len(revealed) <= keep:
        for c in revealed:
            effects.to_hand(state, p, c, False)  # same drawn-not-revealed cards as above
    else:
        push(state, "ab_pick", p, cards=revealed, count=keep)


@ability("PERCEPTION_4")
def perception(state, p, card_id, value):
    _offer_pick(state, p, [effects.draw_from_deck(state) for _ in range(4)], 2)


@ability("SCAVENGING")
def scavenging(state, p, card_id, value):
    state.rng.shuffle(state.discard)
    taken = [state.discard.pop() for _ in range(min(value, len(state.discard)))]
    _offer_pick(state, p, taken, 1)


# ---- Hunter -----------------------------------------------------------------

def _hunter_options(state, frame):
    return [Option(("take", c), f"Take {cards.card(c)['name']}") for c in frame.data["cards"]
            if cards.card(c)["type"] == "animal"] + [effects.SKIP]


def _hunter_apply(state, frame, option):
    pop(state, frame)
    revealed = frame.data["cards"]
    if option.key[0] == "take":
        revealed.remove(option.key[1])
        effects.to_hand(state, frame.player, option.key[1], True)  # Hunter text says "reveal"
    state.discard.extend(revealed)


@ability("HUNTER")
def hunter(state, p, card_id, value):
    revealed = [c for c in (effects.draw_from_deck(state) for _ in range(value)) if c is not None]
    if any(cards.card(c)["type"] == "animal" for c in revealed):
        push(state, "ab_hunter", p, cards=revealed)
    else:
        state.discard.extend(revealed)


# ---- Snapping and Sponsor Magnet ----------------------------------------------

def _snap_options(state, frame):
    options = [Option(("take", i), f"Take display folder {i + 1}")
               for i, c in enumerate(state.display) if c is not None]
    if frame.data["can_replenish"]:
        options.append(Option(("replenish",), "Replenish the display"))
    return options + [effects.SKIP]


def _snap_apply(state, frame, option):
    d = frame.data
    if option.key[0] == "skip":
        pop(state, frame)
    elif option.key[0] == "replenish":
        d["can_replenish"] = False
        effects.refill_display(state)
    else:
        effects.to_hand(state, frame.player, effects.take_from_display(state, option.key[1]), True)  # display
        d["left"] -= 1
        d["can_replenish"] = d["replenish_between"] and d["left"] > 0
        d["replenish_between"] = False
        if d["left"] <= 0:
            pop(state, frame)


def _snapping(state, p, n):
    push(state, "ab_snap", p, left=n, can_replenish=False, replenish_between=n > 1)


@ability("SNAPPING_1")
def snapping_1(state, p, card_id, value):
    _snapping(state, p, 1)


@ability("SNAPPING_2")
def snapping_2(state, p, card_id, value):
    _snapping(state, p, 2)


@ability("SPONSOR_MAGNET")
def sponsor_magnet(state, p, card_id, value):
    for i, c in enumerate(state.display):
        if c is not None and cards.card(c)["type"] == "sponsor":
            effects.to_hand(state, p, effects.take_from_display(state, i), True)  # display


# ---- Sun Bathing, Digging, Pouch -------------------------------------------

def _hand_options(verb):
    return lambda state, frame: [Option((verb, c), f"{verb} {cards.card(c)['name']}")
                                 for c in state.players[frame.player].hand] + [DONE]


def _sun_apply(state, frame, option):
    player = state.players[frame.player]
    frame.data["left"] -= 1
    if option.key[0] == "done" or frame.data["left"] <= 0 or (option.key[0] == "sell" and len(player.hand) <= 1):
        pop(state, frame)
    if option.key[0] == "sell":
        player.hand.remove(option.key[1])
        state.discard.append(option.key[1])
        effects.gain(state, frame.player, "money", SUN_BATHING_PRICE)


@ability("SUN_BATHING")
def sun_bathing(state, p, card_id, value):
    if state.players[p].hand and value > 0:
        push(state, "ab_sun", p, left=value)


def _dig_options(state, frame):
    return ([Option(("discard_display", i), f"Discard display folder {i + 1}")
             for i, c in enumerate(state.display) if c is not None]
            + [Option(("discard_hand", c), f"Discard {cards.card(c)['name']} and draw")
               for c in state.players[frame.player].hand] + [DONE])


def _dig_apply(state, frame, option):
    player = state.players[frame.player]
    frame.data["left"] -= 1
    if option.key[0] == "done" or frame.data["left"] <= 0:
        pop(state, frame)
    if option.key[0] == "discard_display":
        gone = effects.take_from_display(state, option.key[1])
        effects.refill_display(state)  # refill first so a reshuffle cannot return the discarded card
        state.discard.append(gone)
    elif option.key[0] == "discard_hand":
        drawn = effects.draw_from_deck(state)  # draw first so the discarded card cannot be redrawn
        player.hand.remove(option.key[1])
        state.discard.append(option.key[1])
        if drawn is not None:
            effects.to_hand(state, frame.player, drawn, False)  # deck draw


@ability("DIGGING")
def digging(state, p, card_id, value):
    if value > 0:
        push(state, "ab_dig", p, left=value)


def _pouch_apply(state, frame, option):
    player = state.players[frame.player]
    frame.data["left"] -= 1
    if option.key[0] == "done" or frame.data["left"] <= 0 or len(player.hand) <= 1:
        pop(state, frame)
    if option.key[0] == "tuck":
        player.hand.remove(option.key[1])
        player.tucked.append(option.key[1])
        effects.gain(state, frame.player, "appeal", POUCH_APPEAL)


@ability("POUCH")
def pouch(state, p, card_id, value):
    if state.players[p].hand and value > 0:
        push(state, "ab_pouch", p, left=value)


# ---- Resistance, Assertion, Dominance -----------------------------------------

def _resist_options(state, frame):
    return [Option(("keep", c), f"Keep final scoring card {c}") for c in frame.data["cards"]]


def _resist_apply(state, frame, option):
    pop(state, frame)
    kept = option.key[1]
    state.players[frame.player].final_cards.append(kept)
    for c in frame.data["cards"]:
        if c != kept:
            state.final_deck.insert(0, c)


@ability("RESISTANCE")
def resistance(state, p, card_id, value):
    drawn = [state.final_deck.pop() for _ in range(min(2, len(state.final_deck)))]
    if len(drawn) == 1:
        state.players[p].final_cards.append(drawn[0])
    elif drawn:
        push(state, "ab_resist", p, cards=drawn)


def _project_options(state, frame):
    only = frame.data["only"]
    return [Option(("take", c), f"Take base project {cards.card(c)['name']}") for c in state.base_project_deck
            if only is None or c in only] + [effects.SKIP]


def _project_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "take":
        state.base_project_deck.remove(option.key[1])
        effects.to_hand(state, frame.player, option.key[1], True)  # base projects lie face up on the table


@ability("ASSERTION")
def assertion(state, p, card_id, value):
    if state.base_project_deck:
        push(state, "ab_project", p, only=None)


PRIMATES_PROJECT = "108"


@ability("DOMINANCE")
def dominance(state, p, card_id, value):
    if PRIMATES_PROJECT in state.base_project_deck:
        push(state, "ab_project", p, only=[PRIMATES_PROJECT])


register_choice("ab_pick", _pick_options, _pick_apply)
register_choice("ab_hunter", _hunter_options, _hunter_apply)
register_choice("ab_snap", _snap_options, _snap_apply)
register_choice("ab_sun", _hand_options("sell"), _sun_apply)
register_choice("ab_dig", _dig_options, _dig_apply)
register_choice("ab_pouch", _hand_options("tuck"), _pouch_apply)
register_choice("ab_resist", _resist_options, _resist_apply)
register_choice("ab_project", _project_options, _project_apply)
