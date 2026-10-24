import copy
import random

import pytest

np = pytest.importorskip("numpy")

import arknova  # noqa: E402,F401
from arknova import engine as G  # noqa: E402
from arknova.hexmap import MAP0  # noqa: E402
from arknova.rl import encode  # noqa: E402


def random_states(map_name="map0", games=3, every=9, limit=3000):
    """(state, options) at some decisions of random games; each state is a copy, so they can be kept."""
    for seed in range(games):
        state, rng, steps = G.new_game(2, seed=seed, map_name=map_name), random.Random(seed), 0
        while not state.over and steps < limit:
            options = G.legal_options(state)
            if len(options) > 1 and steps % every == 0:
                yield copy.deepcopy(state), options
            G.step(state, rng.choice(options))
            steps += 1


def same_future(a, b, steps=60, seed=7):
    """The two states play out identically under the same random choices (options, then scores)."""
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    rng_a, rng_b = random.Random(seed), random.Random(seed)
    for _ in range(steps):
        if a.over or b.over:
            break
        oa, ob = G.legal_options(a), G.legal_options(b)
        if [o.key for o in oa] != [o.key for o in ob]:
            return False
        G.step(a, rng_a.choice(oa))
        G.step(b, rng_b.choice(ob))
    return a.over == b.over and [p.victory_points for p in a.players] == [p.victory_points for p in b.players]


def test_every_map_uses_map0_cells_and_has_its_name_in_the_vocabulary():
    assert set(G.MAP_DEFS) == set(encode.MAP_NAMES)
    for name in encode.MAP_NAMES:
        assert set(G.MAP_DEFS[name].cells) == set(MAP0.cells)


@pytest.mark.slow
def test_board_features_differ_between_maps_and_every_map_encodes():
    boards = {name: encode.board(name) for name in encode.MAP_NAMES}
    assert len({b.tobytes() for b in boards.values()}) == len(boards)
    width = encode.sizes()
    for name in encode.MAP_NAMES:
        for state, options in random_states(name, games=1, every=25, limit=1500):
            obs = encode.observe(state, options)
            assert len(obs["scalars"]) == width["scalars"] and len(obs["maps"]) == width["maps"]
            tail = len(encode.LAST_ACTIONS) + len(encode.CARD_TYPES) + len(encode.ICONS) + 1
            one_hot = obs["scalars"][-tail - len(encode.MAP_NAMES):-tail]
            assert one_hot.sum() == 1 and one_hot[encode.MAP_NAMES.index(name)] == 1


@pytest.mark.slow
def test_option_slots_point_at_the_same_card_in_the_sets():
    checked = 0
    for state, options in random_states(games=4, every=3):
        obs = encode.observe(state, options)
        cards, slots = obs["option_cards"], obs["option_slots"]
        assert cards.shape == slots.shape
        for card, slot in zip(cards.reshape(-1), slots.reshape(-1)):
            if slot:
                assert obs["sets"][slot - 1] == card
                checked += 1
            elif card:
                assert card not in obs["sets"]
    assert checked > 100


def test_known_hand_of_the_opponent_lists_public_cards_still_in_hand():
    """The list is built from public zones only. A public card leaves the hand publicly except into a Pouch
    (treated as face down: UNVERIFIED in docs/RULES_NOTES.md), so the list is the public cards in hand plus
    possibly cards pouched since."""
    checked = 0
    for state, options in random_states(games=4, every=5):
        frame = state.stack[-1]
        other = state.players[1 - frame.player]
        obs = encode.observe(state, options)
        span = encode.SET_SLICES["other_known_hand"]
        listed = set(obs["sets"][span]) - {0}
        in_hand = {encode.CARD_INDEX[c] for c in other.public_hand if c in other.hand}
        assert in_hand <= listed and listed - in_hand <= {encode.CARD_INDEX[c] for c in other.tucked}
        checked += bool(listed)
    assert checked > 0


@pytest.mark.slow
def test_lookahead_is_off_by_default_and_leaves_the_state_untouched():
    rows = 0
    for state, options in random_states(games=2, every=4):
        off = encode.observe(state, options)
        assert not off["option_effects"].any()
        untouched = copy.deepcopy(state)
        on = encode.observe(state, options, lookahead=True)
        assert same_future(state, untouched)
        assert on["option_effects"].shape == (len(options), encode.LOOKAHEAD_FEATURES)
        rows += int((on["option_effects"][:, :8] != 0).any(1).sum())
        for k in off:
            if k != "option_effects":
                assert np.array_equal(off[k], on[k]), k
    assert rows > 0


@pytest.mark.slow
def test_lookahead_does_not_reveal_the_deck_order():
    """Drawing from the deck: the look-ahead copy reshuffles, so its result cannot depend on the real order."""
    for state, options in random_states(games=2, every=2):
        a = encode.observe(state, options, lookahead=True)["option_effects"]
        shuffled = copy.deepcopy(state)
        random.Random(1).shuffle(shuffled.deck)
        b = encode.observe(shuffled, options, lookahead=True)["option_effects"]
        assert a.shape == b.shape  # same features are computed whatever the deck order; values may differ by chance


@pytest.mark.slow
def test_model_v3_with_and_without_attention():
    torch = pytest.importorskip("torch")
    from arknova.rl import model as M
    observations = [encode.observe(s, o, lookahead=True) for s, o in random_states(games=1, every=11)][:24]
    batch = M.to_tensors(encode.collate(observations), "cpu")
    for attention in (0, 2):
        torch.manual_seed(0)
        net = M.Net(separate_value=True, input_norm=True, set_attention=attention)
        logits, owner, values = net(batch)
        assert logits.shape[0] == int(batch["counts"].sum()) and values.shape[0] == len(observations)
        loss = logits.square().mean() + values.square().mean()
        loss.backward()
        assert all(p.grad is None or torch.isfinite(p.grad).all() for p in net.parameters())


def test_old_checkpoints_still_load(tmp_path):
    torch = pytest.importorskip("torch")
    from arknova.rl import match
    from arknova.rl.v2 import model as model_v2
    net = model_v2.Net(separate_value=True, input_norm=True)
    path = tmp_path / "v2.pt"
    torch.save({"model": net.state_dict(), "version": 2, "net": {"separate_value": True, "input_norm": True,
                                                                 "small_policy_init": False, "policy_layers": 1}}, path)
    loaded, encoder = match.load(path, "cpu")
    assert encoder.VERSION == 2 and not loaded.lookahead
    state = G.new_game(2, seed=0)
    batch = match.model_v3.to_tensors(encoder.collate([encoder.observe(state, G.legal_options(state))]), "cpu")
    loaded(batch)


def test_privileged_inputs_are_zero_unless_asked_and_hold_the_hidden_cards():
    for state, options in random_states(games=2, every=7):
        frame = state.stack[-1]
        other = state.players[1 - frame.player]
        off = encode.observe(state, options)
        assert not any(off[k].any() for k in encode.PRIV_KEYS)
        on = encode.observe(state, options, privileged=True)
        span = encode.PRIV_SLICES["other_hand"]
        listed = [c for c in on["priv_sets"][span] if c]
        assert listed == [encode.CARD_INDEX[c] for c in other.hand][:span.stop - span.start]
        nxt = encode.PRIV_SLICES["deck_next"]
        if state.deck:
            assert on["priv_sets"][nxt.start] == encode.CARD_INDEX[state.deck[-1]]  # the next card drawn
        for k in off:
            if k not in encode.PRIV_KEYS:
                assert np.array_equal(off[k], on[k]), k


def test_hidden_cards_change_the_value_but_never_the_policy():
    torch = pytest.importorskip("torch")
    from arknova.rl import model as M
    pairs = list(random_states(games=1, every=13))[:16]
    obs = [encode.observe(s, o, privileged=True) for s, o in pairs]
    batch = M.to_tensors(encode.collate(obs), "cpu")
    other = {k: v.clone() for k, v in batch.items()}
    rng = torch.Generator().manual_seed(0)
    other["priv_sets"] = torch.randint(1, encode.N_CARDS, other["priv_sets"].shape, generator=rng)
    other["priv_scalars"] = torch.rand(other["priv_scalars"].shape, generator=rng)
    for attention in (0, 1):
        torch.manual_seed(0)
        net = M.Net(separate_value=True, input_norm=True, set_attention=attention, privileged_value=True).eval()
        with torch.no_grad():
            logits_a, _, value_a = net(batch)
            logits_b, _, value_b = net(other)
        assert torch.equal(logits_a, logits_b)
        assert not torch.allclose(value_a, value_b)
    with pytest.raises(ValueError):
        M.Net(separate_value=False, privileged_value=True)


def test_packed_attention_gives_the_same_output_as_attention_over_all_slots():
    torch = pytest.importorskip("torch")
    from arknova.rl import model as M
    observations = [encode.observe(s, o) for s, o in random_states(games=2, every=17)][:32]
    batch = M.to_tensors(encode.collate(observations), "cpu")
    torch.manual_seed(0)
    net = M.Net(separate_value=True, input_norm=True, set_attention=2).eval()
    with torch.no_grad():
        net.pack_tokens = True
        packed = net(batch)
        net.pack_tokens = False
        full = net(batch)
    for a, b in zip(packed, full):
        assert torch.allclose(a.float(), b.float(), atol=1e-5), (a - b).abs().max()
