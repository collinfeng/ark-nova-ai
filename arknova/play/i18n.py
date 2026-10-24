"""Chinese (zh-CN) for the text the server writes: decision titles, why a card or action is not playable,
track rewards, option labels, and the cards themselves (names and effect text).

The board sends its language with each request (header X-Lang, or ?lang=); view.board() sets it for the
duration of the call. English stays the default and the fallback: a missing translation shows English.
Resources live with the board in web/src/i18n/zh-CN/ (ui.json, cards.json).
"""
import contextvars
import json
import re
from pathlib import Path

RES = Path(__file__).resolve().parent.parent.parent / "web" / "src" / "i18n"
SUPPORTED = {"zh-cn": "zh-CN", "zh": "zh-CN", "zh-hans": "zh-CN", "zh-hans-cn": "zh-CN"}

_current = contextvars.ContextVar("lang", default="en")
_cache = {}


def normalize(lang):
    return SUPPORTED.get((lang or "").strip().lower(), "en")


def use(lang):
    """Make `lang` the language of this request; returns a token for reset()."""
    return _current.set(normalize(lang))


def reset(token):
    _current.reset(token)


def lang():
    return _current.get()


def is_zh():
    return _current.get() != "en"


def _res(code):
    if code not in _cache:
        folder = RES / code
        cards_file = folder / "cards.json"  # card names and text: not shipped (game content); English if absent
        _cache[code] = {"ui": json.loads((folder / "ui.json").read_text()),
                        "cards": json.loads(cards_file.read_text())["cards"] if cards_file.exists() else {}}
    return _cache[code]


def _get(tree, path):
    for part in path.split("."):
        if not isinstance(tree, dict) or part not in tree:
            return None
        tree = tree[part]
    return tree if isinstance(tree, str) else None


def tr(key, en, **kw):
    """Text for `key` in the request's language, else the English template; both use {name} fields."""
    template = en
    if is_zh():
        template = _get(_res(lang())["ui"]["server"], key) or en
    return template.format(**kw) if kw else template


def term(group, key, en=None):
    """A game term (terms.<group>.<key> in ui.json), or English."""
    if is_zh():
        found = _get(_res(lang())["ui"]["terms"], f"{group}.{key}")
        if found:
            return found
    return key if en is None else en


def card_zh(cid):
    return _res(lang())["cards"].get(cid) if is_zh() else None


# ---- card names in labels ---------------------------------------------------------------------

_names = {}


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _name_index():
    code = lang()
    if code not in _names:
        from arknova import cards as C
        index = {}
        for cid, zh in _res(code)["cards"].items():
            try:
                index[_norm(C.card(cid)["name"])] = zh["name"]
            except KeyError:
                pass
        _names[code] = index
    return _names[code]


def zname(name):
    """The Chinese name of a card given its English name (as it appears in an option label)."""
    return _name_index().get(_norm(name), name)


def zname_id(cid):
    zh = card_zh(cid)
    return zh["name"] if zh else cid


# ---- option labels --------------------------------------------------------------------------

_GRANT = {"hand": "手牌上限 5，并获得 1 声望", "science2": "2 个研究图标", "science_rep": "1 个研究图标和 2 声望"}


def _a(action):
    return term("actions", action)


def _building(name):
    key = name.strip().replace(" ", "_")
    zh = _get(_res(lang())["ui"]["terms"], f"buildings.{key}")
    return zh or name


def _support_extra(m):
    """The part of a support label that tells options on the same slot apart (association._extra_text)."""
    if m["rel"]:
        return f"，放归{zname(m['rel'])}"
    if m["tok"]:
        return f"，使用来自{zname(m['tok'])}的标记"
    return ""


def _rules():
    nm = r"(?P<n>.+?)"
    ex = r"(?:, release (?P<rel>.+?)|, using a token from (?P<tok>.+?))?"
    return [
        (r"^(?P<a>\w+) at strength (?P<s>\d+)(?: \(\+(?P<x>\d) X\))?$",
         lambda m: f"{_a(m['a'])}，强度 {m['s']}" + (f"（+{m['x']} 枚 X 标记）" if m["x"] else "")),
        (r"^Take an X-token with (?P<a>\w+)$", lambda m: f"用{_a(m['a'])}领取 X 标记"),
        (r"^Upgrade (?P<a>\w+)$", lambda m: f"升级{_a(m['a'])}行动卡牌"),
        (r"^Hire an association worker$", lambda m: "雇佣一名协会事务员"),
        (r"^Move (?P<a>animals|build|cards|association|sponsors) to slot 1$", lambda m: f"将{_a(m['a'])}移动到栏位 1"),
        (r"^Place (?P<a>\w+) on slot (?P<s>\d)$", lambda m: f"将{_a(m['a'])}放到栏位 {m['s']}"),
        (r"^Use the x2 token: (?P<a>\w+) again$", lambda m: f"使用双倍标记：再次执行{_a(m['a'])}"),
        (r"^Put the x2 token on (?P<a>\w+)$", lambda m: f"将双倍标记放在{_a(m['a'])}行动卡牌上"),
        (r"^Skip$", lambda m: "跳过"),
        (r"^Done$", lambda m: "完成"),
        (r"^Finish$", lambda m: "结束"),
        (r"^Done building$", lambda m: "建造完成"),
        (r"^Finish moving animals$", lambda m: "结束迁移动物"),
        (r"^Draw from the deck$", lambda m: "从牌库抽牌"),
        (r"^Replenish the display$", lambda m: "补充展示区"),
        (rf"^Harbour: discard {nm} for (?P<m>\d+) money$", lambda m: f"港口：弃除{zname(m['n'])}，获得 {m['m']} 金钱"),
        (r"^Take display folder (?P<f>\d)$", lambda m: f"拿取展示卡位 {m['f']} 的卡牌"),
        (r"^Snap folder (?P<f>\d)$", lambda m: f"精选展示卡位 {m['f']} 的卡牌"),
        (r"^Discard display folder (?P<f>\d)$", lambda m: f"弃除展示卡位 {m['f']} 的卡牌"),
        (rf"^Discard {nm} and draw$", lambda m: f"弃除{zname(m['n'])}并抽牌"),
        (r"^Give a random hand card$", lambda m: "交出一张随机手牌"),
        (r"^Give up to (?P<n>\d+) money$", lambda m: f"交出最多 {m['n']} 金钱"),
        (rf"^tuck {nm}$", lambda m: f"塞入{zname(m['n'])}"),
        (rf"^sell {nm}$", lambda m: f"出售{zname(m['n'])}"),
        (rf"^Take base project {nm}$", lambda m: f"拿取基础保护项目{zname(m['n'])}"),
        (r"^Keep final scoring card (?P<n>\d{3})$", lambda m: f"保留终局计分卡牌{zname_id(m['n'])}"),
        (r"^Discard final scoring card (?P<n>\d{3})$", lambda m: f"弃除终局计分卡牌{zname_id(m['n'])}"),
        (r"^Discard (?P<n>\d{3})$", lambda m: f"弃除{zname_id(m['n'])}"),
        (r"^Keep (?P<n>\d{3}(?:, \d{3})+)$", lambda m: "保留 " + "、".join(zname_id(i) for i in m["n"].split(", "))),
        (rf"^Keep {nm}$", lambda m: f"保留{zname(m['n'])}"),
        (rf"^Take {nm} from folder (?P<f>\d+)$", lambda m: f"从展示卡位 {m['f']} 拿取{zname(m['n'])}"),
        (rf"^Play {nm} into building (?P<b>\d+) for (?P<c>\d+)$", lambda m: f"花费 {m['c']}，将{zname(m['n'])}放入建筑 {m['b']}"),
        (r"^Donate (?P<n>\d+) money for 1 conservation$", lambda m: f"捐赠 {m['n']} 金钱，获得 1 保护点数"),
        (rf"^Play {nm} from folder (?P<f>\d+) and support it \(slot (?P<s>\d+), token (?P<t>\d+){ex}\)$",
         lambda m: f"从展示卡位 {m['f']} 打出并支持{zname(m['n'])}（栏位 {m['s']}，标记 {m['t']}{_support_extra(m)}）"),
        (rf"^Play {nm} and support it \(slot (?P<s>\d+), token (?P<t>\d+){ex}\)$",
         lambda m: f"打出并支持{zname(m['n'])}（栏位 {m['s']}，标记 {m['t']}{_support_extra(m)}）"),
        (rf"^Support {nm} \(slot (?P<s>\d+), token (?P<t>\d+){ex}\)$",
         lambda m: f"支持{zname(m['n'])}（栏位 {m['s']}，标记 {m['t']}{_support_extra(m)}）"),
        (r"^Reputation \+(?P<n>\d+)$", lambda m: f"声望 +{m['n']}"),
        (r"^Engineer: build another (?P<b>\w+) (?P<s>\d) for (?P<c>\d+)$",
         lambda m: f"工程师：再建造一个{_building(m['b'])}（{m['s']} 格），费用 {m['c']}"),
        (r"^Build (?P<b>\w+) (?P<s>\d) for (?P<c>\d+)$", lambda m: f"建造{_building(m['b'])}（{m['s']} 格），费用 {m['c']}"),
        (r"^Build (?P<b>\w+)$", lambda m: f"建造{_building(m['b'])}"),
        (r"^Break (?P<n>\d+) and take money$", lambda m: f"休息 {m['n']} 格并获得 {m['n']} 金钱"),
        (rf"^Play {nm} for (?P<c>\d+) money$", lambda m: f"花费 {m['c']} 金钱打出{zname(m['n'])}"),
        (rf"^Play {nm}$", lambda m: f"打出{zname(m['n'])}"),
        (r"^Take (?P<n>\d+) money$", lambda m: f"获得 {m['n']} 金钱"),
        (rf"^Take {nm}$", lambda m: f"拿取{zname(m['n'])}"),
        (r"^Small animals \(size 2 or less\)$", lambda m: "小型动物（体型 2 或以下）"),
        (r"^Large animals \(size 4 or more\)$", lambda m: "大型动物（体型 4 或以上）"),
        (r"^Do not use Okapi Stable$", lambda m: "不使用霍加狓棚厩"),
        (r"^Remove a token and play a sponsor card for its level$", lambda m: "移除一枚标记，并按其等级打出一张赞助商卡牌"),
        (r"^Move (?P<n>.+?) into the new (?P<s>[\w ]+)$", lambda m: f"将{zname(m['n'])}移入新的{_building(m['s'])}"),
        (r"^Place the building$", lambda m: "放置此建筑"),
        (r"^Kept 4 starting cards$", lambda m: "保留了 4 张起始卡牌"),
        (r"^Partner zoo: (?P<c>\w+)$", lambda m: f"合作动物园：{term('icons', m['c'])}"),
        (r"^University: (?P<u>\w+)$", lambda m: f"大学：{_GRANT.get(m['u'], m['u'])}"),
    ]


_compiled = {}


def option_label(label, key):
    """The Chinese text for an option, from its English label and key; English if no rule matches."""
    kind = key[0]
    if kind == "partner_zoo" and len(key) > 1:
        return f"合作动物园：{term('icons', key[1])}"
    if kind == "university" and len(key) > 1:
        return f"大学：{_GRANT.get(key[1], key[1])}"
    if kind == "tile" and len(key) > 1:
        return "拿取奖励板块：" + "、".join(tile_effects(key[1]))
    if "rules" not in _compiled:
        _compiled["rules"] = [(re.compile(p), f) for p, f in _rules()]
    for pattern, fn in _compiled["rules"]:
        m = pattern.match(label)
        if m:
            return fn(m)
    return label


def tile_effects(tile):
    from arknova import tables as T
    from . import view
    return [view.effect_label(k, a) for k, a in T.BONUS_TILES.get(tile, [])]
