"""The board JSON's reward tracks: the printed stops, and where each player is."""
import arknova  # noqa: F401
from arknova import engine as G
from arknova import tables as T
from arknova.play import view


def test_sponsor_readiness_uses_money_only_for_display_fees_or_paid_effects():
    from arknova import cards as C, sponsor_rules as SR
    from arknova.actions import sponsors as S
    from arknova.play import i18n
    from arknova.state import push

    state = G.new_game(2, seed=0, map_name="map0")
    player = state.players[0]
    cid = next(c for c in C.ids_of("sponsor") if S.can_play(state, 0, c)
               and 0 < SR.sponsor_level(state, 0, c) <= 5)
    player.hand = [cid]
    player.money = 0
    assert S._playable(state, 0, 5) == [("hand", cid, 0)]
    assert view.readiness(state, 0, cid) == {"ready": True, "why": "", "cost": 0}

    player.upgraded.add("sponsors")
    token = i18n.use("zh-CN")
    try:
        status = view.readiness(state, 0, cid, extra_cost=2, display=True)
        assert not status["ready"] and status["cost"] == 2
        assert status["why"] == "费用为 2，你只有 0 金钱"
    finally:
        i18n.reset(token)
    player.money = 2
    assert view.readiness(state, 0, cid, extra_cost=2, display=True)["ready"]

    push(state, "paid_sponsor", 0)
    level = SR.sponsor_level(state, 0, cid)
    player.money = level - 1
    status = view.readiness(state, 0, cid)
    assert not status["ready"] and status["cost"] == level
    player.money = level
    assert view.readiness(state, 0, cid)["ready"]


def test_opening_tracks_list_every_printed_stop():
    state = G.new_game(2, seed=0, map_name="map0")
    t = view.tracks(state)
    cons = t["conservation"]["stops"]
    assert [s["at"] for s in cons] == [2, 5, 8, 10]
    assert cons[0]["kind"] == "upgrade_or_worker"
    assert len(cons[1]["tiles"]) == 2 and len(cons[2]["tiles"]) == 2
    assert {tile["id"] for tile in cons[1]["tiles"] + cons[2]["tiles"]} <= set(T.BONUS_TILES)
    assert [s["at"] for s in t["reputation"]["stops"]] == [5, 8, 10, 11, 12, 13, 14, 15]
    assert t["reputation"]["stops"][0]["kind"] == "upgrade"
    assert t["reputation"]["gate"] == 9
    assert [s["label"] for s in t["partner_zoos"]["slots"]] == [
        "No slot bonus", "upgrade an action", "1 worker", "2 conservation"]
    assert t["partner_zoos"]["available"] == list(T.CONTINENTS)
    assert [s["label"] for s in t["universities"]["slots"]] == [
        "No slot bonus", "upgrade an action", "2 conservation"]
    assert [u["id"] for u in t["universities"]["available"]] == list(T.UNIVERSITIES)
    assert t["workers"]["last"][0]["kind"] == "conservation"
    assert len(t["tokens"]) == 7 and all(p["on_map"] == [True] * 7 for p in t["players"])
    assert t["players"][0]["conservation"] == 0 and t["players"][0]["reputation"] == 1


def test_tracks_follow_a_player_and_the_shared_pools():
    state = G.new_game(2, seed=1, map_name="map0")
    p = state.players[0]
    p.reputation = 8
    p.conservation = 5
    p.upgraded.add("cards")
    p.partner_zoos = ["africa", "europe"]
    state.partner_zoos_available -= {"africa", "europe"}
    p.universities = ["hand"]
    state.universities_available.discard("hand")
    p.workers = 3
    p.tokens[0] = False
    state.bonus_tiles[8].pop()
    state.final_card_discarded = True
    t = view.tracks(state)
    me = t["players"][0]
    assert me["cards_ii"] and me["reputation"] == 8 and me["conservation"] == 5
    assert me["partner_zoos"] == 2 and "africa" not in t["partner_zoos"]["available"]
    assert [u["id"] for u in t["universities"]["available"]] == ["science2", "science_rep"]
    assert me["on_map"][0] is False and me["workers"] == 3
    assert len(next(s["tiles"] for s in t["conservation"]["stops"] if s["at"] == 8)) == 1
    assert next(s for s in t["conservation"]["stops"] if s["at"] == 10)["spent"] is True


def test_unknown_map_token_stays_on_the_track():
    state = G.new_game(2, seed=0, map_name="plan7")
    tok = view.tracks(state)["tokens"][3]
    assert tok["label"] == "Bonus not confirmed" and tok["repeats"] is True


def test_conservation_choices_keep_their_concrete_icons_after_a_tile_is_taken():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=0)
    original = list(game.initial_bonus_tiles[8])
    taken = game.state.bonus_tiles[8].pop()
    stop = next(s for s in view.board(game)["tracks"]["conservation"]["stops"] if s["at"] == 8)
    assert len(stop["tiles"]) == 1 and len(stop["choices"]) == 2
    assert [choice["id"] for choice in stop["choices"]] == original
    assert all(choice["effects"] for choice in stop["choices"])
    assert next(choice for choice in stop["choices"] if choice["id"] == taken)["available"] is False
    assert game.initial_bonus_tiles[8] == original
    back = Game.resume(FirstOption(), game.to_json())
    assert back.initial_bonus_tiles == game.initial_bonus_tiles


def test_conservation_claims_identify_the_chosen_tile_and_money_and_restore():
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption

    game = Game(FirstOption(), seed=0)
    before = game._point()
    tile = game.initial_bonus_tiles[5][0]
    push(game.state, "conservation_tile", 0, space=5)
    game._step(next(o for o in game.options() if o.key == ("tile", tile)))
    push(game.state, "conservation_tile", 1, space=5)
    game._step(next(o for o in game.options() if o.key == ("money",)))
    stop = next(s for s in view.board(game)["tracks"]["conservation"]["stops"] if s["at"] == 5)
    assert stop["choices"][0]["claimed_by"] == [0]
    assert stop["choices"][1]["claimed_by"] == []
    assert stop["money_claimed_by"] == [1]
    after = game._point()
    game._restore(before)
    assert game.reward_claims == []
    game._restore(after)
    assert game.reward_claims == [{"space": 5, "player": 0, "choice": tile},
                                  {"space": 5, "player": 1, "choice": "money"}]


def test_card_text_keeps_what_the_printed_icons_said():
    waza = view.card("227")
    assert waza["name"] == "WAZA Special Assignment"
    assert "**small**" in waza["effects"][0]["text"] and "**large**" in waza["effects"][0]["text"]
    assert view.card("206")["effects"][0]["text"].endswith("{ConservationPoint-1}.")


def test_option_labels_read_well_and_name_the_action():
    assert view.nicer("Partner zoo: africa", ("partner_zoo", "africa")) == "Partner zoo: Africa"
    assert view.nicer("University: science_rep", ("university", "science_rep")) == "University: 1 science icon and 2 reputation"
    assert view.nicer("Discard 227", ("discard", "227")) == "Discard WAZA Special Assignment"
    assert view.nicer("Build petting_zoo 3 for 6", ("build", "petting_zoo", 3, ((0, 0),))) == "Build petting zoo 3 for 6"
    assert view.nicer("Take bonus tile xtoken3", ("tile", "xtoken3")) == "Take bonus tile: 3 X-tokens"
    assert view._action_in(("boost", 1), "Place build on slot 1") == "build"
    assert view._action_in(("upgrade", "cards"), "Upgrade cards") == "cards"
    assert view._action_in(("donate",), "Donate 2 money") is None


def test_take_card_says_how_many_cards_are_left_to_take():
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    player = game.state.stack[-1].player
    game.state.stack = game.state.stack[:1]
    for _ in range(3):
        push(game.state, "take_card", player)
    assert view.decision(game)["remaining"] == 3


def test_conservation_tile_is_presented_as_a_progress_reward():
    from arknova.play import i18n
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    player = state.stack[-1].player
    state.stack = state.stack[:1]
    push(state, "conservation_tile", player, space=5)

    token = i18n.use("zh-CN")
    try:
        decision = view.decision(game)
    finally:
        i18n.reset(token)
    assert decision["title"] == "选择保护进度奖励"
    assert "保护点数轨道格" in decision["note"]


def test_a_decision_carries_the_cards_its_options_name():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    d = view.decision(game)
    named = {c for o in d["options"] for c in o["cards"]}
    assert named and {c["id"] for c in d["cards"]} == named


def test_snapping_names_the_card_in_each_display_slot():
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    player = state.stack[-1].player
    state.stack = state.stack[:1]
    push(state, "ab_snap", player, left=1, can_replenish=False, replenish_between=False)

    decision = view.decision(game)
    takes = [o for o in decision["options"] if o["key"][0] == "take"]
    assert takes
    for o in takes:
        slot = o["key"][1]
        assert o["cards"] == [state.display[slot]]
        assert "display slot" in o["label"]
    assert {c["id"] for c in decision["cards"]} == {state.display[o["key"][1]] for o in takes}


def test_hunter_reveals_all_four_cards_but_only_animals_are_selectable():
    from arknova import cards as C
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    player = state.stack[-1].player
    animals = C.ids_of("animal")[:2]
    sponsors = C.ids_of("sponsor")[:2]
    revealed = [animals[0], sponsors[0], animals[1], sponsors[1]]
    state.stack = state.stack[:1]
    push(state, "ab_hunter", player, cards=revealed)

    decision = view.decision(game)
    assert [c["id"] for c in decision["revealed_cards"]] == revealed
    assert {c["id"] for c in decision["cards"]} >= set(revealed)
    takes = [o for o in decision["options"] if o["key"][0] == "take"]
    assert {o["cards"][0] for o in takes} == set(animals)


def test_a_sponsor_building_can_be_placed_on_the_map():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    state.stack = state.stack[:1]
    from arknova.state import push
    push(state, "sponsor_building", state.stack[-1].player, card="244")
    d = view.decision(game)
    places = [o for o in d["options"] if o["type"] == "place"]
    assert places and all(o["building"] == "unique" and o["cells"] for o in places)


def test_taking_and_discarding_several_cards_say_how_many_are_needed():
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    player = state.stack[-1].player
    state.stack = state.stack[:1]
    push(state, "discard_hand", player, count=2)
    assert view.decision(game)["pick"] == {"count": 2}
    state.stack = state.stack[:1]
    push(state, "discard_hand", player, limit=len(state.players[player].hand) - 3)
    assert view.decision(game)["pick"] == {"count": 3}


def _play(game, moves, seed=1):
    import random
    rng = random.Random(seed)
    for _ in range(moves):
        if game.state.over:
            break
        if game.turn_done:
            game.end_turn()
            continue
        game.play(rng.randrange(len(game.options())))


def test_the_turn_feed_says_what_changed_and_why():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    _play(game, 25)
    feed = view.board(game)["turn_feed"]
    assert feed, "a turn with moves has a feed"
    for line in feed:
        assert ("note" in line and line["text"]) or (line["who"] in ("you", "ai") and line["amount"] and line["why"])
    # a payment is shown as a loss and blamed on the move that made it
    game = Game(FirstOption(), seed=5)
    _play(game, 80)
    seen = [line for r in game.records for line in view.feed_lines(r.get("feed"), 0)]
    assert any(l.get("amount", 0) < 0 and l["kind"] == "money" for l in seen)


def test_build_payment_is_kept_separate_from_a_money_bonus():
    from arknova import effects as E
    from arknova.play import feed

    state = G.new_game(2, seed=0, map_name="map0")
    before = feed.stats(state)
    state.ledger = []
    state.players[0].money -= 4  # A size-2 enclosure.
    E.gain(state, 0, "money", 2)  # A covered map bonus in the same move.
    entries = feed.entries(state, before, state.ledger, ("act_build", "Build enclosure 2 for 4"))
    amounts = [entry["n"] for entry in entries if entry.get("k") == "money"]
    assert amounts == [2, -4]
    assert sum(amounts) == state.players[0].money - before["players"][0]["money"]


def test_activity_history_includes_both_players_and_follows_undo_and_resume():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption

    game = Game(FirstOption(), seed=5)
    _play(game, 80)
    history = view.board(game)["activity_history"]
    assert {entry["actor"] for entry in history} == {"you", "ai"}
    assert [(entry["turn"], entry["actor"] == "ai") for entry in history] == sorted(
        (entry["turn"], entry["actor"] == "ai") for entry in history)
    own_moves = [move for entry in history if entry["actor"] == "you" for move in entry["moves"]]
    assert [move["label"] for move in own_moves] == [view._named(record["chose"])[0] for record in game.records]
    assert all(move["prob"] is None for move in own_moves)
    assert any(move["feed"] for move in own_moves)
    assert view.board(Game.resume(FirstOption(), game.to_json()))["activity_history"] == history
    hidden = view.board(game, hints=False)["activity_history"]
    assert all(move["prob"] is None for entry in hidden for move in entry["moves"])
    assert game.undo()
    after_undo = view.board(game)["activity_history"]
    assert sum(len(entry["moves"]) for entry in after_undo if entry["actor"] == "you") == len(own_moves) - 1
    assert game.redo()
    assert view.board(game)["activity_history"] == history


def test_a_break_is_announced_with_its_income():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    lines = []
    for seed in range(6):
        _play(game, 60, seed)
        b = view.board(game)
        lines += [l for m in b["ai_moves"] for l in m["feed"]] + b["turn_feed"]
        lines += [l for r in game.records for l in view.feed_lines(r.get("feed"), 0)]
    assert any(l.get("note") == "break" for l in lines)
    assert any(l.get("why", "") and "income" in (l.get("why") or "") for l in lines)


def test_old_activity_feeds_rebuild_break_events_and_their_trigger():
    import json
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption

    game = Game(FirstOption(), seed=5)
    _play(game, 300)
    saved = json.loads(json.dumps(game.to_json()))
    for entry in saved["ai_history"]:
        for move in entry["moves"]:
            move.pop("feed", None)
    for record in saved["records"]:
        record.pop("feed", None)
    for move in saved["ai_moves"]:
        move.pop("feed", None)
    back = Game.resume(FirstOption(), saved)
    history = view.board(back)["activity_history"]
    lines = [line for turn in history for move in turn["moves"] for line in move["feed"]]
    triggered = [line for line in lines if line.get("note") == "break" and "reached the end" in line["text"]]
    assert triggered and all(line.get("why") for line in triggered)
    assert any("income" in (line.get("why") or "") for line in lines)


def test_the_feed_is_in_chinese_when_asked():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    _play(game, 80)
    board = view.board(game, "zh-CN")
    texts = [l.get("why") or l.get("text") for l in board["turn_feed"] + [l for m in board["ai_moves"] for l in m["feed"]]]
    assert texts
    import re
    for text in texts:
        assert not re.search(r"[A-Za-z]{4,}", text.replace("AI", "").replace("X", "")), text


def test_the_cards_action_says_draw_or_snap_not_both():
    from arknova.play.game import Game
    from arknova.state import push
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=5)
    state = game.state
    player = state.stack[-1].player
    state.stack = state.stack[:1]
    push(state, "act_cards", player, draw=2, discard=0, may_snap=True, upgraded=True, drawn=0)
    first = view.decision(game)["note"]
    assert "2" in first and "snap" in first
    state.stack[-1].data["drawn"] = 1
    assert "snap" not in view.decision(game)["note"]


def test_activity_text_reads_like_the_options():
    assert view._named("University: science_rep")[0] == "University: 1 science icon and 2 reputation"
    assert view._named("Partner zoo: africa")[0] == "Partner zoo: Africa"
    assert view._named("Build reptile_house 5 for 10")[0] == "Build reptile house 5 for 10"
    assert view._named("Take bonus tile money10")[0] == "Take bonus tile: 10 money"
    assert view._why(("move", 0, "University: science_rep")) == "University: 1 science icon and 2 reputation"


def test_a_break_discard_is_named_as_one():
    import random
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    for seed in range(20):
        game, rng = Game(FirstOption(), seed=seed), random.Random(seed)
        for _ in range(400):
            if game.state.over:
                break
            if game.turn_done:
                game.end_turn()
                continue
            frame = game.state.stack[-1]
            if frame.kind == "discard_hand":
                d = view.decision(game)
                at_break = any(f.kind == "break" for f in game.state.stack) and frame.data.get("limit") is not None
                assert (d["title"] == "Break: discard down to your hand limit") == at_break
                if at_break:
                    assert "Undo also takes that turn back" in d["note"]
                    return
            game.play(rng.randrange(len(game.options())))
    raise AssertionError("no break discard found")


def test_display_cards_out_of_reach_say_what_reputation_they_need():
    from arknova.play.game import Game
    from tests.test_play_game import FirstOption
    game = Game(FirstOption(), seed=0)
    game.state.players[game.human].reputation = 1  # folder 1 only
    slots = view.board(game)["display"]
    assert [s["in_reach"] for s in slots] == [True] + [False] * 5
    assert [s["reach_reputation"] for s in slots] == [0, 2, 4, 7, 10, 13]
    for s in slots[1:]:
        if s["status"] is not None:
            assert s["status"]["ready"] is False and "needs reputation" in s["status"]["why"]
