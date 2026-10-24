"""Training curves of one or more runs, against decisions, to see whether learning has plateaued.

Usage: python tools/plot_runs.py experiments/ppo/run8 experiments/ppo/base_s1 ... [--out curves.png]
Panels: strength against each benchmark network (with error bars), policy and value loss, entropy,
explained variance and value-vs-result correlation, self-play scores, and the PPO health signals
(clip fraction, approximate KL), and the share of Cards (greedy and sampled) and Build among main actions. Noisy per-update series are smoothed with a moving average.
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PANELS = [
    ("bench", "Margin against benchmark (points)"),
    ("policy_loss", "Policy loss"),
    ("value_loss", "Value loss"),
    ("entropy", "Policy entropy"),
    ("explained", "Value: explained variance"),
    ("value_outcome_corr", "Value vs final result (correlation)"),
    ("best_score", "Self-play winner's score"),
    ("clip_frac", "Clip fraction"),
    ("approx_kl", "Approximate KL"),
    ("greedy_share_cards", "Cards share, greedy benchmark play (trap if near 0)"),
    ("share_cards", "Cards share, sampled training games"),
    ("share_build", "Build share, sampled training games"),
]


def smooth(y, width):
    y = np.asarray(y, dtype=float)
    if len(y) < width or width < 2:
        return y
    kernel = np.ones(width) / width
    padded = np.concatenate([np.full(width - 1, y[0]), y])
    return np.convolve(padded, kernel, mode="valid")


def load(run):
    path = Path(run) / "history.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip().startswith("{")]
    return [r for r in rows if "decisions" in r]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--out", default="curves.png")
    parser.add_argument("--smooth", type=int, default=25, help="moving-average width in updates")
    args = parser.parse_args()
    fig, axes = plt.subplots(4, 3, figsize=(16, 16))
    axes = axes.ravel()
    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for r, run in enumerate(args.runs):
        rows = load(run)
        label = Path(run).name
        colour = colours[r % len(colours)]
        x_all = np.array([row["decisions"] for row in rows]) / 1e6
        for ax, (key, title) in zip(axes, PANELS):
            ax.set_title(title)
            if key == "bench":
                benches = sorted({k[len("bench_"):-len("_margin")] for row in rows for k in row
                                  if k.startswith("bench_") and k.endswith("_margin")})
                for b, name in enumerate(benches):
                    pts = [(row["decisions"] / 1e6, row[f"bench_{name}_margin"], row.get(f"bench_{name}_error", 0))
                           for row in rows if f"bench_{name}_margin" in row]
                    if pts:
                        x, y, e = zip(*pts)
                        ax.errorbar(x, y, yerr=e, color=colour, marker="o", ms=3, capsize=2,
                                    linestyle=["-", "--", ":"][b % 3], label=f"{label} vs {name}")
                ax.axhline(0, color="grey", lw=0.8)
                continue
            pts = [(row["decisions"] / 1e6, row[key]) for row in rows if row.get(key) is not None
                   and np.isfinite(row[key])]
            if pts:
                x, y = zip(*pts)
                ax.plot(x, smooth(y, args.smooth), color=colour, label=label)
        del x_all
    for ax in axes[len(PANELS):]:
        ax.axis("off")
    for ax in axes[:len(PANELS)]:
        ax.set_xlabel("decisions (millions)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(args.out, dpi=110)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
