"""Animal abilities that touch action cards, other players' tokens, or hand over resources.

Clever, Boost, Multiplier, Action: X, Determination, Posturing, Peacocking, Venom,
Constriction, Pilfering and Hypnosis. Venom, Constriction, Pilfering and Hypnosis only
reach a player for whom `effects.affected` holds (appeal >= 5, no Quarantine Lab).
Importing this module registers everything.
"""
from . import effects, tables as T
from .abilities import ability, after_finishing
from .state import Option, pop, push, register_choice

ACTION_FOR = {"ASSOCIATION": "association", "BUILDING": "build", "CARDS": "cards",
              "CARD": "cards", "SPONSORS": "sponsors", "ANIMAL": "animals"}


# ---- Clever and Boost -----------------------------------------------------------

@ability("CLEVER")
def clever(state, p, card_id, value):
    after_finishing(state, "clever", p)


def _boost(action):
    def boost(state, p, card_id, value):
        after_finishing(state, "ab_boost", p, action=action)
    return boost


for _suffix in ("ANIMAL", "ASSOCIATION", "BUILDING", "CARD", "SPONSORS"):
    ability("BOOST_" + _suffix)(_boost(ACTION_FOR[_suffix]))


def _boost_options(state, frame):
    return [Option(("boost", 1), f"Place {frame.data['action']} on slot 1"),
            Option(("boost", 5), f"Place {frame.data['action']} on slot 5"),
            effects.SKIP]


def _boost_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] != "boost":
        return
    slots = state.players[frame.player].slots
    slots.remove(frame.data["action"])
    slots.insert(option.key[1] - 1, frame.data["action"])


# ---- Multiplier and Action: X, Determination ------------------------------------

def _multiplier(action):
    def multiplier(state, p, card_id, value):
        effects.add_action_token(state, p, action, "multiplier")
    return multiplier


def _action(action):
    def take_action(state, p, card_id, value):
        from . import engine
        engine.offer_extra_action(state, p, [action])
    return take_action


for _suffix in ("ASSOCIATION", "BUILDING", "CARD", "SPONSORS"):
    ability("MULTIPLIER_" + _suffix)(_multiplier(ACTION_FOR[_suffix]))
for _suffix in ("ASSOCIATION", "BUILDING", "CARDS", "SPONSORS"):
    ability("ACTION_" + _suffix)(_action(ACTION_FOR[_suffix]))


@ability("DETERMINATION")
def determination(state, p, card_id, value):
    from . import engine
    engine.offer_extra_action(state, p, T.ACTIONS, optional=False)


# ---- Posturing and Peacocking -----------------------------------------------------

@ability("POSTURING")
def posturing(state, p, card_id, value):
    for _ in range(value or 1):
        push(state, "free_build", p, kinds=[("kiosk", 1), ("pavilion", 1)])


@ability("PEACOCKING")
def peacocking(state, p, card_id, value):
    push(state, "free_build", p, kinds=[("aviary", 5)])


# ---- Venom and Constriction -------------------------------------------------------

@ability("VENOM")
def venom(state, p, card_id, value):
    me = state.players[p]
    for q, victim in enumerate(state.players):
        if q == p or victim.appeal <= me.appeal or not effects.affected(state, q):
            continue
        left = value or 1
        for action in list(victim.slots):  # slot 1 upward
            if left <= 0:
                break
            if effects.add_action_token(state, q, action, "venom"):
                left -= 1


@ability("CONSTRICTION")
def constriction(state, p, card_id, value):
    me = state.players[p]
    for q, victim in enumerate(state.players):
        if q == p or not effects.affected(state, q):
            continue
        left = (victim.appeal > me.appeal) + (victim.conservation > me.conservation)
        for action in reversed(victim.slots):  # slot 5 downward
            if left <= 0:
                break
            if effects.add_action_token(state, q, action, "constriction"):
                left -= 1


# ---- Pilfering and Hypnosis -------------------------------------------------------

def _targets(state, p, stat, minimum=0):
    """Players that the ability of player p can hit on this track: the leading players other
    than p, if the lead is at least `minimum` and p is not the sole leader, restricted to those
    who are `effects.affected` (hitting a protected player is never useful, so the choice among
    tied players only offers the others)."""
    values = [getattr(q, stat) for q in state.players]
    top = max(values)
    if top < minimum:
        return []
    return [q for q, v in enumerate(values) if v == top and q != p and effects.affected(state, q)]


def _pilfer(state, p, stat, minimum=0):
    targets = _targets(state, p, stat, minimum)
    if len(targets) == 1:
        push(state, "ab_pilfer", targets[0], thief=p)
    elif targets:
        push(state, "ab_pilfer_pick", p, candidates=targets)


@ability("PILFERING_1")
def pilfering_1(state, p, card_id, value):
    _pilfer(state, p, "appeal")


@ability("PILFERING_2")
def pilfering_2(state, p, card_id, value):
    _pilfer(state, p, "conservation", minimum=1)  # resolves second
    _pilfer(state, p, "appeal")


def _pick_options(state, frame):
    return [Option(("target", q), f"Target player {q}") for q in frame.data["candidates"]]


def _pilfer_pick_apply(state, frame, option):
    pop(state, frame)
    push(state, "ab_pilfer", option.key[1], thief=frame.player)


def _pilfer_options(state, frame):
    options = []
    if state.players[frame.player].hand:
        options.append(Option(("card",), "Give a random hand card"))
    options.append(Option(("money",), "Give up to 5 money"))
    return options


def _pilfer_apply(state, frame, option):
    pop(state, frame)
    victim, thief = state.players[frame.player], state.players[frame.data["thief"]]
    if option.key[0] == "card":
        # the victim sees the card go, so it is known to both players
        effects.to_hand(state, thief.idx, victim.hand.pop(state.rng.randrange(len(victim.hand))), True)
    else:
        paid = min(5, victim.money)
        victim.money -= paid
        thief.money += paid


@ability("HYPNOSIS")
def hypnosis(state, p, card_id, value):
    targets = _targets(state, p, "appeal")
    if len(targets) == 1:
        _offer_hypnosis(state, p, targets[0], value)
    elif targets:
        push(state, "ab_hypnosis_pick", p, candidates=targets, reach=value)


def _offer_hypnosis(state, p, target, reach):
    from . import engine
    engine.offer_extra_action(state, p, state.players[target].slots[:reach or 1], owner=target)


def _hypnosis_pick_apply(state, frame, option):
    pop(state, frame)
    _offer_hypnosis(state, frame.player, option.key[1], frame.data["reach"])


register_choice("ab_boost", _boost_options, _boost_apply)
register_choice("ab_pilfer_pick", _pick_options, _pilfer_pick_apply)
register_choice("ab_pilfer", _pilfer_options, _pilfer_apply)
register_choice("ab_hypnosis_pick", _pick_options, _hypnosis_pick_apply)
