"""Fit the bot's valuation weights by self-play (cross-entropy method).

Each generation samples variations of the current weights, plays every variation against
the current weights on the same seeds from both seats, and moves the weights towards the
best few. Fitness is the average score margin. No model is trained: this only tunes the
numbers in arknova.bot.DEFAULT_WEIGHTS.

Usage: python tools/fit_bot.py [--out experiments/fit] [--minutes 30] [--population 6] [--seeds 2]
                               [--workers 6] [--depth 2 --width 3 --variants 6 --follow 5]
Writes, under --out: fit.log (progress), history.jsonl (every generation) and weights.json
(the current best weights). The weights depend on the search settings they were fitted with.
"""
import argparse
import json
import math
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arknova  # noqa: E402,F401
from arknova import bot  # noqa: E402

SEARCH = dict(depth=2, width=3, variants=6, follow=5)  # defaults; set from the command line
MAX_TURNS_EACH = 55
BASELINE_FIRST_SEED = 101  # fixed games against the starting weights: the reward curve
MARGIN_CAP = 40
BOUNDS = {"decay": (0.3, 1.0), "hold": (0.05, 0.9), "idle_enclosure": (0.0, 1.0)}


def sample(mean, sigma, rng):
    weights = {}
    for key, value in mean.items():
        if key == "decay":
            new = value + rng.gauss(0, sigma * 0.4)
        else:
            new = value * math.exp(rng.gauss(0, sigma))
        low, high = BOUNDS.get(key, (0.01, 50.0))
        weights[key] = min(high, max(low, new))
    return weights


def play(task):
    """One game: candidate in `seat`, incumbent in the other. Returns (candidate index, margin, profile)."""
    index, candidate, incumbent, seed, seat, search, max_turns = task
    bots = [bot.LookaheadBot(incumbent, **search), bot.LookaheadBot(incumbent, **search)]
    bots[seat] = bot.LookaheadBot(candidate, **search)
    state, reason = bot.play_game(bots, seed, max_turns_each=max_turns)
    rows = bot.profile(state)
    margin = rows[seat]["score"] - rows[1 - seat]["score"]
    return index, max(-MARGIN_CAP, min(MARGIN_CAP, margin)), rows[seat], reason == "finished"


def geometric_mean(dicts):
    out = {}
    for key in dicts[0]:
        if key == "decay":
            out[key] = sum(d[key] for d in dicts) / len(dicts)
        else:
            out[key] = math.exp(sum(math.log(d[key]) for d in dicts) / len(dicts))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--population", type=int, default=10)
    parser.add_argument("--elites", type=int, default=3)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--sigma", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--minutes", type=float, default=30, help="stop before a generation would pass this")
    parser.add_argument("--out", default="experiments/fit")
    parser.add_argument("--resume", action="store_true",
                        help="continue from the last generation saved in --out/history.jsonl")
    parser.add_argument("--baseline-seeds", type=int, default=2)
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS_EACH)
    for knob, default in SEARCH.items():
        parser.add_argument(f"--{knob}", type=int, default=default)
    args = parser.parse_args()
    search = {knob: getattr(args, knob) for knob in SEARCH}
    baseline_seeds = [BASELINE_FIRST_SEED * (i + 1) for i in range(args.baseline_seeds)]

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "fit.log", "a", buffering=1)

    def say(message):
        log.write(message + "\n")
        print(message, flush=True)

    rng = random.Random(args.seed)
    mean = dict(bot.DEFAULT_WEIGHTS)
    start_weights = dict(mean)  # the reward curve always measures against these
    sigma = args.sigma
    last_generation_seconds = 0.0
    first_generation = 1
    history_path = out / "history.jsonl"
    if args.resume and history_path.exists():
        saved = [json.loads(line) for line in history_path.read_text().splitlines() if line.strip()]
        if saved:
            mean, sigma, first_generation = saved[-1]["mean"], saved[-1]["sigma"], saved[-1]["generation"] + 1
            rng = random.Random(args.seed * 1000 + first_generation)  # fresh seeds, not a replay
            say(f"resuming after generation {saved[-1]['generation']}")
    say(f"start: generations={args.generations} population={args.population} seeds={args.seeds} "
        f"baseline_seeds={args.baseline_seeds} workers={args.workers} minutes={args.minutes:g} search={search}")
    started = time.time()
    with Pool(args.workers) as pool:
        for generation in range(first_generation, args.generations + 1):
            if time.time() - started + last_generation_seconds > args.minutes * 60:
                say(f"time budget of {args.minutes:g} min reached before generation {generation}")
                break
            generation_started = time.time()
            candidates = [sample(mean, sigma, rng) for _ in range(args.population)]
            seeds = [rng.randrange(10 ** 6) for _ in range(args.seeds)]
            tasks = [(i, c, mean, seed, seat, search, args.max_turns)
                     for i, c in enumerate(candidates) for seed in seeds for seat in (0, 1)]
            # index -1: the current weights against the starting weights, on the same seeds every generation
            tasks += [(-1, mean, start_weights, seed, seat, search, args.max_turns)
                      for seed in baseline_seeds for seat in (0, 1)]
            margins = [[] for _ in candidates]
            profiles, finished, reward, reward_scores = [], 0, [], []
            for index, margin, row, done in pool.imap_unordered(play, tasks):
                finished += done
                if index == -1:
                    reward.append(margin)
                    reward_scores.append(row["score"])
                    continue
                margins[index].append(margin)
                profiles.append(row)
            say(f"REWARD gen {generation:2d}: current weights vs starting weights: margin {sum(reward) / len(reward):+.1f} "
                f"(games {sorted(reward)}), own score {sum(reward_scores) / len(reward_scores):+.1f}")
            fitness = [sum(m) / len(m) for m in margins]
            order = sorted(range(len(candidates)), key=lambda i: -fitness[i])
            elites = [candidates[i] for i in order[:args.elites] if fitness[i] > 0]
            if elites:
                mean = geometric_mean(elites + [mean])  # move towards the winners, not onto them
            sigma *= 0.9
            average = {k: round(sum(r[k] for r in profiles) / len(profiles), 1)
                       for k in ("score", "appeal", "conservation", "animals", "projects", "money", "pavilions", "partner_zoos")}
            say(f"gen {generation:2d} {time.time() - started:6.0f}s fitness best {fitness[order[0]]:+.1f} "
                f"median {sorted(fitness)[len(fitness) // 2]:+.1f} elites {len(elites)} finished {finished}/{len(tasks)} "
                f"candidates avg {average}")
            say("        weights " + json.dumps({k: round(v, 3) for k, v in mean.items()}))
            with open(out / "history.jsonl", "a") as history:
                history.write(json.dumps({"generation": generation, "fitness": fitness, "mean": mean,
                                          "reward": reward, "reward_scores": reward_scores,
                                          "sigma": sigma, "profile": average}) + "\n")
            (out / "weights.json").write_text(json.dumps(mean, indent=1) + "\n")
            last_generation_seconds = time.time() - generation_started
    say(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
