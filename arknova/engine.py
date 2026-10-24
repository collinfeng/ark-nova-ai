"""Game setup, the turn loop, breaks and final scoring.

Public API:
    state = new_game(n_players=2, seed=0)
    options = legal_options(state)      # for state.stack[-1].player
    step(state, option)                 # applies it and runs the engine to the next choice
    to_move(state)                      # index of the player who must choose
"""
import random
from itertools import combinations

from . import cards, maps, tables as T
from . import effects as E
from .hexmap import MAP0, Zoo
from .state import (ACTIONS, AUTOS, CHOICES, EngineError, Option, Player, State, log, note, pop, push, under,
                    register_auto, register_choice)

MAP_DEFS = {"map0": MAP0}
maps.register(MAP_DEFS)  # maps 1-8 and A from data/maps (layouts, side panels, left-edge tokens)
SETUP_DRAW, SETUP_KEEP = 8, 4
EXTRA_OPTIONS = []  # fn(state, frame) -> [Option]: options added to whatever decision is pending (map rules)
EXTRA_APPLY = {}  # option key[0] -> fn(state, frame, option): handled by step; the decision stays pending


def new_game(n_players=2, seed=0, map_name="map0"):
    rng = random.Random(seed)
    players = []
    for i in range(n_players):
        others = [a for a in T.ACTIONS if a != "animals"]
        rng.shuffle(others)
        zoo = Zoo(MAP_DEFS[map_name])
        for kind, size, cells in T.MAPS[map_name].get("prebuilt", []):  # Map A: kiosk and enclosure printed
            zoo.place(kind, size, cells)
        players.append(Player(idx=i, zoo=zoo, slots=["animals"] + others, appeal=i))
    state = State(players=players, rng=rng, map_name=map_name)

    state.deck = cards.zoo_deck_ids()
    rng.shuffle(state.deck)
    state.display = [state.deck.pop() for _ in range(T.DISPLAY_SIZE)]
    state.final_deck = cards.ids_of("endgame")
    rng.shuffle(state.final_deck)
    base = cards.ids_of("project", category="base")
    rng.shuffle(base)
    state.base_projects = base[:T.BASE_PROJECTS[n_players]]
    state.base_project_deck = base[T.BASE_PROJECTS[n_players]:]
    state.project_tokens = {cid: {} for cid in state.base_projects}
    if n_players == 2:
        for position, cid in enumerate(state.base_projects, start=1):
            state.project_tokens[cid][position] = "blocked"
    state.partner_zoos_available = set(T.CONTINENTS)
    state.universities_available = set(T.UNIVERSITIES)
    tiles = sorted(T.BONUS_TILES)
    rng.shuffle(tiles)
    state.bonus_tiles = {T.CONSERVATION_TILE_SPACES[0]: tiles[:2], T.CONSERVATION_TILE_SPACES[1]: tiles[2:4]}

    push(state, "turn", 0)
    for player in reversed(players):
        player.final_cards = [state.final_deck.pop() for _ in range(2)]
        player.hand = [state.deck.pop() for _ in range(SETUP_DRAW)]
        push(state, "setup_keep", player.idx)
    return state


def to_move(state):
    return state.stack[-1].player


def legal_options(state, extras=True):
    """Options of the pending decision, plus (extras=True) the map-rule options from EXTRA_OPTIONS."""
    if state.over:
        return []
    if state.cache_options and state.cached_options is not None:
        options = state.cached_options
    else:
        frame = state.stack[-1]
        options = CHOICES[frame.kind][0](state, frame)
    if extras and EXTRA_OPTIONS:
        added = [o for fn in EXTRA_OPTIONS for o in fn(state, state.stack[-1])]
        if added:
            return list(options) + added
    return options


def step(state, option):
    """Apply an Option (or its key) for the top frame, then run until the next choice."""
    if state.over:
        raise EngineError("the game is over")
    frame = state.stack[-1]
    apply = CHOICES[frame.kind][1]
    key = option.key if isinstance(option, Option) else tuple(option)
    chosen = next((o for o in legal_options(state) if o.key == key), None)
    if chosen is None:
        raise EngineError(f"illegal option {key} for {frame.kind}")
    state.cached_options = None
    log(state, f"P{frame.player} {frame.kind}: {chosen.label or chosen.key}")
    if state.ledger is not None:
        state.causes.append(("move", frame.kind, chosen.label or str(key)))
    try:
        if key[0] in EXTRA_APPLY:
            EXTRA_APPLY[key[0]](state, frame, chosen)  # the decision stays pending
        else:
            apply(state, frame, chosen)
        _settle(state)
    finally:
        if state.ledger is not None:
            state.causes.pop()
    return state


def _settle(state):
    while not state.over:
        if not state.stack:
            raise EngineError("empty stack while the game is running")
        frame = state.stack[-1]
        if frame.kind in AUTOS:
            AUTOS[frame.kind](state, frame)
        elif frame.kind in CHOICES:
            options = CHOICES[frame.kind][0](state, frame)
            if not options:
                raise EngineError(f"choice frame {frame.kind} has no options")
            state.cached_options = options if state.cache_options else None
            return
        else:
            raise EngineError(f"no handler for frame {frame.kind}")


# ---- setup ------------------------------------------------------------------

def _setup_options(state, frame):
    hand = state.players[frame.player].hand
    return [Option(("keep",) + keep, "Keep " + ", ".join(keep)) for keep in combinations(sorted(hand), SETUP_KEEP)]


def _setup_apply(state, frame, option):
    pop(state, frame)
    player = state.players[frame.player]
    keep = list(option.key[1:])
    state.discard.extend(c for c in player.hand if c not in keep)
    player.hand = keep


# ---- turn -------------------------------------------------------------------

def _card_strength(state, owner, action):
    """Slot strength of an action card, lowered by a Constriction token on it."""
    penalty = E.CONSTRICTION_PENALTY if "constriction" in E.tokens_on(state, owner, action) else 0
    return state.players[owner].strength(action) - penalty


def _turn_options(state, frame, charge_venom=True):
    player = state.players[frame.player]
    poisoned = E.has_venom(state, frame.player)
    options = []
    for action in player.slots:
        # While holding Venom, using a card without a Venom token costs money.
        cost = E.VENOM_COST if poisoned and "venom" not in E.tokens_on(state, frame.player, action) else 0
        if charge_venom and player.money < cost:
            continue
        if action in ACTIONS:
            base = _card_strength(state, frame.player, action)
            paid = min(player.money, cost)
            player.money -= paid  # the action must still be possible once the Venom cost is paid
            try:
                for x in range(player.xtokens + 1):
                    if base + x >= 1 and ACTIONS[action][0](state, frame.player, base + x):
                        spent = f" (+{x} X)" if x else ""
                        options.append(Option(("act", action, x), f"{action} at strength {base + x}{spent}"))
            finally:
                player.money += paid
        if player.xtokens < T.MAX_XTOKENS:
            options.append(Option(("xtoken", action), f"Take an X-token with {action}"))
    if not options and charge_venom:
        return _turn_options(state, frame, charge_venom=False)  # cannot pay: no player may be left stuck
    return options


def _use_card(state, owner, action):
    """Strength of the card as used now; using it discards its Venom and Constriction tokens."""
    strength = _card_strength(state, owner, action)
    E.remove_action_token(state, owner, action, "venom")
    E.remove_action_token(state, owner, action, "constriction")
    return strength


def _turn_apply(state, frame, option):
    pop(state, frame)
    p = frame.player
    player = state.players[p]
    action = option.key[1]
    player.last_action = "xtoken" if option.key[0] == "xtoken" else action
    if E.has_venom(state, p) and "venom" not in E.tokens_on(state, p, action):
        player.money -= min(player.money, E.VENOM_COST)
    strength = _use_card(state, p, action)
    state.turn = {"action": action, "after": [], "xtoken": option.key[0] == "xtoken"}
    push(state, "turn_end", p, phase=0)
    if option.key[0] == "xtoken":
        E.gain(state, p, "xtoken", 1)
        return
    strength += option.key[2]
    player.xtokens -= option.key[2]
    state.turn["strength"] = strength
    ACTIONS[action][1](state, p, strength)


def _repeat_options(state, frame):
    """Multiplier token: the action just executed may be executed a second time."""
    p = frame.player
    turn = state.turn
    if turn["xtoken"]:
        can = state.players[p].xtokens < T.MAX_XTOKENS
    else:
        can = ACTIONS[turn["action"]][0](state, p, turn["strength"])
    return ([Option(("repeat",), f"Use the x2 token: {turn['action']} again")] if can else []) + [E.SKIP]


def _repeat_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] != "repeat":
        return
    if state.turn["xtoken"]:
        E.gain(state, frame.player, "xtoken", 1)
    else:
        ACTIONS[state.turn["action"]][1](state, frame.player, state.turn["strength"])


def _turn_end(state, frame):
    p = frame.player
    player = state.players[p]
    if frame.data["phase"] == 0:
        action = state.turn["action"]
        if "multiplier" in E.tokens_on(state, p, action):
            E.remove_action_token(state, p, action, "multiplier")
            push(state, "multiplier_repeat", p)
            return
        frame.data["phase"] = 1
        player.slots.remove(state.turn["action"])
        player.slots.insert(0, state.turn["action"])
        for kind, who, data in reversed(state.turn["after"]):
            push(state, kind, who, **data)
        return
    pop(state, frame)
    E.refill_display(state)
    state.turn = {}
    _check_end(state, during_break=False)
    push(state, "next_turn", p)
    if state.break_by is not None:
        push(state, "break", state.break_by, phase=0)


# ---- extra actions (Action: X, Determination, Hypnosis) ---------------------------

def offer_extra_action(state, p, actions, owner=None, optional=True):
    """After the current action finishes, let player p take one more action with one of the
    given action cards. `owner` is the player whose cards are used (Hypnosis); default p."""
    state.turn["after"].append(("extra_action", p, {"actions": list(actions), "optional": optional,
                                                    "owner": p if owner is None else owner}))


def _extra_options(state, frame):
    p, owner = frame.player, frame.data["owner"]
    options = []
    for action in frame.data["actions"]:
        if action not in ACTIONS:
            continue
        base = _card_strength(state, owner, action)
        state.borrowed = (action, action in state.players[owner].upgraded) if owner != p else None
        try:
            for x in range(state.players[p].xtokens + 1):
                if base + x >= 1 and ACTIONS[action][0](state, p, base + x):
                    spent = f" (+{x} X)" if x else ""
                    options.append(Option(("act", action, x), f"{action} at strength {base + x}{spent}"))
        finally:
            state.borrowed = None
    if frame.data["optional"] or not options:
        options.append(E.SKIP)
    return options


def _extra_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] != "act":
        return
    p, owner = frame.player, frame.data["owner"]
    _, action, x = option.key
    state.players[p].last_action = action  # an extra action is a main action too
    if owner == p and E.has_venom(state, p) and "venom" not in E.tokens_on(state, p, action):
        state.players[p].money -= min(state.players[p].money, E.VENOM_COST)
    strength = _use_card(state, owner, action) + x
    state.players[p].xtokens -= x
    # The outer turn has already moved its card; this action gets its own scratch context.
    state.turn = {"action": action, "after": [], "xtoken": False, "strength": strength, "outer": state.turn}
    if owner != p:
        state.borrowed = (action, action in state.players[owner].upgraded)
    push(state, "extra_end", p, phase=0, owner=owner)
    ACTIONS[action][1](state, p, strength)


def _extra_end(state, frame):
    if frame.data["phase"] == 0:
        frame.data["phase"] = 1
        slots = state.players[frame.data["owner"]].slots
        slots.remove(state.turn["action"])
        slots.insert(0, state.turn["action"])
        state.borrowed = None
        for kind, who, data in reversed(state.turn["after"]):
            push(state, kind, who, **data)
        return
    pop(state, frame)
    state.turn = state.turn["outer"]


def _check_end(state, during_break):
    if state.end_by is not None:
        return
    # At the end of a turn only that player's counters are checked; in a break, everyone's.
    candidates = state.players if during_break else [state.players[state.current]]
    triggered = [q.idx for q in candidates if q.victory_points >= 0]
    if triggered:
        state.end_by = triggered[0]
        state.final_turns = state.n if during_break else state.n - 1
        log(state, f"P{state.end_by} triggers the end of the game")


def _next_turn(state, frame):
    pop(state, frame)
    if state.final_turns is not None:
        if state.final_turns == 0:
            push(state, "final_scoring", state.current, phase=0)
            return
        state.final_turns -= 1
    state.current = (state.current + 1) % state.n
    state.turn_flags = {}
    push(state, "turn", state.current)


# ---- break ------------------------------------------------------------------

def _break(state, frame):
    phase = frame.data["phase"]
    if phase == 0:
        note(state, frame.player, "break_begins")
        frame.data["phase"] = 1
        for player in reversed(state.players):
            if len(player.hand) > player.hand_limit:
                push(state, "discard_hand", player.idx, limit=player.hand_limit)
    elif phase == 1:
        frame.data["phase"] = 2
        for player in state.players:
            player.workers_out = {}
            player.action_tokens = {}
        state.partner_zoos_available = set(T.CONTINENTS)
        state.universities_available = set(T.UNIVERSITIES)
        for index in (0, 1):
            if state.display[index] is not None:
                state.discard.append(state.display[index])
                state.display[index] = None
        E.refill_display(state)
        note(state, frame.player, "break_reset")
        frame.data["order"] = [(frame.player + i) % state.n for i in range(state.n)]
    elif phase == 2:
        if not frame.data["order"]:
            frame.data["phase"] = 3
            return
        p = frame.data["order"].pop(0)
        player = state.players[p]
        income = T.appeal_income(player.appeal) + player.zoo.kiosk_income()
        under(state, ("income", "appeal"), E.gain, state, p, "money", income)
        log(state, f"P{p} income {income}")
        under(state, ("income", "token"), E.token_income, state, p)
        for card_id in reversed(player.zoo_cards):
            if card_id in E.INCOME:
                under(state, ("income", card_id), E.INCOME[card_id], state, p)
        for hook in E.BREAK_INCOME_HOOKS:
            under(state, ("income", "map"), hook, state, p)
    else:
        pop(state, frame)
        state.break_pos = 0
        state.break_by = None
        _check_end(state, during_break=True)


# ---- end of game ------------------------------------------------------------

def _final_scoring(state, frame):
    if frame.data["phase"] == 0:
        frame.data["phase"] = 1
        if not state.final_card_discarded:
            E.push_final_card_discards(state)
        return
    pop(state, frame)
    # End-game effects read only icons, buildings and reputation, which final scoring does not change.
    for p in range(state.n):
        player = state.players[p]
        for card_id in player.zoo_cards + player.final_cards:
            if card_id in E.ENDGAME:
                E.ENDGAME[card_id](state, p)
    state.scores = [player.victory_points for player in state.players]
    state.stack.clear()
    state.over = True


def winners(state):
    """Players with the highest score; ties broken by conservation projects supported."""
    best = max(zip(state.scores, (p.projects_supported for p in state.players)))
    return [p.idx for p in state.players if (state.scores[p.idx], p.projects_supported) == best]


register_choice("setup_keep", _setup_options, _setup_apply)
register_choice("turn", _turn_options, _turn_apply)
register_choice("multiplier_repeat", _repeat_options, _repeat_apply)
register_choice("extra_action", _extra_options, _extra_apply)
register_auto("extra_end", _extra_end)
register_auto("turn_end", _turn_end)
register_auto("next_turn", _next_turn)
register_auto("break", _break)
register_auto("final_scoring", _final_scoring)
