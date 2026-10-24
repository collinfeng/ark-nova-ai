"""The play server's Game: undo, redo, restarting a turn, and resuming a saved game."""
import pytest
import random

import arknova  # noqa: F401
from arknova.play.ai import Analysis
from arknova.play.game import Game


class FirstOption:
    """A deterministic stand-in for the network: always prefers option 0."""
    name = "first"

    def analyse(self, game):
        n = len(game.options())
        return Analysis([1 / n] * n, 0.0, 0)


def _play_until_turn(game, turn, rng):
    """Random human decisions until the game reaches the human's `turn`, one decision into it."""
    while game.turn < turn or game.turn_points() == 0:
        if game.turn_done:
            game.end_turn()
        else:
            game.play(rng.randrange(len(game.options())))


def _snapshot(game):
    return (list(game.moves), len(game.records), game.turn, game.turn_done, list(game.ai_moves), list(game.ai_history))


@pytest.mark.slow
def test_old_saved_moves_rebuild_exact_reward_ownership():
    from arknova.bot import GreedyBot

    game = Game(FirstOption(), seed=0)
    bot, rng = GreedyBot(), random.Random(3)
    for _ in range(200):
        if game.reward_claims:
            break
        if game.turn_done:
            game.end_turn()
        else:
            option = bot.choose(game.state, rng)
            game.play(next(i for i, o in enumerate(game.options()) if o.key == option.key))
    assert game.reward_claims
    saved = game.to_json()
    assert "reward_claims" not in saved  # ownership also works for existing cloud saves
    restored = Game.resume(FirstOption(), saved)
    assert restored.reward_claims == game.reward_claims


def test_undo_then_redo_returns_to_the_same_position():
    game = Game(FirstOption(), seed=5)
    _play_until_turn(game, 2, random.Random(0))
    before = _snapshot(game)
    assert game.undo()
    assert game.redo_stack and _snapshot(game) != before
    assert game.redo()
    assert _snapshot(game) == before and not game.redo_stack


def test_a_new_decision_clears_redo():
    game = Game(FirstOption(), seed=5)
    _play_until_turn(game, 1, random.Random(1))
    game.undo()
    game.play(0)
    assert not game.redo_stack


def test_undo_warns_before_leaving_the_turn_and_restart_stops_at_its_start():
    game = Game(FirstOption(), seed=7)
    rng = random.Random(2)
    _play_until_turn(game, 2, rng)
    while not game.turn_done:  # finish turn 2, then start turn 3 without deciding
        game.play(rng.randrange(len(game.options())))
    assert not game.undo_leaves_turn()
    game.end_turn()
    assert game.turn == 3 and game.turn_points() == 0 and game.undo_leaves_turn()
    history = list(game.ai_history)
    game.undo()  # back into turn 2, the AI's turn undone with it
    assert game.turn == 2 and game.turn_done is False
    assert game.ai_history == history[:-1]
    earlier = game.turn_points() > 0  # none when that was the turn's only decision
    assert game.restart_turn() is earlier
    assert game.turn_points() == 0 and game.turn == 2 and game.undo_leaves_turn()
    first_of_turn = list(game.moves)
    while game.redo():
        pass
    assert game.turn == 3 and len(game.moves) > len(first_of_turn)
    assert game.ai_history == history


def test_resume_rebuilds_turns_and_undo_points():
    game = Game(FirstOption(), seed=9)
    _play_until_turn(game, 3, random.Random(3))
    game.play(0)
    back = Game.resume(FirstOption(), game.to_json())
    assert back.turn == game.turn and back.turn_points() == game.turn_points()
    assert len(back.undo_stack) == len(game.undo_stack) and back.moves == game.moves
    back.undo()
    game.undo()
    assert _snapshot(back)[:4] == _snapshot(game)[:4]
    assert back.ai_history == game.ai_history


def test_ai_history_accumulates_and_old_saves_rebuild_it():
    game = Game(FirstOption(), seed=11)
    _play_until_turn(game, 3, random.Random(4))
    assert [turn["turn"] for turn in game.ai_history] == [1, 2, 3]
    assert all(turn["moves"] for turn in game.ai_history)

    saved = game.to_json()
    back = Game.resume(FirstOption(), saved)
    assert back.ai_history == game.ai_history

    legacy = dict(saved)
    legacy.pop("ai_history")
    rebuilt = Game.resume(FirstOption(), legacy)
    assert [turn["turn"] for turn in rebuilt.ai_history] == [1, 2, 3]
    assert rebuilt.ai_history[-1]["moves"] == saved["ai_moves"]


@pytest.mark.slow
def test_a_single_option_is_still_offered_to_the_human():
    offered = 0
    for seed in range(6):
        game = Game(FirstOption(), seed=seed)
        rng = random.Random(seed)
        for _ in range(300):
            if game.state.over:
                break
            if game.turn_done:
                game.end_turn()
                continue
            assert game.to_move() == game.human  # the board always waits on the human here
            n = len(game.options())
            offered += n == 1
            game.play(rng.randrange(n))
        back = Game.resume(FirstOption(), game.to_json())
        assert len(back.undo_stack) == len(game.undo_stack) == len(game.records)
    assert offered > 0


@pytest.mark.slow
def test_the_ai_choosing_inside_your_turn_does_not_end_it():
    """At a break you trigger the AI discards first; your turn goes on, and a resumed game agrees."""
    found = False
    for seed in range(12):
        game, rng = Game(FirstOption(), seed=seed), random.Random(seed)
        for _ in range(400):
            if game.state.over:
                break
            if game.turn_done:
                assert game._ai_turn_starts()  # the hand-over is the AI starting its turn (or its setup)
                game.end_turn()
                continue
            before = len(game.ai_moves)
            game.play(rng.randrange(len(game.options())))
            if not game.turn_done and len(game.ai_moves) > before:
                found = True
                assert game.turn_points() > 0  # undo stays in this turn
        restored = Game.resume(FirstOption(), game.to_json())
        assert (restored.turn, len(restored.undo_stack)) == (game.turn, len(game.undo_stack))
        assert [e["turn"] for e in restored.ai_history] == [e["turn"] for e in game.ai_history]
    assert found
