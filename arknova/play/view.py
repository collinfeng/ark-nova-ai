"""The game as JSON for the board: everything the human may see, the pending decision with its options
(structured so the board can draw them), why unavailable actions are unavailable, and the analysis.

Hidden information stays hidden: the AI's hand is a count plus the cards the human saw enter it.
"""
import math
import re

from arknova import cards as C
from arknova import effects as E
from arknova import engine as G
from arknova import tables as T
from arknova.hexmap import SPECIAL, neighbors
from arknova import sponsor_rules as SR
from arknova.actions import animals as A
from arknova.actions import sponsors as S

from .ai import win_chance
from arknova.state import clone

from . import i18n
from .game import label as clean_label

TITLES = {
    "setup_keep": "Keep 4 of your 8 starting cards", "turn": "Your turn: choose an action",
    "act_build": "Build", "act_animals": "Animals: play an animal", "act_cards": "Cards: draw or snap",
    "act_association": "Association: choose a task", "act_sponsors": "Sponsors: play a sponsor or take money",
    "discard_hand": "Discard cards", "take_card": "Take a card", "upgrade": "Upgrade an action card",
    "conservation_tile": "Choose a conservation progress reward", "free_build": "Place a free building",
    "upgrade_or_worker": "Upgrade an action card or gain a worker", "discard_final": "Discard a final scoring card",
    "sponsor_building": "Place the sponsor building", "extra_action": "Extra action",
    "ab_boost": "Place an action card on another slot", "ab_dig": "Dig: discard cards to draw",
    "ab_hunter": "Hunter: take an animal", "ab_pick": "Pick a card to keep", "ab_pilfer": "Pilfer: give a card or money",
    "ab_pouch": "Pouch: tuck cards", "ab_project": "Take a base project", "ab_resist": "Keep a final scoring card",
    "ab_snap": "Snap a display card", "ab_sun": "Sunbathing: sell cards", "clever": "Clever: move an action card to slot 1",
    "gain_partner_zoo": "Gain a partner zoo", "gain_university": "Gain a university", "move_animals": "Move animals",
    "multiplier_repeat": "Use the x2 token?", "okapi_stable": "Okapi Stable", "paid_sponsor": "Play a sponsor for money?",
    "place_multiplier": "Place the x2 token", "waza_kind": "WAZA Special Assignment: choose a kind",
}


def title(kind):
    return i18n.tr(f"decisionTitles.{kind}", TITLES.get(kind, kind.replace("_", " ")))
SQRT3 = math.sqrt(3)
# Icons counted on a player's board, in the order the board shows them.
ICON_ORDER = list(T.CONTINENTS) + ["bird", "predator", "herbivore", "reptile", "primate", "bear", "pet",
                                   "science", "rock", "water"]


# ---- cards ---------------------------------------------------------------------------------------

# Card text whose printed icons were lost when the card list was extracted, by card and effect index.
TEXT_FIXES = {
    "227": {0: "Choose **small** (size 1-2) or **large** (size 4+) animals and mark your choice on this card. "
               "Successively reveal cards from the deck and take the first animal of the chosen kind."},
}


def tidy(text):
    """Card text without the stray space the extraction left before punctuation after an icon."""
    return re.sub(r"\} ([.,;:])", r"}\1", text or "")


def card_name(c):
    zh = i18n.card_zh(c["id"]) if "id" in c else None
    if zh:
        return zh["name"]
    name = re.sub(r"'S\b", "'s", c["name"])
    return re.sub(r"\bWaza\b", "WAZA", name)


def _overlay(out, cid):
    """The Chinese name and text over the English card, when the request asks for it."""
    zh = i18n.card_zh(cid)
    if not zh:
        return
    out["name"] = zh["name"]
    if out["type"] == "animal":
        for a, z in zip(out["abilities"], zh.get("abilities", [])):
            a["name"], a["text"] = z.get("name") or a["name"], tidy(z.get("text") or a["text"])
    elif out["type"] == "sponsor":
        for e, z in zip(out["effects"], zh.get("effects", [])):
            e["text"] = tidy(z.get("text") or e["text"])
    elif zh.get("text"):
        out["text"] = [tidy(t) for t in zh["text"]]


def card(cid):
    """A card for display, close to the printed card. Text keeps the card markup: **bold** and icon
    tokens such as {ConservationPoint-2}, {Money-X} or {Slot-1}, which the board draws as icons.

    Animals: enclosure (standard size, rock/water next to it, special buildings), cost, icons (tags:
    categories and continents), play conditions, appeal/conservation/reputation, abilities.
    Sponsors: level (required action strength), conditions, icons, effects by timing: passive
    ("each time"), immediate (once, when played), income (every break), endgame.
    Projects: icon and slots. Endgame cards: their scoring text."""
    if cid is None:
        return None
    c = C.card(cid)
    out = {"id": cid, "name": card_name(c), "type": c["type"], "tags": c.get("tags", []),
           "requirements": [str(r) for r in c.get("requirements", [])],
           "appeal": c.get("appeal", 0), "conservation": c.get("conservation", 0),
           "reputation": c.get("reputation", 0), "text": [], "effects": [], "abilities": []}
    for key in ("min_reputation", "max_appeal"):
        if key in c:
            out[key] = c[key]
    if c["type"] == "animal":
        enc = c.get("enclosure", {})
        out.update(cost=c["cost"], size=c["size"], latin=c.get("latin_name"),
                   enclosure={"size": enc.get("standard_size"), "rock": enc.get("rock") or 0,
                              "water": enc.get("water") or 0,
                              "special": [{"type": x["type"], "size": x["size"]} for x in enc.get("special", [])]})
        out["abilities"] = [{"name": a.get("name"), "keyword": a.get("keyword"), "value": a.get("value"),
                             "text": tidy(a.get("text", ""))} for a in c.get("abilities", [])]
    elif c["type"] == "sponsor":
        out.update(level=c.get("level"), human=c.get("human", False))
        fixes = TEXT_FIXES.get(cid, {})
        out["effects"] = [{"timing": e.get("timing"), "text": tidy(fixes.get(i, e.get("text", ""))),
                           "icon_only": e.get("icon_only", False)}
                          for i, e in enumerate(c.get("effects", []))]
    else:
        out["text"] = [tidy(c.get("text"))]
    if c["type"] == "project":
        out.update(icon=c.get("icon"), category=c.get("category"))
        out["slots"] = [{"position": s["position"], "required": s.get("required"),
                         "rewards": [{"reward": r["reward"], "amount": r["amount"]} for r in s.get("rewards", [])],
                         "size": s.get("animal_size")}
                        for s in c.get("slots", [])]
    if c["type"] == "endgame":
        out["scoring"] = c.get("scoring", [])
    _overlay(out, cid)
    return out


def _sentence(parts):
    """Join reasons into one sentence, capitalising only the first letter (keeps "Animals II")."""
    text = "; ".join(parts)
    return text[:1].upper() + text[1:]


def unmet(player, cid):
    """The card's play conditions that the player does not meet, in words."""
    return [text for _, text in unmet_conditions(player, cid)]


def unmet_conditions(player, cid):
    """(requirement key, words) for each play condition the player does not meet."""
    c = C.card(cid)
    have = C.icons(player)
    needs = {}
    for r in c.get("requirements", []):
        needs[r] = needs.get(r, 0) + 1
    out = []
    for need, n in needs.items():
        if need in ("animalsII", "sponsorsII"):
            if need[:-2] not in player.upgraded:
                out.append((need, i18n.tr("readiness.needsUpgrade", "needs {action} II", action=i18n.term("actions", need[:-2], need[:-2].capitalize()))))
        elif need == "Partner Zoo":
            continents = C.animal_continents(cid)
            owned = [z for z in player.partner_zoos if z in continents] if continents else player.partner_zoos
            if len(owned) < (1 if continents else n):
                out.append((need, i18n.tr("readiness.needsPartnerZooContinent", "needs a partner zoo in {continents}",
                                   continents=i18n.tr("common.or", " or ").join(i18n.term("icons", x, x) for x in continents))
                           if continents else
                           i18n.tr("readiness.needsPartnerZoos", "needs {count} partner zoo{s}", count=n, s="s" if n > 1 else "")))
        elif need == "reputation":
            if player.reputation < c["min_reputation"]:
                out.append((need, i18n.tr("readiness.needsReputation", "needs reputation {count}", count=c["min_reputation"])))
        elif need == "appeal":
            if player.appeal > c["max_appeal"]:
                out.append((need, i18n.tr("readiness.onlyUpToAppeal", "only up to appeal {appeal}", appeal=c["max_appeal"])))
        elif have.get(need, 0) < n:
            out.append((need, i18n.tr("readiness.needsIcon", "needs {count} {icon} icon{s} (you have {have})", count=n,
                                      icon=i18n.term("icons", need, need), s="s" if n > 1 else "", have=have.get(need, 0))))
    return out


def readiness(state, p, cid, extra_cost=0, display=False):
    """Whether the player could play this card now (with their strongest action), and if not, why.
    Returns {"ready": bool, "why": str, "cost": effective money cost} for animals and sponsors.
    Sponsors normally cost only the display surcharge; paid_sponsor effects charge their level."""
    player = state.players[p]
    c = C.card(cid)
    if c["type"] == "animal":
        cost = A._cost(player, cid) + extra_cost
        if display and "animals" not in player.upgraded:
            return {"ready": False, "why": i18n.tr("readiness.needsAnimalsTwoForDisplay", "Needs Animals II for the display"),
                    "cost": cost, "unmet": ["animalsII"]}
        if not SR.requirements_ok(player, cid, state):
            return {"ready": False, "why": _sentence(unmet(player, cid)) or
                    i18n.tr("readiness.playConditionsNotMet", "Play conditions not met"), "cost": cost,
                    "unmet": [k for k, _ in unmet_conditions(player, cid)]}
        if not SR.animal_allowed(player, cid):
            return {"ready": False, "why": i18n.tr("readiness.notAllowedByWazaSpecialAssignment",
                                                   "Not allowed by WAZA Special Assignment"), "cost": cost}
        if not A.housings(player, cid):
            enc = c.get("enclosure", {})
            need = [i18n.tr("readiness.freeEnclosurePart", "a free enclosure {size}+", size=enc["standard_size"])] \
                if enc.get("standard_size") is not None else []
            need += [i18n.term("specialEnclosures", x["type"], x["type"]) for x in enc.get("special", [])]
            terrain = [i18n.tr("readiness.terrainPart", "{count} {terrain}", count=enc[t], terrain=i18n.term("icons", t, t))
                       for t in ("rock", "water") if enc.get(t)]
            joiner = i18n.tr("common.or", " or ")
            with_ = i18n.tr("common.with", " with ") + i18n.tr("common.and", " and ").join(terrain) if terrain else ""
            return {"ready": False, "why": i18n.tr("readiness.needs", "Needs {what}{terrain}", what=joiner.join(need), terrain=with_),
                    "cost": cost}
        if cost > player.money:
            return {"ready": False, "why": i18n.tr("readiness.costsHave", "Costs {cost}, you have {money}", cost=cost,
                                                   money=player.money), "cost": cost}
        return {"ready": True, "why": "", "cost": cost}
    if c["type"] == "sponsor":
        level = SR.sponsor_level(state, p, cid)
        paid = bool(state.stack and state.stack[-1].kind == "paid_sponsor" and state.stack[-1].player == p and not display)
        cost = level if paid else extra_cost
        budget = 5 + player.xtokens + (1 if "sponsors" in player.upgraded else 0)
        if display and "sponsors" not in player.upgraded:
            return {"ready": False, "why": i18n.tr("readiness.needsSponsorsTwoForDisplay", "Needs Sponsors II for the display"),
                    "cost": cost, "unmet": ["sponsorsII"]}
        if not S.can_play(state, p, cid):
            why = _sentence(unmet(player, cid)) or i18n.tr("readiness.noRoomOnMap", "No room on your map for its building")
            return {"ready": False, "why": why, "cost": cost, "unmet": [k for k, _ in unmet_conditions(player, cid)]}
        if not paid and level > budget:
            return {"ready": False, "why": i18n.tr("readiness.levelNeedsStrength", "Level {level} needs strength {level}",
                                                   level=level), "cost": cost}
        if cost > player.money:
            return {"ready": False, "why": i18n.tr("readiness.costsHave", "Costs {cost}, you have {money}", cost=cost,
                                                   money=player.money), "cost": cost}
        return {"ready": True, "why": "", "cost": cost}
    return None


# ---- map -----------------------------------------------------------------------------------------

def _xy(q, r):
    """Centre of an axial cell in hex-radius units (flat-top hexes, columns going right, rows down)."""
    row = r + (q + 1) // 2
    return round(q * 1.5, 3), round(row * SQRT3 + (0 if q % 2 else SQRT3 / 2), 3)


# A map's special sites the board marks (tables.MAPS[map]["special"] name -> what the board calls it).
# The other special entries only restate the layout (Map 3's lake is water, Map A's buildings are built).
SITES = {"observation_tower": "tower", "outdoor_area": "outdoor", "harbor_connecting_building_space": "harbour",
         "park_restaurant": "restaurant", "institute_connecting_building_space": "institute",
         "ice_cream_parlors": "ice_cream", "H": "hollywood"}


def sites(state):
    """{(q, r): site} for the special sites of the game's map."""
    out = {}
    for name, cells in (state.map.get("special") or {}).items():
        if name in SITES:
            for c in cells:
                out[tuple(c)] = SITES[name]
    return out


def zoo(player, state=None):
    z = player.zoo
    site = sites(state) if state is not None else {}
    cells = []
    for (q, r), cell in sorted(z.mapdef.cells.items()):
        x, y = _xy(q, r)
        cells.append({"q": q, "r": r, "x": x, "y": y, "terrain": cell.terrain, "bonus": cell.bonus,
                      "build2": cell.build2_only, "building": z.cell_owner.get((q, r)), "site": site.get((q, r))})
    homes, home_ids = {}, {}
    for cid, (building, _) in player.housing.items():
        homes.setdefault(building, []).append(card_name(C.card(cid)))
        home_ids.setdefault(building, []).append(cid)
    buildings = [{"id": b.id, "kind": b.kind, "size": b.size, "capacity": b.capacity, "occupied": b.occupied,
                  "used": b.used, "name": b.name, "cells": [list(c) for c in sorted(b.cells)],
                  "animals": homes.get(b.id, []), "animal_cards": [card(c) for c in home_ids.get(b.id, [])],
                  "sponsor_card": card(b.name) if b.kind == "unique" and b.name and _is_card(b.name) else None}
                 for b in z.buildings]
    return {"cells": cells, "buildings": buildings}


# ---- players -------------------------------------------------------------------------------------

def _why_not(state, p, action):
    """Why an action card cannot be used now (the engine only says that it cannot)."""
    player = state.players[p]
    if action == "animals":
        if not any(A._count(state, p, s) for s in range(1, 6 + player.xtokens)):
            return i18n.tr("actionReasons.animalsTooWeak", "Too weak in this slot to play an animal")
        return i18n.tr("actionReasons.animalsNoTarget", "No animal in reach that you can afford and house")
    if action == "build":
        if player.money < T.BUILD_COST_PER_SPACE:
            return i18n.tr("actionReasons.buildNoMoney", "Not enough money to build")
        return i18n.tr("actionReasons.buildNoRoom", "No room for a building you can afford")
    if action == "association":
        if player.active_workers <= 0:
            return i18n.tr("actionReasons.associationNoWorker", "No free association worker (they return at the break)")
        return i18n.tr("actionReasons.associationNoTask", "No task within reach (tasks need strength 2-5; repeated tasks need 2 workers)")
    return i18n.tr("readiness.notAvailable", "Not available")


def slots(state, p, options):
    """The five action cards with their strength and, on a turn decision, whether each can be used."""
    player = state.players[p]
    turn = state.stack and state.stack[-1].kind == "turn" and G.to_move(state) == p
    acting = {o.key[1] for o in options if o.key[0] == "act"} if turn else set()
    out = []
    for i, action in enumerate(player.slots):
        entry = {"action": action, "strength": i + 1, "upgraded": action in player.upgraded,
                 "tokens": E.tokens_on(state, p, action) if hasattr(E, "tokens_on") else []}
        if turn:
            entry["playable"] = action in acting
            if not entry["playable"]:
                entry["reason"] = _why_not(state, p, action)
        out.append(entry)
    return out


def player(state, p, me, options):
    pl = state.players[p]
    have = C.icons(pl)
    icons = {k: have.get(k, 0) for k in ICON_ORDER}
    out = {"idx": p, "you": p == me, "appeal": pl.appeal, "conservation": pl.conservation,
           "reputation": pl.reputation, "money": pl.money, "xtokens": pl.xtokens, "workers": pl.workers,
           "active_workers": pl.active_workers, "points": pl.victory_points,
           "income": T.appeal_income(pl.appeal) + pl.zoo.kiosk_income(),
           "folders": T.reputation_folders(pl.reputation), "hand_limit": pl.hand_limit,
           "slots": slots(state, p, options), "icons": icons, "partner_zoos": list(pl.partner_zoos),
           "universities": list(pl.universities), "projects_supported": pl.projects_supported,
           "zoo_cards": [card(c) for c in pl.zoo_cards], "zoo": zoo(pl, state), "hand_size": len(pl.hand),
           "last_action": pl.last_action}
    if p == me:
        out["hand"] = [{**card(c), "status": readiness(state, p, c)} for c in pl.hand]
        out["final_cards"] = [card(c) for c in pl.final_cards]
    else:
        out["known_hand"] = [card(c) for c in pl.public_hand if c in pl.hand]
    return out


# ---- the decision --------------------------------------------------------------------------------

def _cards_in(key):
    return [k for k in key if isinstance(k, str) and re.fullmatch(r"\d{3}", k) and _is_card(k)]


def _is_card(cid):
    try:
        C.card(cid)
        return True
    except KeyError:
        return False


def _cells_in(key):
    for k in key:
        if isinstance(k, tuple) and k and all(isinstance(c, tuple) and len(c) == 2 for c in k):
            return [list(c) for c in k]
    return None


def _display_card(state, key, frame_kind=None):
    """The display card an option refers to by slot index, if any."""
    is_snap_take = frame_kind == "ab_snap" and key[0] == "take"
    if (key[0] in ("display", "snap") or key[0].endswith("_display") or is_snap_take) \
            and len(key) > 1 and isinstance(key[1], int) \
            and 0 <= key[1] < len(state.display):
        return state.display[key[1]]
    return None


def _card_word(m):
    cid = m.group(0)
    return card_name(C.card(cid)) if _is_card(cid) else cid


def nicer(label, key):
    """Option text for people: card names for card numbers, continents and universities by name,
    bonus tiles by what they give, no underscores."""
    if i18n.is_zh():
        return i18n.option_label(re.sub(r"\bWaza\b", "WAZA", label), key)
    return readable(label, cards=key[0] != "keep")


def readable(label, cards=True):
    """Engine text for people, from the text alone (the activity list keeps no option keys)."""
    m = re.fullmatch(r"Partner zoo: (\w+)", label)
    if m:
        return f"Partner zoo: {m[1].capitalize()}"
    m = re.fullmatch(r"University: (\w+)", label)
    if m and m[1] in _UNIVERSITY:
        return f"University: {_UNIVERSITY[m[1]][1]}"
    m = re.fullmatch(r"Take bonus tile:? (\w+)", label)
    if m and m[1] in T.BONUS_TILES:
        return f"Take bonus tile: {', '.join(effect_label(k, a) for k, a in T.BONUS_TILES[m[1]])}"
    if cards:
        label = re.sub(r"\b\d{3}\b", _card_word, label)
    label = re.sub(r"\bWaza\b", "WAZA", label.replace("_", " "))
    return label[:1].upper() + label[1:]


def _action_in(key, label):
    """The action card an option is about, if any (upgrade, slot moves, x2 token, extra action)."""
    if len(key) > 1 and key[1] in T.ACTIONS:
        return key[1]
    if key[0] in ("boost", "repeat"):
        return next((a for a in T.ACTIONS if re.search(rf"\b{a}\b", label)), None)
    return None


def _feeds_kiosk(kind, occupied=False):
    return kind in ("pavilion", "unique") or kind in SPECIAL or (kind == "enclosure" and occupied)


def place_preview(state, p, kind, cells):
    """What placing a building on `cells` would bring, as [{"k": what, "n": how much}]: the bonus spaces it
    covers, its own effect, kiosk income, completing the zoo, the map's sites and the sponsor cards that react
    to building. Computed from the rules, without playing the move (there can be hundreds of placements)."""
    player = state.players[p]
    zoo = player.zoo
    mapdef = zoo.mapdef
    cells = {tuple(c) for c in cells}
    out = []
    twice = SR.has(player, SR.ARCHAEOLOGIST)
    for c in sorted(cells):
        bonus = mapdef.cells[c].bonus
        if bonus:
            out.append({"k": f"bonus:{bonus}", "n": 2 if twice and mapdef.is_border(c) else 1})
    if kind == "pavilion":
        out.append({"k": "appeal", "n": 1})
    if not player.full_cover_scored:
        covered = set(zoo.cell_owner) | cells
        if all(c in covered for c in mapdef.buildable_cells()):
            out.append({"k": "full_cover", "n": T.FULL_COVER_APPEAL})
    near = {zoo.cell_owner[n] for c in cells for n in neighbors(c) if n in zoo.cell_owner}
    near = [zoo.buildings[i] for i in sorted(near)]
    if kind == "kiosk":
        income = sum(1 for b in near if _feeds_kiosk(b.kind, b.occupied))
    elif _feeds_kiosk(kind):
        income = sum(1 for b in near if b.kind == "kiosk")
    else:
        income = 0
    if income:
        out.append({"k": "kiosk_income", "n": income})
    for card_id, terrain in (("241", "water"), ("242", "rock")):
        if card_id in player.zoo_cards:
            n = sum(1 for c in cells if any(m in mapdef.cells and mapdef.cells[m].terrain == terrain
                                            for m in neighbors(c)))
            if n:
                out.append({"k": f"next_to_{terrain}", "n": n})
    special = state.map.get("special") or {}
    spot = lambda name: {tuple(c) for c in special.get(name, [])}
    touches = lambda target: any(n in target for c in cells for n in neighbors(c))
    covers_new = lambda target: bool(cells & target) and not any(c in zoo.cell_owner for c in target)
    if state.map_name == "plan1" and kind == "enclosure" and touches(spot("observation_tower")):
        out.append({"k": "tower", "n": 2})
    if state.map_name == "plan2" and kind == "enclosure" and touches(spot("outdoor_area")):
        out.append({"k": "outdoor", "n": 2})
    if state.map_name == "plan4" and covers_new(spot("harbor_connecting_building_space")):
        out.append({"k": "harbour", "n": 3})
    if state.map_name == "plan5":
        n = sum(1 for r in spot("park_restaurant") for c in neighbors(r) if c in cells)
        if n:
            out.append({"k": "restaurant_income", "n": n})
    if state.map_name == "plan6" and covers_new(spot("institute_connecting_building_space")):
        out.append({"k": "institute", "n": 1})
    if state.map_name == "plan7":
        parlours = spot("kiosk_bonus")
        kiosks = zoo.count("kiosk") + (kind == "kiosk")
        done_before = all(c in zoo.cell_owner for c in parlours)
        if parlours and not done_before and all(c in zoo.cell_owner or c in cells for c in parlours):
            out.append({"k": "ice_cream_income", "n": kiosks})
        elif parlours and done_before and kind == "kiosk":
            out.append({"k": "ice_cream_income", "n": 1})
    if state.map_name == "plan8":
        hills = spot("H")
        n = len(cells & hills)
        if n:
            out.append({"k": "hollywood", "n": n})
            if all(c in zoo.cell_owner or c in cells for c in hills):
                out.append({"k": "hollywood_all", "n": 1})
    return out


UPGRADE_DETAIL = {
    "animals": "Side II: play 1 more animal at strengths 1, 3 and 4, gain 1 reputation first at strength 5, play from the display in reputation range (paying its folder number extra), and play animals that need Animals II.",
    "build": "Side II: several different buildings per action (total size up to the strength), Build II spaces, the reptile house and the aviary.",
    "cards": "Side II: draw more per strength, take from the display in reputation range, snap from strength 3, and reputation above 9.",
    "association": "Side II: several different tasks per action (total strength), one donation, and partner zoos 3 and 4.",
    "sponsors": "Side II: sponsors with total level up to strength + 1, from the display in reputation range, double money when you break, and cards that need Sponsors II.",
}


def _slot_bonus(effects):
    if not effects:
        return ""
    words = ", ".join(effect_label(k, a) for k, a in effects)
    return i18n.tr("detail.slotBonus", " This slot also gives: {bonus}.", bonus=words)


SUPPORT_KINDS = ("support", "release", "play_project", "play_release", "play_project_display", "play_release_display")


def _needs(requirement, n):
    if requirement == "all-animals":
        what = i18n.tr("detail.allAnimals", "different animal categories")
    elif requirement == "all-continents":
        what = i18n.tr("detail.allContinents", "different continents")
    else:
        what = i18n.tr("detail.icons", "{name} icons", name=i18n.term("icons", requirement, requirement.capitalize()))
    return i18n.tr("detail.needs", "needs {n} {what}", n=n, what=what)


def _support_detail(state, key):
    """What supporting a project gives: the slot's reward (and what it needs) and the map token you take."""
    kind, ref, position, token = key[:4]
    pid = state.display[ref] if kind.endswith("_display") and isinstance(ref, int) and ref < len(state.display) else ref
    try:
        project = C.card(pid)
    except Exception:
        return None
    slot = next((x for x in project.get("slots", []) if x["position"] == position), None)
    if slot is None:
        return None
    gains = ", ".join(effect_label(r["reward"], r["amount"]) for r in slot["rewards"])
    text = i18n.tr("detail.slotGives", "This slot: {gains}", gains=gains)
    if slot.get("required"):
        needs = _needs(slot['rewards'][0].get('requirement') or project.get('icon'), slot['required'])
        text += f"（{needs}）" if i18n.is_zh() else f" ({needs})"
    tokens = state.map["tokens"]
    if isinstance(token, int) and 0 <= token < len(tokens):
        effects, repeats = tokens[token]
        bonus = ", ".join(effect_label(k, a) for k, a in effects)
        text += i18n.tr("detail.mapToken", ". Map token you take: {bonus}", bonus=bonus)
        if repeats:
            text += i18n.tr("detail.everyBreak", ", and again every break")
    return text + ("。" if i18n.is_zh() else ".")


def _detail(state, key):
    """One sentence on what a choice does, when its label alone does not say (upgrades, partner zoos,
    universities)."""
    if not state.stack:
        return None
    player = state.players[state.stack[-1].player]
    kind = key[0]
    if kind == "upgrade" and len(key) > 1 and key[1] in UPGRADE_DETAIL:
        return i18n.tr(f"detail.upgrade.{key[1]}", UPGRADE_DETAIL[key[1]])
    if kind == "partner_zoo" and len(key) > 1:
        slots = state.map["partner_zoo_slots"]
        n = len(player.partner_zoos)
        continent = i18n.term("icons", key[1], key[1].capitalize())
        text = i18n.tr("detail.partnerZoo", "Animals from {continent} cost {discount} less, and it counts as one {continent} icon.",
                       continent=continent, discount=T.PARTNER_ZOO_DISCOUNT)
        return text + (_slot_bonus(slots[n]) if n < len(slots) else "")
    if kind in SUPPORT_KINDS and len(key) > 3:
        return _support_detail(state, key)
    if kind == "university":
        slots = state.map["university_slots"]
        n = len(player.universities)
        bonus = _slot_bonus(slots[n]).strip() if n < len(slots) else ""
        return bonus or None
    return None


def _home_name(state, key):
    """The building an animal play goes into, in words ("the size-2 enclosure", "the petting zoo (0/3 used)")."""
    zoo = state.players[state.stack[-1].player].zoo
    b = zoo.buildings[key[2]]
    if b.kind == "enclosure":
        return i18n.tr("detail.enclosureName", "the size-{size} enclosure", size=b.capacity)
    name = i18n.term("buildings", b.kind, b.kind.replace("_", " "))
    return i18n.tr("detail.specialName", "the {name} ({used}/{capacity} used)", name=name, used=b.used, capacity=b.capacity)


def option(i, o, analysis, state=None, frame_kind=None):
    key = o.key
    label = nicer(clean_label(o), key)
    shown = _display_card(state, key, frame_kind) if state is not None else None
    if shown is not None and (key[0] in ("display", "snap") or (frame_kind == "ab_snap" and key[0] == "take")):
        if i18n.is_zh():
            verb = "精选" if frame_kind == "ab_snap" or key[0] == "snap" else "拿取"
            label = f"{verb}展示卡位 {key[1] + 1} 的卡牌"
        else:
            verb = "Snap" if frame_kind == "ab_snap" or key[0] == "snap" else "Take"
            label = f"{verb} the card in display slot {key[1] + 1}"
    if (state is not None and state.stack and key[0] in ("play", "play_display") and len(key) > 2
            and isinstance(key[2], int) and 0 <= key[2] < len(state.players[state.stack[-1].player].zoo.buildings)):
        home = _home_name(state, key)
        label = re.sub(r"into building \d+", f"into {home}", label)
        label = re.sub(r"放入建筑 \d+", f"放入{' ' if home[:1].isdigit() else ''}{home}", label)
    if key[0] in SUPPORT_KINDS and len(key) > 3 and isinstance(key[3], int):  # map tokens count from 1 for people
        label = re.sub(r"token \d+", f"map token {key[3] + 1}", label)
        label = re.sub(r"标记 \d+", f"地图标记 {key[3] + 1}", label)
    out = {"index": i, "label": label, "key": [str(k) if isinstance(k, tuple) else k for k in key],
           "cards": _cards_in(key) + ([shown] if shown is not None else [])}
    about = _action_in(key, clean_label(o))
    if about and key[0] not in ("act", "xtoken"):
        out["action"] = about
    cells = _cells_in(key)
    if cells:
        out["cells"] = cells
    if key[0] == "act":
        out.update(type="act", action=key[1], x=key[2])
    elif key[0] == "xtoken":
        out.update(type="xtoken", action=key[1])
    elif key[0] == "keep":
        out.update(type="keep")
    elif cells:
        # A sponsor card's own building has no kind in its key: it is the "unique" one, drawn by its cells.
        out.update(type="place", building=key[1] if len(key) == 4 else "unique",
                   size=key[2] if len(key) == 4 and isinstance(key[2], int) else None)
        if state is not None and state.stack:
            out["gains"] = place_preview(state, state.stack[-1].player, out["building"], cells)
    else:
        out["type"] = key[0]
    if state is not None:
        detail = _detail(state, key)
        if detail:
            out["detail"] = detail
    if analysis is not None:
        out["ai_prob"] = analysis.probs[i]
    return out


def decision(game, hints=True):
    state = game.state
    if state.over or game.turn_done:
        return None
    frame = state.stack[-1]
    options = game.options()
    a = game.analysis if hints and game.to_move() == game.human else None  # no hints: no AI numbers at all
    out = {"player": frame.player, "kind": frame.kind, "title": title(frame.kind),
           "options": [option(i, o, a, state, frame.kind) for i, o in enumerate(options)]}
    if frame.kind == "ab_hunter":
        out["revealed_cards"] = [card(c) for c in frame.data["cards"]]
    # Cards named by the options that are not on the board (drawn to choose from, revealed): the
    # board needs them to draw the option's icon and card chip.
    named = dict.fromkeys(c for o in out["options"] for c in o["cards"])
    if frame.kind == "ab_hunter":
        named.update(dict.fromkeys(frame.data["cards"]))
    out["cards"] = [card(c) for c in named]
    if frame.kind == "act_cards":  # say the rule: draw N (then discard), or snap one, not both
        d = frame.data
        left, snap = d["draw"] - d["drawn"], d["may_snap"] and d["drawn"] == 0
        text = i18n.tr("note.cardsToDraw", "Cards to draw: {count}", count=left)
        if d["discard"]:
            text += i18n.tr("note.thenDiscard", ", then discard {count}", count=d["discard"])
        if snap:
            text += i18n.tr("note.orSnap", ". Or snap 1 card from the display instead; snapping is only possible before you draw, and it ends the action")
        out["note"] = text
    if frame.kind == "take_card":  # each card to take is its own frame: count the ones queued for this player
        out["remaining"] = 0
        for f in reversed(state.stack):
            if f.kind != "take_card" or f.player != frame.player:
                break
            out["remaining"] += 1
        out["pick"] = {"count": out["remaining"]}
    elif frame.kind == "conservation_tile":
        out["note"] = i18n.tr(
            "note.conservationReward",
            "You crossed a conservation track threshold. Choose a bonus tile or take the money alternative.",
        )
    elif frame.kind == "discard_hand":  # down to the hand limit, or a fixed number of cards
        limit = frame.data.get("limit")
        need = len(state.players[frame.player].hand) - limit if limit is not None else frame.data.get("count", 1)
        out["pick"] = {"count": max(1, need)}
        if limit is not None and any(f.kind == "break" for f in state.stack):  # not your action's discard
            out["title"] = i18n.tr("decisionTitles.breakDiscard", "Break: discard down to your hand limit")
            out["note"] = i18n.tr("note.breakDiscard",
                                  "The break was reached, so everyone discards down to their hand limit ({limit}). "
                                  "This comes after the AI's turn, so Undo also takes that turn back.",
                                  limit=limit)
    if frame.kind == "setup_keep":
        out["keep_from"] = sorted({c for o in options for c in o.key[1:]})
        out["keep_count"] = len(options[0].key) - 1
    if a is not None and a.extra.get("heuristic"):  # a rule policy: its choice, no odds or win chance
        out["ai"] = {"best": a.best, "rule": True}
    elif a is not None:
        out["ai"] = {"best": a.best, "value": a.value, "win_chance": round(win_chance(a.value), 3)}
    return out


def effect_label(kind, amount):
    """A track or tile reward in words ("2 workers", "upgrade an action")."""
    en = {
        "xtoken": "{count} X-token" if amount == 1 else "{count} X-tokens",
        "worker": "{count} worker" if amount == 1 else "{count} workers",
        "card": "{count} card" if amount == 1 else "{count} cards",
        "enclosure": "size-{count} enclosure", "money": "{count} money", "appeal": "{count} appeal",
        "conservation": "{count} conservation", "reputation": "{count} reputation",
        "upgrade": "upgrade an action", "clever": "move an action card to strength 1",
        "kiosk": "a kiosk" if amount == 1 else "{count} kiosks",
        "special_enclosure": "a reptile house or aviary", "multiplier": "a multiplier token",
        "partner_zoo": "a partner zoo", "university": "a university",
        "sponsor_for_money": "play a sponsor for its level",
    }
    camel = {"xtoken": "xToken", "special_enclosure": "specialEnclosure", "sponsor_for_money": "sponsorForMoney",
             "partner_zoo": "partnerZoo"}
    template = en.get(kind, kind + " {count}")
    return i18n.tr(f"trackEffects.{camel.get(kind, kind)}", template, count=amount, size=amount)


def _effects(effects):
    return [{"kind": k, "amount": a, "label": effect_label(k, a)} for k, a in effects]


_UNIVERSITY = {
    "hand": ("Hand limit", "Hand limit 5, plus 1 reputation"),
    "science2": ("Science", "2 science icons"),
    "science_rep": ("Science and reputation", "1 science icon and 2 reputation"),
}
_UNIVERSITY_ZH = {"hand": ("手牌上限", "手牌上限 5，并获得 1 声望"), "science2": ("研究", "2 个研究图标"),
                  "science_rep": ("研究与声望", "1 个研究图标和 2 声望")}


def _university(uid):
    return (_UNIVERSITY_ZH if i18n.is_zh() else _UNIVERSITY).get(uid, (uid, ""))


def _association(state):
    """The association board: the tasks with their strength, every partner zoo and university with its owner,
    the donation track, and per player the workers out on each task and what the next use would take."""
    from arknova.actions import association as AS
    costs = T.DONATION_COSTS[state.n]
    owners = lambda attr, x: [p.idx for p in state.players if x in getattr(p, attr)]
    return {
        "tasks": [{"task": k, "strength": v} for k, v in T.TASK_VALUE.items()],
        "partner_zoos": [{"id": c, "owners": owners("partner_zoos", c), "available": c in state.partner_zoos_available}
                         for c in T.CONTINENTS],
        "universities": [{"id": u, "name": _university(u)[0], "grant": _university(u)[1], "owners": owners("universities", u),
                          "available": u in state.universities_available} for u in T.UNIVERSITIES],
        "donations": {"costs": costs, "final": T.DONATION_FINAL_COST, "made": state.donations,
                      "next": costs[state.donations] if state.donations < len(costs) else T.DONATION_FINAL_COST},
        "players": [{"idx": p.idx, "out": {k: p.workers_out.get(k, 0) for k in T.TASK_VALUE},
                     "next": {k: AS._workers_needed(p, k) for k in T.TASK_VALUE}, "active": p.active_workers}
                    for p in state.players],
    }


def tracks(state, initial_bonus_tiles=None, reward_claims=()):
    """Reward tracks for the board beside the map. Stops are the whole printed track; `players`
    says where each marker is and which map tokens are still on the left edge."""
    board = state.map
    stops = [{"at": T.CONSERVATION_UPGRADE_OR_WORKER, "kind": "upgrade_or_worker",
              "label": i18n.tr("trackEffects.upgradeOrWorker", "Upgrade an action card or gain a worker")}]
    for space in T.CONSERVATION_TILE_SPACES:
        claims = [c for c in reward_claims if c["space"] == space]
        names = list(state.bonus_tiles.get(space, []))
        tiles = [{"id": n, "effects": _effects(T.BONUS_TILES.get(n, []))} for n in names]
        choices = [{"id": n, "effects": _effects(T.BONUS_TILES.get(n, [])), "available": n in names,
                    "claimed_by": [c["player"] for c in claims if c["choice"] == n]}
                   for n in (initial_bonus_tiles or state.bonus_tiles).get(space, [])]
        money_label = effect_label("money", T.CONSERVATION_TILE_MONEY)
        label = i18n.tr("tracks.bonusTileOrMoney", "A bonus tile, or {money}", money=money_label) if names else money_label
        stops.append({"at": space, "kind": "tile", "label": label, "tiles": tiles, "choices": choices,
                      "money": T.CONSERVATION_TILE_MONEY,
                      "money_claimed_by": [c["player"] for c in claims if c["choice"] == "money"]})
    stops.append({"at": T.CONSERVATION_FINAL_CARD_DISCARD, "kind": "final_discard",
                  "label": i18n.tr("trackEffects.discardFinalCard", "Discard a final scoring card"),
                  "spent": bool(state.final_card_discarded)})
    zoo_slots = []
    for i, fx in enumerate(board["partner_zoo_slots"][:T.MAX_PARTNER_ZOOS]):
        eff = _effects(fx)
        zoo_slots.append({"slot": i + 1, "effects": eff, "label": ", ".join(e["label"] for e in eff) or i18n.tr("trackEffects.noSlotBonus", "No slot bonus")})
    uni_slots = []
    for i, fx in enumerate(board["university_slots"]):
        eff = _effects(fx)
        uni_slots.append({"slot": i + 1, "effects": eff, "label": ", ".join(e["label"] for e in eff) or i18n.tr("trackEffects.noSlotBonus", "No slot bonus")})
    available_uni = []
    for uid in T.UNIVERSITIES:
        if uid in state.universities_available:
            name, grant = _university(uid)
            available_uni.append({"id": uid, "name": name, "grant": grant})
    edge = []
    for i, (fx, repeats) in enumerate(board["tokens"]):
        eff = _effects(fx)
        edge.append({"index": i, "repeats": bool(repeats), "effects": eff,
                     "label": ", ".join(e["label"] for e in eff) or i18n.tr("trackEffects.bonusNotConfirmed", "Bonus not confirmed")})
    return {
        "conservation": {"max": T.CONSERVATION_FINAL_CARD_DISCARD, "stops": stops},
        "reputation": {
            "max": T.REPUTATION_MAX, "gate": T.REPUTATION_CAP_WITHOUT_CARDS_II,
            "stops": [{"at": space, "kind": bonus, "label": effect_label(bonus, 1)}
                      for space, bonus in sorted(T.REPUTATION_BONUS.items())],
        },
        "partner_zoos": {
            "max": len(zoo_slots), "slots": zoo_slots, "available": sorted(state.partner_zoos_available),
            "association_from": 3, "discount": T.PARTNER_ZOO_DISCOUNT,
        },
        "universities": {"max": len(uni_slots), "slots": uni_slots, "available": available_uni},
        "workers": {"max": T.MAX_WORKERS, "last": _effects(board["last_worker"])},
        "association": _association(state),
        "tokens": edge,
        "players": [{
            "idx": p.idx, "conservation": p.conservation, "reputation": p.reputation,
            "cards_ii": "cards" in p.upgraded, "association_ii": "association" in p.upgraded,
            "partner_zoos": len(p.partner_zoos), "universities": len(p.universities), "workers": p.workers,
            "on_map": [bool(flag) for flag in p.tokens[:len(edge)]],
        } for p in state.players],
    }


def loc(label):
    """A move text kept in English (records, the AI's moves, what you played) in the request's language."""
    return i18n.option_label(label, ("",)) if i18n.is_zh() else label


def _who(p, me):
    return "you" if p == me else "ai"


def _why(cause):
    """A cause recorded by the engine (see feed.py) in words."""
    if not cause:
        return None
    kind = cause[0]
    if kind == "move":
        text = re.sub(r" at \(\(.*?\)(,\)|\))", "", cause[2])  # the map shows where
        return loc(text) if i18n.is_zh() else readable(text)
    if kind == "build":
        if cause[1] == "pavilion":
            return i18n.tr("feed.pavilion", "A pavilion is built")
        return i18n.tr("feed.fullCover", "Every space of the map is covered")
    if kind == "placement":
        return i18n.tr("feed.placementBonus", "Covered a map space with a bonus")
    if kind == "break":
        return i18n.tr("feed.breakReached", "Reached the end of the break track")
    if kind in ("ability", "card"):
        name = card_name(C.card(cause[1]))
        if kind == "ability":
            return i18n.tr("feed.whenPlayed", "{card}, when played", card=name)
        return i18n.tr("feed.passive", "{card}, each time it triggers", card=name)
    if kind == "income":
        what = cause[1]
        if what == "appeal":
            return i18n.tr("feed.incomeAppeal", "Break income from appeal and kiosks")
        if what == "token":
            return i18n.tr("feed.incomeToken", "Break income from map tokens")
        if what == "map":
            return i18n.tr("feed.incomeMap", "Break income from the map")
        return i18n.tr("feed.incomeCard", "{card}: break income", card=card_name(C.card(what)))
    if kind == "track":
        return i18n.tr("feed.reputationStop", "Reached reputation {n}", n=cause[2])
    return None


def _note(item, me):
    what, detail, p = item["note"], item.get("d"), item["p"]
    who = i18n.tr("feed.you", "You") if p == me else i18n.tr("feed.ai", "The AI")
    if what == "break_triggered":
        return "break", i18n.tr("feed.breakTriggered", "{who} reached the end of the break track: a break is coming", who=who)
    if what == "break_begins":
        return "break", i18n.tr("feed.breakBegins", "Break: anyone above the hand limit discards down to it")
    if what == "break_reset":
        return "break", i18n.tr("feed.breakReset", "Break: the first two display cards are replaced, workers return, partner zoos and universities open again; income follows")
    if what == "break_track":
        return "info", i18n.tr("feed.breakTrack", "Break track {pos}/{max}", pos=detail[0], max=detail[1])
    if what == "conservation_stop":
        return "info", i18n.tr("feed.conservationStop", "{who} reached conservation {n}: a reward is available", who=who, n=detail)
    return "info", what


def feed_lines(entries, me):
    """Feed entries (feed.py) as board lines: who, what changed, and the reason."""
    out = []
    for e in entries or []:
        if "note" in e:
            kind, text = _note(e, me)
            out.append({"note": kind, "text": text,
                        **({"why": _why(e["c"])} if e["note"] == "break_triggered" and e.get("c") else {})})
        else:
            n = e["n"]
            out.append({"who": _who(e["p"], me), "kind": e["k"], "amount": n, "text": effect_label(e["k"], abs(n)),
                        "why": _why(e["c"])})
    return out


def board(game, lang=None, hints=True):
    """The whole board as JSON, with text in `lang` ("zh-CN" or English by default). Without `hints`
    nothing of the AI's evaluation is included (its odds, win chance, how your moves compared)."""
    token = i18n.use(lang)
    try:
        return _board(game, hints)
    finally:
        i18n.reset(token)


def _records(records):
    name = lambda raw: _named(raw)[0]  # noqa: E731
    return [{**{k: v for k, v in r.items() if k != "feed"}, "chose": name(r["chose"]), "ai_best": name(r["ai_best"]),
             "top": [{**t, "label": name(t["label"])} for t in r["top"]]} for r in records]


SECRET_DISCARDS = {"discard_hand", "discard_final"}  # what the AI throws away stays hidden from you


def _named(raw):
    """A label with card numbers turned into names (the Chinese labels already have them), and those cards."""
    ids = [n for n in re.findall(r"\b\d{3}\b", raw) if n in C.all_cards()]
    if i18n.is_zh():
        return loc(raw), ids
    return readable(raw), ids


def _ai_move(move, hints, me, actor="ai"):
    raw = move["label"]
    secret = move["kind"] in SECRET_DISCARDS or re.match(r"Discard (?!display folder)", raw)  # also e.g. "Discard X and draw"
    if actor == "ai" and secret:
        shown, named = i18n.tr("move.aiDiscard", "Discard a card"), []
    else:  # the cards go along for the pop-up
        shown, named = _named(raw)
    return {
        **{k: v for k, v in move.items() if k != "feed"},
        "label": shown,
        "cards": [card(c) for c in named],
        "title": title(move["kind"]),
        **({} if hints else {"prob": None}),
        "feed": feed_lines(move.get("feed"), me),
    }


def activity_history(game, hints=True):
    """Both sides' turns, including the human's current partial turn and saved decisions."""
    human_turns = {}
    for record, point in zip(game.records, game.undo_stack):
        turn = point["turn"] + 1
        human_turns.setdefault(turn, []).append(_ai_move({
            "kind": record["kind"], "label": record["chose"], "prob": None,
            "feed": record.get("feed", []),
        }, hints, game.human, "you"))
    turns = [{"turn": turn, "actor": "you", "moves": moves} for turn, moves in human_turns.items()]
    turns += [{"turn": entry["turn"], "actor": "ai",
               "moves": [_ai_move(move, hints, game.human) for move in entry["moves"]]}
              for entry in game.ai_history]
    return sorted(turns, key=lambda entry: (entry["turn"], entry["actor"] == "ai"))


def _display_slot(state, me, i, c):
    """A display folder: its card, whether your reputation reaches it (to take it with Cards II or play it
    with the upgraded Animals, Sponsors or Association action for its folder number in money), and otherwise the reputation it needs
    (only a Snap takes it then)."""
    folder = i + 1
    reach = i < T.reputation_folders(state.players[me].reputation)
    status = readiness(state, me, c, extra_cost=folder, display=True) if c is not None else None
    if status is not None and not reach:
        status = {**status, "ready": False, "unmet": ["reach"],
                  "why": i18n.tr("readiness.outOfReach", "Out of reach: needs reputation {rep} (a Snap can still take it)",
                                 rep=T.folder_reputation(folder))}
    return {"folder": folder, "card": card(c), "in_reach": reach, "reach_reputation": T.folder_reputation(folder),
            "status": status}


def _board(game, hints=True):
    state = game.state
    options = [] if state.over else game.options()
    me = game.human
    projects = [{"card": card(c), "tokens": {str(k): v for k, v in state.project_tokens.get(c, {}).items()},
                 "base": c in state.base_projects} for c in state.base_projects + state.projects]
    return {
        "seed": game.seed, "map": game.map_name, "human": me, "ai_name": game.ai.name,
        "over": state.over, "scores": state.scores,
        # your_decision: the human chooses; end_turn: the human's turn is over, waiting for End turn;
        # over: game finished.
        "phase": "over" if state.over else "end_turn" if game.turn_done else "your_decision",
        "winners": G.winners(state) if state.over else None,
        "break": {"pos": state.break_pos, "max": T.BREAK_TRACK[state.n]}, "deck": len(state.deck), "discard": len(state.discard),
        "display": [_display_slot(state, me, i, c) for i, c in enumerate(state.display)],
        "projects": projects,
        "tracks": tracks(state, game.initial_bonus_tiles, game.reward_claims),
        "players": [player(state, p, me, options) for p in range(state.n)],
        "can_hint": hints, "hint_model": game.hint_name or "default",
        "decision": decision(game, hints),
        "ai_moves": [_ai_move(m, hints, me) for m in game.ai_moves],
        "ai_history": [
            {"turn": turn["turn"], "moves": [_ai_move(m, hints, me) for m in turn["moves"]]}
            for turn in game.ai_history
        ],
        "activity_history": activity_history(game, hints),
        "turn_feed": feed_lines([e for r in game.turn_records() for e in r.get("feed", [])], me),
        "records": _records(game.records) if hints else [{"move": r["move"], "kind": r["kind"]} for r in game.records],
        "can_undo": bool(game.undo_stack),
        "can_redo": bool(game.redo_stack),
        "can_restart_turn": game.turn_points() > 0,
        "undo_leaves_turn": game.undo_leaves_turn(),
        "turn_log": [loc(re.sub(r" at \(\(.*?\)(,\)|\))", "", line.split(": ", 1)[-1])) for line in game.turn_log()],
        "log": [m for m in (state.log or []) if not m.startswith(f"P{1 - me} setup_keep")][-40:],
    }
