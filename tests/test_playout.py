"""End-to-end check: random legal play must always reach a finished game with a consistent state."""
import random

import pytest

import arknova  # noqa: F401
from arknova import cards, engine as G, tables as T

ALL_CARDS = set(cards.zoo_deck_ids()) | set(cards.ids_of("project", category="base"))


def check_invariants(state):
    seen = [c for c in state.deck + state.discard + state.display if c is not None]
    for p in state.players:
        seen += p.zoo_cards + p.tucked + p.hand
        assert p.money >= 0 and p.appeal >= 0 and 0 <= p.xtokens <= T.MAX_XTOKENS
        assert 1 <= p.reputation <= T.REPUTATION_MAX and 1 <= p.workers <= T.MAX_WORKERS
        assert p.active_workers >= 0 and sorted(p.slots) == sorted(T.ACTIONS)
        assert len(p.partner_zoos) == len(set(p.partner_zoos)) <= T.MAX_PARTNER_ZOOS
        covered = [c for b in p.zoo.buildings for c in b.cells]
        assert len(covered) == len(set(covered))
        # Diversity Researcher (219) may build over water and rock
        assert "219" in p.zoo_cards or all(p.zoo.mapdef.cells[c].terrain == "plain" for c in covered)
        assert all(0 <= b.used <= b.size for b in p.zoo.buildings)
        for building in p.zoo.buildings:  # occupied flags agree with where the animals live
            if building.kind == "enclosure":
                assert building.occupied == any(home == building.id for home, _ in p.housing.values())
    seen += state.projects + state.base_projects + state.base_project_deck
    for frame in state.stack:  # cards revealed and waiting for a choice
        seen += [c for c in frame.data.get("cards", []) if c in ALL_CARDS]
    assert len(seen) == len(set(seen)) and set(seen) == ALL_CARDS, "cards lost or duplicated"


@pytest.mark.parametrize("seed", range(40))
def test_random_playout_finishes(seed):
    n = 2 + seed % 3
    state = G.new_game(n, seed=seed)
    rng = random.Random(seed)
    for steps in range(20000):
        if state.over:
            break
        options = G.legal_options(state)
        assert options and len({o.key for o in options}) == len(options)
        G.step(state, rng.choice(options))
        if steps % 25 == 0:
            check_invariants(state)
    assert state.over, "game did not finish"
    check_invariants(state)
    assert len(state.scores) == n and G.winners(state)
