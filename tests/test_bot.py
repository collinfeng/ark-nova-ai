import pytest
import copy
import random

import arknova  # noqa: F401
from arknova import bot, engine as G


def started(seed=1, n=2):
    state = G.new_game(n, seed=seed)
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    return state


def snapshot(state):
    return (state.deck[:], state.display[:], [(p.money, p.appeal, p.hand[:], p.slots[:]) for p in state.players],
            len(state.stack), state.rng.getstate())


def test_valuation_prefers_progress_and_discounts_spare_money():
    state = started()
    base = bot.evaluate(state, 0)
    state.players[0].appeal += 5
    assert bot.evaluate(state, 0) > base + 5  # appeal also raises income
    state.players[0].appeal -= 5
    state.players[0].money = 0
    broke = bot.evaluate(state, 0)
    state.players[0].money = 5
    with_five = bot.evaluate(state, 0)
    assert with_five > broke  # money it can spend soon is worth having
    state.players[0].money = 205
    assert bot.evaluate(state, 0) - with_five < 200 * 0.05  # a hoard is worth little per coin


def test_valuation_does_not_change_the_state():
    state = started()
    before = snapshot(state), state.players[0].conservation
    bot.evaluate(state, 0)
    assert (snapshot(state), state.players[0].conservation) == before


def test_weights_can_be_overridden():
    state = started()
    state.players[0].xtokens = 3
    assert bot.evaluate(state, 0, dict(bot.DEFAULT_WEIGHTS, xtoken=5.0)) > bot.evaluate(state, 0)
    assert bot.GreedyBot({"xtoken": 5.0}).w["xtoken"] == 5.0 and bot.DEFAULT_WEIGHTS["xtoken"] != 5.0


def test_bots_return_legal_options_and_leave_the_state_alone():
    for make in (bot.GreedyBot, lambda: bot.LookaheadBot(depth=2, width=3)):
        state, rng, player = started(seed=3), random.Random(3), make()
        for _ in range(14):
            before = snapshot(state)
            option = player.choose(state, rng)
            assert snapshot(state) == before
            assert option.key in [o.key for o in G.legal_options(state)]
            G.step(state, option)


def test_bot_cannot_see_the_real_deck_order():
    a = started(seed=5)
    b = copy.deepcopy(a)
    b.deck.reverse()
    for make in (bot.GreedyBot, lambda: bot.LookaheadBot(depth=2, width=3)):
        assert make().choose(a, random.Random(9)).key == make().choose(b, random.Random(9)).key


@pytest.mark.slow
def test_lookahead_plans_an_enclosure_for_an_animal_in_hand():
    """The plan a one-turn search misses: an enclosure pays off only when the animal follows."""
    state = started(seed=1)
    players = [bot.LookaheadBot(depth=3, width=6), bot.LookaheadBot(depth=3, width=6)]
    rng = random.Random(1)
    turns = 0
    while turns < 16 and not state.over:
        turns += state.stack[-1].kind == "turn"
        G.step(state, players[state.stack[-1].player].choose(state, rng))
    assert any(p.housing for p in state.players)


def test_play_game_stops_at_the_turn_limit():
    state, reason = bot.play_game([bot.GreedyBot(), bot.GreedyBot()], seed=2, max_turns_each=3)
    assert not state.over and "3 turns each" in reason
    rows = bot.profile(state)
    assert len(rows) == 2 and {"score", "animals", "money"} <= set(rows[0])


def test_search_considers_boosting_a_card_to_strength_five():
    state = started()
    player = state.players[0]
    player.xtokens = 4
    player.slots = ["animals", "cards", "association", "build", "sponsors"]  # cards at strength 2
    kept = {o.key for o in bot.shortlist(state, G.legal_options(state))}
    assert ("act", "cards", 3) in kept          # 2 + 3 = 5: the boost a project or a snap needs
    assert ("act", "cards", 2) not in kept      # other amounts are left out to keep the search small
    planned = {o.key for o in bot.LookaheadBot()._turn_options(state)}
    assert ("act", "cards", 3) in planned and ("act", "cards", 2) not in planned


def test_playing_a_card_does_not_devalue_the_money_left_over():
    """Money is priced by amount alone, so spending some never makes the rest worth less."""
    state = started()
    player = state.players[0]
    player.money = 60
    rich = bot.evaluate(state, 0)
    player.hand = []
    assert bot.evaluate(state, 0) <= rich  # losing the hand cannot raise the value...
    player.money = 44
    spent = bot.evaluate(state, 0)
    player.money = 60
    assert bot.evaluate(state, 0) - spent < 16 * bot.DEFAULT_WEIGHTS["money"]  # ...and spare money is cheap


def test_open_bot_with_replies_returns_legal_options_and_leaves_the_state_alone():
    state, rng = started(seed=3), random.Random(3)
    player = bot.LookaheadBot(depth=2, width=2, variants=4, follow=4, open_info=True, reply=True)
    for _ in range(10):
        before = snapshot(state)
        option = player.choose(state, rng)
        assert snapshot(state) == before
        assert option.key in [o.key for o in G.legal_options(state)]
        G.step(state, option)


def test_open_copy_keeps_the_real_deck_and_draws():
    state = started(seed=5)
    clone = bot._open_copy(state)
    assert clone.deck == state.deck and clone.rng.getstate() == state.rng.getstate()


def test_replies_move_the_other_player_in_the_search():
    state = started(seed=4)
    p = state.stack[-1].player
    searcher = bot.LookaheadBot(depth=2, width=2, variants=4, follow=4, open_info=True, reply=True)
    after_mine = searcher._turns_from(bot._open_copy(state), p)[0][0]
    other = after_mine.stack[-1].player
    assert other != p
    slots_before = after_mine.players[other].slots[:]
    replied = searcher._others_reply(after_mine, p)
    assert replied.stack[-1].player == p and replied.players[other].slots != slots_before
