"""Build data/cards.json from the raw Ender-Wiggin card-site sources.

The raw files are TypeScript object literals. They are parsed here as data
(never executed): enum members are resolved from src/types, `new Ability(...)`
and `new SpecialEnclosure(...)` become plain dicts, and i18n keys are resolved
against the English locale.

Usage: python3 tools/build_cards.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ender-wiggin"
OUT = ROOT / "data" / "cards.json"

TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`)
  | (?P<num>-?\d+(?:\.\d+)?)
  | (?P<id>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)
  | (?P<punct>[{}\[\](),:;])
    """,
    re.S | re.X,
)


def tokenize(src):
    pos, out = 0, []
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise SyntaxError("unexpected %r at %d" % (src[pos : pos + 30], pos))
        pos = m.end()
        if m.lastgroup != "ws":
            out.append((m.lastgroup, m.group()))
    return out


def unquote(s):
    body = s[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)


class Parser:
    """Recursive-descent parser for the JS literal subset used by the data files."""

    def __init__(self, tokens, enums):
        self.t, self.i, self.enums = tokens, 0, enums

    def peek(self):
        return self.t[self.i]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expect(self, val):
        tok = self.next()
        if tok[1] != val:
            raise SyntaxError("expected %r, got %r (token %d)" % (val, tok[1], self.i))

    def value(self):
        kind, val = self.next()
        if kind == "str":
            return unquote(val)
        if kind == "num":
            return float(val) if "." in val else int(val)
        if val == "{":
            obj = {}
            while self.peek()[1] != "}":
                k = self.next()
                key = unquote(k[1]) if k[0] == "str" else k[1]
                self.expect(":")
                obj[key] = self.value()
                if self.peek()[1] == ",":
                    self.next()
            self.next()
            return obj
        if val == "[":
            return self.sequence("]")
        if kind == "id":
            if val in ("true", "false", "null", "undefined"):
                return {"true": True, "false": False}.get(val)
            if val == "new":
                cls = self.next()[1]
                self.expect("(")
                return {"__new__": cls, "args": self.sequence(")")}
            return self.resolve(val)
        raise SyntaxError("unexpected token %r (token %d)" % (val, self.i))

    def sequence(self, close):
        items = []
        while self.peek()[1] != close:
            items.append(self.value())
            if self.peek()[1] == ",":
                self.next()
        self.next()
        return items

    def resolve(self, ref):
        head, _, member = ref.partition(".")
        if head in self.enums and member in self.enums[head]:
            return self.enums[head][member]
        return {"__ref__": ref}


def load_enums():
    enums = {}
    for path in sorted((RAW / "src" / "types").glob("*.ts")):
        for m in re.finditer(r"export enum (\w+) \{(.*?)\n\}", path.read_text(), re.S):
            members = {}
            for mm in re.finditer(r"(\w+)\s*=\s*('(?:\\.|[^'])*'|\"[^\"]*\")", m.group(2)):
                members[mm.group(1)] = unquote(mm.group(2))
            enums[m.group(1)] = members
    return enums


def load_keywords(enums):
    """KeyWord.X -> (display name, i18n description key)."""
    src = (RAW / "src" / "types" / "KeyWords.ts").read_text()
    out = {}
    for m in re.finditer(r"static (\w+) = new KeyWord\(\s*([^,]+),\s*'([^']+)'", src):
        name = m.group(2).strip()
        if name.startswith("IconName."):
            name = enums["IconName"][name.split(".", 1)[1]]
        else:
            name = unquote(name)
        out[m.group(1)] = (name, m.group(3))
    return out


def load_array(rel, const, enums):
    src = (RAW / rel).read_text()
    m = re.search(r"export const %s\b[^=]*=\s*" % const, src)
    p = Parser(tokenize(src[m.end() :]), enums)
    return p.value()


class Locale:
    def __init__(self):
        self.d = json.loads((RAW / "public/locales/en/common.json").read_text())
        self.missing = []

    def get(self, key):
        node = self.d
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                self.missing.append(key)
                return None
            node = node[part]
        return node if isinstance(node, str) else None


CONTINENTS = ("africa", "americas", "asia", "australia", "europe")
SOURCE_SLUG = {"Base": "base", "Marine World": "marine_world", "Promo": "promo"}


def clean_text(s):
    if s is None:
        return None
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def common(card, ctype):
    src = card["source"]
    return {
        "id": card["id"],
        "type": ctype,
        "name": card["name"].title() if card["name"].isupper() else card["name"],
        "source": SOURCE_SLUG.get(src, src),
        "base_game": src == "Base",
    }


def tag_fields(card):
    tags = card.get("tags", [])
    return {
        "tags": tags,
        "continents": [t for t in tags if t in CONTINENTS],
        "requirements": card.get("requirements", []),
    }


def build_animal(card, keywords, loc):
    out = common(card, "animal")
    out["latin_name"] = card.get("latinName")
    out["cost"] = card["price"]
    out["size"] = card["size"]
    out["enclosure"] = {
        "standard_size": card["size"] if card.get("canBeInStandardEnclosure", True) else None,
        "rock": card.get("rock", 0),
        "water": card.get("water", 0),
        "special": [
            {"type": e["args"][0], "size": e["args"][1]} for e in card.get("specialEnclosures", [])
        ],
    }
    out.update(tag_fields(card))
    out["abilities"] = [build_ability(a, keywords, loc) for a in card.get("abilities", [])]
    if card.get("reefDwellerEffect"):
        out["reef_dweller_abilities"] = [
            build_ability(a, keywords, loc) for a in card["reefDwellerEffect"]
        ]
    if card.get("description"):
        out["text"] = clean_text(loc.get(card["description"]) or card["description"])
    out["appeal"] = card.get("appeal", 0)
    out["conservation"] = card.get("conservationPoint", 0)
    out["reputation"] = card.get("reputation", 0)
    return out


def build_ability(a, keywords, loc):
    ref = a["args"][0]["__ref__"].split(".", 1)[1]
    value = a["args"][1] if len(a["args"]) > 1 else None
    name, desc_key = keywords[ref]
    template = loc.get(desc_key)
    text = template.replace("{}", str(value if value is not None else "")) if template else None
    return {"keyword": ref, "name": name, "value": value, "text": clean_text(text)}


def build_sponsor(card, loc):
    out = common(card, "sponsor")
    out["level"] = card["strength"]
    out["human"] = card.get("type") == "HUMAN"
    out["enclosure"] = {"rock": card.get("rock", 0), "water": card.get("water", 0)}
    out.update(tag_fields(card))
    # Effects flagged display:false upstream are printed as icons only. Their
    # English text is kept when the locale has it; it may still be None.
    out["effects"] = [
        {
            "timing": e["effectType"],
            "text": clean_text(loc.get(e["effectDesc"])),
            "icon_only": e.get("display") is False,
        }
        for e in card.get("effects", [])
    ]
    out["appeal"] = card.get("appeal", 0)
    out["conservation"] = card.get("conservationPoint", 0)
    out["reputation"] = card.get("reputation", 0)
    return out


def build_bonus(b):
    return {
        "reward": {"Conservation Point": "conservation", "Reputation": "reputation"}[b["bonusType"]],
        "amount": b["bonusValue"],
        "requirement": b.get("bonusRequirement"),
    }


def build_project(card, loc):
    out = common(card, "project")
    out["category"] = card["type"].lower()
    out["icon"] = card["tag"]
    out["slots"] = [
        {
            "position": s["position"],
            "required": s.get("indicator"),
            "rewards": [build_bonus(b) for b in s["bonuses"]],
        }
        for s in card["slots"]
    ]
    out["place_bonuses"] = [build_bonus(b) for b in card.get("placeBonuses", [])]
    desc = card["description"]["effectDesc"]
    out["text"] = clean_text(loc.get(desc) or desc)
    return out


def build_endgame(card, loc):
    out = common(card, "endgame")
    desc = card["description"]["effectDesc"]
    out["text"] = clean_text(loc.get(desc))
    # The site's scoreArray is the Marine Worlds revision where one exists;
    # originalArray is what is printed on the base-game card.
    rows = card.get("originalArray", card["scoreArray"])
    if any(isinstance(s["requirement"], str) for s in rows):
        # Not a threshold table: each row is a rule sentence.
        rules = [clean_text(loc.get(s["requirement"])) for s in rows]
        out["text"] = " ".join(filter(None, [out["text"]] + rules)) or None
        out["scoring"] = [
            {"rule": r, "conservation": s["conservationPoint"]} for r, s in zip(rules, rows)
        ]
        return out
    out["scoring"] = [
        {"threshold": s["requirement"], "conservation": s["conservationPoint"]} for s in rows
    ]
    if "originalArray" in card:
        out["scoring_marine_worlds_revision"] = [
            {"threshold": s["requirement"], "conservation": s["conservationPoint"]}
            for s in card["scoreArray"]
        ]
    return out


def _items(d):
    """(key, value) pairs of a JSON object, skipping "_comment"-style keys."""
    return [(k, v) for k, v in d.items() if not k.startswith("_")]


def _timing_case(name, existing):
    """Write a timing name in the same letter case as the card's other timings."""
    seen = [e["timing"] for e in existing]
    if seen and all(s.isupper() for s in seen):
        return name.upper()
    if seen and all(s.istitle() for s in seen):
        return name.capitalize()
    return name.lower()


def apply_overrides(cards):
    """Apply data/overrides.json: values read from the card images that the text source lacks."""
    ov = json.loads((ROOT / "data" / "overrides.json").read_text())
    by_id = {c["id"]: c for c in cards}

    def target(cid):
        if cid not in by_id:
            sys.exit("overrides.json names unknown card id %s" % cid)
        return by_id[cid]

    for cid, timings in _items(ov.get("sponsor_effect_text", {})):
        card = target(cid)
        for timing, text in _items(timings):
            match = [e for e in card["effects"] if e["timing"].lower() == timing.lower()]
            if match:
                match[0]["text"] = text
            else:
                card["effects"].append(
                    {"timing": _timing_case(timing, card["effects"]), "text": text, "icon_only": True}
                )

    for cid, spec in _items(ov.get("sponsor_building", {})):
        card = target(cid)
        enc = card["enclosure"]
        card["building"] = {
            "shape": [list(p) for p in spec["shape"]],
            "size": len(spec["shape"]),
            "rock": enc["rock"] if isinstance(enc.get("rock"), int) else 0,
            "water": enc["water"] if isinstance(enc.get("water"), int) else 0,
            "min_border": spec.get("min_border", 0),
            "needs_adjacency": spec.get("needs_adjacency", True),
        }

    conditions = ov.get("sponsor_conditions", {})
    for key in ("max_appeal", "min_reputation"):
        for cid, value in _items(conditions.get(key, {})):
            target(cid)[key] = value

    release = ov.get("release_projects", {})
    slot_sizes = release.get("slot_animal_size", {})
    for card in cards:
        if card["type"] == "project" and card["category"] == "release":
            for slot in card["slots"]:
                pos = str(slot["position"])
                if pos not in slot_sizes:
                    sys.exit("overrides.json has no slot_animal_size for position %s (card %s)" % (pos, card["id"]))
                slot["animal_size"] = dict(slot_sizes[pos])
            card["play_bonus"] = [list(b) for b in release.get("play_bonus", [])]

    for cid, fields in _items(ov.get("card_fields", {})):
        card = target(cid)
        for path, value in _items(fields):
            *parents, leaf = path.split(".")
            node = card
            for p in parents:
                node = node[p]
            node[leaf] = value


def main():
    enums = load_enums()
    keywords = load_keywords(enums)
    loc = Locale()
    cards = []
    cards += [build_animal(c, keywords, loc) for c in load_array("src/data/Animals.ts", "AnimalsData", enums)]
    cards += [build_sponsor(c, loc) for c in load_array("src/data/Sponsors.ts", "SponsorsData", enums)]
    cards += [build_project(c, loc) for c in load_array("src/data/Projects.ts", "ProjectsData", enums)]
    cards += [build_endgame(c, loc) for c in load_array("src/data/EndGames.ts", "EndGameData", enums)]
    cards.sort(key=lambda c: c["id"])
    apply_overrides(cards)

    ids = Counter(c["id"] for c in cards)
    dupes = [i for i, n in ids.items() if n > 1]
    if dupes:
        sys.exit("duplicate ids: %s" % dupes)

    base = [c for c in cards if c["base_game"]]
    doc = {
        "source": "https://github.com/Ender-Wiggin2019/Next-Ark-Nova-Cards (src/data, src/types, public/locales/en)",
        "counts": {
            "all": dict(Counter(c["type"] for c in cards)),
            "base_game": dict(Counter(c["type"] for c in base)),
        },
        "cards": cards,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "data" / "cards_base.json").write_text(
        json.dumps(base, indent=1, ensure_ascii=False) + "\n"
    )
    print("all      ", doc["counts"]["all"])
    print("base game", doc["counts"]["base_game"])
    if loc.missing:
        print("missing locale keys (%d):" % len(loc.missing), sorted(set(loc.missing))[:40])


if __name__ == "__main__":
    main()
