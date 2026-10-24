"""Look at a trained network: play it against the heuristic bots, or print how it plays.

Usage: python tools/rl_eval.py MODEL.pt versus [--opponent greedy|lookahead] [--seeds 16] [--workers 32]
                                               [--depth 2 --width 3 --variants 6 --follow 5]
       python tools/rl_eval.py MODEL.pt log [--seed 1] [--turns 60]      one self-play game, turn by turn
       python tools/rl_eval.py MODEL.pt match --against OTHER.pt [--games 200]   network against network (GPU)
"""
import argparse
import random
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

import arknova  # noqa: E402,F401
from arknova import bot, engine as G  # noqa: E402
from arknova.rl.play import PolicyBot  # noqa: E402

KEYS = ("score", "appeal", "conservation", "animals", "sponsors", "projects", "money", "upgrades", "pavilions",
        "partner_zoos", "universities", "reputation", "buildings", "empty_enclosures")


def play(task):
    model, opponent, search, seed, seat = task
    torch.set_num_threads(1)
    other = bot.GreedyBot() if opponent == "greedy" else bot.LookaheadBot(**search)
    bots = [other, other]
    bots[seat] = PolicyBot(model)
    state, reason = bot.play_game(bots, seed, max_turns_each=80)
    rows = bot.profile(state)
    return rows[seat], rows[1 - seat], reason == "finished"


def versus(args):
    search = dict(depth=args.depth, width=args.width, variants=args.variants, follow=args.follow)
    tasks = [(args.model, args.opponent, search, 9000 + i, seat) for i in range(args.seeds) for seat in (0, 1)]
    started = time.time()
    with Pool(args.workers) as pool:
        results = pool.map(play, tasks)
    margins = [a["score"] - b["score"] for a, b, _ in results]
    error = statistics.stdev(margins) / len(margins) ** 0.5
    print(f"network vs {args.opponent}" + (f" {search}" if args.opponent == "lookahead" else "")
          + f": {len(tasks)} games in {time.time() - started:.0f}s, {sum(d for _, _, d in results)} finished")
    print(f"margin for the network: {statistics.mean(margins):+.1f} +/- {error:.1f}; wins {sum(m > 0 for m in margins)}, "
          f"losses {sum(m < 0 for m in margins)}")
    for label, index in (("network ", 0), ("opponent", 1)):
        print(f"  {label}: " + ", ".join(f"{k} {statistics.mean(r[index][k] for r in results):.1f}" for k in KEYS))


def log(args):
    player = PolicyBot(args.model)
    rng = random.Random(args.seed)
    state = G.new_game(2, seed=args.seed)
    turn, line = 0, None
    while not state.over:
        frame = state.stack[-1]
        options = G.legal_options(state)
        if len(options) == 1:
            G.step(state, options[0])
            continue
        p, value = player.probabilities(state, options)
        index = int(p.argmax())
        if frame.kind == "turn":
            if line and turn <= args.turns:
                print(line)
            turn += 1
            me = state.players[frame.player]
            line = (f"T{turn:3d} P{frame.player} [money {me.money:3d} appeal {me.appeal:3d} cons {me.conservation:2d} "
                    f"rep {me.reputation:2d} hand {len(me.hand)} X {me.xtokens}] value {value:+.2f} | ")
        elif frame.kind == "setup_keep":
            line = None
        if line is not None:
            line += f"{options[index].label or options[index].key} ({float(p[index]):.0%} of {len(options)}); "
        G.step(state, options[index])
    print(line)
    print(f"\nfinished after {turn} turns")
    for row in bot.profile(state):
        print("  " + ", ".join(f"{k} {row[k]}" for k in KEYS))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("mode", choices=["versus", "log", "match"])
    parser.add_argument("--against", default="experiments/ppo/keep/run4_70M.pt")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--opponent", choices=["greedy", "lookahead"], default="greedy")
    parser.add_argument("--seeds", type=int, default=16)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--turns", type=int, default=200)
    for knob, default in (("depth", 2), ("width", 3), ("variants", 6), ("follow", 5)):
        parser.add_argument(f"--{knob}", type=int, default=default)
    args = parser.parse_args()
    if args.mode == "match":
        from arknova.rl import match as MATCH
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        started = time.time()
        margins = MATCH.match(MATCH.load(args.model, device), MATCH.load(args.against, device), args.games, device)
        print(f"{args.model} vs {args.against}: {MATCH.summary(margins)} in {time.time() - started:.0f}s")
    else:
        versus(args) if args.mode == "versus" else log(args)
