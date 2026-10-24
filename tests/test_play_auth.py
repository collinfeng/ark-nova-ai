"""Accounts for the board: login, tokens, per-account games, and the hints permission."""
import pytest
from fastapi import HTTPException

import arknova  # noqa: F401
from arknova.play import auth, config, game as gamemod, server
from tests.test_play_game import FirstOption


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DIR", tmp_path / "auth")
    monkeypatch.setattr(gamemod, "SAVE_DIR", tmp_path / "games")
    monkeypatch.setattr(gamemod, "CURRENT", tmp_path / "games" / "current.json")
    monkeypatch.setattr(server, "CURRENT", tmp_path / "games" / "current.json")
    monkeypatch.setattr(server, "_ai", lambda checkpoint=None, map_name="map0": FirstOption())
    monkeypatch.setitem(server.ctx, "games", {})
    monkeypatch.setattr(config.paths, "DATA", tmp_path)
    (tmp_path / "config.json").write_text('{"accounts": {"guest": {"hints": false}}}')  # the tests below need a no-hints account
    assert auth.ensure()
    creds = (tmp_path / "auth" / "credentials.txt").read_text().split("\n")
    pw = {}
    for i, line in enumerate(creds):
        if line.startswith("id: "):
            pw[line[4:]] = creds[i + 1][len("password: "):]
    return pw


def test_two_accounts_are_made_once_and_only_hashes_are_kept(accounts, tmp_path):
    assert set(accounts) == {"player", "guest"} and all(len(p) >= 12 for p in accounts.values())
    assert not auth.ensure()  # a second start keeps them
    stored = (tmp_path / "auth" / "users.json").read_text()
    assert not any(p in stored for p in accounts.values())


def test_login_checks_the_password_and_tokens_are_signed(accounts):
    assert auth.check("player", accounts["player"]) == "player"
    assert auth.check("player", accounts["guest"]) is None
    assert auth.check("nobody", "x") is None
    tok = auth.token("guest")
    assert auth.verify(tok) == "guest"
    assert auth.verify(tok[:-2] + "00") is None and auth.verify("garbage") is None and auth.verify(None) is None
    with pytest.raises(HTTPException):
        server.current_user("Bearer nonsense")
    assert server.current_user(f"Bearer {tok}", None) == "guest"


def test_only_one_account_may_use_the_hints(accounts):
    assert auth.can_hint("player") and not auth.can_hint("guest")
    full = server._board("player", None)
    plain = server._board("guest", None)
    assert full["can_hint"] and full["decision"]["ai"] and full["records"] is not None
    assert not plain["can_hint"] and "ai" not in plain["decision"]
    assert all("ai_prob" not in o for o in plain["decision"]["options"])
    assert all(m["prob"] is None for m in plain["ai_moves"])


def test_the_settings_file_can_give_an_account_hints(accounts, tmp_path):
    (tmp_path / "config.json").write_text('{"accounts": {"guest": {"hints": true}}}')
    assert auth.can_hint("guest") and server._board("guest", None)["can_hint"]
    (tmp_path / "config.json").write_text("{}")
    assert auth.can_hint("guest")  # the built-in default now gives the guest account hints
    assert not auth.can_hint("nobody")


def test_nothing_of_the_ai_evaluation_reaches_an_account_without_hints(accounts):
    game = server._game("guest")
    game.play(0)
    board = server._board("guest", None)
    assert all(set(r) == {"move", "kind"} for r in board["records"])
    assert "ai_best" not in str(board) and "win_chance" not in str(board)


def test_each_account_plays_its_own_game(accounts, tmp_path):
    mine, theirs = server._game("player"), server._game("guest")
    assert mine is not theirs
    mine.play(0)
    assert len(theirs.records) == 0
    assert (tmp_path / "games" / "current_player.json").exists() and (tmp_path / "games" / "current_guest.json").exists()


def test_a_game_from_before_accounts_goes_to_the_first_account(accounts, tmp_path):
    old = gamemod.Game(FirstOption(), seed=9)
    old.play(0)
    old.checkpoint()  # experiments/human_games/current.json as it was
    assert server._game("player").seed == 9 and len(server._game("player").records) == 1
    assert server._game("guest").seed != 9


def test_two_browsers_on_one_account_have_separate_games(accounts, tmp_path, monkeypatch):
    from arknova.play import server
    monkeypatch.setattr(server.gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setattr(server, "CURRENT", tmp_path / "none.json")
    monkeypatch.setitem(server.ctx, "games", {})
    from tests.test_play_game import FirstOption
    monkeypatch.setattr(server, "_ai", lambda *a: FirstOption())
    tok = server.auth.token("guest")
    a = server.current_user(f"Bearer {tok}", "aaaaaaaa1111")
    b = server.current_user(f"Bearer {tok}", "bbbbbbbb2222")
    legacy = server.current_user(f"Bearer {tok}", "../x")
    assert a == b == "guest" and legacy.slot == "main"
    assert server._game(a) is not server._game(b)
    assert server._game(a) is server._game(a)
    assert server._path(a) != server._path(b) != server._path(legacy)


def test_guest_cannot_save_and_games_wait_for_a_place(tmp_path, monkeypatch):
    import os
    import time
    import pytest
    from fastapi import HTTPException
    from arknova.play import config, server
    from arknova.play.admission import Admission
    from tests.test_play_game import FirstOption
    monkeypatch.setattr(server.gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setattr(config.paths, "DATA", tmp_path)
    monkeypatch.setitem(server.ctx, "games", {})
    monkeypatch.setattr(server, "_ai", lambda *a: FirstOption())
    assert not config.can_save("guest") and config.can_save("player")
    with pytest.raises(HTTPException) as e:
        server.save(server.Player("guest"))
    assert e.value.status_code == 403
    (tmp_path / "config.json").write_text('{"accounts": {"guest": {"can_save": true}}}')
    assert config.can_save("guest")  # an edit applies without a restart
    (tmp_path / "config.json").write_text("{broken")
    assert not config.can_save("guest")  # a broken file falls back to the defaults

    a = Admission()
    t = 1000.0
    assert [a.check("guest", k, 2, 10, t) for k in "AB"] == [None, None]
    assert a.check("guest", "C", 2, 10, t) == 1 and a.check("guest", "D", 2, 10, t) == 2
    assert a.check("guest", "A", 2, 10, t + 5) is None  # a player keeps their place
    assert a.check("guest", "D", 2, 10, t + 6) == 2  # nobody jumps the line
    # A and B go quiet; C is the one waiting asks, so C comes in, then D.
    assert a.check("guest", "C", 2, 10, t + 700) is None and a.check("guest", "D", 2, 10, t + 700) is None
    assert a.check("guest", "E", 2, 10, t + 701) == 1
    assert a.check("player", "X", 0, 10, t) is None  # no limit
    capped = Admission()  # one place, and room for two in the line
    assert capped.check("guest", "A", 1, 10, t, max_waiting=2) is None
    assert [capped.check("guest", k, 1, 10, t, max_waiting=2) for k in "BCD"] == [1, 2, 0]  # D: the line is full
    assert capped.check("guest", "C", 1, 10, t, max_waiting=2) == 2  # C keeps its place

    old = tmp_path / "current_guest.abc123.json"
    main = tmp_path / "current_guest.json"
    new = tmp_path / "current_guest.def456.json"
    for f in (old, main, new):
        f.write_text("{}")
    os.utime(old, (t, t))
    os.utime(main, (t, t))
    (tmp_path / "config.json").write_text('{"abandoned_game_days": 7}')
    assert server.clean_abandoned(now=time.time()) == [old.name]
    assert main.exists() and new.exists() and not old.exists()


def test_play_as_a_guest_needs_no_password_and_can_be_closed(accounts, tmp_path):
    assert server.guest_open() == {"open": True}
    session = server.guest_login()
    assert session["user"] == "guest" and auth.verify(session["token"]) == "guest"
    (tmp_path / "config.json").write_text('{"guest_play": false}')
    assert server.guest_open() == {"open": False}
    with pytest.raises(HTTPException) as e:
        server.guest_login()
    assert e.value.status_code == 403


def test_a_rule_policy_can_be_the_hint_model(accounts):
    game = server._game("player")
    plain = server._board("player", None)
    assert plain["hint_model"] == "default" and "win_chance" in plain["decision"]["ai"]
    board = server.hint_model(server.HintModel(name="beam_2x3"), None, server.Player("player"))
    assert board["hint_model"] == "beam_2x3"
    ai = board["decision"]["ai"]
    assert ai == {"best": ai["best"], "rule": True}  # a choice, but no odds and no win chance
    probs = [o["ai_prob"] for o in board["decision"]["options"]]  # a deterministic policy: all weight on its move
    assert probs.count(1.0) == 1 and probs[ai["best"]] == 1.0 and sum(probs) == 1.0
    back = server.hint_model(server.HintModel(name="default"), None, server.Player("player"))
    assert back["decision"]["ai"].get("win_chance") is not None  # the opponent's own network again
    server.hint_model(server.HintModel(name="beam_2x3"), None, server.Player("player"))
    game.play(ai["best"])
    rec = server._board("player", None)["records"][-1]
    assert rec["prob"] == 1.0 and rec["rank"] == 1 and rec["value"] is None and rec["rule"]
    assert rec["hint"] == "beam_2x3"  # each move keeps the model that judged it, for the analysis list
    with pytest.raises(HTTPException):
        server.hint_model(server.HintModel(name="../x.pt"), None, server.Player("player"))
    with pytest.raises(HTTPException) as e:
        server.hint_model(server.HintModel(name="greedy"), None, server.Player("nobody"))
    assert e.value.status_code == 403


def test_guest_games_are_deleted_sooner_and_finished_ones_sooner_still(tmp_path, monkeypatch):
    import os
    import time
    from arknova.play import config, server
    monkeypatch.setattr(server.gamemod, "SAVE_DIR", tmp_path)
    monkeypatch.setattr(config.paths, "DATA", tmp_path)
    monkeypatch.setitem(server.ctx, "games", {})
    now = time.time()
    files = {  # name: (age in hours, finished)
        "current_guest.aaaaaa111.json": (30, False),   # guest abandoned: gone after 1 day
        "current_guest.bbbbbb222.json": (5, False),    # still fresh
        "current_guest.cccccc333.json": (2, True),     # guest finished: gone after 1 hour
        "current_guest.dddddd444.json": (0.5, True),   # finished a moment ago
        "current_player.eeeeee555.json": (30, False),  # other accounts keep the 7-day default
        "current_player.ffffff666.json": (30, True),   # and keep finished games
        "current_guest.json": (500, False),            # a main game is never deleted
    }
    for name, (hours, over) in files.items():
        f = tmp_path / name
        f.write_text('{"over": %s}' % ("true" if over else "false"))
        os.utime(f, (now - hours * 3600,) * 2)
    gone = set(server.clean_abandoned(now=now))
    assert gone == {"current_guest.aaaaaa111.json", "current_guest.cccccc333.json"}


def test_quitting_deletes_the_game_and_frees_the_place(accounts, tmp_path):
    me = server.Player("guest")
    me.slot = "qqqqqq111"
    server._game(me).play(0)
    path = server._path(me)
    assert path.exists() and me.key in server.ctx["games"]
    assert server.admission.check("guest", me.key, 1, 10) is None  # holds the only place
    other = server.admission.check("guest", "someone.else", 1, 10)
    assert other == 1
    assert server.quit_game(me) == {"ok": True}
    assert not path.exists() and me.key not in server.ctx["games"]
    assert server.admission.check("guest", "someone.else", 1, 10) is None  # their turn


def test_card_numbers_in_activity_become_names_and_the_ai_discard_stays_hidden(accounts):
    from arknova.play import view
    from arknova import cards as C
    cid = next(c for c in C.all_cards() if c.startswith("2"))
    name = view.card_name(C.card(cid))
    mine = view._ai_move({"kind": "discard_hand", "label": f"Discard {cid}", "prob": None}, True, 0, "you")
    assert mine["label"] == f"Discard {name}" and [c["id"] for c in mine["cards"]] == [cid]
    theirs = view._ai_move({"kind": "discard_hand", "label": f"Discard {cid}", "prob": 1.0}, True, 0, "ai")
    assert theirs["label"] == "Discard a card" and theirs["cards"] == []
    keep = view._ai_move({"kind": "setup_keep", "label": f"Keep {cid}, {cid}", "prob": None}, True, 0, "you")
    assert name in keep["label"] and len(keep["cards"]) == 2
    taken = view._ai_move({"kind": "take_card", "label": "Draw from the deck", "prob": None}, True, 0, "ai")
    assert taken["label"] == "Draw from the deck" and taken["cards"] == []
    dig = view._ai_move({"kind": "dig", "label": f"Discard {name} and draw", "prob": 1.0}, True, 0, "ai")
    assert dig["label"] == "Discard a card" and dig["cards"] == []
    shown = view._ai_move({"kind": "x", "label": "Discard display folder 2", "prob": 1.0}, True, 0, "ai")
    assert shown["label"] == "Discard display folder 2"  # the display is public


class _Req:
    def __init__(self, host="127.0.0.1", headers=()):
        self.client = type("C", (), {"host": host})()
        self.headers = dict(headers)


def test_skip_login_signs_in_a_local_browser_only(accounts, tmp_path):
    with pytest.raises(HTTPException):
        server.current_user(None, None, _Req())  # off by default
    (tmp_path / "config.json").write_text('{"skip_login": "player"}')
    assert server.current_user(None, None, _Req()) == "player"
    assert server.current_user("Bearer nonsense", "abcdef123456", _Req()).key == "player.abcdef123456"
    for far in (_Req(host="203.0.113.9"), _Req(headers={"x-forwarded-for": "203.0.113.9"}), None):
        with pytest.raises(HTTPException):
            server.current_user(None, None, far)  # not from this machine, or through a proxy
    (tmp_path / "config.json").write_text('{"skip_login": "nobody"}')
    with pytest.raises(HTTPException):
        server.current_user(None, None, _Req())  # an account that does not exist


def test_changing_one_account_setting_keeps_its_other_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config.paths, "DATA", tmp_path)
    (tmp_path / "config.json").write_text('{"accounts": {"guest": {"hints": false}}}')
    guest = config.account("guest")
    assert guest["hints"] is False and guest["can_save"] is False and guest["max_players"] == 6


def test_network_names_cannot_leave_the_checkpoint_folder():
    for name in ("../x.pt", "/etc/passwd.pt", ".hidden.pt", "sub/dir.pt", "notes.txt", ""):
        with pytest.raises(HTTPException):
            server._network_file(name)
    assert server._network_file("model.pt") == server.KEEP / "model.pt"
