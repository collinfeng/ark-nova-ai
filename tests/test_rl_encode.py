import copy
import random

import pytest

np = pytest.importorskip("numpy")

import arknova  # noqa: E402,F401
from arknova import engine as G  # noqa: E402
from arknova.rl import encode  # noqa: E402
from arknova.rl.env import SelfPlayEnv  # noqa: E402


def same(a, b):
    return all(np.array_equal(a[k], b[k]) for k in a)


@pytest.mark.slow
def test_every_decision_in_random_games_encodes_without_unknown_words():
    width = encode.sizes()["scalars"]
    for seed in range(25):
        state, rng, steps = G.new_game(2, seed=seed), random.Random(seed), 0
        while not state.over and steps < 3000:
            options = G.legal_options(state)
            obs = encode.observe(state, options)
            assert len(obs["scalars"]) == width
            assert len(obs["option_words"]) == len(options)
            assert encode.UNKNOWN not in obs["option_words"][:, 0] and obs["context"][0] != encode.UNKNOWN
            assert encode.UNKNOWN not in obs["option_words"]
            G.step(state, rng.choice(options))
            steps += 1


@pytest.mark.slow
def test_observation_does_not_depend_on_hidden_information():
    for seed in range(6):
        state, rng = G.new_game(2, seed=seed), random.Random(seed)
        for _ in range(200):
            if state.over:
                break
            options = G.legal_options(state)
            other = state.players[1 - state.stack[-1].player]
            changed = copy.deepcopy(state)
            changed.deck.reverse()
            hidden = changed.players[other.idx]
            hidden.hand = list(reversed(hidden.hand))
            if changed.deck and hidden.hand:
                changed.deck[0], hidden.hand[0] = hidden.hand[0], changed.deck[0]
            if changed.final_deck and hidden.final_cards:
                changed.final_deck[0], hidden.final_cards[0] = hidden.final_cards[0], changed.final_deck[0]
            assert same(encode.observe(state, options), encode.observe(changed, options))
            G.step(state, rng.choice(options))


@pytest.mark.slow
def test_options_that_differ_encode_differently():
    for seed in range(8):
        state, rng = G.new_game(2, seed=seed), random.Random(seed)
        for _ in range(400):
            if state.over:
                break
            options = G.legal_options(state)
            obs = encode.observe(state, options)
            rows = {tuple(np.concatenate([obs[k][i].ravel() for k in encode.OPTION_KEYS]).tolist())
                    for i in range(len(options))}
            assert len(rows) == len(options), (state.stack[-1].kind, [o.key for o in options])
            G.step(state, rng.choice(options))


def test_env_plays_games_with_zero_sum_terminal_rewards():
    env, rng, finished = SelfPlayEnv(seed=1), random.Random(1), 0
    for _ in range(6000):
        assert len(env.options) > 1
        reward, done, info = env.step(rng.randrange(len(env.options)), shaping=1.0)
        if done:
            finished += 1
            assert info["decisions"] > 50
            if info["finished"] and info["scores"][0] != info["scores"][1]:
                assert abs(reward) > 0.5
    assert finished >= 2


def test_collate_concatenates_options():
    env = SelfPlayEnv(seed=2)
    a = env.observe()
    env.step(0)
    b = env.observe()
    batch = encode.collate([a, b])
    assert batch["scalars"].shape[0] == 2
    assert batch["counts"].tolist() == [len(a["option_words"]), len(b["option_words"])]
    assert len(batch["option_cells"]) == batch["counts"].sum()


def test_a_game_can_be_replayed_from_its_seed_and_choices():
    from arknova.rl.env import replay
    env, rng = SelfPlayEnv(seed=4), random.Random(4)
    for _ in range(120):
        env.step(rng.randrange(len(env.options)))
    seed, choices = env.seed, list(env.history)
    keys = [o.key for o in env.options]
    again, last = replay(seed, choices + [0])
    assert last == 0 and [o.key for o in again.options] == keys
