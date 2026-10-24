"""Game state and the pending-decision machinery shared by the UI, bots and the RL wrapper.

The state is plain data (safe to deepcopy for undo and search). Everything a player
can choose is expressed as a Frame on `state.stack`; the top frame's legal Options
are the only way to change the game. Frames are either *choices* (a player picks an
Option) or *auto* (the engine resolves them without input).
"""
import copy
import random
from dataclasses import dataclass, field

from . import tables as T
from .hexmap import Building, Zoo


class EngineError(Exception):
    pass


@dataclass
class Frame:
    kind: str
    player: int
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Option:
    key: tuple
    label: str = ""


@dataclass
class Player:
    idx: int
    zoo: Zoo
    slots: list  # action card names; slots[0] is slot 1
    appeal: int = 0
    money: int = T.START_MONEY
    conservation: int = 0
    reputation: int = 1
    xtokens: int = 0
    upgraded: set = field(default_factory=set)
    workers: int = 1  # hired association workers
    workers_out: dict = field(default_factory=dict)  # task -> workers placed since the last break
    partner_zoos: list = field(default_factory=list)
    universities: list = field(default_factory=list)
    tokens: list = field(default_factory=lambda: [True] * 7)  # True while still on the map's left edge
    hand: list = field(default_factory=list)
    public_hand: list = field(default_factory=list)  # hand cards the opponent saw enter it; may hold stale ids
    zoo_cards: list = field(default_factory=list)  # played animals and sponsors
    final_cards: list = field(default_factory=list)
    housing: dict = field(default_factory=dict)  # animal card id -> (building id, spaces used)
    action_tokens: dict = field(default_factory=dict)  # action -> ["venom" | "constriction" | "multiplier", ...]
    card_tokens: dict = field(default_factory=dict)  # sponsor card id -> player tokens left on it
    tucked: list = field(default_factory=list)  # cards placed under other cards (Pouch); out of play
    full_cover_scored: bool = False
    last_action: str | None = None  # action card (or "xtoken") used for the latest main action

    def strength(self, action):
        return self.slots.index(action) + 1

    @property
    def active_workers(self):
        return self.workers - sum(self.workers_out.values())

    @property
    def hand_limit(self):
        return T.HAND_LIMIT_UNIVERSITY if "hand" in self.universities else T.HAND_LIMIT

    @property
    def projects_supported(self):
        return self.tokens.count(False)

    @property
    def victory_points(self):
        return T.victory_points(self.appeal, self.conservation)


@dataclass
class State:
    players: list
    rng: random.Random
    map_name: str = "map0"
    current: int = 0
    deck: list = field(default_factory=list)
    discard: list = field(default_factory=list)
    display: list = field(default_factory=list)  # index 0 is folder 1; None = taken this turn
    final_deck: list = field(default_factory=list)
    break_pos: int = 0
    break_by: int | None = None  # player who triggered the pending break
    base_projects: list = field(default_factory=list)
    base_project_deck: list = field(default_factory=list)  # unused base projects
    borrowed: tuple | None = None  # (action, upgraded) while acting with another player's card
    projects: list = field(default_factory=list)  # above the board, index 0 is leftmost
    project_tokens: dict = field(default_factory=dict)  # card id -> {slot position: player idx or "blocked"}
    donations: int = 0
    partner_zoos_available: set = field(default_factory=set)
    universities_available: set = field(default_factory=set)
    bonus_tiles: dict = field(default_factory=dict)  # conservation space -> [tile name]
    final_card_discarded: bool = False
    end_by: int | None = None
    final_turns: int | None = None
    over: bool = False
    scores: list | None = None
    turn: dict = field(default_factory=dict)  # scratch for the turn in progress
    turn_flags: dict = field(default_factory=dict)  # once-per-turn markers (map rules); reset each turn
    stack: list = field(default_factory=list)
    log: list | None = field(default_factory=list)
    # Opt-in speed-up for callers that only change the state through engine.step: the options of
    # the pending decision are computed once instead of on every query.
    cache_options: bool = False
    cached_options: list | None = None
    # Opt-in record of what a real move gains and why (the board's activity feed). None while the AI
    # searches, so the hot paths only pay for one attribute test. Entries: ("gain", p, kind, amount,
    # cause) and ("note", p, what, detail, cause); causes nest in `causes`.
    ledger: list | None = None
    causes: list = field(default_factory=list)

    @property
    def n(self):
        return len(self.players)

    @property
    def map(self):
        return T.MAPS[self.map_name]


CHOICES = {}  # kind -> (options(state, frame) -> [Option], apply(state, frame, option))
AUTOS = {}    # kind -> resolve(state, frame)
ACTIONS = {}  # action name -> (feasible(state, player_idx, strength) -> bool, start(state, player_idx, strength))


def register_choice(kind, options, apply):
    CHOICES[kind] = (options, apply)


def register_auto(kind, resolve):
    AUTOS[kind] = resolve


def register_action(name, feasible, start):
    ACTIONS[name] = (feasible, start)


def push(state, kind, player, /, **data):
    frame = Frame(kind, player, data)
    state.stack.append(frame)
    return frame


def pop(state, frame):
    for i in range(len(state.stack) - 1, -1, -1):
        if state.stack[i] is frame:
            del state.stack[i]
            return
    raise EngineError(f"frame {frame.kind} is not on the stack")


def note(state, p, what, detail=None):
    """Record an event for the activity feed (a break, a track stop reached)."""
    if state.ledger is not None:
        state.ledger.append(("note", p, what, detail, state.causes[-1] if state.causes else None))


def under(state, cause, fn, *args, **kwargs):
    """Call fn with `cause` as the reason for any gain it makes (while the ledger is recording)."""
    if state.ledger is None:
        return fn(*args, **kwargs)
    state.causes.append(cause)
    try:
        return fn(*args, **kwargs)
    finally:
        state.causes.pop()


def log(state, message):
    if state.log is not None:
        state.log.append(message)


# ---- fast copy ---------------------------------------------------------------

_ATOMS = frozenset({int, str, float, bool, type(None), frozenset, bytes, Option})


def _copy_value(v):
    """Copy a nested value made of lists, dicts, sets, tuples and immutable atoms."""
    t = type(v)
    if t in _ATOMS:
        return v
    if t is list:
        return [x if type(x) in _ATOMS else _copy_value(x) for x in v]
    if t is dict:
        return {k: (x if type(x) in _ATOMS else _copy_value(x)) for k, x in v.items()}
    if t is tuple:
        return tuple([x if type(x) in _ATOMS else _copy_value(x) for x in v])
    if t is set:
        return set(v)  # members are hashable, so immutable
    if t is Frame:
        return Frame(v.kind, v.player, _copy_value(v.data))
    return copy.deepcopy(v)  # anything unexpected keeps deepcopy's behaviour


def _copy_zoo(zoo):
    new = Zoo.__new__(Zoo)
    new.__dict__.update(zoo.__dict__)  # mapdef is shared: it never changes
    buildings = []
    for b in zoo.buildings:
        nb = Building.__new__(Building)
        nb.__dict__.update(b.__dict__)  # cells is a frozenset
        buildings.append(nb)
    new.buildings = buildings
    new.cell_owner = dict(zoo.cell_owner)
    new._placements = dict(zoo._placements)  # the cached lists are never mutated
    return new


def _copy_player(p):
    new = Player.__new__(Player)
    d = new.__dict__
    for k, v in p.__dict__.items():
        if k != "zoo":
            d[k] = v if type(v) in _ATOMS else _copy_value(v)
    d["zoo"] = _copy_zoo(p.zoo)
    return new


def clone(state):
    """Independent copy of a State, equivalent to copy.deepcopy but several times faster."""
    new = State.__new__(State)
    d = new.__dict__
    for k, v in state.__dict__.items():
        if k != "players" and k != "rng":
            d[k] = v if type(v) in _ATOMS else _copy_value(v)
    d["players"] = [_copy_player(p) for p in state.players]
    rng = random.Random()
    rng.setstate(state.rng.getstate())
    d["rng"] = rng
    return new
