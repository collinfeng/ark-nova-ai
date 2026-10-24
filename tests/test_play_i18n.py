"""Simplified Chinese for the board: cards, option labels, reasons, and the resources it reads."""
import pytest
import json
import random
import re
from pathlib import Path

import arknova  # noqa: F401
from arknova import engine as G
from arknova.play import i18n, view
from arknova.play.game import Game
from arknova.play.ai import Analysis

WEB = Path(__file__).resolve().parent.parent / "web"
CJK = re.compile(r"[一-鿿]")


class FirstOption:
    name = "first"

    def analyse(self, game):
        n = len(game.options())
        return Analysis([1 / n] * n, 0.0, 0)


ZH_CARDS = WEB / "src/i18n/zh-CN/cards.json"
needs_zh_cards = pytest.mark.skipif(not ZH_CARDS.exists(), reason="Chinese card text is not distributed (game content)")


@needs_zh_cards
def test_every_base_card_has_chinese_text_with_the_same_structure():
    zh = json.loads((WEB / "src/i18n/zh-CN/cards.json").read_text())["cards"]
    from arknova import cards as C
    for cid, z in zh.items():
        e = C.card(cid)
        assert z["type"] == e["type"], cid
        if e["type"] == "sponsor":
            assert [x["timing"] for x in z["effects"]] == [x["timing"] for x in e["effects"]], cid
        if e["type"] == "animal":
            assert [(a["keyword"], a["value"]) for a in z["abilities"]] == [(a.get("keyword"), a.get("value")) for a in e["abilities"]], cid
    assert len(zh) == 235


@needs_zh_cards
def test_cards_and_decisions_come_out_in_chinese_and_english_is_unchanged():
    game = Game(FirstOption(), seed=11)
    zh = view.board(game, "zh-CN")
    en = view.board(game)
    assert en["decision"]["title"] == "Keep 4 of your 8 starting cards"
    assert CJK.search(zh["decision"]["title"])
    assert all(CJK.search(o["label"]) for o in zh["decision"]["options"])
    assert zh["players"][0]["hand"][0]["name"] != en["players"][0]["hand"][0]["name"]
    assert CJK.search(zh["display"][0]["status"]["why"]) and "Needs" in en["display"][0]["status"]["why"]
    assert zh["display"][0]["status"]["unmet"] == ["sponsorsII"] == en["display"][0]["status"]["unmet"]
    assert i18n.lang() == "en"  # the request's language is not left behind


@pytest.mark.slow
@needs_zh_cards  # without card names, labels keep them in English
def test_no_option_label_stays_english_in_chinese():
    """Across simulated games, every kind of option and decision gets Chinese text."""
    token = i18n.use("zh-CN")
    try:
        untranslated = {}
        # Map 0 most, and every other map (their rules add options such as the harbour's discard).
        games = [(seed, "map0") for seed in range(12)] + [(seed, m) for m in sorted(G.MAP_DEFS) if m != "map0" for seed in range(2)]
        for seed, map_name in games:
            rng = random.Random(seed)
            state = G.new_game(2, seed=seed, map_name=map_name)
            for _ in range(2500):
                if state.over:
                    break
                options = G.legal_options(state)
                kind = state.stack[-1].kind
                if not CJK.search(view.title(kind)):
                    untranslated[("title", kind)] = view.title(kind)
                for i, o in enumerate(options):
                    label = view.option(i, o, None, state)["label"]
                    english = re.sub(r"X|x2|WAZA|\d", "", label)
                    if not CJK.search(label) or re.search(r"[A-Za-z]{4,}", english):
                        untranslated.setdefault((kind, o.key[0]), label)
                G.step(state, rng.choice(options))
        assert not untranslated, untranslated
    finally:
        i18n.reset(token)


def test_ui_keys_used_by_the_board_have_chinese_text():
    """A key used in the board's code but missing from ui.json would show English in the Chinese UI."""
    ui = json.loads((WEB / "src/i18n/zh-CN/ui.json").read_text())

    def keys(tree, prefix=""):
        for k, v in tree.items():
            if isinstance(v, dict):
                yield from keys(v, f"{prefix}{k}.")
            else:
                yield f"{prefix}{k}"

    have = set(keys(ui["ui"])) | {f"terms.{k}" for k in keys(ui["terms"])}
    missing = set()
    for path in list((WEB / "src").rglob("*.tsx")) + list((WEB / "src").rglob("*.ts")):
        text = path.read_text()
        for m in re.finditer(r"(?<![\w.])(t|term)\(\s*'([\w.]+)'(?:\s*,\s*'(\w+)')?", text):
            if m.group(1) == "term" and not m.group(3):
                continue  # the term's name is a variable, not a literal key
            key = f"terms.{m.group(2)}.{m.group(3)}" if m.group(1) == "term" else m.group(2)
            if key not in have:
                missing.add((key, path.name))
    assert not missing, sorted(missing)


def test_placeholders_in_chinese_ui_text_are_well_formed():
    ui = json.loads((WEB / "src/i18n/zh-CN/ui.json").read_text())
    bad = []

    def walk(tree, prefix=""):
        for k, v in tree.items():
            if isinstance(v, dict):
                walk(v, f"{prefix}{k}.")
            elif v.count("{") != v.count("}") or re.search(r"\{[^}\w]|\{\w*\s", v):
                bad.append(prefix + k)

    walk(ui["ui"])
    walk(ui["server"])
    assert not bad, bad
