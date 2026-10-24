"""Association action: reputation, partner zoos, universities, conservation projects and donations.

Side I performs one task. Side II performs several tasks of different types whose values sum
to at most the strength, then may donate once. The side is fixed when the action starts, so
an upgrade gained midway (a partner zoo or university bonus) does not change the action.

Release into the Wild projects: supporting a slot releases one animal from the zoo (icon of the
project, size within the slot's limits). Option keys carry the animal as a fifth element:
("release", project, position, token, animal), ("play_release", card, ...), ("play_release_display",
index, ...). A base project slot reached with a Breeding token carries "token:<card id>" there.
"""
from .. import cards, effects as E
from .. import sponsor_rules as SR
from .. import tables as T
from . import animals
from ..state import Option, pop, push, register_action, register_choice

PLAYABLE_CATEGORIES = ("base", "normal", "breed", "release")  # base: gained through Assertion or Dominance
SUPPORTABLE_CATEGORIES = ("base", "normal", "breed", "release")


def _workers_needed(player, task):
    """Workers the task would take, or None when it is blocked."""
    out = player.workers_out.get(task, 0)
    if out == 0:
        need = 1
    elif out < 3:
        need = 2
    else:
        return None
    return need if player.active_workers >= need else None


# ---- projects ---------------------------------------------------------------

def _count(player, icon):
    if icon == "all-animals":
        return len(set(T.ANIMAL_CATEGORIES) & set(cards.icons(player)))
    if icon == "all-continents":
        return len(set(T.CONTINENTS) & set(cards.icons(player)))
    if icon in ("animal-size-2", "animal-size-4"):
        sizes = [cards.card(c).get("size") for c in player.zoo_cards if cards.card(c)["type"] == "animal"]
        sizes = [s for s in sizes if s is not None]
        return sum(1 for s in sizes if (s <= 2 if icon == "animal-size-2" else s >= 4))
    return cards.icons(player).get(icon, 0)


def _breed_ok(player, icon):
    for cid in player.zoo_cards:
        c = cards.card(cid)
        if c["type"] == "animal" and icon in c.get("tags", []) \
                and any(k in player.partner_zoos for k in cards.animal_continents(cid)):
            return True
    return False


def _slot_extras(player, project, slot):
    """The ways the player can fill this slot, as the optional fifth key element: None (conditions
    met), an animal to release, or "token:<id>" (a Breeding token supplies the missing icon).
    Empty when the slot is out of reach."""
    category = project["category"]
    if category == "release":
        return SR.releasable(player, project, slot)
    if category == "breed":
        return [None] if _breed_ok(player, project["icon"]) else []
    if category in ("base", "normal") and slot["required"] is not None:
        count = _count(player, project["icon"])
        if count >= slot["required"]:
            return [None]
        if category == "base" and count + 1 >= slot["required"]:
            return [SR.TOKEN_FLAG + cid for cid in SR.breeding_cards(player)]
    return []


def _support_choices(state, p, project_id):
    """(position, token_index, extra) triples the player could take on this project right now."""
    player = state.players[p]
    taken = state.project_tokens.get(project_id, {})
    project = cards.card(project_id)
    if project["category"] not in SUPPORTABLE_CATEGORIES:
        return []
    if p in taken.values() and not (project["category"] == "release" and SR.multi_support_release(player)):
        return []
    tokens = [i for i, on_map in enumerate(player.tokens) if on_map]
    return [(slot["position"], i, extra) for slot in project["slots"] if slot["position"] not in taken
            for extra in _slot_extras(player, project, slot) for i in tokens]


def _extra_text(extra):
    """The part of a support option's label that tells options on the same slot apart."""
    if extra is None:
        return ""
    if isinstance(extra, str) and extra.startswith("token:"):
        return f", using a token from {cards.card(extra[6:])['name']}"
    return f", release {cards.card(extra)['name']}"


def _key(prefix, ref, choice):
    position, token, extra = choice
    return (prefix, ref, position, token) + (() if extra is None else (extra,))


def _project_options(state, p, side2):
    player = state.players[p]
    options = []
    for pid in state.base_projects + state.projects:
        prefix = "release" if cards.card(pid)["category"] == "release" else "support"
        for choice in _support_choices(state, p, pid):
            options.append(Option(_key(prefix, pid, choice),
                                  f"Support {cards.card(pid)['name']} (slot {choice[0]}, token {choice[1]}"
                                  f"{_extra_text(choice[2])})"))
    for cid in player.hand:
        if cards.card(cid)["type"] == "project" and cards.card(cid)["category"] in PLAYABLE_CATEGORIES:
            prefix = "play_release" if cards.card(cid)["category"] == "release" else "play_project"
            for choice in _support_choices(state, p, cid):
                options.append(Option(_key(prefix, cid, choice),
                                      f"Play {cards.card(cid)['name']} and support it "
                                      f"(slot {choice[0]}, token {choice[1]}{_extra_text(choice[2])})"))
    if side2:
        for index in E.cards_in_range(state, p):
            cid = state.display[index]
            if cards.card(cid)["type"] != "project" or cards.card(cid)["category"] not in PLAYABLE_CATEGORIES \
                    or player.money < index + 1:
                continue
            prefix = "play_release_display" if cards.card(cid)["category"] == "release" else "play_project_display"
            for choice in _support_choices(state, p, cid):
                options.append(Option(_key(prefix, index, choice),
                                      f"Play {cards.card(cid)['name']} from folder {index + 1} and support it "
                                      f"(slot {choice[0]}, token {choice[1]}{_extra_text(choice[2])})"))
    return options


# ---- tasks ------------------------------------------------------------------

def _task_options(state, p, remaining, used, side2):
    """All options for starting a task now (donation and done are handled by the frame)."""
    player = state.players[p]
    options = []
    for task in T.TASK_VALUE:
        if task in used or SR.task_value(player, task) > remaining or _workers_needed(player, task) is None:
            continue
        if task == "reputation":
            options.append(Option(("reputation",), f"Reputation +{T.TASK_REPUTATION_GAIN}"))
        elif task == "partner_zoo":
            options += [Option(("partner_zoo", c), f"Partner zoo: {c}") for c in T.CONTINENTS
                        if E.can_take_partner_zoo(state, p, c)]
        elif task == "university":
            options += [Option(("university", u), f"University: {u}") for u in T.UNIVERSITIES
                        if E.can_take_university(state, p, u)]
        else:
            options += _project_options(state, p, side2)
    return options


PROJECT_KEYS = ("support", "play_project", "play_project_display",
                "release", "play_release", "play_release_display")


def _task_of(key):
    kind = key[0]
    return "project" if kind in PROJECT_KEYS else kind


def _donation_cost(state):
    costs = T.DONATION_COSTS[state.n]
    return costs[state.donations] if state.donations < len(costs) else T.DONATION_FINAL_COST


def _can_donate(state, p, d):
    return d["side2"] and d["used"] and not d["donated"] and state.players[p].money >= _donation_cost(state)


def _anything_possible(state, p, d):
    return bool(_task_options(state, p, d["remaining"], d["used"], d["side2"])) or _can_donate(state, p, d)


def feasible(state, p, strength):
    return bool(_task_options(state, p, strength, [], E.is_upgraded(state, p, "association")))


def start(state, p, strength):
    push(state, "act_association", p, strength=strength, remaining=strength, used=[], donated=False,
         side2=E.is_upgraded(state, p, "association"))


def _options(state, frame):
    d = frame.data
    p = frame.player
    options = _task_options(state, p, d["remaining"], d["used"], d["side2"])
    if _can_donate(state, p, d):
        options.append(Option(("donate",), f"Donate {_donation_cost(state)} money for 1 conservation"))
    if d["used"]:
        options.append(Option(("done",), "Finish"))
    return options


def _apply(state, frame, option):
    d = frame.data
    p = frame.player
    player = state.players[p]
    key = option.key
    kind = key[0]

    if kind == "done":
        pop(state, frame)
        return

    if kind == "donate":
        player.money -= _donation_cost(state)
        state.donations += 1
        d["donated"] = True

        def effects():
            E.gain(state, p, "conservation", 1)
    else:
        task = _task_of(key)
        player.workers_out[task] = player.workers_out.get(task, 0) + _workers_needed(player, task)
        d["remaining"] -= SR.task_value(player, task)
        d["used"].append(task)
        effects = _task_effects(state, p, key)

    if not d["side2"]:
        pop(state, frame)  # the final gains may push frames of their own
        effects()
        return
    effects()
    # Gains may have pushed frames; only end here when ours is still on top and nothing is left to do.
    if state.stack and state.stack[-1] is frame and not _anything_possible(state, p, d):
        pop(state, frame)


def _task_effects(state, p, key):
    kind = key[0]
    if kind == "reputation":
        return lambda: E.gain(state, p, "reputation", T.TASK_REPUTATION_GAIN)
    if kind == "partner_zoo":
        return lambda: E.take_partner_zoo(state, p, key[1])
    if kind == "university":
        return lambda: E.take_university(state, p, key[1])
    player = state.players[p]
    played = kind in ("play_project", "play_release", "play_project_display", "play_release_display")
    if kind in ("support", "release"):
        project_id = key[1]
    elif kind in ("play_project", "play_release"):
        project_id = key[1]
        player.hand.remove(project_id)
        _put_project_in_play(state, project_id)
    else:  # play_*_display
        player.money -= key[1] + 1
        project_id = E.take_from_display(state, key[1])
        _put_project_in_play(state, project_id)
    position, token = key[2], key[3]
    extra = key[4] if len(key) > 4 else None
    project = cards.card(project_id)
    slot = next(s for s in project["slots"] if s["position"] == position)
    if extra is not None and extra.startswith(SR.TOKEN_FLAG):
        SR.spend_breeding_token(player, extra[len(SR.TOKEN_FLAG):])
        extra = None

    def support():
        for reward, amount in project.get("play_bonus", []) if played else []:
            E.gain(state, p, reward, amount)
        if extra is not None:
            animals.release_animal(state, p, extra)
        state.project_tokens[project_id][position] = p
        E.take_map_token(state, p, token)
        for r in slot["rewards"]:
            E.gain(state, p, r["reward"], r["amount"])
        if project["category"] == "release":
            SR.release_bonus(state, p)
    return support


def _put_project_in_play(state, project_id):
    state.projects.insert(0, project_id)
    state.project_tokens[project_id] = {}
    while len(state.projects) > T.PROJECTS_ABOVE_BOARD[state.n]:
        gone = state.projects.pop()
        state.project_tokens.pop(gone, None)
        state.discard.append(gone)


register_action("association", feasible, start)
register_choice("act_association", _options, _apply)
