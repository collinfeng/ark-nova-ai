"""PPO by self-play: one network plays both seats.

Usage: python tools/train_ppo.py [--out experiments/ppo/run1] [--minutes 30] [--workers 32] [--per-worker 32]
                                 [--learner async|sync]
Writes under --out: train.log, history.jsonl, model.pt and a checkpoint at every benchmark.

Two processes in the default `async` mode, as in Sample Factory's APPO (Petrenko et al. 2020):
- the main process steps the games (through the worker processes) and chooses moves with a copy of
  the network, without ever waiting for learning;
- a learner process trains on each finished batch and publishes new weights after every gradient
  step; the main process picks them up before choosing moves.
The data is therefore slightly stale (a fraction of an update to about one update). PPO's ratio
corrects for that, dual-clip (Ye et al. 2020) bounds the worst case, and the learner recomputes the
value estimates with current weights before computing advantages. `--learner sync` runs the same
learning code in the main process between batches, as before. In async mode the script starts
NVIDIA MPS itself if it is not running (tools/start_mps.sh), so both processes share the GPU.
"""
import argparse
import collections
import copy
import json
import queue
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.multiprocessing as tmp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arknova  # noqa: E402,F401
from arknova import tables as T  # noqa: E402
from arknova.rl import encode, match as MATCH, model as M  # noqa: E402
from arknova.rl.env import VecEnv  # noqa: E402
from arknova.rl.league import agent_advantages  # noqa: E402

OPTION_KEYS = encode.OPTION_KEYS
FLAT_KEYS = (*encode.STATE_KEYS, *OPTION_KEYS, "counts", "logp")


def advantages(rewards, values, dones, players, last_value, last_player, gamma, lam):
    """GAE over a sequence in which the two players alternate. Every value is from the side of the
    player deciding at that step, so the next step's value is negated when the player changes."""
    steps = len(rewards)
    out = np.zeros_like(rewards)
    running = np.zeros_like(last_value)
    next_value, next_player = last_value, last_player
    for t in reversed(range(steps)):
        sign = np.where(players[t] == next_player, 1.0, -1.0) * (~dones[t])
        delta = rewards[t] + gamma * sign * next_value - values[t]
        running = delta + gamma * lam * sign * running
        out[t] = running
        next_value, next_player = values[t], players[t]
    return out


def subset(batch, chosen):
    """The decisions `chosen` (a tensor of indices) of a batch from encode.collate, on the same device."""
    counts = batch["counts"]
    starts = counts.cumsum(0) - counts
    c = counts[chosen]
    first = c.cumsum(0) - c
    rows = torch.repeat_interleave(starts[chosen] - first, c) + torch.arange(int(c.sum()), device=counts.device)
    out = {k: batch[k][chosen] for k in encode.STATE_KEYS}
    out.update({k: batch[k][rows] for k in OPTION_KEYS})
    out["counts"] = c
    return out


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/ppo/run1")
    parser.add_argument("--minutes", type=float, default=30)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--per-worker", type=int, default=32)
    parser.add_argument("--steps", type=int, default=64, help="decisions per game per update")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--minibatches", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.999)
    parser.add_argument("--lam", type=float, default=0.97)
    parser.add_argument("--clip", type=float, default=0.2)
    parser.add_argument("--dual-clip", type=float, default=3.0,
                        help="dual-clip bound c for negative advantages (Ye et al. 2020); 0 turns it off")
    parser.add_argument("--entropy", type=float, default=0.01)
    parser.add_argument("--value-weight", type=float, default=0.5)
    parser.add_argument("--shaping", type=float, default=1.0)
    parser.add_argument("--shaping-fade-updates", type=int, default=0, help="0 keeps the shaping term constant")
    parser.add_argument("--aux-value", action="store_true",
                        help="a second value head learns the shaped return (win + margin/20) as an auxiliary task; "
                             "use with --zero-final-potential so the policy itself learns from win/loss only")
    parser.add_argument("--aux-weight", type=float, default=0.5, help="weight of the auxiliary value loss")
    parser.add_argument("--zero-final-potential", action=argparse.BooleanOptionalAction, default=True,
                        help="shaping potential is 0 at the end of a game: the return is win/loss only, the lead "
                             "still shapes learning during the game (default since 2026-10-18; "
                             "--no-zero-final-potential gives the old return win + margin/20)")
    parser.add_argument("--bench", default="experiments/ppo/keep/long_s0_262M.pt,experiments/ppo/keep/long_s0_1B.pt",
                        help="comma-separated checkpoints to play every --bench-every updates; empty to skip")
    parser.add_argument("--bench-every", type=int, default=100)
    parser.add_argument("--bench-games", type=int, default=200)
    parser.add_argument("--pool-fraction", type=float, default=0.0,
                        help="share of games in which one seat is played by a past version of the network")
    parser.add_argument("--pool-every", type=int, default=20, help="updates between snapshots added to the pool")
    parser.add_argument("--pool-size", type=int, default=20)
    parser.add_argument("--anneal-lr", action="store_true",
                        help="learning rate falls linearly to 0 over the whole run (same as --lr-decay-start 0)")
    parser.add_argument("--lr-decay-start", type=float, default=0.7,
                        help="learning rate is constant until this fraction of the run (--max-decisions, or --minutes "
                             "if not set), then falls linearly to 0 at the end; 1 keeps it constant. Late only: an "
                             "early decay made the no-Cards trap likely (07_devlog.md, 2026-10-16)")
    parser.add_argument("--ema", type=float, default=0.999,
                        help="decay per update of an exponential moving average of the weights (0: off); saved as "
                             "ema_NM.pt beside each model_NM.pt and benchmarked as bench_ema_*")
    parser.add_argument("--entropy-final", type=float, default=None,
                        help="entropy weight at the end of the run, reached linearly from --entropy")
    parser.add_argument("--groups", type=int, default=2,
                        help="games are split into this many groups stepped in turn (1: everything in lockstep)")
    parser.add_argument("--learner", choices=["async", "sync"], default="async")
    parser.add_argument("--no-refresh-values", dest="refresh_values", action="store_false",
                        help="use the value estimates made while playing instead of recomputing them")
    # Defaults since 2026-10-17 (step 3c, docs/rl/07_devlog.md): separate value trunk, input normalisation,
    # 16 minibatches, lambda 0.97. Before: shared trunk, no normalisation, 8 minibatches, lambda 0.95
    # (run8, base_s1, base_s2, long_s0); --no-separate-value --no-input-norm --minibatches 8 --lam 0.95.
    parser.add_argument("--separate-value", action=argparse.BooleanOptionalAction, default=True,
                        help="value head with its own trunk")
    parser.add_argument("--input-norm", action=argparse.BooleanOptionalAction, default=True,
                        help="LayerNorm on the trunk input")
    parser.add_argument("--small-policy-init", action="store_true", help="last policy layer scaled by 0.01")
    parser.add_argument("--policy-layers", type=int, default=1, help="hidden layers in the option-scoring head")
    parser.add_argument("--set-attention", type=int, default=0, help="transformer layers over the card sets (v3)")
    parser.add_argument("--privileged-value", action="store_true",
                        help="the value network also sees hidden cards (training only; needs the separate value trunk)")
    parser.add_argument("--lookahead", action="store_true",
                        help="per-option look-ahead features (v3; one state copy and engine step per option)")
    parser.add_argument("--max-decisions", type=int, default=0, help="stop after this many decisions (0: time only)")
    parser.add_argument("--resume", action="store_true",
                        help="continue from OUT/model.pt (weights, optimiser if saved, counters); logs are appended")
    parser.add_argument("--trunk-hidden", type=int, default=512, help="width of the trunks' hidden layer")
    parser.add_argument("--state-dim", type=int, default=256, help="width of the trunks' output (the state features)")
    parser.add_argument("--maps", default="map0",
                        help="comma-separated maps (map0, plan1..plan8, plana) or 'all'; each game is on one drawn "
                             "at random, and benchmark deals cycle through them")
    parser.add_argument("--init", default=None,
                        help="start from this checkpoint's weights (fresh optimiser and counters); same network options")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cuda", help="pass cpu to train without a GPU")
    return parser.parse_args(argv)


def train_maps(args):
    return tuple(encode.MAP_NAMES) if args.maps == "all" else tuple(args.maps.split(","))


def net_config(args):
    return {"separate_value": args.separate_value, "input_norm": args.input_norm,
            "small_policy_init": args.small_policy_init, "policy_layers": args.policy_layers,
            "set_attention": args.set_attention, "privileged_value": args.privileged_value,
            "aux_value": args.aux_value, "trunk_hidden": args.trunk_hidden, "state_dim": args.state_dim}


# ---- learning ---------------------------------------------------------------------------------

# The trap is measured on the network's most likely choices (benchmark games): a trapped policy still puts
# about 15% on Cards at every turn, so sampled training games show Cards often while greedy play never takes it.
CARDS_TRAP = 0.05  # healthy runs take Cards for about a quarter of their greedy main actions; trapped ones under 2%
CARDS_TRAP_AFTER = 15e6  # every run avoids Cards at first (about 0% at 6M decisions); healthy ones stop by 13M


def action_shares(games):
    """Share of each main action (animals, build, cards, association, sponsors) over recent games; a share of
    Cards near zero is the "no Cards" trap that hyg_s1 and hyg_s2 fell into."""
    totals = dict.fromkeys(T.ACTIONS, 0)  # an action never taken still gets a share (0), so the trap shows
    for g in games:
        for name, n in g.get("actions", {}).items():
            totals[name] = totals.get(name, 0) + n
    count = sum(totals.values())
    return {f"share_{name}": round(n / count, 3) for name, n in totals.items()} if count else {}


class Learner:
    """The network being trained, its optimiser, and everything done once per batch: advantages, the PPO
    update, logging, benchmarks and checkpoints. Runs in the main process (sync) or its own (async)."""

    def __init__(self, args, device, publish=None):
        self.args, self.device, self.publish = args, device, publish
        torch.manual_seed(args.seed)
        self.net = M.Net(**net_config(args)).to(device)
        self.net.lookahead = args.lookahead  # benchmark games must encode the same way as training
        self.optimiser = torch.optim.Adam(self.net.parameters(), lr=args.lr, eps=1e-5)
        self.out = ROOT / args.out
        self.out.mkdir(parents=True, exist_ok=True)
        self.log = open(self.out / "train.log", "a", buffering=1)
        self.bench = {Path(p).stem: MATCH.load(ROOT / p, device) for p in args.bench.split(",") if p}
        self.ema = copy.deepcopy(self.net).eval().requires_grad_(False) if args.ema else None
        self.update_count, self.total, self.steps_done = 0, 0, 0
        self.recent = []
        self.started = time.time()
        if getattr(args, "resume", False) and (self.out / "model.pt").exists():
            self.resume(torch.load(self.out / "model.pt", map_location=device))
        elif args.init:
            self.net.load_state_dict(torch.load(ROOT / args.init, map_location=device)["model"])
            if self.ema is not None:
                self.ema.load_state_dict(self.net.state_dict())

    def resume(self, checkpoint):
        """Continue from a saved checkpoint: weights, optimiser (if it was saved) and counters."""
        self.net.load_state_dict(checkpoint["model"])
        if self.ema is not None:
            self.ema.load_state_dict(checkpoint.get("ema", checkpoint["model"]))
        if "optimiser" in checkpoint:
            self.optimiser.load_state_dict(checkpoint["optimiser"])
        self.update_count, self.total = checkpoint["update"], checkpoint["decisions"]
        # steps_done is not restored: it counts weight versions shared with the playing process, which restarts at 0
        self.say(json.dumps({"event": "resume", "update": self.update_count, "decisions": self.total,
                             "optimiser": "optimiser" in checkpoint}))

    def say(self, message):
        self.log.write(message + "\n")
        print(message, flush=True)

    def _values_now(self, flat):
        """Value estimates of every stored decision with the current weights, in chunks; the auxiliary
        head's estimates are left in self.aux_now (None without --aux-value)."""
        out, aux = [], []
        counts = flat["counts"]
        decisions = len(counts)
        with torch.no_grad():
            for chunk in torch.arange(decisions, device=self.device).tensor_split(max(1, decisions // 8192)):
                out.append(self.net(subset(flat, chunk))[2])
                if self.net.last_aux is not None:
                    aux.append(self.net.last_aux)
        self.aux_now = torch.cat(aux).cpu().numpy() if aux else None
        return torch.cat(out).cpu().numpy()

    def update(self, payload):
        args, net, device = self.args, self.net, self.device
        info = payload["info"]
        self.update_count += 1
        lag = self.steps_done - info["version_first"]  # gradient steps between the data's weights and now
        tick = time.time()
        progress = info["progress"]
        start = 0.0 if args.anneal_lr else args.lr_decay_start
        factor = 1.0 if progress <= start or start >= 1 else max(0.0, (1 - progress) / (1 - start))
        for group in self.optimiser.param_groups:
            group["lr"] = args.lr * factor
        entropy_weight = (args.entropy if args.entropy_final is None
                          else args.entropy + (args.entropy_final - args.entropy) * progress)
        flat = payload["flat"]
        if "league" in payload:  # one agent among others: credit from its own decisions only (arknova.rl.league)
            league = payload["league"]
            values = self._values_now(flat) if args.refresh_values else league["values"]
            adv, values = agent_advantages(league["groups"], values, league["me"], args.shaping, args.gamma,
                                           args.lam)
        else:
            groups = payload["groups"]
            if args.refresh_values:
                fresh = self._values_now(flat)
                at = 0
                for g in groups:
                    size = g["values"].size
                    g["values"] = fresh[at:at + size].reshape(g["values"].shape)
                    if self.aux_now is not None:
                        g["aux_values"] = self.aux_now[at:at + size].reshape(g["values"].shape)
                    at += size
            all_values, all_adv = [], []
            for g in groups:
                adv = advantages(g["rewards"], g["values"], g["dones"], g["players"], g["last_value"],
                                 g["last_player"], args.gamma, args.lam)
                all_values.append(g["values"].reshape(-1))
                all_adv.append(adv.reshape(-1))
            values, adv = np.concatenate(all_values), np.concatenate(all_adv)
            if args.aux_value:  # targets of the auxiliary head: lambda-returns of the auxiliary rewards
                aux_returns = np.concatenate([
                    (advantages(g["aux_rewards"], g["aux_values"], g["dones"], g["players"], g["last_aux_value"],
                                g["last_player"], args.gamma, args.lam) + g["aux_values"]).reshape(-1)
                    for g in groups])
                aux_values = np.concatenate([g["aux_values"].reshape(-1) for g in groups])
                all_aux_returns = torch.as_tensor(aux_returns, device=device, dtype=torch.float32)
        returns = adv + values
        all_returns = torch.as_tensor(returns, device=device, dtype=torch.float32)
        all_adv_t = torch.as_tensor(adv, device=device, dtype=torch.float32)
        all_trainable = torch.as_tensor(payload["trainable"], device=device, dtype=torch.float32)
        counts = flat["counts"]
        starts = counts.cumsum(0) - counts
        decisions = len(counts)
        self.total += decisions
        stats, first_shift = [], None
        # small batches (a league agent with a small share) are not cut into minibatches of a few decisions
        minibatches = max(1, min(args.minibatches, decisions // 256))
        for _ in range(args.epochs):
            order = torch.randperm(decisions, device=device)
            for chunk in order.tensor_split(minibatches):
                c = counts[chunk]
                first = c.cumsum(0) - c  # where each decision's options start inside the minibatch
                rows = torch.repeat_interleave(starts[chunk] - first, c) + torch.arange(int(c.sum()), device=device)
                batch = {k: flat[k][chunk] for k in encode.STATE_KEYS}
                batch.update({k: flat[k][rows] for k in OPTION_KEYS})
                batch["counts"] = c
                picked = first + (flat["picked"][chunk] - starts[chunk])
                old_logp = flat["logp"][chunk]
                target = all_returns[chunk]
                a = all_adv_t[chunk]
                if len(a) > 1:  # the standard deviation of one value is undefined (NaN)
                    a = (a - a.mean()) / (a.std() + 1e-8)
                m = all_trainable[chunk]
                logits, owner, value = net(batch)
                logp = M.log_probabilities(logits, owner, len(chunk))
                ratio = (logp[picked] - old_logp).exp()
                surrogate = torch.min(ratio * a, ratio.clamp(1 - args.clip, 1 + args.clip) * a)
                if args.dual_clip:
                    surrogate = torch.where(a < 0, torch.max(surrogate, args.dual_clip * a), surrogate)
                policy_loss = -(surrogate * m).sum() / m.sum().clamp(min=1)
                value_loss = 0.5 * (value - target).pow(2).mean()
                ent = (M.entropy(logp, owner, len(chunk)) * m).sum() / m.sum().clamp(min=1)
                loss = policy_loss + args.value_weight * value_loss - entropy_weight * ent
                if args.aux_value and "league" not in payload:  # the league does not pass auxiliary rewards
                    loss = loss + args.aux_weight * 0.5 * (net.last_aux - all_aux_returns[chunk]).pow(2).mean()
                if not torch.isfinite(loss):  # never let a bad batch poison the weights
                    self.say(json.dumps({"event": "skipped_minibatch", "reason": "non-finite loss",
                                         "update": self.update_count + 1}))
                    continue
                self.optimiser.zero_grad()
                loss.backward()
                grad_norm = torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                self.optimiser.step()
                self.steps_done += 1
                if self.publish:
                    self.publish(net, self.steps_done)
                with torch.no_grad():
                    log_ratio = logp[picked] - old_logp
                    approx_kl = ((ratio - 1) - log_ratio).mean().item()
                    clip_frac = ((ratio - 1).abs() > args.clip).float().mean().item()
                shift = (ratio - 1).abs().mean().item()
                if first_shift is None:
                    first_shift = shift  # ~0 when the data came from these very weights (sync mode)
                stats.append((policy_loss.item(), value_loss.item(), ent.item(), shift, approx_kl, clip_frac,
                              float(grad_norm)))
        if self.ema is not None:  # weight averaging: smooths the update-to-update drift of self-play
            decay = min(args.ema, (1 + self.update_count) / (10 + self.update_count))  # short memory at first
            with torch.no_grad():
                for avg, now in zip(self.ema.state_dict().values(), net.state_dict().values()):
                    if avg.dtype.is_floating_point:
                        avg.lerp_(now, 1 - decay)
                    else:
                        avg.copy_(now)
        t_learn = time.time() - tick
        self.recent = (self.recent + info["infos"])[-200:]
        if not stats:  # every minibatch was skipped
            stats, first_shift = [(float("nan"),) * 7], float("nan")
        mean = np.mean(stats, axis=0)
        explained = 1 - np.var(returns - values) / (np.var(returns) + 1e-8)
        aux_explained = (1 - np.var(aux_returns - aux_values) / (np.var(aux_returns) + 1e-8)
                         if args.aux_value and "league" not in payload else None)
        row = {"update": self.update_count, "decisions": self.total, "seconds": round(time.time() - self.started),
               "per_second": round(decisions / max(info["wall"], 1e-6)),
               "time_env": round(info["t_env"], 2), "time_act": round(info["t_act"], 2), "time_learn": round(t_learn, 2),
               "lag_steps": lag, "policy_loss": round(float(mean[0]), 4), "value_loss": round(float(mean[1]), 4),
               "entropy": round(float(mean[2]), 3), "ratio_shift": round(float(mean[3]), 4),
               "explained": round(float(explained), 3), "approx_kl": round(float(mean[4]), 5),
               "clip_frac": round(float(mean[5]), 4), "grad_norm": round(float(mean[6]), 3),
               "first_shift": round(first_shift, 5), "options_per_decision": round(float(counts.float().mean()), 1),
               "games": len(self.recent), "lr": self.optimiser.param_groups[0]["lr"],
               "entropy_weight": round(entropy_weight, 4), "pool": info["pool"]}
        if aux_explained is not None:
            row["aux_explained"] = round(float(aux_explained), 3)
        pairs = info["outcome_pairs"]
        if len(pairs) > 50:
            v, z = pairs.T
            row.update(value_outcome_mse=round(float(np.mean((v - z) ** 2)), 4),
                       value_outcome_corr=round(float(np.corrcoef(v, z)[0, 1]), 3))
        if self.recent:
            row.update(game_length=round(float(np.mean([g["decisions"] for g in self.recent]))),
                       finished=round(float(np.mean([g["finished"] for g in self.recent])), 2),
                       score=round(float(np.mean([np.mean(g["scores"]) for g in self.recent])), 1),
                       best_score=round(float(np.mean([max(g["scores"]) for g in self.recent])), 1))
            row.update(action_shares(self.recent))
        benchmark = self.bench and self.update_count % args.bench_every == 0
        if benchmark:
            tick = time.time()
            net.eval()
            greedy = {}
            for name, opponent in self.bench.items():
                result = MATCH.summary(MATCH.match((net, encode), opponent, args.bench_games, device,
                                                   seed=self.update_count, actions=greedy, maps=train_maps(args)))
                row.update({f"bench_{name}_{k}": result[k] for k in ("margin", "error", "win_rate")})
                if train_maps(args) != ("map0",):  # Map 0 on its own as well: a mix can hide a loss there
                    result = MATCH.summary(MATCH.match((net, encode), opponent, args.bench_games, device,
                                                       seed=self.update_count, maps=("map0",)))
                    row.update({f"bench_map0_{name}_{k}": result[k] for k in ("margin", "error", "win_rate")})
                if self.ema is not None:
                    self.ema.lookahead = net.lookahead
                    result = MATCH.summary(MATCH.match((self.ema, encode), opponent, args.bench_games, device,
                                                       seed=self.update_count, maps=train_maps(args)))
                    row.update({f"bench_ema_{name}_{k}": result[k] for k in ("margin", "error", "win_rate")})
            net.train()
            row.update({f"greedy_{k}": v for k, v in action_shares([{"actions": greedy}]).items()})
            if row.get("greedy_share_cards", 1) < CARDS_TRAP and self.total > CARDS_TRAP_AFTER:
                self.say(f"warning: Cards is {row['greedy_share_cards']:.0%} of the network's main actions in "
                         "benchmark games; it may be stuck avoiding Cards (docs/rl/07_devlog.md, 2026-10-16)")
            row["time_bench"] = round(time.time() - tick, 1)
        self.say(json.dumps(row))
        with open(self.out / "history.jsonl", "a") as history:
            history.write(json.dumps(row) + "\n")
        checkpoint = {"model": net.state_dict(), "update": self.update_count, "decisions": self.total,
                      "args": vars(args), "version": encode.VERSION, "net": net_config(args),
                      "lookahead": args.lookahead}
        if benchmark:
            torch.save(checkpoint, self.out / f"model_{self.total // 1_000_000}M.pt")
            if self.ema is not None:  # same format, so matches and the board load it like any checkpoint
                torch.save({**checkpoint, "model": self.ema.state_dict(), "ema_of": "model"},
                           self.out / f"ema_{self.total // 1_000_000}M.pt")
        if self.ema is not None:
            checkpoint["ema"] = self.ema.state_dict()
        checkpoint["optimiser"] = self.optimiser.state_dict()  # for --resume
        torch.save(checkpoint, self.out / "model.tmp")
        (self.out / "model.tmp").replace(self.out / "model.pt")  # a crash mid-save cannot corrupt model.pt


class SharedWeights:
    """Two GPU copies of the weights; the learner writes the one not in use, then switches. A version
    number counts gradient steps, so the player knows when to copy and how stale its moves are."""

    def __init__(self, net, ctx):
        self.buffers = [{k: v.detach().clone() for k, v in net.state_dict().items()} for _ in range(2)]
        self.index = ctx.Value("i", 0)
        self.version = ctx.Value("i", 0)

    def write(self, net, version):
        target = 1 - self.index.value
        with torch.no_grad():
            for k, v in net.state_dict().items():
                self.buffers[target][k].copy_(v)
        torch.cuda.synchronize()
        self.index.value = target
        self.version.value = version

    def read_into(self, net):
        version = self.version.value
        source = self.buffers[self.index.value]
        with torch.no_grad():
            for k, v in net.state_dict().items():
                v.copy_(source[k])
        return version


def mps_running():
    """Whether the MPS control daemon is alive (its pipe files outlive it, so they prove nothing)."""
    return subprocess.run(["pgrep", "-x", "nvidia-cuda-mps"], capture_output=True).returncode == 0 or \
        subprocess.run(["pgrep", "-f", "^nvidia-cuda-mps-control"], capture_output=True).returncode == 0


def ensure_mps():
    """Start NVIDIA MPS if it is not running, so the player and learner processes share the GPU at the same
    time instead of taking turns (async is then about 1.5x faster). Must happen before this process first
    touches CUDA: a process connects to MPS, or not, when its CUDA context is created."""
    if mps_running():
        return
    script = ROOT / "tools" / "start_mps.sh"
    try:
        result = subprocess.run([str(script)], capture_output=True, text=True, timeout=30)
        started = result.returncode == 0 and mps_running()
    except (OSError, subprocess.TimeoutExpired):
        started = False
    if started:
        print("started NVIDIA MPS for the async learner", flush=True)
    else:
        print("warning: could not start NVIDIA MPS, so the two processes will take turns on the GPU "
              "(async is then barely faster than sync); try tools/start_mps.sh by hand", flush=True)


def learner_process(args_dict, shared, batches, done):
    """Entry point of the learner process: train on each batch from the queue until it receives None."""
    args = argparse.Namespace(**args_dict)
    device = torch.device(args.device)
    learner = Learner(args, device, publish=shared.write)
    for k, v in learner.net.state_dict().items():  # start from the weights the player starts with
        v.data.copy_(shared.buffers[shared.index.value][k])
    while True:
        payload = batches.get()
        if payload is None:
            break
        if "reset" in payload:  # league: restart from given weights (an exploiter after it is frozen)
            learner.net.load_state_dict({k: v.to(device) for k, v in payload["reset"].items()})
            learner.optimiser = torch.optim.Adam(learner.net.parameters(), lr=args.lr, eps=1e-5)
            learner.steps_done += 1
            shared.write(learner.net, learner.steps_done)
            learner.say(json.dumps({"event": "reset", "update": learner.update_count}))
            continue
        learner.update(payload)
        del payload
    learner.say(f"learner done: {learner.update_count} updates, {learner.total:,} decisions")
    done.set()


# ---- playing ----------------------------------------------------------------------------------

def main():
    args = parse_args()
    if args.learner == "async" and args.device.startswith("cuda"):
        ensure_mps()  # before anything touches CUDA in this process
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        sys.exit("no GPU visible to PyTorch; fix that or pass --device cpu")
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    envs = VecEnv(args.workers, args.per_worker, seed=args.seed, groups=args.groups, lookahead=args.lookahead,
                  privileged=args.privileged_value, zero_final=args.zero_final_potential,
                  aux=args.aux_value, maps=train_maps(args))
    n = envs.n_group  # games per group; the groups take turns so the workers never wait for the network

    if args.learner == "sync":
        learner = Learner(args, device)
        player = learner.net  # the same network plays and learns
        shared, batches, learner_done, process = None, None, None, None
    else:
        ctx = tmp.get_context("spawn")
        player = M.Net(**net_config(args)).to(device).eval()
        start = ROOT / args.out / "model.pt" if args.resume and (ROOT / args.out / "model.pt").exists() else \
            (ROOT / args.init if args.init else None)
        if start:
            player.load_state_dict(torch.load(start, map_location=device)["model"])
        shared = SharedWeights(player, ctx)
        batches, learner_done = ctx.Queue(maxsize=1), ctx.Event()
        process = ctx.Process(target=learner_process, args=(vars(args), shared, batches, learner_done))
        process.start()
        learner = None
    say = learner.say if learner else (lambda message: print(message, flush=True))
    say(f"start: {vars(args)}; games in parallel {envs.n} in {args.groups} groups; "
        f"parameters {sum(p.numel() for p in player.parameters()):,}")

    pool, pool_net = [], M.Net(**net_config(args)).to(device).eval()
    pool_slots = np.arange(n) < round(args.pool_fraction * n)  # in these games the pool plays seat (slot % 2)
    pool_seat = np.arange(n) % 2
    observed = [envs.observe(g) for g in range(args.groups)]
    obs, players = [o for o, _ in observed], [p for _, p in observed]
    game_values = [[[] for _ in range(n)] for _ in range(args.groups)]  # per game: (value, player) so far
    in_flight = collections.deque(maxlen=3)  # batches the learner may still read (their GPU memory must live)
    started, update, version = time.time(), 0, 0
    last_sent = time.time()
    sent = 0
    if args.resume and (ROOT / args.out / "model.pt").exists():
        sent = torch.load(ROOT / args.out / "model.pt", map_location="cpu")["decisions"]
    while time.time() - started < args.minutes * 60 and not (args.max_decisions and sent >= args.max_decisions):
        if learner is None and not process.is_alive():
            sys.exit("the learner process stopped")
        update += 1
        shaping = args.shaping * (max(0.0, 1 - update / args.shaping_fade_updates) if args.shaping_fade_updates else 1.0)
        progress = min(1.0, sent / args.max_decisions if args.max_decisions  # schedules follow the decision budget
                       else (time.time() - started) / (args.minutes * 60))
        if shared is not None:
            version = shared.read_into(player)
        version_first = version if learner is None else learner.steps_done
        if pool_slots.any() and update % args.pool_every == 1:
            pool.append(copy.deepcopy({k: v.cpu() for k, v in player.state_dict().items()}))
            del pool[:-args.pool_size]
        use_pool = pool_slots.any() and len(pool) > 0
        if use_pool:
            pool_net.load_state_dict(pool[np.random.randint(len(pool))])
        timing = {"act": 0.0, "wait": 0.0}
        stores = [{k: [] for k in (*FLAT_KEYS, "picked", "value", "reward", "done", "player", "trainable",
                                   "aux_value", "aux_reward")}
                  for _ in range(args.groups)]
        offsets = [0] * args.groups
        outcome_pairs = []  # (value estimate, final result from the same player's side) for finished games

        def act(g):
            """Choose moves for group g from its latest observations and send them to the workers."""
            nonlocal version
            tick = time.time()
            if shared is not None and shared.version.value != version:
                version = shared.read_into(player)
            store = stores[g]
            batch = M.to_tensors(obs[g], device)
            with torch.no_grad():
                logits, owner, value = player(batch)
                logp = M.log_probabilities(logits, owner, n)
                action, picked = M.sample(logp, owner, batch["counts"])
            actions = action.cpu().numpy()
            trainable = np.ones(n, dtype=bool)
            if use_pool:
                theirs = np.flatnonzero(pool_slots & (players[g] == pool_seat))
                if len(theirs):
                    with torch.no_grad():
                        sub = subset(batch, torch.as_tensor(theirs, device=device))
                        sub_logits, sub_owner, _ = pool_net(sub)
                        sub_logp = M.log_probabilities(sub_logits, sub_owner, len(theirs))
                        actions[theirs] = M.sample(sub_logp, sub_owner, sub["counts"])[0].cpu().numpy()
                    trainable[theirs] = False  # the pool's moves are not the current policy's: no policy update
            store["trainable"].append(trainable)
            for k in (*encode.STATE_KEYS, *OPTION_KEYS, "counts"):
                store[k].append(batch[k])
            store["picked"].append(picked + offsets[g])
            store["logp"].append(logp[picked])
            values_now = value.cpu().numpy()
            store["value"].append(values_now)
            if args.aux_value:
                store["aux_value"].append(player.last_aux.cpu().numpy())
            store["player"].append(players[g])
            for i in range(n):
                game_values[g][i].append((float(values_now[i]), int(players[g][i])))
            offsets[g] += int(obs[g]["counts"].sum())
            envs.send_step(g, actions, shaping)
            timing["act"] += time.time() - tick

        def receive(g):
            tick = time.time()
            obs[g], players[g], reward, done, infos = envs.recv_step()
            for i, info in zip(np.flatnonzero(done), infos):  # infos come in the order of the finished games
                history, game_values[g][i] = game_values[g][i], []
                if info.get("finished"):
                    a, b = info["scores"]
                    result = [np.sign(a - b), np.sign(b - a)]
                    outcome_pairs.extend((v, result[p]) for v, p in history)
            if args.aux_value:  # reward pairs: (reward, auxiliary reward)
                reward, aux_reward = reward[:, 0], reward[:, 1]
                stores[g]["aux_reward"].append(aux_reward)
            stores[g]["reward"].append(reward)
            stores[g]["done"].append(done)
            all_infos.extend(infos)
            timing["wait"] += time.time() - tick

        all_infos = []
        for g in range(args.groups):
            act(g)
        for _ in range(args.steps - 1):
            for g in range(args.groups):
                receive(g)
                act(g)
        for g in range(args.groups):
            receive(g)

        # one batch for the learner: GPU tensors joined across groups, small arrays on the CPU
        groups, parts, rows_before = [], [], 0
        for g in range(args.groups):
            store = stores[g]
            with torch.no_grad():
                last_value = player(M.to_tensors(obs[g], device))[2].cpu().numpy()
            groups.append({"rewards": np.stack(store["reward"]), "values": np.stack(store["value"]),
                           "dones": np.stack(store["done"]), "players": np.stack(store["player"]),
                           "last_value": last_value, "last_player": players[g]})
            if args.aux_value:
                groups[-1].update(aux_rewards=np.stack(store["aux_reward"]), aux_values=np.stack(store["aux_value"]),
                                  last_aux_value=player.last_aux.cpu().numpy())
            part = {k: torch.cat(store[k]) for k in FLAT_KEYS}
            part["picked"] = torch.cat(store["picked"]) + rows_before
            rows_before += int(part["counts"].sum())
            parts.append(part)
        flat = {k: torch.cat([p[k] for p in parts]) for k in (*FLAT_KEYS, "picked")}
        trainable = np.concatenate([np.concatenate(s["trainable"]) for s in stores])
        now = time.time()
        payload = {"flat": flat, "groups": groups, "trainable": trainable,
                   "info": {"t_act": timing["act"], "t_env": timing["wait"], "wall": now - last_sent,
                            "progress": progress, "pool": len(pool) if use_pool else 0, "infos": all_infos,
                            "outcome_pairs": np.array(outcome_pairs, dtype=np.float32).reshape(-1, 2),
                            "version_first": version_first}}
        sent += len(trainable)
        last_sent = now  # the time between batches is what counts for throughput, learning included
        if learner is not None:
            learner.update(payload)
        else:
            in_flight.append(payload)
            while True:  # waits while the learner is still busy with the previous batch
                try:
                    batches.put(payload, timeout=10)
                    break
                except queue.Full:
                    if not process.is_alive():  # a dead learner would otherwise leave the run hanging
                        envs.close()
                        sys.exit("the learner process stopped")
    if learner is None:
        batches.put(None)
        learner_done.wait()
        process.join(timeout=30)
    envs.close()
    say(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
