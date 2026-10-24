import random

import pytest

np = pytest.importorskip("numpy")

from arknova.rl.league import Results, SELF, agent_advantages, choose_opponent, pfsp_weights  # noqa: E402


def timeline(deciders, ctrl_seats, win=None, change=None, done=None, end_decider=0, end_value=0.0):
    """One group with one game slot; deciders: seat per step; ctrl_seats: (controller of seat 0, of seat 1)."""
    steps = len(deciders)
    ctrl = np.zeros((steps, 1, 2), dtype=int)
    ctrl[:, 0, 0], ctrl[:, 0, 1] = ctrl_seats
    col = lambda xs: np.array(xs if xs is not None else [0.0] * steps, dtype=float).reshape(steps, 1)  # noqa: E731
    return {"decider": np.array(deciders).reshape(steps, 1), "ctrl": ctrl, "win": col(win), "change": col(change),
            "done": col(done).astype(bool), "end_decider": np.array([end_decider]), "end_value": np.array([end_value])}


def test_self_play_both_seats_get_the_outcome_from_their_side():
    g = timeline([0, 1, 0, 1], (7, 7), win=[0, 0, 0, 1], done=[0, 0, 0, 1])
    adv, _ = agent_advantages([g], np.zeros(4), me=7, shaping=0.0, gamma=1.0, lam=1.0)
    assert adv.tolist() == [-1.0, 1.0, -1.0, 1.0]


def test_opponent_moves_are_environment_and_its_win_is_my_loss():
    g = timeline([0, 1, 0, 1], (7, 3), win=[0, 0, 0, 1], done=[0, 0, 0, 1])
    adv, _ = agent_advantages([g], np.zeros(2), me=7, shaping=0.0, gamma=1.0, lam=1.0)
    assert adv.tolist() == [-1.0, -1.0]


def test_cut_off_slice_bootstraps_from_the_next_position_with_the_right_sign():
    g = timeline([0, 1, 0, 1], (7, 3), end_decider=1, end_value=0.5)  # opponent to move, rates it +0.5 for itself
    adv, _ = agent_advantages([g], np.zeros(2), me=7, shaping=0.0, gamma=1.0, lam=1.0)
    assert adv.tolist() == [-0.5, -0.5]


def test_shaping_weight_is_the_agents_own_and_values_are_subtracted():
    g = timeline([0, 1], (7, 3), change=[0.2, 0.1], done=[0, 1])
    adv, _ = agent_advantages([g], np.array([0.05]), me=7, shaping=2.0, gamma=1.0, lam=1.0)
    assert adv.tolist() == pytest.approx([2.0 * 0.2 - 2.0 * 0.1 - 0.05])


def test_new_game_in_the_same_slot_does_not_inherit_the_old_one():
    g = timeline([0, 1, 0, 1], (7, 3), win=[0, -1, 0, 0], done=[0, 1, 0, 0], end_decider=0, end_value=0.25)
    adv, _ = agent_advantages([g], np.zeros(2), me=7, shaping=0.0, gamma=1.0, lam=1.0)
    assert adv.tolist() == [1.0, 0.25]  # first game: the opponent lost; second: cut off, I am to move


def test_count_mismatch_is_an_error():
    g = timeline([0, 1], (7, 3))
    with pytest.raises(ValueError):
        agent_advantages([g], np.zeros(5), me=7, shaping=0.0, gamma=1.0, lam=1.0)


def test_pfsp_prefers_hard_opponents_and_results_are_symmetric():
    weights = pfsp_weights([0.9, 0.5, 0.1])
    assert weights[2] > weights[1] > weights[0] and abs(weights.sum() - 1) < 1e-9
    results = Results()
    for _ in range(50):
        results.add("main", "old", 1.0)
    assert results.win_rate("main", "old") > 0.9 and results.win_rate("old", "main") < 0.1
    rng = random.Random(0)
    picks = [choose_opponent("main", ["old", "new"], results, rng, self_share=0.0) for _ in range(400)]
    assert picks.count("new") > picks.count("old")
    assert choose_opponent("main", [], results, rng, self_share=0.0) == SELF


def test_league_subset_matches_train_ppo_subset():
    torch = pytest.importorskip("torch")
    train_league = pytest.importorskip("tools.train_league")
    from tools.train_ppo import subset
    from arknova.rl import encode
    rng = np.random.default_rng(0)
    counts = rng.integers(1, 9, size=40).astype(np.int32)
    rows = int(counts.sum())
    batch = {k: torch.as_tensor(rng.integers(0, 50, size=(40, 3))) for k in encode.STATE_KEYS}
    batch.update({k: torch.as_tensor(rng.integers(0, 50, size=(rows, 2))) for k in encode.OPTION_KEYS})
    batch["counts"] = torch.as_tensor(counts).long()
    idx = np.array([3, 7, 8, 21, 39])
    ours = train_league.gpu_subset(batch, torch.as_tensor(idx), torch.as_tensor(train_league.rows_of(counts, idx)))
    theirs = subset(batch, torch.as_tensor(idx))
    for k in theirs:
        assert torch.equal(ours[k], theirs[k]), k
