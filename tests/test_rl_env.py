import random

import pytest

pytest.importorskip("numpy")

from arknova import tables as T  # noqa: E402
from arknova.rl.env import SelfPlayEnv, replay  # noqa: E402


def test_finished_game_reports_its_main_actions():
    env, rng = SelfPlayEnv(3), random.Random(0)
    for _ in range(5000):
        _, done, info = env.step(rng.randrange(len(env.options)))
        if done:
            break
    assert done and set(info["actions"]) == set(T.ACTIONS)
    assert sum(info["actions"].values()) > 20  # every turn of both players is one main action or an X-token
    assert sum(env.actions.values()) <= 1  # the counts start again with the next game


def test_action_shares_flag_a_run_that_avoids_cards():
    train_ppo = pytest.importorskip("tools.train_ppo")
    games = [{"actions": {"animals": 10, "build": 30, "association": 10}}] * 3  # Cards never taken
    shares = train_ppo.action_shares(games)
    assert shares["share_cards"] < train_ppo.CARDS_TRAP and shares["share_build"] == 0.6
    assert train_ppo.action_shares([{"decisions": 0, "crashed": True}]) == {}


@pytest.mark.parametrize("zero_final", [False, True])
def test_shaping_telescopes_to_final_lead_or_to_zero(zero_final):
    """Shaping is potential-based on the lead: from player 0's side, a game's rewards sum to
    win/loss + (final lead - first lead); with zero_final the final lead counts as 0, so they sum to
    win/loss - first lead and the return is the result alone (up to the small starting lead)."""
    from arknova.rl.env import SelfPlayEnv, lead
    env = SelfPlayEnv(3, zero_final=zero_final)
    rng = random.Random(0)
    first = lead(env.state, 0)
    total, done = 0.0, False
    while not done:
        p = env.player
        reward, done, info = env.step(rng.randrange(len(env.options)), shaping=1.0)
        total += reward if p == 0 else -reward
    final_state_lead = (info["scores"][0] - info["scores"][1]) / 20
    result = total - (0.0 if zero_final else final_state_lead) + first
    assert info["finished"]
    assert abs(abs(result) - 1.0) < 1e-6 or abs(result) < 1e-6  # win, loss (or a tie)


def test_aux_reward_keeps_the_final_lead():
    """With zero_final the rewards sum to the result alone, while the auxiliary rewards of the same steps
    still sum to the result plus the final lead (the shaped return the auxiliary head learns)."""
    from arknova.rl.env import SelfPlayEnv, lead
    env = SelfPlayEnv(5, zero_final=True)
    rng = random.Random(1)
    first = lead(env.state, 0)
    total = aux_total = 0.0
    done = False
    while not done:
        p = env.player
        reward, done, info = env.step(rng.randrange(len(env.options)), shaping=1.0)
        sign = 1 if p == 0 else -1
        total += sign * reward
        aux_total += sign * env.aux_reward
    final_lead = (info["scores"][0] - info["scores"][1]) / 20
    assert abs((aux_total - total) - final_lead) < 1e-6
    assert abs(abs(total + first) - 1.0) < 1e-6 or abs(total + first) < 1e-6


def test_games_spread_over_the_given_maps_and_replay():
    env, rng, seen = SelfPlayEnv(7, maps=("map0", "plan3", "plana")), random.Random(7), set()
    for _ in range(12):
        seen.add(env.map_name)
        assert env.state.map_name == env.map_name
        env.reset()
    assert seen == {"map0", "plan3", "plana"}
    for _ in range(40):
        env.step(rng.randrange(len(env.options)))
    again, last = replay(env.seed, env.history + [0], env.map_name)
    assert again.state.map_name == env.map_name and again.decisions == env.decisions


def test_single_map_runs_keep_their_deals():
    assert [SelfPlayEnv(9).seed for _ in range(2)] == [SelfPlayEnv(9, maps=("map0",)).seed for _ in range(2)]


# A game on Map 4 (from a training crash record, 2026-10-19) that reaches an association action whose only
# options play Yosemite National Park from hand, with the harbour connected and unused this turn.
HARBOUR_GAME = (232247723, [
    18, 7, 7, 124, 7, 8, 8, 1, 6, 1, 8, 6, 6, 0, 3, 7, 1, 6, 0, 6, 124, 7, 6, 0, 11, 4, 7, 2, 3, 3, 3, 7, 6, 1,
    2, 7, 7, 1, 2, 6, 1, 9, 10, 30, 5, 3, 2, 6, 5, 10, 5, 5, 1, 10, 1, 2, 6, 20, 21, 1, 9, 3, 7, 8, 6, 9, 31,
    3, 9, 1, 5, 5, 9, 5, 1, 9, 12, 10, 0, 0, 20, 9, 1, 0, 10, 5, 3, 2, 16, 2, 1, 0, 0, 0, 10, 2, 25, 7, 6, 1,
    8, 7, 2, 16, 6, 4, 27, 10, 3, 7, 1, 19, 4, 8, 3, 0, 9, 12, 14, 30, 8, 1, 14, 0, 0, 0, 0, 5, 7, 5, 15, 5, 6,
    3, 23, 1, 0, 2, 0, 0, 16, 1, 0, 0, 7, 3, 1, 13, 6, 0, 7, 1, 7, 5, 14, 6, 13, 19, 0, 16, 39, 13, 3, 4, 0,
    24, 36, 11, 15, 0, 13, 14, 2, 3, 0, 0, 1, 0, 8, 0, 27, 8, 1, 0, 1, 0, 10, 0, 2, 15, 1, 0, 0, 0, 8, 10, 3,
    2, 16, 10, 4, 5, 2, 4, 2, 10, 12, 16, 3, 2, 16, 33, 28, 14, 7, 2, 0, 16, 2, 0, 0, 2, 0, 3, 15, 0, 1, 9, 3,
    3, 2, 4, 7, 3, 5, 4, 2, 4, 1, 1, 0, 1, 4, 1, 1, 2, 0, 2, 16, 4, 0, 8, 0, 0, 3, 1, 0, 9,
])


def test_harbour_does_not_offer_the_card_an_action_needs():
    env, _ = replay(HARBOUR_GAME[0], HARBOUR_GAME[1] + [0], "plan4")
    keys = [o.key for o in env.options]
    assert all(k[0] == "play_release" or k[0] == "harbor" for k in keys)
    harbour = [k[1] for k in keys if k[0] == "harbor"]
    yosemite = {k[1] for k in keys if k[0] != "harbor"}
    assert harbour and not yosemite & set(harbour)
    for card_id in harbour:  # every harbour discard offered leaves something to choose
        again, _ = replay(HARBOUR_GAME[0], HARBOUR_GAME[1] + [0], "plan4")
        again.step(next(i for i, o in enumerate(again.options) if o.key == ("harbor", card_id)))
        assert again.options
