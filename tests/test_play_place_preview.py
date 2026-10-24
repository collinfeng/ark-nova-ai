"""The build preview (view.place_preview) against what placing the building really does."""
import random

import arknova  # noqa: F401
from arknova import engine as G
from arknova.play import view
from arknova.state import clone

REP = {"bonus:rep1": 1, "bonus:rep2": 2}


def _check(state, option, p):
    out = view.option(0, option, None, state, state.stack[-1].kind)
    gains = {g["k"]: g["n"] for g in out["gains"]}
    before = state.players[p]
    after_state = clone(state)
    G.step(after_state, option)
    after = after_state.players[p]
    rep = sum(REP.get(k, 0) * n for k, n in gains.items())
    if before.reputation + rep <= 9:  # above 9 needs Cards II, past 15 it turns into appeal
        assert after.reputation - before.reputation == rep, out
        assert after.appeal - before.appeal == gains.get("appeal", 0) + gains.get("full_cover", 0), out
    income = after.zoo.kiosk_income() - before.zoo.kiosk_income()
    assert income == gains.get("kiosk_income", 0), out


def test_preview_matches_the_move_on_every_map():
    checked = 0
    for map_name in sorted(G.MAP_DEFS):
        for seed in range(2):
            rng = random.Random(seed)
            state = G.new_game(2, seed=seed, map_name=map_name)
            for _ in range(2500):
                if state.over:
                    break
                options = G.legal_options(state)
                frame = state.stack[-1]
                places = [o for o in options if o.key[0] in ("build", "engineer") and len(o.key) == 4]
                for o in places[:: max(1, len(places) // 6)]:
                    _check(state, o, frame.player)
                    checked += 1
                G.step(state, rng.choice(options))
    assert checked > 200


def test_animal_plays_name_their_building_and_upgrades_say_what_side_two_adds():
    rng = random.Random(4)
    state = G.new_game(2, seed=4, map_name="map0")
    plays = upgrades = 0
    for _ in range(2500):
        if state.over:
            break
        options = G.legal_options(state)
        for i, o in enumerate(options):
            out = view.option(i, o, None, state, state.stack[-1].kind)
            if o.key[0] in ("play", "play_display") and len(o.key) > 2 and isinstance(o.key[2], int):
                assert "building" not in out["label"] and " into the " in out["label"], out["label"]
                plays += 1
            if o.key[0] == "upgrade":
                assert out["detail"].startswith("Side II"), out
                upgrades += 1
        G.step(state, rng.choice(options))
    assert plays and upgrades
