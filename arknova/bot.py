"""Heuristic opponents: a position valuation plus a search over the bot's own next turns.

    bot = LookaheadBot()                 # or GreedyBot(), or LookaheadBot(weights=..., depth=2)
    option = bot.choose(state, rng)      # for whoever must decide at state.stack[-1]

The valuation (`evaluate`) prices a position in appeal-equivalents. Realised progress counts
in full; unrealised assets (money, cards in hand, empty enclosures) count only for what they
can turn into soon, and always less than using them, so the bot prefers doing to hoarding.

The search never uses hidden information: it works on a copy whose deck has been reshuffled,
and it never reads another player's hand. Opponents are treated as passive.
"""
import copy
import random

from . import cards, effects as E, engine as G, tables as T
from .actions import animals as AN
from .hexmap import neighbors

# Fitted by tools/fit_bot.py; see docs/BOT.md. Values are appeal-equivalents.
DEFAULT_WEIGHTS = {
    "money": 0.28,          # per money, for the first MONEY_WORKING
    "spare_money": 0.08,    # per money for the next MONEY_SPARE; anything beyond is worth nothing
    "conservation": 2.6,    # per conservation point on a card, when estimating a play
    "income": 0.15,         # per money of break income, per break left
    "hold": 0.35,           # share of a playable card's net gain credited while it is in hand
    "xtoken": 0.8,
    "upgrade": 5.0,         # per upgraded action card, scaled by time left
    "reputation": 0.4,      # per reputation step up to 9
    "reputation_high": 0.3, # per reputation step above 9
    "worker": 1.9,          # first extra worker; later ones are multiplied by `decay` each
    "partner": 2.0,         # first partner zoo; later ones decay
    "university": 2.0,      # first university; later ones decay
    "decay": 0.8,           # each further worker / zoo / university is worth this share of the last
    "sponsor_level": 0.8,   # lasting effects of a sponsor in play, per level
    "slot": 0.15,           # per slot step of an action card (strength in reserve)
    "idle_enclosure": 0.45, # share of its cost kept by an empty enclosure nothing in hand fits
}
UPGRADE_WEIGHT = {"animals": 1.2, "association": 1.1, "cards": 1.0, "build": 0.85, "sponsors": 0.7}
SLOT_WEIGHT = {"animals": 1.2, "build": 1.0, "association": 1.1, "cards": 0.7, "sponsors": 0.6}
BREAKS_PER_GAME = 7
MONEY_WORKING = 25   # money up to here is priced in full: enough for an animal and its enclosure
MONEY_SPARE = 25     # the next band is priced low; a larger hoard adds nothing
PROJECT_STRENGTH = 5


# ---- valuation --------------------------------------------------------------------------

def track_value(player):
    """Appeal plus the appeal the conservation counter is worth: victory points + 100."""
    return player.appeal + 100 - T.target_appeal(player.conservation)


def progress(state):
    """0 at the start of the game, 1 when a player reaches the end-game trigger."""
    start = -14
    return max(0.0, min(1.0, max((track_value(pl) - start) / (100 - start) for pl in state.players)))


def endgame_points(state, p):
    """(appeal, conservation) the player's sponsors and final scoring cards would score right now."""
    player = state.players[p]
    appeal, conservation = player.appeal, player.conservation
    for card_id in player.zoo_cards + player.final_cards:
        if card_id in E.ENDGAME:
            E.ENDGAME[card_id](state, p)
    gained = player.appeal - appeal, player.conservation - conservation
    player.appeal, player.conservation = appeal, conservation
    return gained


def sponsor_lasting(card_id, w):
    """Worth of a sponsor's lasting effects (income, triggers, rule changes), before time discount."""
    c = cards.card(card_id)
    lasting = any(e["timing"] in ("income", "passive", "endgame") for e in c.get("effects", []))
    return w["sponsor_level"] * c["level"] if lasting else 0.0


def play_gain(player, card_id, left, w):
    """(net gain of playing the card now, money it needs, whether its conditions are met)."""
    c = cards.card(card_id)
    printed = c.get("appeal", 0) + w["conservation"] * c.get("conservation", 0) + w["reputation"] * c.get("reputation", 0)
    if c["type"] == "animal":
        cost = AN._cost(player, card_id)
        if not AN.housings(player, card_id) and c["enclosure"]["standard_size"]:
            cost += T.BUILD_COST_PER_SPACE * c["enclosure"]["standard_size"]
        gain = printed + (1.0 if c["abilities"] else 0.0) - cost * w["money"]
        return gain, cost, cards.unmet_requirements(player, card_id) == 0
    if c["type"] == "sponsor":
        return printed + sponsor_lasting(card_id, w) * left + 1.0, 0, cards.unmet_requirements(player, card_id) == 0
    return 1.5, 0, False


def hand_value(player, left, w):
    """(value of holding the hand, money its two best plays need)."""
    rated = sorted((play_gain(player, c, left, w) for c in player.hand), key=lambda t: (t[2], t[0]), reverse=True)
    value, need = 0.0, 0
    for i, (gain, cost, playable) in enumerate(rated[:player.hand_limit]):  # the rest will be discarded
        if playable and gain > 0:
            value += min(3.0, w["hold"] * gain) + 0.3
            if i < 2:
                need += cost
        else:
            value += 0.4
    return value, need


def _diminishing(first, count, decay):
    return sum(first * decay ** i for i in range(count))


def evaluate(state, p, w=DEFAULT_WEIGHTS):
    """Value of the position for player p, in appeal-equivalents."""
    player = state.players[p]
    left = 1 - progress(state)
    value = track_value(player)
    appeal, conservation = endgame_points(state, p)
    value += (appeal + w["conservation"] * conservation) * (1 - 0.5 * left)
    value += (T.appeal_income(player.appeal) + player.zoo.kiosk_income()) * BREAKS_PER_GAME * left * w["income"]

    # Money is priced by how much there is, not by what the hand could buy with it: tying it to
    # the hand made playing a card look like a loss, because the money left over lost its use.
    hold, _ = hand_value(player, left, w)
    value += hold + w["money"] * min(player.money, MONEY_WORKING)
    value += w["spare_money"] * min(max(player.money - MONEY_WORKING, 0), MONEY_SPARE)

    value += player.xtokens * w["xtoken"]
    value += (w["reputation"] * min(player.reputation - 1, 8) + w["reputation_high"] * max(player.reputation - 9, 0)) * left
    value += sum(UPGRADE_WEIGHT[a] for a in player.upgraded) * (w["upgrade"] * left + 0.5)
    value += (_diminishing(w["worker"], player.workers - 1, w["decay"])
              + _diminishing(w["partner"], len(player.partner_zoos), w["decay"])
              + _diminishing(w["university"], len(player.universities), w["decay"])) * left
    value += sum(SLOT_WEIGHT[a] * i for i, a in enumerate(player.slots)) * w["slot"]
    value += sum(sponsor_lasting(c, w) for c in player.zoo_cards if cards.card(c)["type"] == "sponsor") * left

    playable_animals = [c for c in player.hand
                        if cards.card(c)["type"] == "animal" and cards.unmet_requirements(player, c) == 0]
    for b in player.zoo.buildings:
        if b.kind == "enclosure" and not b.occupied:
            fits = any((b.id, 0) in AN.housings(player, c) for c in playable_animals)
            share = 1.0 if fits else w["idle_enclosure"]
            value += T.BUILD_COST_PER_SPACE * b.size * w["money"] * share + (0.3 if fits else 0.0)
        elif b.kind in ("reptile_house", "aviary", "petting_zoo"):
            value += T.BUILD_COST_PER_SPACE * (b.size - b.used) * w["money"] * w["idle_enclosure"]

    if state.end_by == p or (state.end_by is None and player.victory_points >= 0):
        best_other = max(q.victory_points for q in state.players if q.idx != p)
        value += 3 if player.victory_points >= best_other else -4  # only end the game when ahead
    return value


# ---- option handling ----------------------------------------------------------------------

PLACEMENTS_PER_BUILDING = 3


def _placement_score(zoo, cells, kind):
    score = 0.0
    for c in cells:
        if zoo.mapdef.cells[c].bonus:
            score += 2.0
        for n in neighbors(c):
            if n in zoo.cell_owner:
                score += 0.15  # keep the zoo compact
            elif kind == "enclosure" and n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain != "plain":
                score += 0.3   # rock and water neighbours keep animal options open
    return score


def shortlist(state, options):
    """Cut the option list where positions explode: a few good spots per building, and each action
    card with at most one X-token."""
    frame = state.stack[-1]
    if frame.kind in ("act_build", "free_build", "sponsor_building"):
        zoo = state.players[frame.player].zoo
        groups, rest = {}, []
        for o in options:
            if isinstance(o.key[-1], tuple) and o.key[0] in ("build", "engineer", "place"):
                groups.setdefault(o.key[:-1], []).append(o)
            else:
                rest.append(o)
        kept = []
        for key, group in groups.items():
            kind = key[1] if len(key) > 1 else "unique"
            group.sort(key=lambda o: -_placement_score(zoo, o.key[-1], kind))
            kept += group[:PLACEMENTS_PER_BUILDING]
        return kept + rest
    if frame.kind in ("turn", "extra_action"):
        return [o for o in options if o.key[0] != "act" or _worth_trying(state, frame, o)]
    return options


def _worth_trying(state, frame, option):
    """Which X-token spends the search considers for an action card: none, one, or exactly enough
    to reach strength 5 (a conservation project, two animals, a size-5 building, a snap)."""
    spent = option.key[2]
    if spent <= 1:
        return True
    owner = frame.data.get("owner", frame.player)
    return G._card_strength(state, owner, option.key[1]) + spent == PROJECT_STRENGTH


def passive_option(options):
    """The do-nothing choice, used for other players and to finish a simulated turn cheaply."""
    for o in options:
        if o.key[0] in ("done", "skip", "no"):
            return o
    return options[0]


def _finish_passively(state, limit=80):
    while not state.over and state.stack[-1].kind != "turn" and limit:
        G.step(state, passive_option(G.legal_options(state, extras=False)))
        limit -= 1


def _hidden_copy(state, rng):
    """A copy the bot may search: no log, and a deck order it could not know."""
    clone = copy.deepcopy(state)
    clone.log = None
    clone.cache_options, clone.cached_options = False, None  # the search edits its copies directly
    clone.rng = random.Random(rng.random())
    clone.deck.sort()  # forget the real order entirely before shuffling
    clone.rng.shuffle(clone.deck)
    return clone


def _open_copy(state):
    """A copy with the real deck order and draws: for a bot allowed to see everything."""
    clone = copy.deepcopy(state)
    clone.log = None
    clone.cache_options, clone.cached_options = False, None
    return clone


class GreedyBot:
    """Looks to the end of the current turn only: each option is worth the position it leads to."""

    def __init__(self, weights=None, open_info=False):
        self.w = dict(DEFAULT_WEIGHTS, **(weights or {}))
        self.open_info = open_info  # search the real deck order instead of a reshuffled one

    def _copy(self, state, rng):
        return _open_copy(state) if self.open_info else _hidden_copy(state, rng)

    def value_after(self, state, option, p, depth=0):
        clone = copy.deepcopy(state)
        G.step(clone, option)
        if depth and not clone.over and clone.stack[-1].kind != "turn" and clone.stack[-1].player == p:
            follow = shortlist(clone, G.legal_options(clone, extras=False))[:15]
            if len(follow) > 1:
                return max(self.value_after(clone, o, p, depth - 1) for o in follow)
        _finish_passively(clone)
        return evaluate(clone, p, self.w)

    def keep_cards(self, state, options):
        player = state.players[state.stack[-1].player]

        def worth(card_id):
            gain, _, playable = play_gain(player, card_id, 1.0, self.w)
            return max(0.0, gain) * (1.0 if playable else 0.3)
        return max(options, key=lambda o: sum(worth(c) for c in o.key[1:]))

    def choose(self, state, rng):
        frame = state.stack[-1]
        options = G.legal_options(state, extras=False)
        if len(options) == 1:
            return options[0]
        if frame.kind == "setup_keep":
            return self.keep_cards(state, options)
        base = self._copy(state, rng)
        depth = 2 if frame.kind in ("turn", "extra_action") else 1
        return max(shortlist(base, options),
                   key=lambda o: self.value_after(base, o, frame.player, depth) + rng.random() * 0.01)


class LookaheadBot(GreedyBot):
    """Searches a beam of its own next `depth` turns and follows the first turn of the best line."""

    def __init__(self, weights=None, depth=3, width=8, variants=10, follow=8, open_info=False, reply=False):
        super().__init__(weights, open_info)
        self.depth, self.width, self.variants, self.follow = depth, width, variants, follow
        self.reply = reply  # other players take their turns in the search, by the same valuation
        self.planned = {}  # player -> option keys still to play this turn

    def _turn_options(self, state):
        """Each action card at base strength, boosted to strength 5 with X-tokens when it has them
        (one X-token also when that is the only way to use the card), and a single X-token action."""
        options = G.legal_options(state, extras=False)
        frame = state.stack[-1]
        owner = frame.data.get("owner", frame.player)
        usable = {o.key[1] for o in options if o.key[0] == "act" and o.key[2] == 0}
        kept, x_taken = [], False
        for o in options:
            if o.key[0] == "act":
                spent = o.key[2]
                reaches_five = spent and G._card_strength(state, owner, o.key[1]) + spent == PROJECT_STRENGTH
                if spent == 0 or reaches_five or (spent == 1 and o.key[1] not in usable):
                    kept.append(o)
            elif o.key[0] == "xtoken":
                if not x_taken:
                    kept.append(o)
                x_taken = True
            else:
                kept.append(o)
        return kept or options

    def _one_of_each(self, state, p, options):
        """The best option of each kind. Ranking them all together would keep only instant gains
        (a pavilion) and drop the first step of every plan (the enclosure for an animal in hand)."""
        groups = {}
        for o in options:
            last = o.key[-1]
            kind = o.key[:-1] if len(o.key) > 1 and isinstance(last, (tuple, int)) else o.key
            groups.setdefault(kind, []).append(o)
        scored = [max(((self.value_after(state, o, p), o) for o in group[:6]), key=lambda t: t[0])
                  for group in groups.values()]
        scored.sort(key=lambda t: -t[0])
        return [o for _, o in scored[:self.variants]]

    def _finish_turn(self, state, p, keys):
        limit = 80
        while not state.over and state.stack[-1].kind != "turn" and limit:
            options = G.legal_options(state, extras=False)
            if state.stack[-1].player == p and len(options) > 1:
                choice = max(shortlist(state, options)[:self.follow], key=lambda o: self.value_after(state, o, p))
                keys.append(choice.key)
            else:
                choice = passive_option(options)
            G.step(state, choice)
            limit -= 1
        return keys

    def _turns_from(self, state, p):
        """Ways to play p's whole turn from a turn frame: [(position after it, option keys used)]."""
        lines = []
        for o in self._turn_options(state):
            first = copy.deepcopy(state)
            G.step(first, o)
            branches = [(first, [o.key])]
            if not first.over and first.stack[-1].kind != "turn" and first.stack[-1].player == p:
                follow = shortlist(first, G.legal_options(first, extras=False))
                if len(follow) > 1:
                    branches = []
                    for x in self._one_of_each(first, p, follow):
                        second = copy.deepcopy(first)
                        G.step(second, x)
                        branches.append((second, [o.key, x.key]))
            for position, keys in branches:
                lines.append((position, self._finish_turn(position, p, keys)))
        return lines

    def _others_reply(self, state, p):
        """Play the other players' turns, each as the one-turn line they value most, until it is p's turn."""
        limit = len(state.players)
        while not state.over and state.stack[-1].kind == "turn" and state.stack[-1].player != p and limit:
            q = state.stack[-1].player
            state = max(self._turns_from(state, q), key=lambda line: evaluate(line[0], q, self.w))[0]
            limit -= 1
        return state

    def plan(self, state, p, rng):
        base = self._copy(state, rng)
        beam = sorted(((evaluate(s, p, self.w), i, s, keys) for i, (s, keys) in enumerate(self._turns_from(base, p))),
                      key=lambda t: (-t[0], t[1]))[:self.width]
        for _ in range(1, self.depth):
            reached = []
            for value, i, s, keys in beam:
                if s.over:
                    reached.append((value, i, s, keys))
                    continue
                if self.reply:
                    s = self._others_reply(s, p)
                    if s.over:
                        reached.append((evaluate(s, p, self.w), i, s, keys))
                        continue
                top = s.stack[-1]
                if top.player != p:  # opponents are passive in the search
                    top.player, s.current = p, p
                for j, (after, _) in enumerate(self._turns_from(s, p)):
                    reached.append((evaluate(after, p, self.w), i * 1000 + j, after, keys))
            beam = sorted(reached, key=lambda t: (-t[0], t[1]))[:self.width]
        return beam[0][3]

    def choose(self, state, rng):
        frame = state.stack[-1]
        p = frame.player
        options = G.legal_options(state, extras=False)
        if len(options) == 1:
            return options[0]
        if frame.kind == "turn":
            keys = self.plan(state, p, rng)
            self.planned[p] = keys[1:]
            return next(o for o in options if o.key == keys[0])
        planned = self.planned.get(p)
        if planned:
            match = next((o for o in options if o.key == planned[0]), None)
            if match is not None:
                planned.pop(0)
                return match
            self.planned[p] = []  # a real draw differed from the simulated one
        return super().choose(state, rng)


# ---- running games ------------------------------------------------------------------------

def play_game(bots, seed, max_turns_each=80, on_turn=None):
    """Play one game between bots (one per seat). Returns (state, reason): reason is "finished"
    or says which guard stopped it. `on_turn(state, option)` is called for every turn choice."""
    rng = random.Random(seed)
    state = G.new_game(len(bots), seed=seed)
    turns = 0
    while not state.over:
        frame = state.stack[-1]
        if frame.kind == "turn":
            turns += 1
            if turns > max_turns_each * len(bots):
                return state, f"stopped after {max_turns_each} turns each"
        option = bots[frame.player].choose(state, rng)
        if on_turn and frame.kind == "turn":
            on_turn(state, option)
        G.step(state, option)
    return state, "finished"


def profile(state):
    """Per-player summary of how the game went, for comparing bots with human play."""
    rows = []
    for player in state.players:
        kinds = [cards.card(c)["type"] for c in player.zoo_cards]
        rows.append({
            "score": player.victory_points, "appeal": player.appeal, "conservation": player.conservation,
            "reputation": player.reputation, "money": player.money, "animals": kinds.count("animal"),
            "sponsors": kinds.count("sponsor"), "projects": player.projects_supported,
            "upgrades": len(player.upgraded), "partner_zoos": len(player.partner_zoos),
            "universities": len(player.universities), "pavilions": player.zoo.count("pavilion"),
            "buildings": len(player.zoo.buildings),
            "empty_enclosures": sum(1 for b in player.zoo.buildings if b.kind == "enclosure" and not b.occupied),
        })
    return rows
