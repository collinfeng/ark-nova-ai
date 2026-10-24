"""Zoo maps other than Map 0, loaded from the transcriptions in data/maps/<plan>.json.

Each transcription gives the 58-space layout (terrain, placement bonuses, Build II spaces), the
special-site cells, the side-panel bonuses (partner zoo slots, university slots, last worker) and the
seven left-edge tokens. Maps are registered under their file name ("plan1" ... "plan8", "plana") in
engine.MAP_DEFS (layout) and tables.MAPS (everything else), next to "map0".

The maps' special rules (observation tower, harbour, ...) live in map_rules.py; MAP_RULES lists them.
"""
import json
import re
from pathlib import Path

from . import tables as T
from .hexmap import Cell, MapDef

DATA = Path(__file__).resolve().parent.parent / "data" / "maps"

# Placement bonuses that appear on maps 1-8 and A in addition to Map 0's.
EXTRA_PLACEMENT_BONUS = {
    "money2": [("money", 2)], "rep1": [("reputation", 1)], "kiosk": [("kiosk", 1)], "worker1": [("worker", 1)],
    "partner_zoo": [("partner_zoo", 1)], "university": [("university", 1)], "multiplier": [("multiplier", 1)],
    "sponsor_for_money": [("sponsor_for_money", 1)],
}

# Effect names in the transcriptions -> engine effect kinds.
EFFECT_NAMES = {
    "card": "card", "money": "money", "xtoken": "xtoken", "worker": "worker", "upgrade": "upgrade",
    "upgrade_PROBABLE": "upgrade",  # Map 3's rotate-card token; read as an upgrade, not confirmed
    "conservation": "conservation", "reputation": "reputation", "rep": "reputation", "clever": "clever",
    "enclosure": "enclosure", "enclosure_size": "enclosure", "partner_zoo": "partner_zoo",
    "university": "university", "multiplier": "multiplier", "sponsor_for_money": "sponsor_for_money",
    "free_special_enclosure_choice_of_2": "special_enclosure",
}
UNKNOWN_EFFECTS = {"animal_silhouette_2_UNKNOWN"}  # Map 7's purple token: meaning not found; no effect

# Special rules of each map; all of them are implemented in map_rules.py (see docs/RULES_NOTES.md, "Maps 1-8").
MAP_RULES = {
    "plan1": "observation tower: +2 appeal when an adjacent standard enclosure becomes occupied",
    "plan2": "outdoor area: adjacent standard enclosures count as 2 spaces larger",
    "plan3": "none beyond the layout",
    "plan4": "commercial harbour: once connected, once per turn discard a hand card for 3 money (any decision of your turn)",
    "plan5": "park restaurant: break income 1 money per covered space adjacent to it",
    "plan6": "research institute: once connected, ignore 1 condition when playing an animal",
    "plan7": "ice cream parlours: all kiosk bonus spaces covered -> +1 money income per kiosk",
    "plan8": "Hollywood Hills: covering an H takes the first sponsor revealed; all 3 covered -> sponsors 1 level cheaper",
    "plana": "none beyond the pre-built kiosk and enclosure",
}
MAP_RULES_TODO = {}  # nothing left to implement


def _effect(name, amount):
    if name in UNKNOWN_EFFECTS:
        return []
    match = re.fullmatch(r"([a-zA-Z_]+?)_?(\d+)", name) if amount is None else None
    if match and match.group(1) in EFFECT_NAMES:
        name, amount = match.group(1), int(match.group(2))
    if name not in EFFECT_NAMES:
        raise ValueError(f"unknown map effect {name!r}")
    return [(EFFECT_NAMES[name], 1 if amount is None else int(amount))]


def parse_effects(entry):
    """Normalise the reviewers' formats: "none", "upgrade1", ["card1"], ["card", 1], [["card", 1]],
    {"upgrade": 1}, [{"upgrade": 1}] -> [(kind, amount), ...]."""
    if entry in (None, "none", "", []):
        return []
    if isinstance(entry, str):
        return _effect(entry, None)
    if isinstance(entry, dict):
        return [e for k, v in entry.items() for e in _effect(k, v)]
    if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str) and isinstance(entry[1], int):
        return _effect(entry[0], entry[1])
    if isinstance(entry, list):
        return [e for item in entry for e in parse_effects(item)]
    raise ValueError(f"cannot read map effect {entry!r}")


def _axial(col, row):
    return (col, row - (col + 1) // 2)


def load(name):
    """(MapDef, board dict for tables.MAPS) for data/maps/<name>.json."""
    data = json.loads((DATA / f"{name}.json").read_text())
    columns = data["columns"]
    if [len(c) for c in columns] != [6, 7, 6, 7, 6, 7, 6, 7, 6]:
        raise ValueError(f"{name}: unexpected column lengths")
    cells = {}
    for col, tokens in enumerate(columns):
        for row, token in enumerate(tokens):
            terrain = {"W": "water", "R": "rock"}.get(token.split(":")[0], "plain")
            bonus = token[2:] if token.startswith(".:") and token != ".:build2" else None
            cells[_axial(col, row)] = Cell(terrain, bonus, token == ".:build2")
    specials = {}
    for entry in data.get("special", []) + data.get("special_spaces", []):
        if isinstance(entry, dict):
            specials.setdefault(entry["name"], []).extend(_axial(c, r) for c, r in entry.get("cells", []))
    for c in specials.get("build2_with_money2", []):  # Map 3: Build II spaces that also pay 2 money
        cells[c] = Cell("plain", "money2", True)
    tokens = []
    for effects, repeats in data["tokens"]:
        tokens.append((parse_effects(effects), bool(repeats)))
    board = {
        "partner_zoo_slots": [parse_effects(e) for e in data["partner_zoo_slots"]],
        "university_slots": [parse_effects(e) for e in data["university_slots"]],
        "last_worker": parse_effects(data["last_worker"]),
        "tokens": tokens,
        "special": specials,
        "name": data.get("name", name),
        "prebuilt": [("kiosk", 1, specials.get("prebuilt_kiosk", [])),
                     ("enclosure", 3, specials.get("prebuilt_enclosure_size3", []))] if name == "plana" else [],
    }
    for bonus in {cell.bonus for cell in cells.values() if cell.bonus}:
        if bonus not in T.PLACEMENT_BONUS and bonus not in EXTRA_PLACEMENT_BONUS:
            raise ValueError(f"{name}: unknown placement bonus {bonus!r}")
    return MapDef(data.get("name", name), cells), board


def available():
    return sorted(p.stem for p in DATA.glob("*.json"))


def register(map_defs):
    """Add every transcribed map to engine.MAP_DEFS (passed in) and tables.MAPS."""
    T.PLACEMENT_BONUS.update(EXTRA_PLACEMENT_BONUS)
    for name in available():
        mapdef, board = load(name)
        map_defs[name] = mapdef
        T.MAPS[name] = board
