"""Where the time goes when generating training data.

Usage: python tools/bench_rl.py profile            one process: engine, encoding, collating
       python tools/bench_rl.py vec [--workers 32] [--per-worker 8 16 32] [--seconds 10]
                                                   worker processes with random moves, no network
"""
import argparse
import cProfile
import pstats
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arknova  # noqa: E402,F401
from arknova.rl import encode  # noqa: E402
from arknova.rl.env import SelfPlayEnv, VecEnv  # noqa: E402


def one_process(decisions=6000):
    envs, rng = [SelfPlayEnv(i) for i in range(8)], random.Random(0)

    def run():
        for _ in range(decisions // len(envs)):
            encode.collate([e.observe() for e in envs])
            for e in envs:
                e.step(rng.randrange(len(e.options)))

    started = time.time()
    profiler = cProfile.Profile()
    profiler.runcall(run)
    print(f"{decisions / (time.time() - started):.0f} decisions/s under the profiler")
    pstats.Stats(profiler).sort_stats("cumulative").print_stats(28)


def vectorised(workers, per_worker, seconds):
    envs = VecEnv(workers, per_worker)
    obs, _ = envs.observe()
    rng = np.random.default_rng(0)
    started, decisions = time.time(), 0
    while time.time() - started < seconds:
        obs, _, _, _, _ = envs.step((rng.random(envs.n) * obs["counts"]).astype(np.int64))
        decisions += envs.n
    rate = decisions / (time.time() - started)
    envs.close()
    print(f"workers {workers} x {per_worker} games: {rate:,.0f} decisions/s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["profile", "vec"])
    parser.add_argument("--workers", type=int, nargs="+", default=[32])
    parser.add_argument("--per-worker", type=int, nargs="+", default=[8, 16, 32])
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    if args.mode == "profile":
        one_process()
    else:
        for w in args.workers:
            for k in args.per_worker:
                vectorised(w, k, args.seconds)
