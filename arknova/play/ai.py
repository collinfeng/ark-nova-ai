"""The AI behind the board: chooses its own moves and analyses the human's.

Implementations share one interface, `analyse(game) -> Analysis`:
- LocalNet runs a checkpoint in this process (CPU is enough: a few ms per decision).
- HeuristicAI runs Greedy or Beam, with a separate neural adviser for human hints.
- RemoteAI asks another game server (e.g. on the PC, through an SSH tunnel) at /api/ai/analyse.
  It sends only the seed, map and the moves so far; the engine is deterministic, so the other side
  replays them. That keeps working when search or a different engine runs there.
"""
import json
import math
import random
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Analysis:
    probs: list  # probability of each legal option, in engine order
    value: float  # the network's estimate for the player to move: about +1 a sure win, -1 a sure loss
    best: int = 0  # index of the most likely option
    extra: dict = field(default_factory=dict)
    hint: str | None = None  # which hint model made it (see Game.set_hint)

    def to_json(self):
        return {"probs": self.probs, "value": self.value, "best": self.best, **self.extra}


class LocalNet:
    def __init__(self, checkpoint, device="cpu"):
        import torch  # noqa: PLC0415 (only needed when a network is used)
        from arknova.rl import match, model as model_v3  # noqa: PLC0415
        self.torch, self.model_v3, self.device = torch, model_v3, device
        self.net, self.encoder = match.load(checkpoint, device)
        self.name = Path(checkpoint).stem
        self.checkpoint = Path(checkpoint).name

    def analyse_state(self, state, options):
        extra = {"lookahead": True} if getattr(self.net, "lookahead", False) else {}
        batch = self.model_v3.to_tensors(self.encoder.collate([self.encoder.observe(state, options, **extra)]),
                                         self.device)
        with self.torch.no_grad():
            logits, _, value = self.net(batch)  # (option logits, owner index, value)
        probs = self.torch.softmax(logits, 0).tolist()
        best = max(range(len(probs)), key=probs.__getitem__)
        return Analysis([round(p, 4) for p in probs], round(float(value.flatten()[0]), 4), best)

    def analyse(self, game):
        return self.analyse_state(game.state, game.options())


BUILTIN_OPPONENTS = {
    "greedy": None,
    "beam_2x3": {"depth": 2, "width": 3, "variants": 6, "follow": 5},
    "beam_3x8": {"depth": 3, "width": 8, "variants": 10, "follow": 8},
}


class HeuristicAI:
    """A game-local rule/search opponent; the neural adviser still evaluates human decisions.

    A rule bot's policy is all on its move (probability 1); it has no calibrated win prediction, and its
    moves carry no odds in the activity log. They use their own RNG, never the real deck's RNG.
    """
    def __init__(self, name, adviser=None):
        """`adviser`: the network that evaluates the human's decisions when this is the opponent. Without
        one, human decisions get this bot's own choice too: that is how a rule policy gives hints."""
        self.name = self.checkpoint = name
        self.adviser = adviser
        self._prefix = None
        self._last = None
        self._reset()

    def _reset(self):
        from arknova import bot
        config = BUILTIN_OPPONENTS[self.name]
        self.bot = bot.GreedyBot() if config is None else bot.LookaheadBot(**config)

    def analyse(self, game):
        if self.adviser is not None and game.to_move() == game.human:
            return self.adviser.analyse(game)
        prefix = game.moves
        if self._prefix == prefix and self._last is not None:
            return self._last
        if self._prefix is not None and prefix[:len(self._prefix)] != self._prefix:
            self._reset()  # undo, restart or another branch invalidates a stored search plan
        rng = random.Random(f"{self.name}:{game.seed}:{len(prefix)}")
        options = game.options()
        selected = self.bot.choose(game.state, rng)
        best = next(i for i, option in enumerate(options) if option.key == selected.key)
        self._prefix = list(prefix)
        # A deterministic policy is a distribution with all its weight on its move; it has no value estimate.
        self._last = Analysis([1.0 if i == best else 0.0 for i in range(len(options))], 0.0, best, {"heuristic": True})
        return self._last

    def forced(self, key):
        """Forced steps are played by Game, but may also be part of a beam's queued plan."""
        normalised = json.loads(json.dumps(key))
        for planned in getattr(self.bot, "planned", {}).values():
            if planned and json.loads(json.dumps(planned[0])) == normalised:
                planned.pop(0)


class RemoteAI:
    def __init__(self, url, name="remote"):
        self.url = url.rstrip("/") + "/api/ai/analyse"
        self.name = name

    def analyse(self, game):
        body = json.dumps({"seed": game.seed, "map": game.map_name, "moves": game.moves}).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        return Analysis(d["probs"], d["value"], d["best"])


def win_chance(value):
    """Rough reading of a value as a win probability (the value target is +1 win / -1 loss plus a small
    lead term), for display only."""
    return max(0.0, min(1.0, (value + 1) / 2)) if math.isfinite(value) else 0.5
