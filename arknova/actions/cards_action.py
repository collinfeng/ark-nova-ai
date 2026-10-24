"""Cards action: advance the break 2, then draw (deck, or display in range on side II) or snap."""
from .. import effects as E
from .. import tables as T
from ..state import Option, pop, push, register_action, register_choice


def _row(state, p, strength):
    upgraded = E.is_upgraded(state, p, "cards")
    return upgraded, T.CARDS_TABLE[upgraded][min(strength, 5) - 1]


def feasible(state, p, strength):
    return True


def start(state, p, strength):
    upgraded, (draw, discard, may_snap) = _row(state, p, strength)
    push(state, "act_cards", p, draw=draw, discard=discard, may_snap=may_snap, upgraded=upgraded, drawn=0)
    E.advance_break(state, p, 2)


def _options(state, frame):
    d = frame.data
    options = []
    if state.deck or state.discard:
        options.append(Option(("deck",), "Draw from the deck"))
    if d["upgraded"]:
        options += [Option(("display", i), f"Take folder {i + 1}") for i in E.cards_in_range(state, frame.player)]
    if d["may_snap"] and d["drawn"] == 0:
        options += [Option(("snap", i), f"Snap folder {i + 1}")
                    for i, c in enumerate(state.display) if c is not None]
    return options or [E.SKIP]


def _apply(state, frame, option):
    d = frame.data
    player = state.players[frame.player]
    kind = option.key[0]
    if kind in ("snap", "skip"):
        pop(state, frame)
        if kind == "snap":
            E.to_hand(state, frame.player, E.take_from_display(state, option.key[1]), True)  # snap from display
        return
    if kind == "deck" and not d["upgraded"]:
        # Side I draws only from the deck, so there is nothing further to choose.
        for _ in range(d["draw"]):
            card_id = E.draw_from_deck(state)
            if card_id is not None:
                E.to_hand(state, frame.player, card_id, False)  # deck draw
        d["drawn"] = d["draw"]
    else:
        if kind == "deck":
            E.to_hand(state, frame.player, E.draw_from_deck(state), False)
        else:
            E.to_hand(state, frame.player, E.take_from_display(state, option.key[1]), True)  # display
        d["drawn"] += 1
    if d["drawn"] >= d["draw"]:
        pop(state, frame)
        if d["discard"] and player.hand:
            push(state, "discard_hand", frame.player, count=d["discard"])


register_action("cards", feasible, start)
register_choice("act_cards", _options, _apply)
