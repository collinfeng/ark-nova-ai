"""Shared game effects: gains, track bonuses, the display, and placing buildings.

Action modules and card effects should go through these helpers so that track
bonuses and follow-up choices are triggered consistently. Helpers that need a
player decision push a choice frame; it resolves before the caller's frame continues.
"""
from . import cards, tables as T
from .state import Option, log, note, pop, push, register_choice, under


# ---- deck and display -------------------------------------------------------

def draw_from_deck(state):
    if not state.deck:
        state.deck, state.discard = state.discard, []
        state.rng.shuffle(state.deck)
    return state.deck.pop() if state.deck else None


def to_hand(state, p, card, public):
    """Put a card into player p's hand; `public` cards are also noted in public_hand (once)."""
    player = state.players[p]
    player.hand.append(card)
    if public and card not in player.public_hand:
        player.public_hand.append(card)


def cards_in_range(state, p):
    """Display indices (folder - 1) the player may take from by reputation."""
    folders = T.reputation_folders(state.players[p].reputation)
    return [i for i in range(folders) if state.display[i] is not None]


def take_from_display(state, index):
    card_id, state.display[index] = state.display[index], None
    return card_id


def refill_display(state):
    kept = [c for c in state.display if c is not None]
    while len(kept) < T.DISPLAY_SIZE:
        card_id = draw_from_deck(state)
        if card_id is None:
            break
        kept.append(card_id)
    state.display = kept + [None] * (T.DISPLAY_SIZE - len(kept))


def advance_break(state, p, steps):
    """Move the break token; the player who reaches the end triggers the break and gains an X-token."""
    if state.break_by is not None or steps <= 0:
        return
    state.break_pos = min(state.break_pos + steps, T.BREAK_TRACK[state.n])
    if state.break_pos >= T.BREAK_TRACK[state.n]:
        state.break_by = p
        log(state, f"P{p} triggers a break")
        note(state, p, "break_triggered")
        under(state, ("break",), gain, state, p, "xtoken", 1)


def is_upgraded(state, p, action):
    """Side II of the action card in use; a borrowed card (Hypnosis) uses its owner's side."""
    if state.borrowed and state.borrowed[0] == action:
        return state.borrowed[1]
    return action in state.players[p].upgraded


# ---- action card tokens -------------------------------------------------

IMMUNITY_CARDS = {"225"}  # Quarantine Lab
INTERACTIVE_MIN_APPEAL = 5
VENOM_COST = 2
CONSTRICTION_PENALTY = 2


def affected(state, q):
    """Whether Venom, Constriction, Hypnosis and Pilfering can target player q."""
    player = state.players[q]
    return player.appeal >= INTERACTIVE_MIN_APPEAL and not IMMUNITY_CARDS & set(player.zoo_cards)


def tokens_on(state, p, action):
    return state.players[p].action_tokens.get(action, [])


def add_action_token(state, p, action, token):
    """Put a token on an action card. Venom and Constriction: at most one of each per card."""
    held = state.players[p].action_tokens.setdefault(action, [])
    if token != "multiplier" and token in held:
        return False
    held.append(token)
    return True


def remove_action_token(state, p, action, token):
    held = state.players[p].action_tokens.get(action, [])
    if token in held:
        held.remove(token)
    if not held:
        state.players[p].action_tokens.pop(action, None)


def has_venom(state, p):
    return any("venom" in held for held in state.players[p].action_tokens.values())


# ---- card effect registries ----------------------------------------------
# Sponsor (and final scoring) card effects register here by card id.

ICON_TRIGGERS = {}  # card id -> fn(state, owner, player, icons, new_icons): icons were played into player's zoo
IMMEDIATE = {}      # card id -> fn(state, p): when the card is played
INCOME = {}         # card id -> fn(state, p): in every break
BREAK_INCOME_HOOKS = []  # fn(state, p): extra income in every break (map rules)
CONDITION_ALLOWANCE = []  # fn(state, player, card_id) -> int: animal conditions that may be ignored (map rules)
SPONSOR_LEVEL_DELTA = []  # fn(state, p, card_id) -> int: change to a sponsor's level (map rules)
ENDGAME = {}        # card id -> fn(state, p): at final scoring; use score(), not gain()


def register(table, *card_ids):
    def wrap(fn):
        for card_id in card_ids:
            table[card_id] = fn
        return fn
    return wrap


def icons_played(state, p, icons, before):
    """Announce icons added to player p's zoo. `before` is that zoo's icon count beforehand."""
    if not icons:
        return
    new_icons = [i for i in icons if not before.get(i)]
    for step in range(state.n):
        owner = (p + step) % state.n
        for card_id in list(state.players[owner].zoo_cards):
            trigger = ICON_TRIGGERS.get(card_id)
            if trigger:
                under(state, ("card", card_id), trigger, state, owner, p, icons, new_icons)


def score(state, p, kind, amount):
    """Final-scoring gain: no track bonuses, no follow-up choices."""
    player = state.players[p]
    if kind == "conservation":
        player.conservation += amount
    elif kind == "appeal":
        player.appeal += amount
    else:
        raise ValueError(kind)


# ---- gains ------------------------------------------------------------------

def apply_effects(state, p, effects):
    for kind, amount in effects:
        gain(state, p, kind, amount)


def gain(state, p, kind, amount=1):
    """Apply one effect to player p. Unknown kinds raise, so typos surface in tests."""
    player = state.players[p]
    if amount <= 0:
        return
    if state.ledger is not None:
        state.ledger.append(("gain", p, kind, amount, state.causes[-1] if state.causes else None))
    if kind == "money":
        player.money += amount
    elif kind == "appeal":
        player.appeal += amount
    elif kind == "xtoken":
        player.xtokens = min(T.MAX_XTOKENS, player.xtokens + amount)
    elif kind == "conservation":
        _gain_conservation(state, p, amount)
    elif kind == "reputation":
        _gain_reputation(state, p, amount)
    elif kind == "worker":
        for _ in range(amount):
            if player.workers < T.MAX_WORKERS:
                player.workers += 1
                if player.workers == T.MAX_WORKERS:
                    apply_effects(state, p, state.map["last_worker"])
    elif kind == "upgrade":
        for _ in range(amount):
            push(state, "upgrade", p)
    elif kind == "card":
        for _ in range(amount):
            push(state, "take_card", p)
    elif kind == "clever":
        for _ in range(amount):
            push(state, "clever", p)
    elif kind == "enclosure":
        push(state, "free_build", p, kinds=[("enclosure", amount)])
    elif kind == "kiosk":  # map placement bonus: a free kiosk
        for _ in range(amount):
            push(state, "free_build", p, kinds=[("kiosk", 1)])
    elif kind == "special_enclosure":  # Map 5: a free reptile house or aviary, even with Build not upgraded
        push(state, "free_build", p, kinds=[("reptile_house", 5), ("aviary", 5)])
    elif kind == "multiplier":
        push(state, "place_multiplier", p)
    elif kind == "partner_zoo":
        push(state, "gain_partner_zoo", p)
    elif kind == "university":
        push(state, "gain_university", p)
    elif kind == "sponsor_for_money":
        push(state, "paid_sponsor", p)
    else:
        raise ValueError(f"unknown effect {kind!r}")


def _gain_conservation(state, p, amount):
    player = state.players[p]
    old, player.conservation = player.conservation, player.conservation + amount
    new = player.conservation

    def crossed(space):
        return old < space <= new

    for space in (*T.CONSERVATION_TILE_SPACES, T.CONSERVATION_UPGRADE_OR_WORKER, T.CONSERVATION_FINAL_CARD_DISCARD):
        if crossed(space):
            note(state, p, "conservation_stop", space)
    if crossed(T.CONSERVATION_FINAL_CARD_DISCARD) and not state.final_card_discarded:
        push_final_card_discards(state)
    for space in reversed(T.CONSERVATION_TILE_SPACES):
        if crossed(space):
            push(state, "conservation_tile", p, space=space)
    if crossed(T.CONSERVATION_UPGRADE_OR_WORKER):
        push(state, "upgrade_or_worker", p)


def push_final_card_discards(state):
    state.final_card_discarded = True
    for q in reversed(range(state.n)):
        if len(state.players[q].final_cards) > 1:
            push(state, "discard_final", q)


def _gain_reputation(state, p, amount):
    player = state.players[p]
    for _ in range(amount):
        if player.reputation >= T.REPUTATION_MAX:
            player.appeal += 1
            continue
        if player.reputation >= T.REPUTATION_CAP_WITHOUT_CARDS_II and "cards" not in player.upgraded:
            break
        player.reputation += 1
        bonus = T.REPUTATION_BONUS.get(player.reputation)
        if bonus:
            under(state, ("track", "reputation", player.reputation), gain, state, p, bonus, 1)


def take_map_token(state, p, index):
    """Remove a left-edge token (when supporting a project) and gain its bonus."""
    player = state.players[p]
    assert player.tokens[index]
    player.tokens[index] = False
    apply_effects(state, p, state.map["tokens"][index][0])


def token_income(state, p):
    """Break income from activated repeating left-edge bonuses."""
    for on_map, (effects, repeats) in zip(state.players[p].tokens, state.map["tokens"]):
        if repeats and not on_map:
            apply_effects(state, p, effects)


def can_take_partner_zoo(state, p, continent):
    player = state.players[p]
    slot = len(player.partner_zoos)
    return (continent in state.partner_zoos_available and continent not in player.partner_zoos
            and slot < T.MAX_PARTNER_ZOOS and (slot < 2 or "association" in player.upgraded))


def take_partner_zoo(state, p, continent):
    player = state.players[p]
    slot = len(player.partner_zoos)
    before = cards.icons(player)
    player.partner_zoos.append(continent)
    state.partner_zoos_available.discard(continent)
    icons_played(state, p, {continent: 1}, before)
    apply_effects(state, p, state.map["partner_zoo_slots"][slot])


def can_take_university(state, p, university):
    player = state.players[p]
    return (university in state.universities_available and university not in player.universities
            and len(player.universities) < len(state.map["university_slots"]))


def take_university(state, p, university):
    player = state.players[p]
    slot = len(player.universities)
    before = cards.icons(player)
    player.universities.append(university)
    state.universities_available.discard(university)
    science = {"science2": 2, "science_rep": 1}.get(university, 0)
    icons_played(state, p, {"science": science} if science else {}, before)
    apply_effects(state, p, state.map["university_slots"][slot])
    gain(state, p, "reputation", {"hand": 1, "science_rep": 2}.get(university, 0))


# ---- buildings --------------------------------------------------------------

AFTER_BUILD_HOOKS = []  # fn(state, player_idx, building); may push choice frames


def place_building(state, p, kind, size, cells, name=None):
    """Put a building on the map (no payment) and resolve everything placement triggers."""
    player = state.players[p]
    building, bonuses = player.zoo.place(kind, size, cells, name=name)
    for hook in reversed(AFTER_BUILD_HOOKS):
        hook(state, p, building)
    if kind == "pavilion":
        under(state, ("build", "pavilion"), gain, state, p, "appeal", 1)
    if not player.full_cover_scored and player.zoo.is_fully_covered():
        player.full_cover_scored = True
        under(state, ("build", "cover"), gain, state, p, "appeal", T.FULL_COVER_APPEAL)
    for bonus in reversed(bonuses):
        under(state, ("placement", bonus), apply_effects, state, p, T.PLACEMENT_BONUS[bonus])
    return building


def cells_key(cells):
    return tuple(sorted(cells))


# ---- choice frames ----------------------------------------------------------

SKIP = Option(("skip",), "Skip")


def _upgrade_options(state, frame):
    player = state.players[frame.player]
    return [Option(("upgrade", a), f"Upgrade {a}") for a in T.ACTIONS if a not in player.upgraded] or [SKIP]


def _upgrade_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "upgrade":
        state.players[frame.player].upgraded.add(option.key[1])


def _upgrade_or_worker_options(state, frame):
    player = state.players[frame.player]
    options = _upgrade_options(state, frame)
    if player.workers < T.MAX_WORKERS:
        options = [o for o in options if o is not SKIP] + [Option(("worker",), "Hire an association worker")]
    return options


def _upgrade_or_worker_apply(state, frame, option):
    if option.key[0] == "worker":
        pop(state, frame)
        gain(state, frame.player, "worker", 1)
    else:
        _upgrade_apply(state, frame, option)


def _tile_options(state, frame):
    tiles = state.bonus_tiles.get(frame.data["space"], [])
    return [Option(("money",), f"Take {T.CONSERVATION_TILE_MONEY} money")] + [
        Option(("tile", t), f"Take bonus tile {t}") for t in tiles]


def _tile_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "money":
        gain(state, frame.player, "money", T.CONSERVATION_TILE_MONEY)
    else:
        state.bonus_tiles[frame.data["space"]].remove(option.key[1])
        apply_effects(state, frame.player, T.BONUS_TILES[option.key[1]])


def _take_card_options(state, frame):
    options = [Option(("deck",), "Draw from the deck")] if state.deck or state.discard else []
    options += [Option(("display", i), f"Take folder {i + 1}") for i in cards_in_range(state, frame.player)]
    return options or [SKIP]


def _take_card_apply(state, frame, option):
    pop(state, frame)
    player = state.players[frame.player]
    if option.key[0] == "deck":
        to_hand(state, frame.player, draw_from_deck(state), False)  # face down from the deck
    elif option.key[0] == "display":
        to_hand(state, frame.player, take_from_display(state, option.key[1]), True)  # face-up display
        # Outside a turn (break income) the display is refilled straight away.
        if not state.turn:
            refill_display(state)


def _clever_options(state, frame):
    slots = state.players[frame.player].slots
    return [Option(("clever", a), f"Move {a} to slot 1") for a in slots[1:]] + [SKIP]


def _clever_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "clever":
        slots = state.players[frame.player].slots
        slots.remove(option.key[1])
        slots.insert(0, option.key[1])


def _free_build_options(state, frame):
    player = state.players[frame.player]
    options = []
    for kind, size in frame.data["kinds"]:
        # Diversity Researcher (219) lets its owner build on water and rock.
        for c in player.zoo.legal_placements(kind, size, build2="build" in player.upgraded,
                                             any_terrain="219" in player.zoo_cards):
            options.append(Option(("place", kind, size, cells_key(c)), f"Build {kind} at {cells_key(c)}"))
    return options + [SKIP]


def _free_build_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "place":
        _, kind, size, cells = option.key
        place_building(state, frame.player, kind, size, frozenset(cells))


def _multiplier_options(state, frame):
    return [Option(("multiplier", a), f"Put the x2 token on {a}") for a in frame.data.get("actions", T.ACTIONS)]


def _multiplier_apply(state, frame, option):
    pop(state, frame)
    add_action_token(state, frame.player, option.key[1], "multiplier")


def _partner_zoo_options(state, frame):
    return [Option(("partner_zoo", c), f"Partner zoo: {c}") for c in T.CONTINENTS
            if can_take_partner_zoo(state, frame.player, c)] or [SKIP]


def _partner_zoo_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "partner_zoo":
        take_partner_zoo(state, frame.player, option.key[1])


def _university_options(state, frame):
    return [Option(("university", u), f"University: {u}") for u in T.UNIVERSITIES
            if can_take_university(state, frame.player, u)] or [SKIP]


def _university_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "university":
        take_university(state, frame.player, option.key[1])


def _discard_final_options(state, frame):
    return [Option(("discard_final", c), f"Discard final scoring card {c}")
            for c in state.players[frame.player].final_cards]


def _discard_final_apply(state, frame, option):
    pop(state, frame)
    state.players[frame.player].final_cards.remove(option.key[1])
    state.final_deck.insert(0, option.key[1])


def _discard_hand_options(state, frame):
    return [Option(("discard", c), f"Discard {c}") for c in state.players[frame.player].hand]


def _discard_hand_apply(state, frame, option):
    """Discard cards until `count` have been discarded or the hand is down to `limit`."""
    player = state.players[frame.player]
    player.hand.remove(option.key[1])
    state.discard.append(option.key[1])
    data = frame.data
    data["count"] = data.get("count", 1) - 1
    limit = data.get("limit")
    if (limit is not None and len(player.hand) <= limit) or (limit is None and data["count"] <= 0) \
            or not player.hand:
        pop(state, frame)


register_choice("upgrade", _upgrade_options, _upgrade_apply)
register_choice("upgrade_or_worker", _upgrade_or_worker_options, _upgrade_or_worker_apply)
register_choice("conservation_tile", _tile_options, _tile_apply)
register_choice("take_card", _take_card_options, _take_card_apply)
register_choice("clever", _clever_options, _clever_apply)
register_choice("free_build", _free_build_options, _free_build_apply)
register_choice("place_multiplier", _multiplier_options, _multiplier_apply)
register_choice("gain_partner_zoo", _partner_zoo_options, _partner_zoo_apply)
register_choice("gain_university", _university_options, _university_apply)
register_choice("discard_final", _discard_final_options, _discard_final_apply)
register_choice("discard_hand", _discard_hand_options, _discard_hand_apply)
