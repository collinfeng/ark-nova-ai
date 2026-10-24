"""Sponsors action: play sponsor cards, or advance the break and take money.

`play_sponsor` is the one way a sponsor enters play (this action, the bonus tile, Okapi
Stable): printed points, unique building, immediate effect and icon triggers. The effects
themselves are registered by card id in sponsor_effects.py and sponsor_rules.py.
"""
from .. import cards, effects as E, sponsor_rules as SR
from ..state import Option, pop, push, register_action, register_choice


def _budget(state, p, strength):
    return strength + 1 if E.is_upgraded(state, p, "sponsors") else strength


def building_spots(state, p, card_id):
    """Legal positions for the card's unique building ([] if none); None if the card has no building."""
    spec = cards.card(card_id).get("building")
    if not spec:
        return None
    player = state.players[p]
    return player.zoo.legal_placements(
        "unique", spec["size"], build2="build" in player.upgraded, shape=[tuple(c) for c in spec["shape"]],
        need_rock=spec["rock"], need_water=spec["water"], min_border=spec["min_border"],
        adjacent=spec["needs_adjacency"], any_terrain="219" in player.zoo_cards)


def can_play(state, p, card_id):
    """Conditions and (for unique buildings) room on the map; level and money are checked by the caller."""
    return (cards.card(card_id)["type"] == "sponsor"
            and cards.unmet_requirements(state.players[p], card_id) == 0
            and building_spots(state, p, card_id) != [])


def play_sponsor(state, p, card_id):
    """Put a sponsor card into play: printed points, unique building, immediate effect, icon triggers.
    The caller has already paid and removed the card from where it came from."""
    player = state.players[p]
    c = cards.card(card_id)
    icons_before = cards.icons(player)
    player.zoo_cards.append(card_id)
    # Icon triggers and the immediate effect run now; the building frame is pushed last so
    # that it is the first choice the player makes.
    E.icons_played(state, p, cards.icons_of(card_id), icons_before)
    if card_id in E.IMMEDIATE:
        E.IMMEDIATE[card_id](state, p)
    for kind in ("reputation", "conservation", "appeal"):
        E.gain(state, p, kind, c[kind])
    if c.get("building"):
        push(state, "sponsor_building", p, card=card_id)


def _level(state, p, card_id):
    return SR.sponsor_level(state, p, card_id)


def _playable(state, p, budget):
    """(source, card id, extra cost) for sponsor cards the player could play within the level budget."""
    player = state.players[p]
    found = [("hand", c, 0) for c in player.hand]
    if E.is_upgraded(state, p, "sponsors"):
        found += [(("display", i), state.display[i], i + 1) for i in E.cards_in_range(state, p)]
    return [(src, c, extra) for src, c, extra in found
            if cards.card(c)["type"] == "sponsor" and _level(state, p, c) <= budget
            and player.money >= extra and can_play(state, p, c)]


def feasible(state, p, strength):
    return True  # the break option is always available


def start(state, p, strength):
    push(state, "act_sponsors", p, strength=strength, budget=_budget(state, p, strength), played=0)


def _options(state, frame):
    d = frame.data
    options = []
    if d["played"] == 0:
        options.append(Option(("break",), f"Break {d['strength']} and take money"))
    for src, card_id, extra in _playable(state, frame.player, d["budget"]):
        key = ("play", card_id) if src == "hand" else ("play_display", src[1])
        options.append(Option(key, f"Play {cards.card(card_id)['name']}"))
    if d["played"]:
        options.append(Option(("done",), "Finish"))
    return options


def _apply(state, frame, option):
    d = frame.data
    p = frame.player
    player = state.players[p]
    kind = option.key[0]
    if kind in ("break", "done"):
        pop(state, frame)
        if kind == "break":
            upgraded = E.is_upgraded(state, p, "sponsors")
            E.gain(state, p, "money", d["strength"] * (2 if upgraded else 1))
            E.advance_break(state, p, d["strength"])
        return
    if kind == "play":
        card_id = option.key[1]
        player.hand.remove(card_id)
    else:
        player.money -= option.key[1] + 1
        card_id = E.take_from_display(state, option.key[1])
    c = cards.card(card_id)
    d["budget"] -= _level(state, p, card_id)
    d["played"] += 1
    if not E.is_upgraded(state, p, "sponsors"):
        pop(state, frame)
    play_sponsor(state, p, card_id)


def _building_options(state, frame):
    spots = building_spots(state, frame.player, frame.data["card"]) or []
    return [Option(("place", E.cells_key(c)), f"Place the building at {E.cells_key(c)}") for c in spots] or [E.SKIP]


def _building_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "place":
        c = cards.card(frame.data["card"])
        E.place_building(state, frame.player, "unique", c["building"]["size"], frozenset(option.key[1]),
                         name=frame.data["card"])


def _paid_options(state, frame):
    """Play one sponsor card from hand by paying its level in money (bonus tile, Okapi Stable)."""
    player = state.players[frame.player]
    return [Option(("play", c), f"Play {cards.card(c)['name']} for {_level(state, frame.player, c)} money")
            for c in player.hand
            if can_play(state, frame.player, c) and player.money >= _level(state, frame.player, c)] + [E.SKIP]


def _paid_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "play":
        player = state.players[frame.player]
        player.money -= _level(state, frame.player, option.key[1])
        player.hand.remove(option.key[1])
        play_sponsor(state, frame.player, option.key[1])


register_action("sponsors", feasible, start)
register_choice("act_sponsors", _options, _apply)
register_choice("sponsor_building", _building_options, _building_apply)
register_choice("paid_sponsor", _paid_options, _paid_apply)
