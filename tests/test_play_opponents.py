"""Selectable rule bots, honest odds, and saved opponent identities."""
import json
from types import SimpleNamespace

import pytest

from arknova import engine as G
from arknova.play import server, view
from arknova.play.ai import BUILTIN_OPPONENTS, HeuristicAI
from arknova.play.game import Game
from tests.test_play_game import FirstOption


@pytest.mark.parametrize("name", BUILTIN_OPPONENTS)
def test_rule_opponent_is_legal_repeatable_and_leaves_the_real_state_unchanged(name):
    ai = HeuristicAI(name, FirstOption())
    state = G.new_game(2, seed=3)
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    # Keep search small while exercising a real turn, not only the opening hand selection.
    for player in state.players:
        player.hand = []
    game = SimpleNamespace(seed=3, moves=[], state=state, human=1-state.stack[-1].player,
                           to_move=lambda: G.to_move(state), options=lambda: G.legal_options(state))
    before = (state.deck[:], state.rng.getstate(), [(p.money, p.hand[:], p.slots[:]) for p in state.players])
    a = ai.analyse(game)
    assert a is ai.analyse(game)
    assert 0 <= a.best < len(game.options()) and a.extra["heuristic"]
    assert a.probs == [1.0 if i == a.best else 0.0 for i in range(len(game.options()))]  # all weight on its move
    assert before == (state.deck[:], state.rng.getstate(), [(p.money, p.hand[:], p.slots[:]) for p in state.players])
    assert ai.analyse(SimpleNamespace(to_move=lambda: 0, human=0, options=lambda: [1, 2])).probs == [0.5, 0.5]


def test_rule_opponent_game_records_no_invented_ai_odds_and_can_resume():
    game = Game(HeuristicAI("greedy", FirstOption()), seed=5)
    for _ in range(35):
        if game.state.over:
            break
        if game.turn_done:
            game.end_turn()
        else:
            game.play(0)
    moves = [move for turn in game.ai_history for move in turn["moves"]]
    assert moves and all(move["prob"] is None for move in moves)
    assert game.to_json()["opponent"] == "greedy"
    back = Game.resume(HeuristicAI("greedy", FirstOption()), game.to_json())
    assert back.moves == game.moves and back.ai.name == "greedy"
    assert view.board(back)["activity_history"] == view.board(game)["activity_history"]
    assert game.undo() and game.redo()


def test_rule_bot_search_plans_are_not_shared_between_games(monkeypatch):
    monkeypatch.setitem(server.ctx, "remote", None)
    monkeypatch.setitem(server.ctx, "default", "fake.pt")
    monkeypatch.setitem(server.ctx, "nets", {"fake.pt": FirstOption()})
    a, b = server._ai("beam_2x3"), server._ai("beam_2x3")
    assert a is not b and a.bot is not b.bot
    assert a.adviser is b.adviser
    a.bot.planned[0] = [("done",)]
    assert not b.bot.planned


@pytest.mark.parametrize("saved_id", ["greedy", "beam_2x3", "beam_3x8", "run4_70M.pt", "run5_13M.pt"])
def test_server_restores_the_selected_opponent_after_restart(tmp_path, monkeypatch, saved_id):
    from arknova.play import game as gamemod
    monkeypatch.setattr(gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setitem(server.ctx, "games", {})
    game = Game(FirstOption(), seed=8)
    saved = game.to_json()
    saved["opponent"] = saved_id
    (tmp_path / "current_test.json").write_text(json.dumps(saved))
    chosen = []
    def make(checkpoint=None, map_name="map0"):
        chosen.append(checkpoint)
        ai = FirstOption()
        ai.name, ai.checkpoint = saved_id, saved_id
        return ai
    monkeypatch.setattr(server, "_ai", make)
    assert server._game("test").ai.name == saved_id
    assert chosen == [saved_id]


def test_old_network_saves_also_keep_their_opponent(tmp_path, monkeypatch):
    from arknova.play import game as gamemod
    monkeypatch.setattr(gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setattr(server, "KEEP", tmp_path)
    monkeypatch.setitem(server.ctx, "games", {})
    (tmp_path / "run4_70M.pt").touch()
    saved = Game(FirstOption(), seed=8).to_json()
    saved.pop("opponent")
    saved["ai"] = "run4_70M"
    (tmp_path / "current_test.json").write_text(json.dumps(saved))
    chosen = []
    def make(checkpoint=None, map_name="map0"):
        chosen.append(checkpoint)
        return FirstOption()
    monkeypatch.setattr(server, "_ai", make)
    server._game("test")
    assert chosen == ["run4_70M.pt"]


def test_list_includes_rule_bots_and_available_models(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "KEEP", tmp_path)
    monkeypatch.setitem(server.ctx, "default", str(tmp_path / "long_s0_1B.pt"))
    for name in ("run4_70M.pt", "run5_13M.pt", "long_s0_1B.pt"):
        (tmp_path / name).touch()
    listing = server.checkpoints(user="test")
    # run4_70M is no longer offered (M10 is Normal now), though games saved against it still load.
    assert set(listing["checkpoints"]) == set(BUILTIN_OPPONENTS) | {"run5_13M.pt", "long_s0_1B.pt"}


def test_other_maps_take_rule_bots_and_the_all_maps_network_only(tmp_path, monkeypatch):
    from arknova.play import game as gamemod
    from fastapi import HTTPException
    monkeypatch.setattr(gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setattr(server, "KEEP", tmp_path)
    monkeypatch.setitem(server.ctx, "games", {})
    monkeypatch.setitem(server.ctx, "default", str(tmp_path / "long_s0_1B.pt"))
    for name in ("run5_13M.pt", "long_s0_1B.pt", "maps10_s0_1B_ema.pt"):
        (tmp_path / name).touch()
    made = []
    def make(checkpoint=None, map_name="map0"):
        made.append((checkpoint, map_name))
        return FirstOption()
    monkeypatch.setattr(server, "_ai", make)
    listing = server.checkpoints(user="test")
    assert listing["maps"][0] == "map0" and set(listing["maps"]) == set(G.MAP_DEFS) and len(listing["maps"]) == 10
    assert listing["any_map"] == [*BUILTIN_OPPONENTS, "maps10_s0_1B_ema.pt"]
    assert listing["map_default"] == "maps10_s0_1B_ema.pt"
    board = server.new(server.NewGame(map="plan4", checkpoint="greedy"), None, server.Player("test"))
    assert board["map"] == "plan4" and made[-1] == ("greedy", "plan4")
    sites = {c["site"] for c in board["players"][0]["zoo"]["cells"]} - {None}
    assert sites == {"harbour"}
    server.new(server.NewGame(map="plan8", checkpoint="maps10_s0_1B_ema.pt"), None, server.Player("test"))
    for bad, why in ((server.NewGame(map="plan4", checkpoint="run5_13M.pt"), "only plays Map 0"),
                     (server.NewGame(map="plan9"), "no map")):
        with pytest.raises(HTTPException) as e:
            server.new(bad, None, server.Player("test"))
        assert e.value.status_code == 400 and why in e.value.detail
