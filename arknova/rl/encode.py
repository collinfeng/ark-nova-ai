"""Turn a pending decision into arrays for a network: what the deciding player may see, and one
row per legal option. Two players only. Nothing hidden from the deciding player is read: not the
deck order, the other hand, or the other player's final scoring cards.

Version 3 (2026-10-17) adds to version 2:
- the board: per cell its terrain, Build II flag, placement bonus and special-site membership, and which
  map is played, so one network can play every map;
- the opponent's known hand cards (cards the deciding player saw enter it), a summary of the discard pile
  (card types and icons), and the opponent's last main action;
- per option, the slot of each of its cards in the card sets, so the network can use that card's
  representation in context (attention over the sets, in the model);
- optional one-step look-ahead per option (`observe(..., lookahead=True)`): the change in the deciding player's
  appeal, conservation, money, reputation, hand size, X-tokens and points, the opponent's points, and
  whether the decision stays with the same player, from applying the option to a copy of the state. The
  copy's deck is reshuffled first, so the look-ahead never reveals the deck order.
- privileged inputs for the value network only (`observe(..., privileged=True)`, zero otherwise): the
  opponent's whole hand and final scoring cards, the next deck cards in order, and a summary of the rest of
  the deck. The policy never reads them (the model enforces it, and a test checks it); the value network is
  used only in training, as the baseline of the advantages (asymmetric actor-critic: Pinto et al. 2017; the
  value also gets the normal observation, as Baisero & Amato 2022 require for an unbiased baseline).
Versions 1 and 2 are frozen in arknova/rl/v1 and arknova/rl/v2 for checkpoints trained with them.

Not encoded yet: which animal is housed in which enclosure.
"""
import copy
import random
import re

import numpy as np

from .. import cards, effects as E, engine as G, state as S, tables as T
from ..hexmap import MAP0

# ---- vocabularies -------------------------------------------------------------------------

CARD_IDS = sorted(cards.all_cards())
CARD_INDEX = {c: i + 1 for i, c in enumerate(CARD_IDS)}  # 0 = no card
N_CARDS = len(CARD_IDS) + 1

ICONS = ["africa", "americas", "asia", "australia", "europe", "bear", "bird", "herbivore", "pet", "predator",
         "primate", "reptile", "rock", "science", "water"]
CARD_TYPES = ["animal", "sponsor", "project", "endgame"]
BUILDING_KINDS = ["enclosure", "kiosk", "pavilion", "petting_zoo", "reptile_house", "aviary"]  # then "other"
TOKEN_KINDS = ["venom", "constriction", "multiplier"]

# every word that appears in an option key (verbs and named arguments), plus the decision kinds
_OPTION_WORDS = """act africa americas animals asia association australia aviary boost break build card cards cards3
clever deck discard discard_display discard_final discard_hand display donate done enclosure enclosure3 engineer
europe hand keep kind kiosk large money money10 move multiplier no partner_zoo pavilion petting_zoo pick place play
play_display play_project play_project_display play_release play_release_display release repeat reptile_house
reputation reputation2 science2 science_rep sell skip small snap sponsor sponsors support take take_small tile token
tuck university upgrade worker xtoken xtoken3 yes""".split()
NONE, UNKNOWN = 0, 1
WORDS = ["<none>", "<unknown>"] + _OPTION_WORDS + sorted(k for k in S.CHOICES if k not in _OPTION_WORDS)
WORD_INDEX = {w: i for i, w in enumerate(WORDS)}
N_WORDS = len(WORDS)

# verbs whose first number is a display folder: the card there is added to the option's cards
DISPLAY_VERBS = {"display", "snap", "play_display", "discard_display", "play_project_display",
                 "play_release_display", "take_small"}
DISPLAY_FRAMES = {"ab_snap"}  # here "take" also names a folder

CELLS = sorted(MAP0.cells)
CELL_INDEX = {c: i for i, c in enumerate(CELLS)}
N_CELLS = len(CELLS)
CELL_FEATURES = len(BUILDING_KINDS) + 3  # kinds, other, size, occupied

FRAME_NUMBERS = ["budget", "count", "discard", "draw", "drawn", "left", "limit", "played", "remaining", "strength",
                 "space"]
FRAME_FLAGS = ["all_small", "donated", "engineer_used", "may_snap", "normal_done", "side2", "upgraded", "optional"]

# card sets in the observation: (name, padded length)
SETS = [("hand", 24), ("zoo", 48), ("other_zoo", 48), ("display", 6), ("projects", 12), ("final", 2),
        ("other_known_hand", 24)]
SET_SLICES, _at = {}, 0
for _name, _size in SETS:
    SET_SLICES[_name] = slice(_at, _at + _size)
    _at += _size
N_SET_SLOTS = _at

OPTION_ARGS, OPTION_CARDS, OPTION_NUMBERS = 2, 4, 4
SET_EXTRA = 4  # numbers per card in a set that depend on where it lies (see _set_extras)

VERSION = 3

# the board: every map uses Map 0's 58 cells (checked in tests), so cell features line up across maps
MAP_NAMES = ["map0", "plan1", "plan2", "plan3", "plan4", "plan5", "plan6", "plan7", "plan8", "plana"]
BOARD_BONUSES = ["card", "clever", "kiosk", "money10", "money2", "money5", "multiplier", "partner_zoo", "rep1",
                 "rep2", "sponsor_for_money", "university", "worker1", "xtoken"]
SPECIAL_SITES = ["H", "build2_with_money2", "commercial_harbor", "harbor_connecting_building_space", "hollywood_h",
                 "ice_cream_parlors", "institute_connecting_building_space", "kiosk_bonus", "observation_tower",
                 "outdoor_area", "park_restaurant", "partner_zoo_bonus", "prebuilt_enclosure_size3",
                 "prebuilt_kiosk", "research_institute", "restaurant_adjacent_spaces", "silver_lake",
                 "start_enclosure", "start_kiosk", "xtoken_at_bonus"]
BOARD_FEATURES = 3 + len(BOARD_BONUSES) + len(SPECIAL_SITES)  # water, rock, Build II, bonus, special sites
LAST_ACTIONS = T.ACTIONS + ["xtoken"]
LOOKAHEAD_FEATURES = 9

# privileged (hidden) information, for the value network only
PRIV_SETS = [("other_hand", 24), ("other_final", 2), ("deck_next", 12)]
PRIV_SLICES, _p = {}, 0
for _name, _size in PRIV_SETS:
    PRIV_SLICES[_name] = slice(_p, _p + _size)
    _p += _size
N_PRIV_SLOTS = _p
PRIV_SCALARS = len(CARD_TYPES) + len(ICONS) + 1  # summary of the deck beyond the next cards, and its size

REQUIREMENTS = ["science", "Partner Zoo", "animalsII", "sponsorsII", "appeal", "reputation", "primate", "reptile",
                "bird", "predator", "herbivore", "bear", "africa", "americas", "asia", "australia", "europe"]
ABILITIES = sorted({a["keyword"] for c in cards.all_cards().values() for a in c.get("abilities") or []})
TIMINGS = ["income", "immediate", "passive", "endgame"]
EFFECT_WORDS = ["Money", "ConservationPoint", "Appeal", "Reputation", "XToken", "Slot", "BuildActionCard",
                "AnimalActionCard"]
SPECIAL_ENCLOSURES = ["Reptile House", "Aviary", "Petting Zoo"]
PROJECT_CATEGORIES = ["base", "release", "breed", "normal"]
PROJECT_ICONS = sorted({c.get("icon") for c in cards.all_cards().values() if c["type"] == "project"} - {None})
BONUS_TILE_NAMES = list(T.BONUS_TILES)


def card_features():
    """[N_CARDS, F] printed features of every card; row 0 (no card) is zero."""
    rows = []
    for card_id in CARD_IDS:
        c = cards.card(card_id)
        row = [c["type"] == t for t in CARD_TYPES]
        for key, scale in (("cost", 30), ("size", 5), ("appeal", 10), ("conservation", 3), ("reputation", 3),
                           ("level", 8), ("min_reputation", 15), ("max_appeal", 50)):
            value = c.get(key)
            row.append(value / scale if isinstance(value, (int, float)) else 0)
        icons = cards.icons_of(card_id)
        row += [icons.get(icon, 0) for icon in ICONS]
        enclosure = c.get("enclosure") or {}
        row += [(enclosure.get("rock") or 0) / 2, (enclosure.get("water") or 0) / 2]
        special = {e.get("type"): e.get("size", 0) for e in enclosure.get("special") or [] if isinstance(e, dict)}
        row += [(special[k] + 1) / 5 if k in special else 0 for k in SPECIAL_ENCLOSURES]
        requirements = c.get("requirements") or []
        row += [requirements.count(r) / 2 for r in REQUIREMENTS]
        abilities = {a["keyword"]: a.get("value") for a in c.get("abilities") or []}
        row += [(abilities[k] / 4 if isinstance(abilities[k], (int, float)) and abilities[k] else 1)
                if k in abilities else 0 for k in ABILITIES]
        effects = c.get("effects") or []
        row += [sum(e["timing"] == t for e in effects) for t in TIMINGS]
        words = [w for e in effects for w in re.findall(r"\{([A-Za-z]+)", e["text"])]
        row += [words.count(w) / 2 for w in EFFECT_WORDS]
        building = c.get("building") or {}
        row += [bool(building), (building.get("size") or 0) / 5, bool(c.get("human"))]
        row += [c.get("category") == k for k in PROJECT_CATEGORIES]
        row += [c.get("icon") == k for k in PROJECT_ICONS]
        slots = sorted(c.get("slots") or [], key=lambda slot: slot["position"])[:3]
        slots += [None] * (3 - len(slots))
        for slot in slots:
            row.append(((slot.get("required") or 0) / 5) if slot else 0)
            row.append(sum(r["amount"] for r in slot["rewards"]) / 5 if slot else 0)
        scoring = c.get("scoring") or []
        row += [max((t.get("threshold") or 0 for t in scoring), default=0) / 10, len(scoring) / 4]
        rows.append(row)
    table = np.zeros((N_CARDS, len(rows[0])), dtype=np.float32)
    table[1:] = np.asarray(rows, dtype=np.float32)
    return table


_BOARDS = {}
_CARD_SUMMARY = None


def board(map_name):
    """[N_CELLS, BOARD_FEATURES] fixed features of a map's cells (cached)."""
    if map_name not in _BOARDS:
        mapdef = G.MAP_DEFS[map_name]
        out = np.zeros((N_CELLS, BOARD_FEATURES), dtype=np.float32)
        for cell, info in mapdef.cells.items():
            row = out[CELL_INDEX[cell]]
            row[0], row[1], row[2] = info.terrain == "water", info.terrain == "rock", info.build2_only
            if info.bonus in BOARD_BONUSES:
                row[3 + BOARD_BONUSES.index(info.bonus)] = 1
        for name, site_cells in T.MAPS[map_name].get("special", {}).items():
            if name in SPECIAL_SITES:
                for cell in site_cells:
                    if cell in CELL_INDEX:
                        out[CELL_INDEX[cell], 3 + len(BOARD_BONUSES) + SPECIAL_SITES.index(name)] = 1
        _BOARDS[map_name] = out
    return _BOARDS[map_name]


def _card_summary():
    """[N_CARDS, types + icons] per card, for summing over piles like the discard pile."""
    global _CARD_SUMMARY
    if _CARD_SUMMARY is None:
        table = np.zeros((N_CARDS, len(CARD_TYPES) + len(ICONS)), dtype=np.float32)
        for card_id, i in CARD_INDEX.items():
            icons = cards.icons_of(card_id)
            table[i] = [cards.card(card_id)["type"] == t for t in CARD_TYPES] + [icons.get(k, 0) for k in ICONS]
        _CARD_SUMMARY = table
    return _CARD_SUMMARY


def _clone(state):
    clone = getattr(S, "clone", None)
    return clone(state) if clone else copy.deepcopy(state)


_SHUFFLE = random.Random(0)


def _lookahead(state, options, on):
    """[n, LOOKAHEAD_FEATURES]: what applying each option changes, up to the next decision (zero when off).
    Costs one state copy and one engine step per option, several times the rest of the encoding."""
    out = np.zeros((len(options), LOOKAHEAD_FEATURES), dtype=np.float32)
    if not on:
        return out
    p = state.stack[-1].player

    def snapshot(st):
        me, other = st.players[p], st.players[1 - p]
        return np.array([me.appeal / 10, me.conservation / 3, me.money / 10, me.reputation / 3, len(me.hand) / 3,
                         me.xtokens / 2, me.victory_points / 10, other.victory_points / 10], dtype=np.float32)

    before = snapshot(state)
    for i, option in enumerate(options):
        clone = _clone(state)
        clone.log, clone.cached_options = None, None
        clone.rng = random.Random(_SHUFFLE.random())
        clone.rng.shuffle(clone.deck)  # the deciding player does not know the deck order
        try:
            G.step(clone, option)
        except Exception:  # noqa: BLE001  an engine error in a look-ahead leaves that row at zero
            continue
        out[i, :8] = snapshot(clone) - before
        out[i, 8] = (not clone.over) and clone.stack[-1].player == p
    return out


# ---- observation --------------------------------------------------------------------------

def _player_features(player, out):
    out += [player.money / 50, player.appeal / 100, player.conservation / 40, player.reputation / 15,
            player.xtokens / 5, player.workers / 4, player.active_workers / 4, len(player.hand) / 10,
            player.projects_supported / 7, player.victory_points / 100]
    for action in T.ACTIONS:
        tokens = player.action_tokens.get(action, ())
        out += [action in player.upgraded, player.strength(action) / 5]
        out += [tokens.count(kind) for kind in TOKEN_KINDS]
    out += [c in player.partner_zoos for c in T.CONTINENTS]
    out += [u in player.universities for u in T.UNIVERSITIES]
    out += player.tokens
    icons = cards.icons(player)
    out += [icons.get(icon, 0) / 5 for icon in ICONS]
    kinds = [0] * (len(BUILDING_KINDS) + 1)
    empty = [0] * 5
    for b in player.zoo.buildings:
        kinds[BUILDING_KINDS.index(b.kind) if b.kind in BUILDING_KINDS else -1] += 1
        if b.kind == "enclosure" and not b.occupied:
            empty[min(b.size, 5) - 1] += 1
    out += [k / 5 for k in kinds] + empty
    out.append(len(player.zoo.cell_owner) / N_CELLS)


def _map_features(zoo, out):
    """out: [N_CELLS, CELL_FEATURES] view to fill."""
    for b in zoo.buildings:
        kind = BUILDING_KINDS.index(b.kind) if b.kind in BUILDING_KINDS else len(BUILDING_KINDS)
        for cell in b.cells:
            row = out[CELL_INDEX[cell]]
            row[kind] = 1
            row[-2] = b.size
            row[-1] = b.occupied or b.used > 0


def _fill(sets, name, ids):
    span = SET_SLICES[name]
    ids = [CARD_INDEX[c] for c in ids if c is not None][:span.stop - span.start]
    sets[span.start:span.start + len(ids)] = ids


def _set_extras(state, me, other):
    """[N_SET_SLOTS, SET_EXTRA] numbers for each card that depend on the game, aligned with `sets`."""
    out = np.zeros((N_SET_SLOTS, SET_EXTRA), dtype=np.float32)
    at = SET_SLICES["hand"].start
    for card_id in me.hand[:SET_SLICES["hand"].stop - at]:
        c = cards.card(card_id)
        out[at] = [cards.unmet_requirements(me, card_id) == 0, (c.get("cost") or 0) <= me.money, 0, 0]
        at += 1
    for name, player in (("zoo", me), ("other_zoo", other)):
        at = SET_SLICES[name].start
        for card_id in player.zoo_cards[:SET_SLICES[name].stop - at]:
            tokens = player.card_tokens.get(card_id, 0)
            out[at, 0] = (tokens if isinstance(tokens, int) else 1) / 5
            at += 1
    at = SET_SLICES["display"].start
    reachable = T.reputation_folders(me.reputation)
    for folder, card_id in enumerate(state.display[:6]):
        if card_id is not None:
            out[at] = [(folder + 1) / 6, folder < reachable, 0, 0]
            at += 1
    at = SET_SLICES["projects"].start
    for card_id in (state.base_projects + state.projects)[:SET_SLICES["projects"].stop - at]:
        taken = state.project_tokens.get(card_id, {}).values()
        out[at] = [sum(t == me.idx for t in taken), sum(t == other.idx for t in taken),
                   sum(t == "blocked" for t in taken), len(cards.card(card_id).get("slots") or ()) - len(taken)]
        at += 1
    return out


def _option_rows(state, frame, options):
    n = len(options)
    words = np.zeros((n, 1 + OPTION_ARGS), dtype=np.int16)
    card_ids = np.zeros((n, OPTION_CARDS), dtype=np.int16)
    numbers = np.zeros((n, OPTION_NUMBERS), dtype=np.float32)
    cells = np.zeros((n, N_CELLS), dtype=np.uint8)
    folders = frame.kind in DISPLAY_FRAMES
    for i, option in enumerate(options):
        key = option.key
        verb = key[0]
        words[i, 0] = WORD_INDEX.get(verb, UNKNOWN)
        n_args = n_cards = n_numbers = 0
        folder = verb in DISPLAY_VERBS or (folders and verb == "take")
        for part in key[1:]:
            if isinstance(part, str):
                head, _, tail = part.partition(":")
                card_id = CARD_INDEX.get(tail if tail else head)
                if card_id and n_cards < OPTION_CARDS:
                    card_ids[i, n_cards] = card_id
                    n_cards += 1
                if (tail or not card_id) and n_args < OPTION_ARGS:
                    n_args += 1
                    words[i, n_args] = WORD_INDEX.get(head, UNKNOWN)
            elif isinstance(part, tuple):
                for cell in part:
                    cells[i, CELL_INDEX[cell]] = 1
            else:
                if folder:
                    folder = False
                    shown = state.display[part] if part < len(state.display) else None
                    if shown is not None and n_cards < OPTION_CARDS:
                        card_ids[i, n_cards] = CARD_INDEX[shown]
                        n_cards += 1
                if n_numbers < OPTION_NUMBERS:
                    numbers[i, n_numbers] = (part + 1) / 5
                    n_numbers += 1
    return words, card_ids, numbers, cells


def _known_hand(state, me, other):
    """Cards the deciding player saw enter the opponent's hand and has not seen anywhere public since. Read
    from public zones only, never from the opponent's actual hand, so nothing hidden leaks (a card that left
    the hand face down stays listed)."""
    seen = set(other.zoo_cards) | set(me.zoo_cards) | set(state.discard) | set(me.hand) | set(me.final_cards)
    seen |= {c for c in state.display if c is not None} | set(state.base_projects) | set(state.projects)
    return [c for c in getattr(other, "public_hand", ()) if c not in seen]


def _privileged(state, me, other, on):
    """Hidden information for the value network: (card ids [N_PRIV_SLOTS], position of each deck card
    [N_PRIV_SLOTS, 1], deck summary [PRIV_SCALARS]). All zero when off."""
    ids = np.zeros(N_PRIV_SLOTS, dtype=np.int16)
    position = np.zeros((N_PRIV_SLOTS, 1), dtype=np.float32)
    summary = np.zeros(PRIV_SCALARS, dtype=np.float32)
    if not on:
        return ids, position, summary

    def fill(name, cards_):
        span = PRIV_SLICES[name]
        found = [CARD_INDEX[c] for c in cards_ if c in CARD_INDEX][:span.stop - span.start]
        ids[span.start:span.start + len(found)] = found
        return span.start, len(found)

    fill("other_hand", other.hand)
    fill("other_final", other.final_cards)
    upcoming = list(reversed(state.deck))  # the deck is drawn from its end
    start, n = fill("deck_next", upcoming)
    position[start:start + n, 0] = (np.arange(n) + 1) / n if n else 0
    rest = [CARD_INDEX[c] for c in upcoming[PRIV_SLICES["deck_next"].stop - PRIV_SLICES["deck_next"].start:]
            if c in CARD_INDEX]
    summary[:-1] = _card_summary()[rest].sum(0) / 50
    summary[-1] = len(state.deck) / 200
    return ids, position, summary


def observe(state, options=None, lookahead=False, privileged=False):
    """Arrays for the decision on top of the stack, from the deciding player's side."""
    frame = state.stack[-1]
    me, other = state.players[frame.player], state.players[1 - frame.player]
    if options is None:
        options = G.legal_options(state)

    scalars = []
    _player_features(me, scalars)
    _player_features(other, scalars)
    scalars += [state.break_pos / T.BREAK_TRACK[state.n], state.donations / 5, len(state.deck) / 200,
                state.end_by == me.idx, state.end_by == other.idx, state.final_turns is not None,
                len(state.stack) / 4]
    scalars += [c in state.partner_zoos_available for c in T.CONTINENTS]
    scalars += [u in state.universities_available for u in T.UNIVERSITIES]
    for space in sorted(state.bonus_tiles)[:2]:
        scalars += [name in state.bonus_tiles[space] for name in BONUS_TILE_NAMES]
    scalars += [0] * len(BONUS_TILE_NAMES) * (2 - min(2, len(state.bonus_tiles)))
    data = frame.data
    scalars += [(data.get(k) or 0) / 5 if isinstance(data.get(k), int) else 0 for k in FRAME_NUMBERS]
    scalars += [bool(data.get(k)) for k in FRAME_FLAGS]
    scalars += [state.map_name == m for m in MAP_NAMES]
    scalars += [getattr(other, "last_action", None) == a for a in LAST_ACTIONS]
    discard = [CARD_INDEX[c] for c in state.discard if c in CARD_INDEX]
    scalars += list(_card_summary()[discard].sum(0) / 20) + [len(discard) / 50]

    sets = np.zeros(N_SET_SLOTS, dtype=np.int16)
    _fill(sets, "hand", me.hand)
    _fill(sets, "zoo", me.zoo_cards)
    _fill(sets, "other_zoo", other.zoo_cards)
    _fill(sets, "display", state.display)
    _fill(sets, "projects", state.base_projects + state.projects)
    _fill(sets, "final", me.final_cards)
    _fill(sets, "other_known_hand", _known_hand(state, me, other))

    extras = _set_extras(state, me, other)

    maps = np.zeros((2, N_CELLS, CELL_FEATURES), dtype=np.uint8)
    _map_features(me.zoo, maps[0])
    _map_features(other.zoo, maps[1])
    maps = np.concatenate([maps.reshape(-1).astype(np.float32), board(state.map_name).reshape(-1)])

    parent = state.stack[-2].kind if len(state.stack) > 1 else None
    words, card_ids, numbers, cells = _option_rows(state, frame, options)
    slot_of = np.zeros(N_CARDS, dtype=np.int16)  # card index -> 1 + its first slot in `sets` (0: not in a set)
    filled = np.flatnonzero(sets)
    ids, first = np.unique(sets[filled], return_index=True)
    slot_of[ids] = filled[first] + 1
    slot_of[0] = 0
    slots = slot_of[card_ids]
    return {
        "scalars": np.asarray(scalars, dtype=np.float32),
        "context": np.array([WORD_INDEX.get(frame.kind, UNKNOWN), WORD_INDEX.get(parent, NONE)], dtype=np.int16),
        "sets": sets,
        "set_extras": extras,
        "maps": maps,
        "option_words": words, "option_cards": card_ids, "option_numbers": numbers, "option_cells": cells,
        "option_slots": slots, "option_effects": _lookahead(state, options, lookahead),
        **dict(zip(PRIV_KEYS, _privileged(state, me, other, privileged))),
    }


N_SCALARS = None  # set on first use by sizes()


def sizes():
    """Array widths a model needs."""
    global N_SCALARS
    if N_SCALARS is None:
        N_SCALARS = len(observe(G.new_game(2, seed=0))["scalars"])
    return {"scalars": N_SCALARS, "maps": 2 * N_CELLS * CELL_FEATURES + N_CELLS * BOARD_FEATURES,
            "sets": N_SET_SLOTS, "cards": N_CARDS, "set_extra": SET_EXTRA, "words": N_WORDS, "cells": N_CELLS,
            "option_numbers": OPTION_NUMBERS, "option_effects": LOOKAHEAD_FEATURES, "set_kinds": len(SETS),
            "priv_sets": len(PRIV_SETS), "priv_scalars": PRIV_SCALARS}


PRIV_KEYS = ("priv_sets", "priv_positions", "priv_scalars")  # read by the value network only
STATE_KEYS = ("scalars", "context", "sets", "set_extras", "maps") + PRIV_KEYS
OPTION_KEYS = ("option_words", "option_cards", "option_numbers", "option_cells", "option_slots", "option_effects")


def collate(observations):
    """Stack observations; option rows are concatenated, with `counts` saying how many each has."""
    batch = {k: np.stack([o[k] for o in observations]) for k in STATE_KEYS}
    for k in OPTION_KEYS:
        batch[k] = np.concatenate([o[k] for o in observations])
    batch["counts"] = np.array([len(o["option_words"]) for o in observations], dtype=np.int32)
    return batch
