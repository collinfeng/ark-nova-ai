"""Play a run's saved checkpoints against one opponent on chosen maps (after the fact, or beside a run).

Usage: python tools/ckpt_sweep.py experiments/ppo/RUN OPPONENT.pt [--maps map0] [--games 400] [--every 2]
       [--prefix model] [--seed 11]
Prints and appends to RUN/sweep_<maps>_<opponent>.jsonl one line per checkpoint (skipping ones already there),
so it can be rerun while the run goes on. Same seed for every checkpoint, so they meet the same deals.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

import arknova  # noqa: E402,F401
from arknova.rl import match as MATCH  # noqa: E402
from arknova.rl.encode import MAP_NAMES  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("opponent")
    parser.add_argument("--maps", default="map0")
    parser.add_argument("--games", type=int, default=400)
    parser.add_argument("--every", type=int, default=1, help="use every n-th checkpoint")
    parser.add_argument("--prefix", default="model", help="model or ema")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    maps = tuple(MAP_NAMES) if args.maps == "all" else tuple(args.maps.split(","))
    run, device = ROOT / args.run, torch.device(args.device)
    found = sorted((int(m.group(1)), f) for f in run.glob(f"{args.prefix}_*M.pt")
                   if (m := re.fullmatch(rf"{args.prefix}_(\d+)M\.pt", f.name)))[::args.every]
    out = run / f"sweep_{args.prefix}_{args.maps.replace(',', '_')}_{Path(args.opponent).stem}.jsonl"
    done = {json.loads(line)["decisions_M"] for line in out.open()} if out.exists() else set()
    opponent = MATCH.load(ROOT / args.opponent, device)
    for millions, path in found:
        if millions in done:
            continue
        result = MATCH.summary(MATCH.match(MATCH.load(path, device), opponent, args.games, device, seed=args.seed,
                                           maps=maps))
        row = {"decisions_M": millions, **{k: result[k] for k in ("margin", "error", "win_rate")}}
        print(json.dumps(row), flush=True)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
