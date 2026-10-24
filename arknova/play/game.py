"""One game between a human and the AI: the authoritative state, the move list, undo and analysis.

Moves are stored as JSON-normalised option keys, so a game can be saved, replayed (here or on another
machine) and reviewed. Undo restores a copy of the state saved before each human decision; redo puts
back what undo took, until the human decides something new. Each undo point carries the number of the
human's turn it belongs to, so the board can warn before an undo leaves the current turn.
"""
import json
import random
import re
import threading
import time

from arknova import engine as G
from arknova.state import clone

from . import feed, paths

HIDDEN = {"setup_keep"}  # the AI's choices here would reveal its hand

SAVE_DIR = paths.DATA / "human_games"
CURRENT = SAVE_DIR / "current.json"  # the game in progress, rewritten after every change


def label(option):
    """An option's text without hex coordinates (the board shows placements on the map)."""
    return re.sub(r" at \(\(.*?\)(,\)|\))", "", option.label or str(option.key))


def norm(key):
    """An option key as plain JSON (tuples become lists), for storing and comparing."""
    return json.loads(json.dumps(key))


def find(options, key):
    k = norm(key)
    return next(i for i, o in enumerate(options) if norm(o.key) == k)


def replay(seed, map_name, moves):
    """The state after playing `moves` (normalised keys) from a new game."""
    state = G.new_game(2, seed=seed, map_name=map_name)
    for key in moves:
        options = G.legal_options(state)
        G.step(state, options[find(options, key)])
    return state


class Game:
    path = None  # where checkpoint() keeps this game (an account's own file); None = CURRENT

    def __init__(self, ai, seed=None, human=0, map_name="map0"):
        self.ai = ai
        self.seed = random.randrange(1 << 30) if seed is None else seed
        self.human = human
        self.map_name = map_name
        self.state = G.new_game(2, seed=self.seed, map_name=map_name)
        self.initial_bonus_tiles = {space: list(tiles) for space, tiles in self.state.bonus_tiles.items()}
        self.moves = []  # every option taken, by either side
        self.reward_claims = []  # rebuilt from moves, including for older saved games
        self.records = []  # one per human decision: what the AI thought and what was played
        self.ai_moves = []  # the AI's moves since the human last decided, for the board to show
        self.ai_history = []  # every completed AI turn: [{"turn": n, "moves": [...]}, ...]
        self.undo_stack = []  # undo points: _point() taken before each human decision
        self.redo_stack = []  # undo points of what undo took back, newest last
        self.turn = 0  # the human's turn number: +1 at every end_turn()
        self.started = time.strftime("%Y-%m-%d_%H%M%S")
        self.analysis = None
        self.hint = None  # who advises the human (None: the opponent's own network); see set_hint
        self.hint_name = None
        self.turn_done = False  # the human's turn is over; waiting for "End turn" before the AI plays
        self.acted = False  # the human has decided something since the AI last played
        self.advance()

    # ---- flow -------------------------------------------------------------------------------

    def options(self):
        return G.legal_options(self.state)

    def to_move(self):
        return None if self.state.over else G.to_move(self.state)

    def _step(self, option):
        frame = self.state.stack[-1]
        claim = ({"space": frame.data["space"], "player": frame.player,
                  "choice": option.key[1] if option.key[0] == "tile" else "money"}
                 if frame.kind == "conservation_tile" else None)
        self.moves.append(norm(option.key))
        G.step(self.state, option)
        if claim is not None:
            self.reward_claims.append(claim)

    def _recorded_step(self, option):
        """Play `option` and say what it changed and why (see feed.py)."""
        state = self.state
        kind, text = state.stack[-1].kind, label(option)
        state.ledger, state.causes = [], []
        before = feed.stats(state)
        try:
            self._step(option)
            return feed.entries(state, before, state.ledger, (kind, text))
        finally:
            state.ledger = None

    def advance(self):
        """Play the AI's moves (and its forced ones) until the human has a decision or the game ends.
        The human is asked even when only one option is left, so nothing is played for them unseen.
        Analyses the human's pending decision. When the human's turn has ended, stops before the AI's
        first move and waits for end_turn(), so the hand-over is visible and the turn can be undone."""
        self.analysis = None
        while not self.state.over:
            if self.acted and self._ai_turn_starts():
                self.turn_done = True
                return
            options = self.options()
            if self.to_move() == self.human:
                if self.acted and self.ai_moves:  # the AI chose inside your turn (e.g. its break discard)
                    self._keep_ai_moves()
                self.analysis = self._advise()
                return
            if len(options) == 1:
                if hasattr(self.ai, "forced"):
                    self.ai.forced(options[0].key)
                extra = self._recorded_step(options[0])  # a forced move: its changes belong to the AI's last move
                if self.ai_moves:
                    self.ai_moves[-1].setdefault("feed", []).extend(extra)
                continue
            a = self.ai.analyse(self)
            option = options[a.best]
            kind = self.state.stack[-1].kind
            shown = "Kept 4 starting cards" if kind in HIDDEN else label(option)
            self.ai_moves.append({"kind": kind, "label": shown,
                                  "prob": None if a.extra.get("heuristic") else a.probs[a.best]})
            self.ai_moves[-1]["feed"] = [] if kind in HIDDEN else self._recorded_step(option)
            if kind in HIDDEN:
                self._step(option)

    def _ai_turn_starts(self):
        """True when the AI is about to start its own turn. Its other decisions inside your turn
        (discarding at a break you triggered) do not end your turn."""
        return self.to_move() != self.human and self.state.stack[-1].kind in ("turn", *HIDDEN)  # or its setup

    def _keep_ai_moves(self):
        """The AI's moves since its turn began, kept as that turn's history entry."""
        if self.ai_history and self.ai_history[-1]["turn"] == self.turn:
            self.ai_history[-1] = {"turn": self.turn, "moves": list(self.ai_moves)}
        else:
            self.ai_history.append({"turn": self.turn, "moves": list(self.ai_moves)})

    def _advise(self):
        """The hint for the human's pending decision, from the chosen hint model."""
        a = (self.hint or self.ai).analyse(self)
        a.hint = self.hint_name
        return a

    def _hint_label(self):
        """Name of the model that judges the human's moves now (for the analysis list)."""
        named = self.hint or getattr(self.ai, "adviser", None) or self.ai  # a rule opponent is advised by a network
        return str(getattr(named, "name", None) or "default").removesuffix(".pt")

    def set_hint(self, ai, name):
        """Choose who advises the human (`ai`, called `name`; None for the opponent's own network)."""
        self.hint, self.hint_name = ai, name
        if self.analysis is not None and not self.state.over and not self.turn_done:
            self.analysis = self._advise()

    def play(self, index):
        """The human takes option `index` of the pending decision."""
        if self.state.over or self.to_move() != self.human:
            raise ValueError("not your decision")
        options = self.options()
        option = options[index]
        a = self.analysis
        self.undo_stack.append(self._point())
        self.redo_stack = []
        # Rank counts the options with more weight, so options tied at 0 (a rule policy) share a rank.
        order = sorted(range(len(options)), key=lambda i: -a.probs[i])
        rule = bool(a.extra.get("heuristic"))
        record = {"prob": a.probs[index], "rank": 1 + sum(p > a.probs[index] for p in a.probs),
                  "ai_best_prob": a.probs[a.best], "value": None if rule else a.value,
                  "top": [{"label": label(options[i]), "prob": a.probs[i]} for i in order[:1 if rule else 3]],
                  **({"rule": True} if rule else {})}
        self.records.append({
            "hint": self._hint_label(),
            "move": len(self.moves), "kind": self.state.stack[-1].kind, "chose": label(option),
            "options": len(options), "ai_best": label(options[a.best]), **record,
        })
        self.acted = True
        self.records[-1]["feed"] = self._recorded_step(option)
        self.advance()

    def end_turn(self):
        """The human confirms the end of their turn; the AI plays until the human decides again."""
        if not self.turn_done:
            raise ValueError("your turn is not over")
        self.turn_done = False
        self.acted = False
        self.ai_moves = []
        self.turn += 1
        self.advance()
        if self.ai_moves:
            self._keep_ai_moves()

    # ---- undo and redo ----------------------------------------------------------------------

    def _point(self):
        """Everything needed to come back to this moment exactly."""
        return {"state": clone(self.state), "moves": list(self.moves), "records": list(self.records),
                "reward_claims": list(self.reward_claims),
                "ai_moves": list(self.ai_moves), "ai_history": list(self.ai_history),
                "turn": self.turn, "turn_done": self.turn_done,
                "acted": self.acted, "analysis": self.analysis}

    def _restore(self, point):
        self.state = clone(point["state"])
        self.reward_claims = list(point["reward_claims"])
        self.moves, self.records = list(point["moves"]), list(point["records"])
        self.ai_moves = list(point["ai_moves"])
        self.ai_history = list(point["ai_history"])
        self.turn, self.turn_done, self.acted = point["turn"], point["turn_done"], point["acted"]
        self.analysis = point["analysis"]
        if (self.analysis is None or self.analysis.hint != self.hint_name) and not self.turn_done and not self.state.over:
            self.analysis = self._advise()  # also when the hint model changed since this point was taken

    def undo_leaves_turn(self):
        """True when the next undo goes back into an earlier turn (and so undoes the AI's turn too)."""
        return bool(self.undo_stack) and self.undo_stack[-1]["turn"] < self.turn

    def turn_points(self):
        """How many undo points belong to the current turn."""
        return sum(1 for pt in self.undo_stack if pt["turn"] == self.turn)

    def turn_records(self):
        """The records of the human's decisions in the current turn."""
        return self.records[len(self.records) - self.turn_points():] if self.turn_points() else []

    def turn_log(self):
        """The log lines of the human's current turn so far, forced moves included."""
        first = next((pt for pt in self.undo_stack if pt["turn"] == self.turn), None)
        if first is None:
            return []
        lines = (self.state.log or [])[len(first["state"].log or []):]
        return [line for line in lines if line.startswith(f"P{self.human} ")]

    def undo(self):
        """Back to the human's previous decision."""
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._point())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        """Put back the last decision undo took."""
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._point())
        self._restore(self.redo_stack.pop())
        return True

    def restart_turn(self):
        """Back to the first decision of the current turn. Redo can step forward again."""
        if not self.turn_points():
            return False
        while self.turn_points():
            self.undo()
        return True

    # ---- saving -----------------------------------------------------------------------------

    def to_json(self):
        return {"seed": self.seed, "map": self.map_name, "human": self.human, "ai": self.ai.name,
                "opponent": getattr(self.ai, "checkpoint", None), "hint": self.hint_name,
                "started": self.started, "moves": self.moves, "records": self.records,
                "ai_moves": self.ai_moves, "ai_history": self.ai_history,
                "turn_done": self.turn_done, "acted": self.acted,
                "over": self.state.over, "scores": self.state.scores}

    def checkpoint(self):
        """Keep the game in progress on disk, so a server restart does not lose it."""
        target = self.path or CURRENT
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(f".{threading.get_ident()}.tmp")  # requests run in parallel threads
        tmp.write_text(json.dumps(self.to_json()))
        tmp.replace(target)

    @classmethod
    def resume(cls, ai, data):
        """Rebuild a saved game by replaying its moves, with the undo points before each human decision."""
        game = cls.__new__(cls)
        game.ai, game.seed, game.human = ai, data["seed"], data["human"]
        game.map_name, game.started = data["map"], data["started"]
        game.state = G.new_game(2, seed=game.seed, map_name=game.map_name)
        game.initial_bonus_tiles = {space: list(tiles) for space, tiles in game.state.bonus_tiles.items()}
        game.moves, game.records, game.undo_stack, game.redo_stack = [], [], [], []
        game.reward_claims = []
        game.ai_moves, game.ai_history, game.turn, game.turn_done, game.analysis = [], [], 0, False, None
        saved_history = {entry["turn"]: entry for entry in data.get("ai_history", [])}
        def restore_feeds(saved, rebuilt):
            if saved is None:
                return rebuilt
            return [{**move, **({"feed": rebuilt[i].get("feed", [])}
                                if i < len(rebuilt)
                                and move["label"] == rebuilt[i]["label"] else {})}
                    for i, move in enumerate(saved)]

        records = data["records"]
        acted = False  # as in advance(): the turn ends when the AI starts its turn after a human decision
        for key in data["moves"]:
            options = game.options()
            if acted and game._ai_turn_starts():
                game.turn, acted, game.ai_moves = game.turn + 1, False, []
            # A human decision is wherever a record says one was made (older saves played the human's
            # single options without asking, so those moves have no record).
            decided = len(game.records) < len(records) and records[len(game.records)]["move"] == len(game.moves)
            if decided:
                game.acted = acted
                game.undo_stack.append(game._point())
                game.records.append(dict(records[len(game.records)]))
                acted = True
            elif game.to_move() != game.human and len(options) > 1:
                kind = game.state.stack[-1].kind  # the AI's turn as the board lists it, without its odds
                option = options[find(options, key)]
                game.ai_moves.append({"kind": kind, "label": "Kept 4 starting cards" if kind in HIDDEN else label(option),
                                      "prob": None})
            ai_step = game.to_move() != game.human
            hidden = ai_step and game.state.stack[-1].kind in HIDDEN
            if hidden:
                game._step(options[find(options, key)])
                extra = []
            else:
                extra = game._recorded_step(options[find(options, key)])
            if ai_step and game.ai_moves:
                game.ai_moves[-1].setdefault("feed", []).extend(extra)
            elif decided:
                game.records[-1]["feed"] = extra
            if ai_step and game.ai_moves and (game.state.over or game.to_move() == game.human):
                saved = saved_history.get(game.turn)
                entry = {"turn": game.turn, "moves": restore_feeds(saved["moves"] if saved else None, list(game.ai_moves))}
                if game.ai_history and game.ai_history[-1]["turn"] == game.turn:
                    game.ai_history[-1] = entry  # more of the AI's moves inside your turn
                else:
                    game.ai_history.append(entry)
        game.ai_moves = restore_feeds(data.get("ai_moves"), game.ai_moves)
        if "ai_history" in data:
            rebuilt_history = {entry["turn"]: entry["moves"] for entry in game.ai_history}
            game.ai_history = [{**entry, "moves": restore_feeds(entry["moves"], rebuilt_history.get(entry["turn"], []))}
                               for entry in data["ai_history"]]
        elif game.ai_moves:
            if game.ai_history and game.ai_history[-1]["turn"] == game.turn:
                game.ai_history[-1] = {"turn": game.turn, "moves": list(game.ai_moves)}
            else:
                game.ai_history.append({"turn": game.turn, "moves": list(game.ai_moves)})
        game.turn_done, game.acted = data.get("turn_done", False), data.get("acted", False)
        if not game.state.over and game.to_move() != game.human:  # saved mid hand-over (older saves)
            game.turn_done = game.acted = True
        game.hint = game.hint_name = None  # the server sets the saved hint model (set_hint) after resuming
        game.analysis = None if game.turn_done or game.state.over else game._advise()
        return game

    def save(self):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        path = SAVE_DIR / f"{self.started}_seed{self.seed}.json"
        path.write_text(json.dumps(self.to_json(), indent=1))
        return path
