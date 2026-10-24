"""Round robin between trained networks, and each network against the scripted bots.

Usage: python tools/rl_panel.py A.pt B.pt ... [--games 200] [--sample] [--bot-deals 16] [--bots greedy,lookahead]
                                [--out experiments/panel/NAME]
Network pairs play on the GPU (both seats on each deal); bot games run on the CPU in a pool. Writes a
markdown matrix and a JSON file. For each network it reports the mean margin over the panel and the worst
one, the "robustness" number: a network that is strong on average but loses badly to one opponent is
exploitable.
"""
import argparse
import json
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

import arknova  # noqa: E402,F401
from arknova import bot  # noqa: E402
from arknova.rl import match as MATCH  # noqa: E402
from arknova.rl.encode import MAP_NAMES  # noqa: E402
from arknova.rl.play import PolicyBot  # noqa: E402

BOTS = {"greedy": lambda: bot.GreedyBot(),
        "lookahead": lambda: bot.LookaheadBot(depth=2, width=3, variants=6, follow=5)}


def label(path):
    p = Path(path)
    return p.stem if p.stem != "model" else p.parent.name


def bot_game(task):
    model, opponent, seed, seat = task
    torch.set_num_threads(1)
    other = BOTS[opponent]()
    bots = [other, other]
    bots[seat] = PolicyBot(model)
    state, _ = bot.play_game(bots, seed, max_turns_each=80)
    rows = bot.profile(state)
    return rows[seat]["score"] - rows[1 - seat]["score"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--sample", action="store_true", help="networks sample from their policy instead of argmax")
    parser.add_argument("--bots", default="greedy,lookahead")
    parser.add_argument("--bot-deals", type=int, default=16)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--maps", default="map0",
                        help="maps for the network pairs (comma-separated, or 'all'); deals cycle through them. "
                             "Bot games stay on map0")
    parser.add_argument("--out", default="experiments/panel/latest")
    args = parser.parse_args()
    maps = tuple(MAP_NAMES) if args.maps == "all" else tuple(args.maps.split(","))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    names = [label(m) for m in args.models]
    nets = {n: MATCH.load(m, device) for n, m in zip(names, args.models)}
    started = time.time()
    results = {}  # (row, column) -> summary from the row's side
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            s = MATCH.summary(MATCH.match(nets[a], nets[b], args.games, device, seed=7, sample=args.sample,
                                              maps=maps))
            results[(a, b)] = s
            results[(b, a)] = {**s, "margin": -s["margin"], "win_rate": round(1 - s["win_rate"], 3),
                               "wins": s["losses"], "losses": s["wins"]}
    bots = [b for b in args.bots.split(",") if b]
    if bots:
        tasks = [(m, o, 9000 + d, seat) for m in args.models for o in bots for d in range(args.bot_deals)
                 for seat in (0, 1)]
        with Pool(args.workers) as pool:
            margins = pool.map(bot_game, tasks)
        for (m, o, _, _), margin in zip(tasks, margins):
            results.setdefault((label(m), o), []).append(margin)
        for n in names:
            for o in bots:
                ms = results[(n, o)]
                deals = [(ms[k] + ms[k + 1]) / 2 for k in range(0, len(ms), 2)]
                results[(n, o)] = {"margin": round(statistics.mean(ms), 2),
                                   "error": round(statistics.stdev(deals) / len(deals) ** 0.5, 2),
                                   "win_rate": round((sum(x > 0 for x in ms) + 0.5 * sum(x == 0 for x in ms)) / len(ms), 3),
                                   "games": len(ms)}
    columns = names + bots
    lines = [f"Panel ({'sampled' if args.sample else 'argmax'} play; {args.games} games per network pair, "
             f"{2 * args.bot_deals} per bot pair; margin ± error over deals, win rate). Row's result against column.",
             "", "| | " + " | ".join(columns) + " | mean | worst |", "|---" * (len(columns) + 3) + "|"]
    table = {}
    for n in names:
        cells, ms = [], []
        for c in columns:
            if c == n:
                cells.append("")
                continue
            r = results[(n, c)]
            ms.append(r["margin"])
            cells.append(f"{r['margin']:+.1f} ± {r['error']:.1f} ({r['win_rate']:.0%})")
        table[n] = {"mean": round(statistics.mean(ms), 2), "worst": round(min(ms), 2)}
        lines.append(f"| {n} | " + " | ".join(cells) + f" | {table[n]['mean']:+.1f} | {table[n]['worst']:+.1f} |")
    lines.append("")
    lines.append(f"{time.time() - started:.0f} s")
    text = "\n".join(lines)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text(text + "\n")
    out.with_suffix(".json").write_text(json.dumps({"models": dict(zip(names, args.models)), "summary": table,
                                                    "results": {f"{a} vs {b}": r for (a, b), r in results.items()}},
                                                   indent=1) + "\n")


if __name__ == "__main__":
    main()
