"""The association board and support details the board shows."""
import random

import arknova  # noqa: F401
from arknova import engine as G
from arknova import tables as T
from arknova.play import view


def test_association_board_tracks_owners_donations_and_workers():
    rng = random.Random(2)
    state = G.new_game(2, seed=2, map_name="map0")
    supports = 0
    for _ in range(2500):
        if state.over:
            break
        a = view.tracks(state)["association"]
        for z in a["partner_zoos"]:
            assert z["owners"] == [p.idx for p in state.players if z["id"] in p.partner_zoos]
        assert a["donations"]["made"] == state.donations
        for p, row in zip(state.players, a["players"]):
            assert row["out"] == {k: p.workers_out.get(k, 0) for k in T.TASK_VALUE}
            assert row["active"] == p.active_workers
        options = G.legal_options(state)
        for i, o in enumerate(options):
            if o.key[0] in view.SUPPORT_KINDS:
                out = view.option(i, o, None, state, state.stack[-1].kind)
                assert out["detail"].startswith("This slot:") and "Map token you take:" in out["detail"]
                assert "map token" in out["label"]
                supports += 1
        G.step(state, rng.choice(options))
    assert supports
