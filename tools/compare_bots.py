"""Head-to-head between two weight sets, both seats on every seed.

Usage: python tools/compare_bots.py A.json B.json [--seeds 12] [--a-open] [--a-reply] [--b-open] [--b-reply]
       [--depth 2 --width 3 --variants 6 --follow 5]
A weights file is a JSON object of overrides for arknova.bot.DEFAULT_WEIGHTS; use "default" for none.
Reports A's score margin over B with a standard error, win counts, and each side's play profile.
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

import arknova  # noqa: E402,F401
from arknova import bot  # noqa: E402


def load(name):
    return {} if name == "default" else json.loads(Path(name).read_text())


def play(task):
    a, b, seed, seat, search, max_turns, a_mode, b_mode = task
    bots = [bot.LookaheadBot(b, **search, **b_mode), bot.LookaheadBot(b, **search, **b_mode)]
    bots[seat] = bot.LookaheadBot(a, **search, **a_mode)
    state, reason = bot.play_game(bots, seed, max_turns_each=max_turns)
    rows = bot.profile(state)
    return rows[seat], rows[1 - seat], reason == "finished"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--first-seed", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-turns", type=int, default=55)
    for knob, default in (("depth", 2), ("width", 3), ("variants", 6), ("follow", 5)):
        parser.add_argument(f"--{knob}", type=int, default=default)
    for side in "ab":
        parser.add_argument(f"--{side}-open", action="store_true", help="this side sees the real deck order")
        parser.add_argument(f"--{side}-reply", action="store_true", help="this side steps its opponent in the search")
    args = parser.parse_args()
    a_mode = dict(open_info=args.a_open, reply=args.a_reply)
    b_mode = dict(open_info=args.b_open, reply=args.b_reply)
    search = dict(depth=args.depth, width=args.width, variants=args.variants, follow=args.follow)
    a, b = load(args.a), load(args.b)
    tasks = [(a, b, args.first_seed + i, seat, search, args.max_turns, a_mode, b_mode) for i in range(args.seeds) for seat in (0, 1)]
    started = time.time()
    with Pool(args.workers) as pool:
        results = pool.map(play, tasks)
    margins = [ra["score"] - rb["score"] for ra, rb, _ in results]
    mean = statistics.mean(margins)
    error = statistics.stdev(margins) / len(margins) ** 0.5
    wins = sum(m > 0 for m in margins)
    losses = sum(m < 0 for m in margins)
    print(f"A mode {a_mode}, B mode {b_mode}")
    print(f"{args.a} vs {args.b}; search {search}; {len(tasks)} games in {time.time() - started:.0f}s; "
          f"{sum(done for _, _, done in results)} finished")
    print(f"margin for A: {mean:+.1f} +/- {error:.1f} (standard error); A wins {wins}, loses {losses}, "
          f"draws {len(margins) - wins - losses}")
    keys = ("score", "appeal", "conservation", "animals", "sponsors", "projects", "money", "pavilions",
            "partner_zoos", "reputation", "empty_enclosures")
    for label, index in (("A", 0), ("B", 1)):
        print(f"  {label}: " + ", ".join(f"{k} {statistics.mean(r[index][k] for r in results):.1f}" for k in keys))


if __name__ == "__main__":
    main()
