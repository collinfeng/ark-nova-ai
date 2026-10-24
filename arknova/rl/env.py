"""Self-play environment: one step is one decision by whoever must decide. Decisions with a single
legal option are taken automatically. Rewards are zero-sum and given from the side of the player
who just decided: win or loss at the end, plus an optional shaping term (change in the lead on the
appeal + conservation track).
"""
import json
import queue
import random
import threading
from pathlib import Path
from multiprocessing import Pipe, Process

import numpy as np

from .. import bot, engine as G, tables as T
from . import encode

SHAPING_SCALE = 1 / 20  # a 20-point lead on the track is worth as much as a win
MAX_DECISIONS = 2500    # a game still running after this many decisions is cut off as a draw


def lead(state, p):
    return (bot.track_value(state.players[p]) - bot.track_value(state.players[1 - p])) * SHAPING_SCALE


class SelfPlayEnv:
    def __init__(self, seed, zero_final=False, maps=("map0",)):
        # zero_final: the shaping potential (the lead) counts as 0 once the game is over, so a game's
        # shaping rewards sum to minus the starting lead (about 0) and the return is the win/loss alone;
        # the shaping still rewards gaining the lead during the game (Ng, Harada & Russell 1999).
        self.zero_final = zero_final
        self.maps = tuple(maps)  # each game is on one of these maps, drawn at random
        self.map_name = self.maps[0]
        self.aux_reward = 0.0
        self.seeds = random.Random(seed)
        self.reset()

    def reset(self):
        self.seed = self.seeds.randrange(2 ** 31)
        if len(self.maps) > 1:  # drawn only then, so single-map runs keep their old deals
            self.map_name = self.seeds.choice(self.maps)
        self.history = []  # option indices chosen so far: with the seed and map, enough to replay the game
        self.state = G.new_game(2, seed=self.seed, map_name=self.map_name)
        self.state.log = None
        self.state.cache_options = True
        self.decisions = 0
        self.actions = dict.fromkeys(T.ACTIONS, 0)  # main actions taken this game (both players)
        self._advance()

    def _advance(self):
        """Take forced decisions until a real choice (or the end of the game)."""
        state = self.state
        while not state.over:
            self.options = G.legal_options(state)
            if len(self.options) > 1:
                return
            self._count(self.options[0])
            G.step(state, self.options[0])

    def _count(self, option):
        if option.key[0] == "act":
            self.actions[option.key[1]] += 1

    @property
    def player(self):
        return self.state.stack[-1].player

    def observe(self, lookahead=False, privileged=False):
        return encode.observe(self.state, self.options, lookahead, privileged)

    def step(self, index, shaping=0.0):
        """Returns (reward for the player who decided, done, info). On done the next game has started.
        With shaping=None the reward comes in two parts, (win/loss, change in lead), each from the side of
        the player who decided, so a caller can apply its own shaping weight (the league does, per agent)."""
        state, p = self.state, self.player
        parts = shaping is None
        before = lead(state, p) if (shaping or parts) else 0.0
        self.history.append(index)
        self._count(self.options[index])
        G.step(state, self.options[index])
        self.decisions += 1
        self._advance()
        done = state.over or self.decisions >= MAX_DECISIONS
        removed = 0.0  # the final lead that zero_final leaves out of this step's shaping
        if shaping or parts:
            after = lead(state, p)
            if done and self.zero_final:
                removed, after = after, 0.0
            change = after - before
        else:
            change = 0.0
        reward = 0.0 if parts else shaping * change
        if done:
            info = {"decisions": self.decisions, "finished": state.over,
                    "scores": [pl.victory_points for pl in state.players], "actions": self.actions}
            if state.over:
                winners = G.winners(state)
                if len(winners) == 1:
                    reward += 1.0 if winners[0] == p else -1.0
            # the same step's reward without zero_final (so its game return is win + margin/20), for an
            # auxiliary value head; equal to reward when zero_final is off
            self.aux_reward = reward + (0.0 if parts else shaping * removed)
            self.reset()
            if parts:
                return (reward, change), True, info
            return reward, True, info
        self.aux_reward = reward
        return ((0.0, change) if parts else reward), False, None


CRASHES = Path(__file__).resolve().parent.parent.parent / "experiments" / "crashes"


def _safe_step(env, index, shaping):
    """An engine error must not end a training run: save how to replay the game, start a new one."""
    try:
        return env.step(index, shaping)
    except Exception as error:  # noqa: BLE001
        CRASHES.mkdir(parents=True, exist_ok=True)
        with (CRASHES / "crashes.jsonl").open("a") as log:
            log.write(json.dumps({"error": repr(error), "seed": env.seed, "map": env.map_name,
                                  "choices": env.history}) + "\n")
        env.reset()
        env.aux_reward = 0.0
        return ((0.0, 0.0) if shaping is None else 0.0), True, {"decisions": 0, "finished": False,
                                                                "scores": [0, 0], "crashed": True}


def _worker(pipe, seed, n_envs, groups, lookahead=False, privileged=False, zero_final=False, aux=False,
            maps=("map0",)):
    """Steps its games on command. Games are split into `groups` that are stepped separately, so the
    main process can choose moves for one group while this process plays the other. Results go out
    through a sending thread, so stepping the next group does not wait for the main process to read."""
    envs = [SelfPlayEnv(seed * 1000 + i, zero_final, maps) for i in range(n_envs)]
    size = n_envs // groups
    outbox = queue.Queue()

    def send_loop():
        while True:
            message = outbox.get()
            if message is None:
                return
            pipe.send(message)

    sender = threading.Thread(target=send_loop, daemon=True)
    sender.start()

    def view(part):
        return (encode.collate([e.observe(lookahead, privileged) for e in part]),
                np.array([e.player for e in part], dtype=np.int8))

    while True:
        command, payload = pipe.recv()
        if command == "observe":
            outbox.put(view(envs[payload * size:(payload + 1) * size]))
        elif command == "step":
            group, actions, shaping = payload
            part = envs[group * size:(group + 1) * size]
            results = [_safe_step(e, int(a), shaping) for e, a in zip(part, actions)]
            # with aux, each reward is the pair (reward, auxiliary reward), see SelfPlayEnv.aux_reward
            rewards = [(r[0], e.aux_reward) for r, e in zip(results, part)] if aux else [r[0] for r in results]
            outbox.put((view(part), np.array(rewards, dtype=np.float32),
                        np.array([r[1] for r in results], dtype=bool), [r[2] for r in results if r[2]]))
        else:
            outbox.put(None)
            sender.join()
            pipe.close()
            return


def _join(batches):
    out = {k: np.concatenate([b[k] for b in batches]) for k in batches[0]}
    return out


def replay(seed, choices, map_name="map0"):
    """The game from a crash record, stopped just before its last choice. Returns (env, last index)."""
    env = SelfPlayEnv(0, maps=(map_name,))
    env.seed, env.history, env.decisions = seed, [], 0
    env.state = G.new_game(2, seed=seed, map_name=map_name)
    env.state.log = None
    env.state.cache_options = True
    env._advance()
    for index in choices[:-1]:
        env.step(index)
    return env, choices[-1]


class VecEnv:
    """`workers` processes with `per_worker` games each. The games form `groups` groups (each worker
    holds an equal share of every group); a group is stepped with send_step then recv_step, so the
    caller can work on one group while the workers step another."""

    def __init__(self, workers, per_worker, seed=0, groups=1, lookahead=False, privileged=False, zero_final=False,
                 aux=False, maps=("map0",)):
        assert per_worker % groups == 0
        self.pipes, self.processes = [], []
        self.groups, self.share = groups, per_worker // groups
        self.per_worker, self.n = per_worker, workers * per_worker
        self.n_group = workers * self.share
        for i in range(workers):
            ours, theirs = Pipe()
            process = Process(target=_worker,
                              args=(theirs, seed + i + 1, per_worker, groups, lookahead, privileged, zero_final, aux,
                                    maps),
                              daemon=True)
            process.start()
            self.pipes.append(ours)
            self.processes.append(process)

    def observe(self, group=0):
        for pipe in self.pipes:
            pipe.send(("observe", group))
        parts = [pipe.recv() for pipe in self.pipes]
        return _join([p[0] for p in parts]), np.concatenate([p[1] for p in parts])

    def send_step(self, group, actions, shaping=0.0):
        k = self.share
        for i, pipe in enumerate(self.pipes):
            pipe.send(("step", (group, actions[i * k:(i + 1) * k], shaping)))

    def recv_step(self):
        """Results of the oldest group sent: (observations, players to decide, rewards, dones, infos)."""
        parts = [pipe.recv() for pipe in self.pipes]
        return (_join([p[0][0] for p in parts]), np.concatenate([p[0][1] for p in parts]),
                np.concatenate([p[1] for p in parts]), np.concatenate([p[2] for p in parts]),
                [info for p in parts for info in p[3]])

    def step(self, actions, shaping=0.0, group=0):
        self.send_step(group, actions, shaping)
        return self.recv_step()

    def close(self):
        for pipe in self.pipes:
            pipe.send(("close", None))
        for process in self.processes:
            process.join(timeout=2)
