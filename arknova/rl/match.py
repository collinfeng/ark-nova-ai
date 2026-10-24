"""Games between two networks, batched on one device: for evaluation during and after training."""
import math

import torch

from . import encode as encode_v3, model as model_v3
from .env import SelfPlayEnv, _safe_step
from .v1 import encode as encode_v1, model as model_v1
from .v2 import encode as encode_v2, model as model_v2

VERSIONS = {1: (encode_v1, model_v1), 2: (encode_v2, model_v2), 3: (encode_v3, model_v3)}


def load(checkpoint, device):
    """(network, its encoder module) from a checkpoint file; checkpoints without a version are v1."""
    saved = torch.load(checkpoint, map_location=device, weights_only=True)
    encoder, module = VERSIONS[saved.get("version", 1)]
    net = (module.Net(**saved.get("net", {})) if saved.get("version", 1) >= 2 else module.Net()).to(device)
    net.load_state_dict(saved["model"])
    net.eval()
    net.lookahead = saved.get("lookahead", False)  # v3 networks may be trained with look-ahead features
    return net, encoder


def _choose(net, encoder, envs, device, generator=None):
    """Each game's option: the most likely one, or sampled from the policy when a generator is given."""
    extra = {"lookahead": True} if getattr(net, "lookahead", False) else {}
    batch = model_v3.to_tensors(encoder.collate([encoder.observe(e.state, e.options, **extra) for e in envs]), device)
    with torch.no_grad():
        logits, _, _ = net(batch)
    out = []
    for part in torch.split(logits, batch["counts"].tolist()):
        if generator is None:
            out.append(int(part.argmax()))
        else:
            out.append(int(torch.multinomial(torch.softmax(part, 0), 1, generator=generator)))
    return out


def match(first, second, games, device, seed=0, sample=False, actions=None, maps=("map0",)):
    """`first` and `second` are (network, encoder). Each plays both seats on games // 2 deals (games 2k and
    2k + 1 share a deal), taking its most likely option, or sampling from its policy with `sample`.
    Returns first's score margins (one per game). A dict passed as `actions` counts first's main actions.
    Deal k is on maps[k % len(maps)], so the maps get equal shares."""
    generator = torch.Generator(device=device).manual_seed(seed) if sample else None
    envs = [SelfPlayEnv(seed * 100003 + g // 2, maps=(maps[g // 2 % len(maps)],)) for g in range(games)]
    seat = [g % 2 for g in range(games)]  # first's seat in game g
    margins = [None] * games
    while any(m is None for m in margins):
        for side, (net, encoder) in enumerate((first, second)):
            mine = [g for g in range(games) if margins[g] is None and (envs[g].player == seat[g]) == (side == 0)]
            if not mine:
                continue
            for g, index in zip(mine, _choose(net, encoder, [envs[g] for g in mine], device, generator)):
                key = envs[g].options[index].key
                if actions is not None and side == 0 and key[0] == "act":
                    actions[key[1]] = actions.get(key[1], 0) + 1
                # an engine error is recorded for replay and the game counts as a draw, as in training:
                # a benchmark must not end a run (M7 was stopped by one, 2026-10-19)
                _, done, info = _safe_step(envs[g], index, 0.0)
                if done:
                    scores = info["scores"]
                    margins[g] = scores[seat[g]] - scores[1 - seat[g]] if info["finished"] else 0
    return margins


def summary(margins):
    """Margin and win rate for the first player of a match. The two games of a deal (2k, 2k + 1) are not
    independent, so the standard error is taken over per-deal means."""
    n = len(margins)
    deals = [sum(margins[i:i + 2]) / len(margins[i:i + 2]) for i in range(0, n, 2)]
    mean = sum(margins) / n
    k = len(deals)
    error = math.sqrt(sum((d - mean) ** 2 for d in deals) / (k - 1) / k) if k > 1 else 0.0
    wins, losses = sum(m > 0 for m in margins), sum(m < 0 for m in margins)
    return {"margin": round(mean, 2), "error": round(error, 2), "win_rate": round((wins + 0.5 * (n - wins - losses)) / n, 3),
            "wins": wins, "losses": losses, "games": n}
