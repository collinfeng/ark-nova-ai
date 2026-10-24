"""Sponsor cards that change core rules, plus the helpers the action modules call.

A player "has" a sponsor when its id is in `player.zoo_cards`. The action modules
(animals, build, association) import this module and ask it questions; it never imports them
at module level (lazy imports inside functions) so there is no import cycle.

Card effects registered here (see effects.py for the registries):
    203 Veterinarian        project task value 4            -> task_value()           (association)
    215/218 Breeding *      2 tokens, 1 token = 1 extra icon on base projects, endgame
    217 Engineer            one extra identical building    -> has_engineer()         (build)
    219 Diversity Research. build on water/rock             -> ignores_terrain()      (hexmap, animals, ...)
    221 Archaeologist       border placement bonus twice    (AFTER_BUILD_HOOKS)
    224 Migration Recording release projects: +1 conservation, repeatable  (association)
    227 Waza Special Assign. small / large only             -> animal_allowed(), on_animal_played()
    228 Waza Small Program  extra small animal + display take              (animals)
    229/230 Expert in ...    animal cost reduction           -> animal_cost_reduction()
    253 Okapi Stable        tokens: play a sponsor on herbivore icons
    263 Waza Large Program  ignore 1 condition for large animals           -> requirements_ok()
"""
from . import cards, effects as E, tables as T
from .state import Option, pop, push, register_choice

VETERINARIAN, BREEDING = "203", ("215", "218")
ENGINEER, DIVERSITY, ARCHAEOLOGIST, MIGRATION = "217", "219", "221", "224"
WAZA_CHOICE, WAZA_SMALL, EXPERT_SMALL, EXPERT_LARGE, OKAPI, WAZA_LARGE = "227", "228", "229", "230", "253", "263"

VETERINARIAN_PROJECT_VALUE = 4
BREEDING_TOKENS = 2
OKAPI_TOKENS = 3
EXPERT_SMALL_DISCOUNT, EXPERT_LARGE_DISCOUNT = 3, 4
WAZA_APPEAL = {"small": 2, "large": 4}
TOKEN_FLAG = "token:"  # prefix of the extra key element for a Breeding token ("token:215")


def has(player, card_id):
    return card_id in player.zoo_cards


# ---- association -----------------------------------------------------------------------

def task_value(player, task):
    """Association value of a task for this player (Veterinarian makes projects cost 4)."""
    value = T.TASK_VALUE[task]
    if task == "project" and has(player, VETERINARIAN):
        value = min(value, VETERINARIAN_PROJECT_VALUE)
    return value


def breeding_cards(player):
    """Breeding Cooperation / Breeding Program cards that still hold a token."""
    return [cid for cid in BREEDING if has(player, cid) and player.card_tokens.get(cid, 0) > 0]


def spend_breeding_token(player, card_id):
    assert player.card_tokens.get(card_id, 0) > 0
    player.card_tokens[card_id] -= 1


def multi_support_release(player):
    """Migration Recording: release projects may be supported more than once."""
    return has(player, MIGRATION)


def release_bonus(state, p):
    """Extra conservation for supporting a release project (Migration Recording)."""
    if has(state.players[p], MIGRATION):
        E.gain(state, p, "conservation", 1)


def size_fits(spec, size):
    return size >= spec.get("min", 0) and size <= spec.get("max", 99)


def releasable(player, project, slot):
    """Animals in the zoo that can be released into this release-project slot."""
    spec = slot.get("animal_size") or {}
    found = []
    for cid in player.zoo_cards:
        c = cards.card(cid)
        if c["type"] == "animal" and project["icon"] in c.get("tags", []) and size_fits(spec, c["size"]):
            found.append(cid)
    return found


# ---- animals -------------------------------------------------------------------------

def waza_kind(player):
    """'small' or 'large' once Waza Special Assignment's choice is made, else None."""
    kind = player.card_tokens.get(WAZA_CHOICE)
    return kind if has(player, WAZA_CHOICE) and kind in WAZA_APPEAL else None


def animal_allowed(player, card_id):
    """Waza Special Assignment forbids playing animals of the other kind."""
    kind = waza_kind(player)
    if kind == "small":
        return not cards.is_large(card_id)
    if kind == "large":
        return not cards.is_small(card_id)
    return True


def animal_cost_reduction(player, card_id):
    reduction = 0
    if cards.is_small(card_id) and has(player, EXPERT_SMALL):
        reduction += EXPERT_SMALL_DISCOUNT
    if cards.is_large(card_id) and has(player, EXPERT_LARGE):
        reduction += EXPERT_LARGE_DISCOUNT
    return reduction


def requirements_ok(player, card_id, state=None):
    """Play conditions met, allowing Waza Large Animal Program to ignore one for a large animal and,
    with `state`, any map rule that lets a condition be ignored (Map 6 research institute)."""
    unmet = cards.unmet_requirements(player, card_id)
    if unmet == 0:
        return True
    allowance = 1 if has(player, WAZA_LARGE) and cards.is_large(card_id) else 0
    if state is not None:
        allowance += sum(hook(state, player, card_id) for hook in E.CONDITION_ALLOWANCE)
    return unmet <= allowance


def sponsor_level(state, p, card_id):
    """Level of a sponsor card for player p: its cost in money and the strength it needs (map rules
    such as Map 8 can lower it)."""
    return max(0, cards.card(card_id)["level"] + sum(hook(state, p, card_id) for hook in E.SPONSOR_LEVEL_DELTA))


def on_animal_played(state, p, card_id):
    """Waza Special Assignment: appeal for each animal of the chosen kind played."""
    player = state.players[p]
    kind = waza_kind(player)
    if kind == "small" and cards.is_small(card_id) or kind == "large" and cards.is_large(card_id):
        E.gain(state, p, "appeal", WAZA_APPEAL[kind])


def has_small_program(player):
    return has(player, WAZA_SMALL)


# ---- building ------------------------------------------------------------------------

def ignores_terrain(player):
    """Diversity Researcher: may build on water and rock, and ignores rock/water requirements
    (animal enclosures and unique buildings). Pass as `any_terrain` to Zoo.legal_placements."""
    return has(player, DIVERSITY)


def has_engineer(player):
    return has(player, ENGINEER)


ENGINEER_KINDS = ("kiosk", "pavilion", "enclosure")  # no special enclosures


# ---- immediate effects and passives --------------------------------------------------------

@E.register(E.IMMEDIATE, *BREEDING)
def _breeding_tokens(state, p):
    for cid in BREEDING:
        if has(state.players[p], cid):
            state.players[p].card_tokens.setdefault(cid, BREEDING_TOKENS)


@E.register(E.ENDGAME, *BREEDING)
def _breeding_endgame(state, p):
    if state.players[p].projects_supported >= 5:
        E.score(state, p, "conservation", 1)


@E.register(E.IMMEDIATE, DIVERSITY)
def _diversity_immediate(state, p):
    icons = cards.icons(state.players[p])
    E.gain(state, p, "money", 2 * (icons.get("water", 0) + icons.get("rock", 0)))


def _archaeologist(state, p, building):
    """Each border-space placement bonus covered by the building is gained once more."""
    player = state.players[p]
    if not has(player, ARCHAEOLOGIST):
        return
    mapdef = player.zoo.mapdef
    for c in sorted(building.cells):
        bonus = mapdef.cells[c].bonus
        if bonus and mapdef.is_border(c):
            E.apply_effects(state, p, T.PLACEMENT_BONUS[bonus])


if _archaeologist not in E.AFTER_BUILD_HOOKS:
    E.AFTER_BUILD_HOOKS.append(_archaeologist)


@E.register(E.IMMEDIATE, WAZA_LARGE)
def _waza_large_immediate(state, p):
    push(state, "free_build", p, kinds=[("enclosure", 5)])


# 227 Waza Special Assignment

@E.register(E.IMMEDIATE, WAZA_CHOICE)
def _waza_choice_immediate(state, p):
    push(state, "waza_kind", p)


def _waza_options(state, frame):
    return [Option(("kind", "small"), "Small animals (size 2 or less)"),
            Option(("kind", "large"), "Large animals (size 4 or more)")]


def reveal_first(state, p, kind):
    """Reveal cards from the deck until the first animal of the kind; it goes to the hand, the rest
    to the discard pile. The discard pile is reshuffled at most once; returns the card or None."""
    return reveal_until(state, p, cards.is_small if kind == "small" else cards.is_large)


def reveal_until(state, p, test):
    """Reveal cards until test(card id) holds; that card goes to p's hand, the others are discarded."""
    revealed, found, reshuffled = [], None, False
    while True:
        if not state.deck:
            if reshuffled or not state.discard:
                break
            state.deck, state.discard = state.discard, []
            state.rng.shuffle(state.deck)
            reshuffled = True
        card_id = state.deck.pop()
        if test(card_id):
            found = card_id
            break
        revealed.append(card_id)
    state.discard.extend(revealed)
    if found is not None:
        E.to_hand(state, p, found, True)  # the card was revealed to both players
    return found


def _waza_apply(state, frame, option):
    pop(state, frame)
    kind = option.key[1]
    state.players[frame.player].card_tokens[WAZA_CHOICE] = kind
    reveal_first(state, frame.player, kind)


register_choice("waza_kind", _waza_options, _waza_apply)


# 253 Okapi Stable: the token is removed when the player says yes (before the sponsor is chosen).

def _okapi_playable(state, p):
    from .actions import sponsors
    player = state.players[p]
    return [c for c in player.hand
            if sponsors.can_play(state, p, c) and player.money >= sponsor_level(state, p, c)]


@E.register(E.IMMEDIATE, OKAPI)
def _okapi_immediate(state, p):
    state.players[p].card_tokens.setdefault(OKAPI, OKAPI_TOKENS)


@E.register(E.ICON_TRIGGERS, OKAPI)
def _okapi_trigger(state, owner, player, icons, new_icons):
    # The card's own icon arrives before its immediate effect runs, hence setdefault here too.
    if owner != player or not icons.get("herbivore"):
        return
    me = state.players[owner]
    if me.card_tokens.setdefault(OKAPI, OKAPI_TOKENS) > 0 and _okapi_playable(state, owner):
        push(state, "okapi_stable", owner)


def _okapi_options(state, frame):
    options = []
    if state.players[frame.player].card_tokens.get(OKAPI, 0) > 0 and _okapi_playable(state, frame.player):
        options.append(Option(("yes",), "Remove a token and play a sponsor card for its level"))
    return options + [Option(("no",), "Do not use Okapi Stable")]


def _okapi_apply(state, frame, option):
    pop(state, frame)
    if option.key[0] == "yes":
        state.players[frame.player].card_tokens[OKAPI] -= 1
        push(state, "paid_sponsor", frame.player)


register_choice("okapi_stable", _okapi_options, _okapi_apply)
