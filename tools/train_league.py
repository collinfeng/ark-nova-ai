"""League training: several agents learn at once and play each other and frozen snapshots.

Usage: python tools/train_league.py --out experiments/league/L1 [--minutes 300] [--max-decisions N]
                                    [--agents agents.json] [any tools/train_ppo.py option]

Design (docs/rl/06_audit.md, "League: design"):
- Agents: by default `main`, `alt` (different settings, so a different style) and `exploiter` (plays only
  the latest frozen main and looks for its weaknesses). Each has its own learner process, as in
  train_ppo.py's async mode, and its own share of the games.
- Matches: one per game, fixed until the game ends. A main-type agent plays itself in --self-share of
  its games and otherwise an opponent drawn by prioritised fictitious self-play (PFSP) from the frozen
  snapshots and the other learning agents.
- Credit: every agent learns only from its own decisions; the opponent's moves are part of the
  environment (arknova.rl.league.agent_advantages). Untrained networks never enter the pool.
- Snapshots: a main-type agent is frozen every --snapshot-every of its decisions. The exploiter is
  frozen when it beats its target in --exploiter-threshold of recent games (or runs out of budget)
  and then restarts from the latest main snapshot.
- Active opponents: new games draw frozen opponents only from --active-opponents snapshots, re-drawn by PFSP
  every --active-every updates, so the cost of a decision round does not grow with the pool.
- A snapshot is dropped from the pool (beyond --pool-max) only when no running game plays with it.
- The exploiter starts as a copy of its first target (the first frozen main), not from random weights.
- --resume continues a stopped run: agents' weights and optimisers from OUT/<agent>/model.pt, the pool from
  OUT/pool/, win rates and exploiter progress from OUT/league_state.json; logs are appended.
Writes per agent: OUT/<agent>/ (train.log, history.jsonl, checkpoints); league-wide: OUT/league.jsonl,
OUT/league_state.json and OUT/pool/<snapshot>.pt.
"""
import argparse
import collections
import copy
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.multiprocessing as tmp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import arknova  # noqa: E402,F401
from arknova.rl import encode, league as L, model as M  # noqa: E402
from arknova.rl.env import VecEnv  # noqa: E402
from train_ppo import FLAT_KEYS, SharedWeights, ensure_mps, learner_process, net_config, subset  # noqa: E402
from train_ppo import parse_args as ppo_args  # noqa: E402

OPTION_KEYS = encode.OPTION_KEYS
FROZEN_BASE = 100  # controller ids: learning agents 0.., frozen snapshots FROZEN_BASE..

DEFAULT_AGENTS = [
    {"name": "main", "role": "main", "share": 0.5, "settings": {}},
    {"name": "alt", "role": "main", "share": 0.3, "settings": {"entropy": 0.03, "shaping": 0.5}},
    {"name": "exploiter", "role": "exploiter", "share": 0.2, "target": "main", "settings": {}},
]


def parse():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agents", default="", help="JSON file with a list of agent specs (default: built in)")
    parser.add_argument("--snapshot-every", type=int, default=8_000_000,
                        help="freeze a main-type agent into the pool every this many of its decisions")
    parser.add_argument("--pool-max", type=int, default=30)
    parser.add_argument("--self-share", type=float, default=0.35)
    parser.add_argument("--exploiter-threshold", type=float, default=0.85)
    parser.add_argument("--exploiter-budget", type=int, default=30_000_000,
                        help="decisions an exploiter gets before it is frozen (if it wins > 50%%) and restarted")
    parser.add_argument("--league-log-every", type=int, default=20)
    parser.add_argument("--active-opponents", type=int, default=4,
                        help="frozen snapshots new games can draw from at a time (re-drawn by PFSP)")
    parser.add_argument("--active-every", type=int, default=10, help="updates between re-draws of the active set")
    own, rest = parser.parse_known_args()
    base = ppo_args(rest)
    return own, base


class Frozen:
    def __init__(self, sid, name, source, net, decisions):
        self.sid, self.name, self.source, self.net, self.decisions = sid, name, source, net, decisions


def rows_of(counts, idx):
    """Option-row indices (numpy) of the decisions `idx` in a batch whose decisions have `counts` options."""
    starts = np.cumsum(counts) - counts
    c = counts[idx]
    return (np.repeat(starts[idx] - (np.cumsum(c) - c), c) + np.arange(int(c.sum()))).astype(np.int64)


def gpu_subset(batch, idx, rows):
    """Like train_ppo.subset, with the decision and row indices already on the GPU (no host round trip)."""
    out = {k: batch[k].index_select(0, idx) for k in encode.STATE_KEYS}
    out.update({k: batch[k].index_select(0, rows) for k in OPTION_KEYS})
    out["counts"] = batch["counts"].index_select(0, idx)
    return out


def main():
    own, base = parse()
    specs = json.loads(Path(own.agents).read_text()) if own.agents else DEFAULT_AGENTS
    names = [s["name"] for s in specs]
    index_of = {name: i for i, name in enumerate(names)}
    out = ROOT / base.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "pool").mkdir(exist_ok=True)
    log = open(out / "league.jsonl", "a", buffering=1)
    ensure_mps()
    if not torch.cuda.is_available():
        sys.exit("no GPU visible to PyTorch")
    device = torch.device(base.device)
    rng = random.Random(base.seed)
    np_rng = np.random.default_rng(base.seed)
    envs = VecEnv(base.workers, base.per_worker, seed=base.seed, groups=2, lookahead=base.lookahead,
                  privileged=base.privileged_value)
    groups_n, n = 2, envs.n_group

    # one learner process per agent, each with its own settings and output folder
    ctx = tmp.get_context("spawn")
    players, shared, queues, finished, processes, agent_cfg = [], [], [], [], [], []
    agent_decisions = [0] * len(specs)
    for i, spec in enumerate(specs):
        cfg = copy.copy(base)
        for key, value in spec.get("settings", {}).items():
            setattr(cfg, key, value)
        cfg.out = f"{base.out}/{spec['name']}"
        cfg.seed = base.seed * 100 + i
        cfg.learner = "async"
        agent_cfg.append(cfg)
        torch.manual_seed(cfg.seed)  # agents start from different weights
        player = M.Net(**net_config(cfg)).to(device).eval()
        saved = ROOT / cfg.out / "model.pt"
        if base.resume and saved.exists():
            checkpoint = torch.load(saved, map_location=device)
            player.load_state_dict(checkpoint["model"])
            agent_decisions[i] = checkpoint["decisions"]
        weights = SharedWeights(player, ctx)
        batches, done = ctx.Queue(maxsize=1), ctx.Event()
        process = ctx.Process(target=learner_process, args=(vars(cfg), weights, batches, done))
        process.start()
        players.append(player)
        shared.append(weights)
        queues.append(batches)
        finished.append(done)
        processes.append(process)
    versions = [0] * len(specs)

    def say(row):
        log.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)

    results = L.Results()
    match = [[] for _ in range(groups_n)]  # per game slot: (controller of seat 0, of seat 1), set below
    frozen = {}  # sid -> Frozen
    next_sid = FROZEN_BASE
    since_reset = [0] * len(specs)
    exploiter_started = [False] * len(specs)  # an exploiter starts as a copy of its first target, not from scratch
    state_file = out / "league_state.json"
    if base.resume:  # rebuild the pool from its files and the league state (if saved) from league_state.json
        for path in sorted((out / "pool").glob("*.pt")):
            name = path.stem  # "<agent>-<sid>@<N>M"
            source, sid = name.split("@")[0].rsplit("-", 1)
            checkpoint = torch.load(path, map_location=device)
            net = M.Net(**checkpoint["net"]).to(device).eval()
            net.load_state_dict(checkpoint["model"])
            frozen[int(sid)] = Frozen(int(sid), name, source, net, checkpoint["decisions"])
        next_sid = max(frozen, default=FROZEN_BASE - 1) + 1
        if state_file.exists():
            state = json.loads(state_file.read_text())
            since_reset = state["since_reset"]
            exploiter_started = state["exploiter_started"]
            for (a, b), games in state["results"]:
                results.games[(a, b)].extend(games)
        else:  # a run from before the state file: its exploiters have already been restarted from main
            exploiter_started = [spec["role"] == "exploiter" and agent_decisions[i] > 0 for i, spec in enumerate(specs)]
    next_snapshot = [(d // own.snapshot_every + 1) * own.snapshot_every for d in agent_decisions]

    def label(c):
        return names[c] if c < FROZEN_BASE else frozen[c].name

    def in_use():
        return {c for g in range(groups_n) for pair in match[g] for c in pair if c >= FROZEN_BASE}

    def trim_pool():
        """Drop the oldest snapshots beyond --pool-max, but never an agent's latest one or one a running game
        still plays with (dropping that crashed L1); the pool may stay over the limit until those games end."""
        while len(frozen) > own.pool_max:
            latest = {max((s for s in frozen.values() if s.source == a), key=lambda s: s.sid).sid
                      for a in {s.source for s in frozen.values()}}
            busy = in_use()
            droppable = [s for s in frozen if s not in latest and s not in busy]
            if not droppable:
                return
            oldest = min(droppable)
            del frozen[oldest]
            active.discard(oldest)

    def freeze(i):
        nonlocal next_sid
        net = M.Net(**net_config(agent_cfg[i])).to(device).eval()
        net.load_state_dict(players[i].state_dict())
        sid = next_sid
        next_sid += 1
        snap = Frozen(sid, f"{names[i]}-{sid}@{agent_decisions[i] / 1e6:.0f}M", names[i], net, agent_decisions[i])
        frozen[sid] = snap
        torch.save({"model": net.state_dict(), "version": encode.VERSION, "net": net_config(agent_cfg[i]),
                    "args": vars(agent_cfg[i]), "decisions": agent_decisions[i], "lookahead": base.lookahead},
                   out / "pool" / f"{snap.name}.pt")
        trim_pool()
        say({"event": "freeze", "snapshot": snap.name, "pool": len(frozen)})
        return sid

    def latest_snapshot(agent_name):
        own_snaps = [s for s in frozen.values() if s.source == agent_name]
        return max(own_snaps, key=lambda s: s.sid).sid if own_snaps else None

    # Active opponents: new games draw frozen opponents only from a small set, re-drawn by PFSP every
    # --active-every updates. Each distinct network in a decision round costs a forward pass and its overhead,
    # so this keeps the cost fixed however large the pool grows (L1 fell from 37k to 11k decisions/s).
    active = set()

    def redraw_active():
        active.clear()
        sids = list(frozen)
        if not sids:
            return
        rates = [results.win_rate("main", frozen[s].name) for s in sids]
        k = min(own.active_opponents, len(sids))
        active.update(int(s) for s in np_rng.choice(sids, size=k, replace=False, p=L.pfsp_weights(rates)))

    def new_match():
        """(controller of seat 0, controller of seat 1): fixed until the game ends."""
        focus = rng.choices(range(len(specs)), weights=[s["share"] for s in specs])[0]
        spec = specs[focus]
        if spec["role"] == "exploiter":
            target = latest_snapshot(spec["target"])
            opponent = target if target is not None else index_of[spec["target"]]
        else:
            candidates = [frozen[s].name for s in active if s in frozen] + [
                nm for nm in names if nm != spec["name"] and specs[index_of[nm]]["role"] != "exploiter"]
            pick = L.choose_opponent(spec["name"], candidates, results, rng, own.self_share)
            if pick == L.SELF:
                opponent = focus
            elif pick in index_of:
                opponent = index_of[pick]
            else:
                opponent = next(s.sid for s in frozen.values() if s.name == pick)
        return (focus, opponent) if rng.random() < 0.5 else (opponent, focus)

    def save_state():
        state_file.with_suffix(".tmp").write_text(json.dumps({
            "since_reset": since_reset, "exploiter_started": exploiter_started,
            "results": [[list(pair), list(games)] for pair, games in results.games.items()]}))
        state_file.with_suffix(".tmp").replace(state_file)

    trim_pool()  # after a resume the pool folder holds every snapshot ever frozen
    redraw_active()
    for g in range(groups_n):
        match[g] = [new_match() for _ in range(n)]
    say({"event": "resume" if base.resume else "start", "agents": specs, "league": vars(own), "base": vars(base),
         "decisions": dict(zip(names, agent_decisions)), "pool": [s.name for s in frozen.values()]})
    observed = [envs.observe(g) for g in range(groups_n)]
    obs, deciders = [o for o, _ in observed], [p for _, p in observed]
    in_flight = collections.deque(maxlen=3 * len(specs))  # batches learners may still read: their GPU memory must live
    started, update = time.time(), 0
    sent = sum(agent_decisions)
    last_sent = time.time()
    try:
        while time.time() - started < base.minutes * 60 and not (base.max_decisions and sent >= base.max_decisions):
            if not all(p.is_alive() for p in processes):
                sys.exit("a learner process stopped")
            update += 1
            if update % own.active_every == 0:
                redraw_active()
            progress = min(1.0, sent / base.max_decisions if base.max_decisions
                           else (time.time() - started) / (base.minutes * 60))
            version_first = list(versions)
            timing = {"act": 0.0, "wait": 0.0}
            stores = [[{k: [] for k in (*FLAT_KEYS, "picked", "value")} for _ in range(groups_n)] for _ in specs]
            offsets = [[0] * groups_n for _ in specs]
            timelines = [{"decider": [], "ctrl": [], "win": [], "change": [], "done": []} for _ in range(groups_n)]
            all_infos = []

            def act(g):
                """Choose every game's option. Index arithmetic is done on the CPU and sent in one copy, and the
                chosen options come back in one copy, so the GPU is synchronised once per round, not twice per
                network in the round."""
                tick = time.time()
                for i in range(len(specs)):
                    if shared[i].version.value != versions[i]:
                        versions[i] = shared[i].read_into(players[i])
                counts = obs[g]["counts"]
                batch = M.to_tensors(obs[g], device)
                ctrl = np.array(match[g], dtype=np.int64)  # [n, 2] at the time of this decision
                decider = deciders[g].astype(np.int64)
                who = ctrl[np.arange(n), decider]
                controllers = [int(c) for c in np.unique(who)]
                idxs = [np.flatnonzero(who == c) for c in controllers]
                rows = [rows_of(counts, idx) for idx in idxs]
                flat_index = torch.as_tensor(np.concatenate(idxs + rows), device=device)
                pieces = torch.split(flat_index, [len(x) for x in idxs + rows])
                actions = torch.zeros(n, dtype=torch.long, device=device)
                for k, c in enumerate(controllers):
                    idx_t, rows_t = pieces[k], pieces[len(controllers) + k]
                    sub = gpu_subset(batch, idx_t, rows_t)
                    net = players[c] if c < FROZEN_BASE else frozen[c].net
                    with torch.no_grad():
                        logits, owner, value = net(sub)
                        logp = M.log_probabilities(logits, owner, len(idxs[k]))
                        action, picked = M.sample(logp, owner, sub["counts"])
                    actions.index_copy_(0, idx_t, action)
                    if c < FROZEN_BASE:  # a learning agent's decision: keep it for its learner
                        store = stores[c][g]
                        for key in (*encode.STATE_KEYS, *OPTION_KEYS, "counts"):
                            store[key].append(sub[key])
                        store["picked"].append(picked + offsets[c][g])
                        store["logp"].append(logp[picked])
                        store["value"].append(value)
                        offsets[c][g] += len(rows[k])
                        agent_decisions[c] += len(idxs[k])
                        since_reset[c] += len(idxs[k])
                timelines[g]["decider"].append(decider)
                timelines[g]["ctrl"].append(ctrl)
                envs.send_step(g, actions.cpu().numpy(), None)  # reward in parts: each agent applies its own shaping
                timing["act"] += time.time() - tick

            def receive(g):
                tick = time.time()
                obs[g], deciders[g], reward, done, infos = envs.recv_step()
                timelines[g]["win"].append(reward[:, 0])
                timelines[g]["change"].append(reward[:, 1])
                timelines[g]["done"].append(done)
                for i, info in zip(np.flatnonzero(done), infos):
                    a, b = match[g][i]
                    if info.get("finished") and a != b:
                        s0, s1 = info["scores"]
                        results.add(label(a), label(b), 1.0 if s0 > s1 else 0.0 if s0 < s1 else 0.5)
                    match[g][i] = new_match()
                all_infos.extend(infos)
                timing["wait"] += time.time() - tick

            for g in range(groups_n):
                act(g)
            for _ in range(base.steps - 1):
                for g in range(groups_n):
                    receive(g)
                    act(g)
            for g in range(groups_n):
                receive(g)

            now = time.time()
            common = [{k: np.stack(v) for k, v in tl.items()} for tl in timelines]
            for i in range(len(specs)):
                parts, rows_before, values = [], 0, []
                for g in range(groups_n):
                    store = stores[i][g]
                    if not store["counts"]:
                        continue
                    part = {k: torch.cat(store[k]) for k in FLAT_KEYS}
                    part["picked"] = torch.cat(store["picked"]) + rows_before
                    rows_before += offsets[i][g]
                    parts.append(part)
                    values.append(torch.cat(store["value"]))
                if not parts:
                    continue
                flat = {k: torch.cat([p[k] for p in parts]) for k in (*FLAT_KEYS, "picked")}
                groups = []
                for g in range(groups_n):
                    with torch.no_grad():
                        end_value = players[i](M.to_tensors(obs[g], device))[2].cpu().numpy()
                    groups.append({**common[g], "end_decider": deciders[g].astype(np.int64), "end_value": end_value})
                decisions = len(flat["counts"])
                payload = {"flat": flat, "trainable": np.ones(decisions, dtype=bool),
                           "league": {"groups": groups, "me": i, "values": torch.cat(values).cpu().numpy()},
                           "info": {"t_act": timing["act"], "t_env": timing["wait"], "wall": now - last_sent,
                                    "progress": progress, "pool": len(frozen), "infos": all_infos,
                                    "outcome_pairs": np.zeros((0, 2), dtype=np.float32),
                                    "version_first": version_first[i]}}
                in_flight.append(payload)
                queues[i].put(payload)
                sent += decisions
            last_sent = now

            # snapshots and exploiter restarts
            for i, spec in enumerate(specs):
                if spec["role"] == "main" and agent_decisions[i] >= next_snapshot[i]:
                    freeze(i)
                    next_snapshot[i] += own.snapshot_every
                if spec["role"] == "exploiter":
                    target = latest_snapshot(spec["target"])
                    if target is None:
                        continue
                    key = (spec["name"], frozen[target].name)
                    rate, games = results.win_rate(*key), results.count(*key)
                    first = not exploiter_started[i]
                    if first or (games >= 100 and rate >= own.exploiter_threshold) \
                            or since_reset[i] >= own.exploiter_budget:
                        if not first and rate > 0.5:
                            freeze(i)
                        queues[i].put({"reset": {k: v.cpu() for k, v in frozen[target].net.state_dict().items()}})
                        for pair in [p for p in results.games if spec["name"] in p]:
                            del results.games[pair]
                        say({"event": "exploiter_start" if first else "exploiter_restart", "target": frozen[target].name,
                             "rate": round(rate, 3), "games": games, "decisions": since_reset[i]})
                        since_reset[i] = 0
                        exploiter_started[i] = True
            if update % own.league_log_every == 0:
                save_state()
                opponents = sorted({b for (a, b) in results.games if a == "main"})
                say({"update": update, "seconds": round(time.time() - started), "sent": sent,
                     "decisions": dict(zip(names, agent_decisions)), "pool": [s.name for s in frozen.values()],
                     "active": sorted(frozen[s].name for s in active if s in frozen),
                     "main_win_rate": {b: round(results.win_rate("main", b), 3) for b in opponents},
                     "main_games": {b: results.count("main", b) for b in opponents}})
        for q in queues:
            q.put(None)
        for done, process in zip(finished, processes):
            done.wait(timeout=600)
            process.join(timeout=30)
        save_state()
        say({"event": "done", "seconds": round(time.time() - started), "decisions": dict(zip(names, agent_decisions))})
    finally:  # on a crash too: stop the learners, so the run exits instead of hanging on the GPU (L1 did)
        for process in processes:
            if process.is_alive():
                process.terminate()
        envs.close()


if __name__ == "__main__":
    main()
