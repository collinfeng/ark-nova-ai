"""Public hand cards, last action and the fast state copy (clone)."""
import copy
import random
import time

import pytest

from arknova import effects as E, engine, maps, tables as T
from arknova.hexmap import MapDef
from arknova.state import Frame, Option, clone

MAPS = ["map0"] + maps.available()
MAX_STEPS = 4000


def legal(state):
    """Legal options; the plan4 harbour discard is left out while a hand-discard frame is pending, where it
    can empty the hand and leave that frame without options (an engine bug unrelated to copying)."""
    options = engine.legal_options(state)
    if state.stack and state.stack[-1].kind == "discard_hand":
        options = [o for o in options if o.key[0] != "harbor"]
    return options


def play(state, rng, steps=MAX_STEPS, trace=None):
    """Random legal options until the game ends; returns the sequence of option keys."""
    seen = []
    for _ in range(steps):
        if state.over:
            break
        options = legal(state)
        seen.append(tuple(o.key for o in options))
        engine.step(state, rng.choice(options))
    return seen


def advance(state, rng, n):
    for _ in range(n):
        if state.over:
            return
        engine.step(state, rng.choice(legal(state)))


def mutable_ids(obj, out, skip=(MapDef, Option)):
    """ids of every mutable container / object reachable from obj (map definitions excluded)."""
    if isinstance(obj, (int, str, float, bool, type(None), frozenset, bytes)) or isinstance(obj, skip):
        return
    if id(obj) in out:
        return
    if isinstance(obj, tuple):
        for x in obj:
            mutable_ids(x, out, skip)
        return
    out.add(id(obj))
    if isinstance(obj, dict):
        for k, v in obj.items():
            mutable_ids(v, out, skip)
    elif isinstance(obj, (list, set)):
        for x in obj:
            mutable_ids(x, out, skip)
    elif hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k != "_placements":  # cached lists that are never mutated, shared on purpose (as in Zoo.__deepcopy__)
                mutable_ids(v, out, skip)


def snapshot(state):
    """Comparable plain view of a state."""
    return (state.scores, state.current, state.deck, state.discard, state.display, state.over,
            [(p.hand, p.public_hand, p.money, p.appeal, p.conservation, p.reputation, p.slots, p.last_action,
              [(b.id, b.kind, b.used, b.occupied, b.extra_size) for b in p.zoo.buildings])
             for p in state.players],
            [(f.kind, f.player, repr(f.data)) for f in state.stack], repr(state.turn), state.rng.getstate())


# ---- clone ------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("map_name", MAPS)
def test_clone_matches_deepcopy(map_name):
    for seed in range(3):
        rng = random.Random(seed * 101 + 7)
        state = engine.new_game(2, seed=seed, map_name=map_name)
        while not state.over:
            advance(state, rng, rng.randint(1, 60))
            if state.over:
                break
            a, b, ref = copy.deepcopy(state), clone(state), copy.deepcopy(state)
            assert snapshot(a) == snapshot(b)
            shared = set()
            mutable_ids(state, shared)
            other = set()
            mutable_ids(b, other)
            assert not shared & other
            seed_c = rng.random()
            seen_a = play(a, random.Random(seed_c), steps=150)
            seen_b = play(b, random.Random(seed_c), steps=150)
            assert seen_a == seen_b
            assert snapshot(a) == snapshot(b)
            # stepping the clone did not touch the original
            assert snapshot(state) == snapshot(ref)
            if len(seen_a) < 150 and a.over:
                assert a.scores == b.scores


@pytest.mark.parametrize("map_name", MAPS)
def test_clone_full_games(map_name):
    for seed in range(2):
        state = engine.new_game(2, seed=seed + 40, map_name=map_name)
        a, b = copy.deepcopy(state), clone(state)
        seen_a = play(a, random.Random(seed))
        seen_b = play(b, random.Random(seed))
        assert seen_a == seen_b and a.scores == b.scores


def test_clone_frame_data_independent():
    state = engine.new_game(2, seed=1)
    state.stack.append(Frame("x", 0, {"cards": [1, 2], "nested": {"k": [3]}, "t": (1, [2])}))
    c = clone(state)
    c.stack[-1].data["cards"].append(9)
    c.stack[-1].data["nested"]["k"].append(9)
    c.stack[-1].data["t"][1].append(9)
    assert state.stack[-1].data == {"cards": [1, 2], "nested": {"k": [3]}, "t": (1, [2])}
    assert c.rng is not state.rng and c.players[0].zoo is not state.players[0].zoo
    assert c.players[0].zoo.mapdef is state.players[0].zoo.mapdef


def test_clone_timing(capsys):
    times_c, times_d = [], []
    for seed in range(3):
        rng = random.Random(seed)
        state = engine.new_game(2, seed=seed)
        for _ in range(8):
            advance(state, rng, 40)
            t = time.perf_counter()
            for _ in range(20):
                clone(state)
            times_c.append((time.perf_counter() - t) / 20)
            t = time.perf_counter()
            for _ in range(20):
                copy.deepcopy(state)
            times_d.append((time.perf_counter() - t) / 20)
    c, d = sum(times_c) / len(times_c), sum(times_d) / len(times_d)
    with capsys.disabled():
        print(f"\nclone {c * 1e3:.3f} ms vs deepcopy {d * 1e3:.3f} ms ({d / c:.1f}x)")
    assert c < d / 2


# ---- public hand ------------------------------------------------------------

def test_to_hand_public_once():
    state = engine.new_game(2, seed=0)
    p = state.players[0]
    E.to_hand(state, 0, "A", False)
    assert p.hand[-1] == "A" and "A" not in p.public_hand
    E.to_hand(state, 0, "B", True)
    E.to_hand(state, 0, "B", True)
    assert p.public_hand == ["B"] and p.hand.count("B") == 2


def test_public_hand_in_random_games():
    for seed in range(6):
        rng = random.Random(seed)
        state = engine.new_game(2, seed=seed)
        while not state.over:
            engine.step(state, rng.choice(legal(state)))
            for p in state.players:
                assert len(p.public_hand) == len(set(p.public_hand))
        assert any(p.public_hand for p in state.players)


def fresh(seed=0):
    """A game past setup, with the stack holding only the first turn."""
    state = engine.new_game(2, seed=seed)
    state.stack = [Frame("turn", 0)]
    return state


def test_deck_draw_is_hidden():
    state = fresh()
    top = state.deck[-1]
    state.players[0].hand = []
    from arknova.state import push
    push(state, "take_card", 0)
    engine.step(state, next(o for o in engine.legal_options(state) if o.key[0] == "deck"))
    assert state.players[0].hand == [top] and state.players[0].public_hand == []


def test_pilfer_steals_publicly():
    state = fresh()
    thief, victim = state.players
    victim.hand = ["a", "b"]
    thief.hand = []
    from arknova.state import push
    push(state, "ab_pilfer", 1, thief=0)
    engine.step(state, next(o for o in engine.legal_options(state) if o.key[0] == "card"))
    assert len(thief.hand) == 1 and thief.public_hand == thief.hand


# ---- last action ------------------------------------------------------------

def test_last_action_follows_turns():
    rng = random.Random(3)
    state = engine.new_game(2, seed=3)
    assert all(p.last_action is None for p in state.players)
    used = set()
    while not state.over:
        options = legal(state)
        frame = state.stack[-1]
        o = rng.choice(options)
        before = state.players[frame.player].last_action
        engine.step(state, o)
        if frame.kind == "turn":
            expected = "xtoken" if o.key[0] == "xtoken" else o.key[1]
            assert state.players[frame.player].last_action == expected
            used.add(expected)
    assert "xtoken" in used and used & set(T.ACTIONS)
