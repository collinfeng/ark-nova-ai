"""Turn a pending decision into arrays for a network: what the deciding player may see, and one
row per legal option. Two players only. Nothing hidden from the deciding player is read: not the
deck order, the other hand, or the other player's final scoring cards.

Not encoded yet (first version): which project slots are taken, bonus tiles left, cards seen so far.
"""
import numpy as np

from ... import cards, engine as G, state as S, tables as T
from ...hexmap import MAP0

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
SETS = [("hand", 24), ("zoo", 48), ("other_zoo", 48), ("display", 6), ("projects", 12), ("final", 2)]
SET_SLICES, _at = {}, 0
for _name, _size in SETS:
    SET_SLICES[_name] = slice(_at, _at + _size)
    _at += _size
N_SET_SLOTS = _at

OPTION_ARGS, OPTION_CARDS, OPTION_NUMBERS = 2, 4, 4


def card_features():
    """[N_CARDS, F] printed features of every card; row 0 (no card) is zero."""
    rows = np.zeros((N_CARDS, len(CARD_TYPES) + 6 + len(ICONS)), dtype=np.float32)
    for card_id, i in CARD_INDEX.items():
        c = cards.card(card_id)
        row = rows[i]
        if c["type"] in CARD_TYPES:
            row[CARD_TYPES.index(c["type"])] = 1
        base = len(CARD_TYPES)
        for j, (key, scale) in enumerate((("cost", 30), ("size", 5), ("appeal", 10), ("conservation", 3),
                                          ("reputation", 3), ("level", 8))):
            value = c.get(key)
            if isinstance(value, (int, float)):
                row[base + j] = value / scale
        for icon, count in cards.icons_of(card_id).items():
            if icon in ICONS:
                row[base + 6 + ICONS.index(icon)] = count
    return rows


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


def observe(state, options=None):
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
    data = frame.data
    scalars += [(data.get(k) or 0) / 5 if isinstance(data.get(k), int) else 0 for k in FRAME_NUMBERS]
    scalars += [bool(data.get(k)) for k in FRAME_FLAGS]

    sets = np.zeros(N_SET_SLOTS, dtype=np.int16)
    _fill(sets, "hand", me.hand)
    _fill(sets, "zoo", me.zoo_cards)
    _fill(sets, "other_zoo", other.zoo_cards)
    _fill(sets, "display", state.display)
    _fill(sets, "projects", state.base_projects + state.projects)
    _fill(sets, "final", me.final_cards)

    maps = np.zeros((2, N_CELLS, CELL_FEATURES), dtype=np.uint8)
    _map_features(me.zoo, maps[0])
    _map_features(other.zoo, maps[1])

    parent = state.stack[-2].kind if len(state.stack) > 1 else None
    words, card_ids, numbers, cells = _option_rows(state, frame, options)
    return {
        "scalars": np.asarray(scalars, dtype=np.float32),
        "context": np.array([WORD_INDEX.get(frame.kind, UNKNOWN), WORD_INDEX.get(parent, NONE)], dtype=np.int16),
        "sets": sets,
        "maps": maps.reshape(-1),
        "option_words": words, "option_cards": card_ids, "option_numbers": numbers, "option_cells": cells,
    }


N_SCALARS = None  # set on first use by sizes()


def sizes():
    """Array widths a model needs."""
    global N_SCALARS
    if N_SCALARS is None:
        N_SCALARS = len(observe(G.new_game(2, seed=0))["scalars"])
    return {"scalars": N_SCALARS, "maps": 2 * N_CELLS * CELL_FEATURES, "sets": N_SET_SLOTS, "cards": N_CARDS,
            "words": N_WORDS, "cells": N_CELLS, "option_numbers": OPTION_NUMBERS}


STATE_KEYS = ("scalars", "context", "sets", "maps")
OPTION_KEYS = ("option_words", "option_cards", "option_numbers", "option_cells")


def collate(observations):
    """Stack observations; option rows are concatenated, with `counts` saying how many each has."""
    batch = {k: np.stack([o[k] for o in observations]) for k in STATE_KEYS}
    for k in OPTION_KEYS:
        batch[k] = np.concatenate([o[k] for o in observations])
    batch["counts"] = np.array([len(o["option_words"]) for o in observations], dtype=np.int32)
    return batch
