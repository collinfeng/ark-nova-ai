"""Compare card values transcribed from the card images with data/cards.json.

Usage: python tools/check_transcriptions.py FILE.json [FILE.json ...]
Each file: {"<card id>": {"name": str, "cost": int, "size": int, "appeal": int}} for animals
           {"<card id>": {"name": str, "level": int}} for sponsors
Prints only disagreements.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cards = {c["id"]: c for c in json.loads((ROOT / "data" / "cards.json").read_text())["cards"]}
seen, problems = set(), 0
for path in sys.argv[1:]:
    for card_id, read in json.loads(Path(path).read_text()).items():
        seen.add(card_id)
        card = cards[card_id]
        for field, value in read.items():
            expected = card.get(field)
            if field == "name":
                same = "".join(filter(str.isalnum, str(value).lower())) == "".join(filter(str.isalnum, card["name"].lower()))
            else:
                same = value == expected
            if not same:
                problems += 1
                print(f"#{card_id} {card['name']}: {field} read {value!r}, data has {expected!r}")
print(f"{len(seen)} cards checked, {problems} disagreements")
