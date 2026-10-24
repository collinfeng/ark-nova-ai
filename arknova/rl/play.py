"""Use a trained network as a player with the same interface as the bots in arknova.bot."""
import torch

from .. import engine as G
from . import model as M


class PolicyBot:
    """Plays the network's most likely option (or samples from it)."""

    def __init__(self, checkpoint, device="cpu", sample=False):
        from .match import load
        self.device = torch.device(device)
        self.net, self.encoder = load(checkpoint, self.device)
        self.sample = sample

    def probabilities(self, state, options):
        extra = {"lookahead": True} if getattr(self.net, "lookahead", False) else {}
        batch = M.to_tensors(self.encoder.collate([self.encoder.observe(state, options, **extra)]), self.device)
        with torch.no_grad():
            logits, _, value = self.net(batch)
        return torch.softmax(logits, 0), float(value)

    def choose(self, state, rng):
        options = G.legal_options(state)
        if len(options) == 1:
            return options[0]
        p, _ = self.probabilities(state, options)
        index = rng.choices(range(len(options)), weights=p.tolist())[0] if self.sample else int(p.argmax())
        return options[index]
