"""Do different maps pull a network's weights in different directions? (gradient conflict test)

Usage: python tools/grad_conflict.py CHECKPOINT [--games 48] [--maps all] [--out experiments/grad_conflict/NAME]

For each map, the network plays `--games` self-play games (sampling from its policy). From those decisions it
computes the gradient of a Monte Carlo actor-critic loss: policy term -(z - v) log pi(chosen) and value term
(v - z)^2 / 2, where z is the decider's final result (+1 win, -1 loss). The games of each map are split in
two halves (even and odd games), giving two independent gradient estimates per map.

Per parameter group it reports
  - same map: cosine between the two halves of one map (the noise ceiling: what agreement looks like when
    the task is identical),
  - other maps: cosine between half A of one map and half B of another.
Other maps well below same map means the maps want different changes; negative means they conflict
(one map's improvement is another's loss), the case for per-map parameters or a mixture of experts.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

import arknova  # noqa: E402,F401
from arknova.rl import match as MATCH, model as M  # noqa: E402
from arknova.rl.encode import MAP_NAMES  # noqa: E402
from arknova.rl.env import SelfPlayEnv  # noqa: E402

GROUPS = [  # (name, parameter-name prefixes)
    ("card and word embeddings", ("card_id", "card_printed", "card_context", "word", "set_kind", "input_norm")),
    ("policy trunk, input layer", ("trunk.0.0",)),
    ("policy trunk, 2nd layer", ("trunk.0.2",)),
    ("option encoder", ("option",)),
    ("policy head", ("policy",)),
    ("value trunk, input layer", ("value_trunk.0.0",)),
    ("value trunk, 2nd layer", ("value_trunk.0.2",)),
    ("value head", ("value.",)),
]


def play(net, encoder, map_name, games, device, seed):
    """Self-play games on one map; returns, per game, its decisions (observation, chosen index, decider) and result."""
    envs = [SelfPlayEnv(seed * 1000 + g, maps=(map_name,)) for g in range(games)]
    records = [[] for _ in range(games)]
    results = [None] * games
    generator = torch.Generator(device=device).manual_seed(seed)
    while any(r is None for r in results):
        live = [g for g in range(games) if results[g] is None]
        observations = [encoder.observe(envs[g].state, envs[g].options) for g in live]
        batch = M.to_tensors(encoder.collate(observations), device)
        with torch.no_grad():
            logits, _, _ = net(batch)
        for g, obs, part in zip(live, observations, torch.split(logits, batch["counts"].tolist())):
            index = int(torch.multinomial(torch.softmax(part, 0), 1, generator=generator))
            records[g].append((obs, index, envs[g].player))
            _, done, info = envs[g].step(index)
            if done:
                s = info["scores"]
                results[g] = (s if info["finished"] else None) or [0, 0]
    return [(rec, res) for rec, res in zip(records, results)]


def gradient(net, encoder, games, device, chunk=1024):
    """Flat gradient per group of the Monte Carlo actor-critic loss over these games' decisions."""
    rows = []
    for rec, scores in games:
        for obs, index, p in rec:
            z = 0.0 if scores[0] == scores[1] else (1.0 if scores[p] > scores[1 - p] else -1.0)
            rows.append((obs, index, z))
    net.zero_grad()
    for start in range(0, len(rows), chunk):
        part = rows[start:start + chunk]
        batch = M.to_tensors(encoder.collate([r[0] for r in part]), device)
        logits, _, values = net(batch)
        z = torch.tensor([r[2] for r in part], device=device)
        logp = torch.stack([torch.log_softmax(seg, 0)[r[1]]
                            for seg, r in zip(torch.split(logits, batch["counts"].tolist()), part)])
        loss = (-(z - values.detach()) * logp + 0.5 * (values - z) ** 2).sum() / len(rows)
        loss.backward()
    named = dict(net.named_parameters())
    out = {}
    for name, prefixes in GROUPS:
        grads = [named[k].grad.flatten() for k in named if k.startswith(prefixes) and named[k].grad is not None]
        if grads:
            out[name] = torch.cat(grads).clone()
    return out, len(rows)


def cosine(a, b):
    return float(torch.dot(a, b) / (a.norm() * b.norm() + 1e-12))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("--games", type=int, default=48, help="games per map (split into two halves)")
    parser.add_argument("--maps", default="all")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", default="experiments/grad_conflict/latest")
    args = parser.parse_args()
    maps = list(MAP_NAMES) if args.maps == "all" else args.maps.split(",")
    device = torch.device(args.device)
    net, encoder = MATCH.load(ROOT / args.checkpoint, device)
    halves, decisions = {}, {}
    for i, m in enumerate(maps):
        games = play(net, encoder, m, args.games, device, seed=1 + i)
        halves[m] = [gradient(net, encoder, games[h::2], device)[0] for h in (0, 1)]
        decisions[m] = sum(len(r) for r, _ in games)
        print(f"{m}: {args.games} games, {decisions[m]} decisions", flush=True)
    report = {"checkpoint": args.checkpoint, "games_per_map": args.games, "decisions": decisions, "groups": {}}
    lines = [f"Gradient agreement between maps, {Path(args.checkpoint).name}, {args.games} games per map "
             "(cosine of gradients; same map = two halves of one map's games, the noise ceiling)", "",
             "| Parameter group | same map | other maps | other maps, lowest pair | other / same |",
             "|---|---|---|---|---|"]
    for name, _ in GROUPS:
        if name not in halves[maps[0]][0]:
            continue
        same = [cosine(halves[m][0][name], halves[m][1][name]) for m in maps]
        pairs = {(a, b): cosine(halves[a][0][name], halves[b][1][name]) for a in maps for b in maps if a != b}
        lowest = min(pairs, key=pairs.get)
        s, o = statistics.mean(same), statistics.mean(pairs.values())
        lines.append(f"| {name} | {s:+.3f} | {o:+.3f} | {pairs[lowest]:+.3f} ({lowest[0]}, {lowest[1]}) | "
                     f"{o / s if s > 0 else float('nan'):.2f} |")
        report["groups"][name] = {"same": dict(zip(maps, same)), "other_mean": o,
                                  "pairs": {f"{a},{b}": v for (a, b), v in pairs.items()}}
    text = "\n".join(lines)
    print(text)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(text + "\n")
    (out / "report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
