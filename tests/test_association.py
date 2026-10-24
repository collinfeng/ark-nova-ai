import pytest

import arknova.actions.association as assoc
from arknova import cards, engine, tables as T
from arknova.state import push

ACT = "act_association"


# ---- helpers ----------------------------------------------------------------

def new(seed=0):
    state = engine.new_game(2, seed=seed)
    while state.stack[-1].kind == "setup_keep":
        engine.step(state, engine.legal_options(state)[0])
    p = state.players[0]
    p.hand = []
    p.workers = 4  # enough workers for several tasks; worker tests set their own
    return state


def go(state, strength, side2=False):
    """Play the association card from slot min(strength, 5) with X-tokens making up the rest."""
    p = state.players[0]
    pos = min(strength, 5)
    others = [a for a in T.ACTIONS if a != "association"]
    p.slots = others[:pos - 1] + ["association"] + others[pos - 1:]
    p.xtokens = max(0, strength - 5)
    if side2:
        p.upgraded.add("association")
    engine.step(state, ("act", "association", p.xtokens))


def keys(state):
    return [o.key for o in engine.legal_options(state)]


def pick(state, key):
    engine.step(state, key)


def resolve(state):
    """Settle follow-up frames (gain choices) by taking their first option."""
    while state.stack[-1].kind not in (ACT, "turn"):
        engine.step(state, engine.legal_options(state)[0])


def in_action(state):
    return any(f.kind == ACT for f in state.stack)


def positions(state, kind="support"):
    return {k[2] for k in keys(state) if k[0] == kind}


def set_projects(state, base, projects=()):
    state.base_projects = list(base)
    state.projects = list(projects)
    state.project_tokens = {cid: {} for cid in list(base) + list(projects)}


def animals(pred, n):
    found = [c["id"] for c in sorted(cards.all_cards().values(), key=lambda c: c["id"])
             if c["type"] == "animal" and pred(c)]
    assert len(found) >= n
    return found[:n]


def single_cat(cat):
    return lambda c: [t for t in c["tags"] if t in T.ANIMAL_CATEGORIES] == [cat]


def one_continent(cont):
    return lambda c: c["continents"] == [cont] and c["tags"].count(cont) == 1


# ---- feasibility and task values ---------------------------------------------

def test_feasible_by_strength():
    state = new()
    assert not assoc.feasible(state, 0, 1)
    assert assoc.feasible(state, 0, 2)  # reputation
    state.players[0].workers = 1
    state.players[0].workers_out = {"reputation": 1}
    assert not assoc.feasible(state, 0, 2)  # no free worker


def test_task_values_against_strength():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 2)
    set_projects(state, ["103"])  # Africa: slot 3 needs 2 icons
    go(state, 2)
    ks = keys(state)
    assert ks == [("reputation",)]

    for strength, expected in [(3, {"reputation", "partner_zoo"}),
                               (4, {"reputation", "partner_zoo", "university"}),
                               (5, {"reputation", "partner_zoo", "university", "support"})]:
        state = new()
        p = state.players[0]
        p.zoo_cards = animals(one_continent("africa"), 2)
        set_projects(state, ["103"])
        go(state, strength)
        assert {k[0] for k in keys(state)} == expected, strength
        assert ("done",) not in keys(state) and ("donate",) not in keys(state)


# ---- workers ----------------------------------------------------------------

def test_worker_cost_one_then_two_then_blocked():
    state = new()
    p = state.players[0]
    p.workers = 4
    go(state, 2)
    pick(state, ("reputation",))
    assert p.workers_out == {"reputation": 1}

    # Already one there: costs 2.
    p.workers_out = {"reputation": 1}
    assert assoc._workers_needed(p, "reputation") == 2
    p.workers_out = {"reputation": 2}
    assert assoc._workers_needed(p, "reputation") == 2
    p.workers_out = {"reputation": 3}  # active worker left, but the task is blocked
    assert p.active_workers == 1
    assert assoc._workers_needed(p, "reputation") is None
    assert not assoc.feasible(state, 0, 2)


def test_second_placement_takes_two_workers():
    state = new()
    p = state.players[0]
    p.workers = 3
    p.workers_out = {"reputation": 1}
    go(state, 2)
    pick(state, ("reputation",))
    assert p.workers_out["reputation"] == 3
    assert p.active_workers == 0


def test_not_enough_workers_for_second_placement():
    state = new()
    p = state.players[0]
    p.workers = 2
    p.workers_out = {"reputation": 1}  # one active worker, but a second placement needs two
    assert not assoc.feasible(state, 0, 2)
    p.workers = 3
    assert assoc.feasible(state, 0, 2)


def test_running_out_of_workers_in_one_action():
    state = new()
    p = state.players[0]
    p.workers = 1
    p.money = 0
    go(state, 5, side2=True)
    assert ("reputation",) in keys(state)
    pick(state, ("reputation",))
    # The only worker is out and a donation is unaffordable: the action ends by itself.
    assert not in_action(state)
    assert p.active_workers == 0
    assert p.slots[0] == "association"


def test_workers_do_not_block_donation():
    state = new()
    p = state.players[0]
    p.workers = 1
    p.money = 25
    go(state, 5, side2=True)
    pick(state, ("reputation",))
    assert in_action(state)
    assert set(keys(state)) == {("donate",), ("done",)}


# ---- side I -----------------------------------------------------------------

def test_side_one_ends_after_one_task_and_card_moves_to_slot_one():
    state = new()
    p = state.players[0]
    go(state, 5)
    assert ("done",) not in keys(state)
    pick(state, ("reputation",))
    assert not in_action(state)
    assert p.reputation == 1 + T.TASK_REPUTATION_GAIN
    assert p.slots[0] == "association" and len(p.slots) == 5
    assert state.stack[-1].kind == "turn" and state.stack[-1].player == 1


# ---- side II ----------------------------------------------------------------

def test_side_two_several_different_tasks_within_budget():
    state = new()
    p = state.players[0]
    p.money = 0  # no donation
    go(state, 5, side2=True)
    pick(state, ("reputation",))
    assert in_action(state)
    ks = keys(state)
    assert ("reputation",) not in ks  # each task type once per action
    assert ("university", "hand") not in ks  # 4 > the 3 left
    assert ("partner_zoo", "africa") in ks and ("done",) in ks
    pick(state, ("partner_zoo", "africa"))
    assert not in_action(state)  # budget spent, nothing else possible
    assert p.partner_zoos == ["africa"] and p.reputation == 3
    assert p.workers_out == {"reputation": 1, "partner_zoo": 1}


def test_side_two_done_after_one_task():
    state = new()
    go(state, 4, side2=True)
    assert ("done",) not in keys(state) and ("donate",) not in keys(state)
    pick(state, ("university", "hand"))
    assert in_action(state)
    assert ("reputation",) not in keys(state)  # 4 spent, 0 left
    assert set(keys(state)) == {("donate",), ("done",)}
    pick(state, ("done",))
    assert not in_action(state)
    assert state.donations == 0


def test_side_two_budget_cannot_be_exceeded():
    state = new()
    go(state, 5, side2=True)
    pick(state, ("university", "hand"))
    assert all(k[0] in ("donate", "done") for k in keys(state))  # 1 left, cheapest task costs 2


def test_donation_once_per_action_and_ends_frame():
    state = new()
    p = state.players[0]
    go(state, 2, side2=True)
    pick(state, ("reputation",))
    money = p.money
    pick(state, ("donate",))
    assert p.money == money - 2 and p.conservation == 1 and state.donations == 1
    assert not in_action(state)


def test_donation_followed_by_more_tasks():
    state = new()
    p = state.players[0]
    go(state, 5, side2=True)
    pick(state, ("reputation",))
    pick(state, ("donate",))
    assert in_action(state)
    ks = keys(state)
    assert ("donate",) not in ks and ("done",) in ks and ("partner_zoo", "asia") in ks
    pick(state, ("partner_zoo", "asia"))
    assert not in_action(state) and p.conservation == 1


def test_donation_needs_a_task_first():
    state = new()
    go(state, 5, side2=True)
    assert ("donate",) not in keys(state)


def test_donation_unaffordable_not_offered():
    state = new()
    p = state.players[0]
    go(state, 4, side2=True)
    pick(state, ("university", "hand"))
    p.money = 1
    assert keys(state) == [("done",)]


def test_donation_cost_sequence_two_players_and_tail():
    state = new()
    p = state.players[0]
    expected = [2, 5, 7, 10, 12, 12, 12]
    for cost in expected:
        state.stack.clear()
        push(state, "turn", 0)
        state.current = 0
        p.workers_out = {}
        p.money, p.conservation, p.reputation = 100, 0, 1
        before = state.donations
        go(state, 2, side2=True)
        pick(state, ("reputation",))
        pick(state, ("donate",))
        resolve(state)
        assert p.money == 100 - cost
        assert state.donations == before + 1
    assert state.donations == 7


def test_side_one_has_no_donation():
    state = new()
    go(state, 2)
    pick(state, ("reputation",))
    assert state.donations == 0 and state.players[0].conservation == 0


# ---- partner zoos and universities --------------------------------------------

def test_partner_zoo_third_slot_needs_side_two():
    state = new()
    p = state.players[0]
    p.partner_zoos = ["africa", "asia"]
    state.partner_zoos_available = {"americas", "australia", "europe"}
    go(state, 3)
    assert not any(k[0] == "partner_zoo" for k in keys(state))

    state = new()
    p = state.players[0]
    p.partner_zoos = ["africa", "asia"]
    p.workers = 2
    state.partner_zoos_available = {"americas", "australia", "europe"}
    go(state, 3, side2=True)
    pick(state, ("partner_zoo", "europe"))
    assert p.partner_zoos == ["africa", "asia", "europe"]
    assert p.workers == 3  # slot 3 bonus
    assert "europe" not in state.partner_zoos_available


def test_partner_zoo_only_available_continents():
    state = new()
    p = state.players[0]
    p.partner_zoos = ["africa"]
    state.partner_zoos_available = {"asia", "africa"}
    go(state, 3)
    assert {k[1] for k in keys(state) if k[0] == "partner_zoo"} == {"asia"}


def test_university_reputation_and_slots():
    state = new()
    p = state.players[0]
    go(state, 4)
    assert {k[1] for k in keys(state) if k[0] == "university"} == set(T.UNIVERSITIES)
    pick(state, ("university", "hand"))
    assert p.universities == ["hand"] and p.reputation == 2  # +1 reputation
    assert p.hand_limit == T.HAND_LIMIT_UNIVERSITY

    state = new()
    p = state.players[0]
    go(state, 4)
    pick(state, ("university", "science_rep"))
    assert p.reputation == 3


# ---- projects ---------------------------------------------------------------

def test_support_base_project_conditions_and_rewards():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 2)
    p.conservation = 5
    set_projects(state, ["103"])
    go(state, 5)
    assert positions(state) == {3}  # 2 africa icons -> only the slot that needs 2
    assert {k[3] for k in keys(state) if k[0] == "support"} == set(range(7))
    pick(state, ("support", "103", 3, 2))  # token 2 gives 5 money
    assert not in_action(state)
    assert state.project_tokens["103"] == {3: 0}
    assert p.tokens[2] is False and p.tokens.count(False) == 1
    assert p.money == T.START_MONEY + 5
    assert p.conservation == 7
    assert p.workers_out == {"project": 1}


def test_support_threshold_per_slot():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 4)
    set_projects(state, ["103"])
    go(state, 5)
    assert positions(state) == {2, 3}

    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 5)
    set_projects(state, ["103"])
    go(state, 5)
    assert positions(state) == {1, 2, 3}

    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 1)
    set_projects(state, ["103"])
    assert "support" not in {k[0] for k in _task_keys(state, 5)}


def _task_keys(state, strength):
    return [o.key for o in assoc._task_options(state, 0, strength, [], False)]


def test_support_slot_taken_or_blocked():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 4)
    set_projects(state, ["103"])
    state.project_tokens["103"] = {3: "blocked"}
    go(state, 5)
    assert positions(state) == {2}

    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 4)
    set_projects(state, ["103"])
    state.project_tokens["103"] = {3: "blocked", 2: 1}
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]


def test_support_each_project_once_per_player():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 5)
    set_projects(state, ["103"])
    state.project_tokens["103"] = {1: 0}  # we already sit on slot 1
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]
    state.project_tokens["103"] = {1: 1}  # the other player does: we may still join
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {2, 3}


def test_support_needs_token_on_map():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 2)
    set_projects(state, ["103"])
    p.tokens = [False] * 7
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]
    p.tokens[4] = True
    assert {k[3] for k in _task_keys(state, 5) if k[0] == "support"} == {4}


def test_support_token_bonus_applied_with_follow_up_frame():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 2)
    p.conservation = 5
    set_projects(state, ["103"])
    hand = len(p.hand)
    go(state, 5)
    pick(state, ("support", "103", 3, 0))  # token 0: one card
    # The action ended before the gain; the card choice resolves on top of the turn end.
    assert not in_action(state)
    assert state.stack[-1].kind == "take_card"
    resolve_first = engine.legal_options(state)[0]
    engine.step(state, resolve_first)
    assert len(p.hand) == hand + 1
    assert state.stack[-1].kind == "turn"


def test_base_project_icon_conditions():
    # all-animals: distinct categories
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(single_cat("bird"), 2) + animals(single_cat("herbivore"), 1)
    set_projects(state, ["101"])  # slots need 5 / 4 / 3
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == set()  # 2 categories
    p.zoo_cards += animals(single_cat("predator"), 1)
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {3}  # 3 categories
    p.zoo_cards += animals(single_cat("reptile"), 1)
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {2, 3}  # 4 categories
    p.zoo_cards += animals(single_cat("primate"), 1)
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {1, 2, 3}

    # all-continents: partner zoos count too
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 1) + animals(one_continent("asia"), 1)
    p.partner_zoos = ["europe"]
    set_projects(state, ["102"])
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {3}

    # animal-size-2 (needs 8 / 5 / 2) and animal-size-4 (4 / 3 / 2)
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(lambda c: c["size"] <= 2, 2)
    set_projects(state, ["130"])
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {3}
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(lambda c: c["size"] >= 4, 3)
    set_projects(state, ["131"])
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {2, 3}
    # size 3 animals count for neither
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(lambda c: c["size"] == 3, 4)
    set_projects(state, ["130", "131"])
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]

    # science via universities
    state = new()
    p = state.players[0]
    p.universities = ["science2"]
    set_projects(state, ["132"])
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {3}


def test_breed_project_condition():
    bird = animals(lambda c: "bird" in c["tags"] and c["continents"][:1] == ["africa"], 1)
    state = new()
    p = state.players[0]
    set_projects(state, [], ["123"])
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]  # nothing in the zoo

    p.zoo_cards = bird
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]  # no partner zoo
    p.partner_zoos = ["europe"]
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]  # wrong continent
    p.partner_zoos = ["europe", "africa"]
    assert {k[2] for k in _task_keys(state, 5) if k[0] == "support"} == {1, 2, 3}

    # A predator in the zoo does not satisfy the bird program
    p.zoo_cards = animals(lambda c: "predator" in c["tags"] and "africa" in c["continents"], 1)
    assert not [k for k in _task_keys(state, 5) if k[0] == "support"]


def test_breed_project_rewards():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(lambda c: "bird" in c["tags"] and c["continents"][:1] == ["africa"], 1)
    p.partner_zoos = ["africa"]
    p.conservation = 5
    set_projects(state, [], ["123"])
    go(state, 5)
    pick(state, ("support", "123", 1, 2))
    assert p.conservation == 7 and p.reputation == 3
    assert state.project_tokens["123"] == {1: 0}


def test_play_project_from_hand():
    state = new()
    p = state.players[0]
    p.universities = ["science2"]
    p.conservation = 5
    p.hand = ["132", "401"]
    set_projects(state, [])
    go(state, 5)
    ks = keys(state)
    assert ("play_project", "132", 3, 2) in ks
    assert not any(k[0] == "play_project" and k[1] == "401" for k in ks)
    pick(state, ("play_project", "132", 3, 2))
    assert p.hand == ["401"]
    assert state.projects == ["132"]
    assert state.project_tokens["132"] == {3: 0}
    assert p.conservation == 7
    assert not in_action(state)


def test_play_project_needs_condition_met():
    state = new()
    p = state.players[0]
    p.hand = ["132"]  # no science
    set_projects(state, [])
    assert not [k for k in _task_keys(state, 5) if k[0] == "play_project"]


def test_play_project_overflow_discards_rightmost():
    state = new()
    p = state.players[0]
    p.universities = ["science2"]
    p.conservation = 5
    p.hand = ["132"]
    set_projects(state, [], ["129", "128"])
    state.project_tokens["128"] = {1: 1}
    assert T.PROJECTS_ABOVE_BOARD[2] == 2
    go(state, 5)
    pick(state, ("play_project", "132", 3, 2))
    assert state.projects == ["132", "129"]
    assert "128" not in state.project_tokens and "128" in state.discard
    assert set(state.project_tokens) == {"132", "129"}


def test_play_project_from_display_costs_folder_on_side_two():
    state = new()
    p = state.players[0]
    p.universities = ["science2"]
    p.reputation = 4  # folders 1-3
    p.conservation = 5
    state.display[2] = "132"
    set_projects(state, [])
    p.money = 3
    go(state, 5, side2=True)
    ks = keys(state)
    assert ("play_project_display", 2, 3, 2) in ks
    pick(state, ("play_project_display", 2, 3, 2))
    assert p.money == 0 + 5  # folder 3 cost 3 of 3 money; token 2 pays 5
    assert state.display[2] is None
    assert state.projects == ["132"] and state.project_tokens["132"] == {3: 0}


def test_display_play_needs_money_range_and_side_two():
    p_setup = lambda s: (setattr(s.players[0], "universities", ["science2"]), set_projects(s, []))
    # too poor for folder 3 (costs 3)
    state = new()
    p_setup(state)
    p = state.players[0]
    p.reputation, p.money = 4, 2
    state.display[2] = "132"
    p.upgraded.add("association")
    assert not [k for k in _task_keys_side(state, 5, True) if k[0] == "play_project_display"]
    # out of reputation range (folder 4 at reputation 4)
    state = new()
    p_setup(state)
    p = state.players[0]
    p.reputation, p.money = 4, 50
    state.display[3] = "132"
    assert not [k for k in _task_keys_side(state, 5, True) if k[0] == "play_project_display"]
    # side I never plays from the display
    state = new()
    p_setup(state)
    p = state.players[0]
    p.reputation, p.money = 4, 50
    state.display[2] = "132"
    assert not [k for k in _task_keys_side(state, 5, False) if k[0] == "play_project_display"]
    assert [k for k in _task_keys_side(state, 5, True) if k[0] == "play_project_display"]


def _task_keys_side(state, strength, side2):
    return [o.key for o in assoc._task_options(state, 0, strength, [], side2)]


def test_non_project_cards_in_hand_or_display_ignored():
    state = new()
    p = state.players[0]
    p.reputation, p.money = 4, 50
    p.hand = animals(lambda c: True, 2)
    state.display[0] = "201"  # sponsor
    set_projects(state, [])
    assert not [k for k in _task_keys_side(state, 5, True)
                if k[0] in ("play_project", "play_project_display", "support")]


def test_release_projects_offered_with_animal_keys():
    state = new()
    p = state.players[0]
    p.reputation, p.money = 4, 50
    p.zoo_cards = animals(one_continent("europe"), 6)
    p.partner_zoos = ["europe"]
    p.hand = ["113", "118"]
    state.display[0] = "114"
    set_projects(state, ["113"], ["119"])
    ks = _task_keys_side(state, 5, True)
    assert [k for k in ks if k[0] == "release" and k[1] == "113"]  # europe icon: on the board
    assert not [k for k in ks if k[0] == "release" and k[1] == "119"]  # bird project: no bird in the zoo
    assert not [k for k in ks if k[0] in ("support", "play_project", "play_project_display")]
    assert all(len(k) == 5 for k in ks if k[0].endswith("release") or "release" in k[0])
    assert [k for k in ks if k[0] == "play_release" and k[1] == "113"]
    assert not [k for k in _task_keys_side(state, 5, False) if k[0] == "play_release_display"]
    assert not [k for k in ks if k[0] == "play_release_display"]  # americas icon: none in the zoo


def test_feasible_with_project_only():
    state = new()
    p = state.players[0]
    p.zoo_cards = animals(one_continent("africa"), 2)
    set_projects(state, ["103"])
    p.workers_out = {"reputation": 3, "partner_zoo": 3, "university": 3}  # everything else blocked
    p.workers = 12  # test shortcut: plenty of active workers, those three task types still blocked
    assert assoc.feasible(state, 0, 5)
    assert not assoc.feasible(state, 0, 4)


def test_action_registered_and_turn_option_offered():
    state = new()
    p = state.players[0]
    p.slots = ["association", "animals", "build", "cards", "sponsors"]
    assert ("act", "association", 0) not in keys(state)  # strength 1 buys no task
    p.xtokens = 1
    assert ("act", "association", 1) in keys(state)
    p.slots = ["animals", "association", "build", "cards", "sponsors"]
    assert ("act", "association", 0) in keys(state)


def test_side_two_survives_follow_up_frame_from_a_task():
    state = new()
    p = state.players[0]
    p.partner_zoos = ["africa"]
    state.partner_zoos_available = {"asia", "europe"}
    go(state, 5, side2=True)
    pick(state, ("partner_zoo", "asia"))  # slot 2 bonus: an upgrade choice, on top of our frame
    assert state.stack[-1].kind == "upgrade"
    assert in_action(state)
    engine.step(state, ("upgrade", "animals"))
    assert state.stack[-1].kind == ACT
    assert ("reputation",) in keys(state) and ("done",) in keys(state)
    pick(state, ("done",))
    assert not in_action(state) and "animals" in p.upgraded


def test_side_fixed_at_start_even_if_upgraded_midway():
    state = new()
    p = state.players[0]
    p.partner_zoos = ["africa"]
    state.partner_zoos_available = {"asia"}
    go(state, 5)  # side I
    pick(state, ("partner_zoo", "asia"))
    engine.step(state, ("upgrade", "association"))  # the upgrade lands after the action ended
    assert not in_action(state)
