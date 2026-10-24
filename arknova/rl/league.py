"""League training pieces that do not need a GPU: credit assignment for one agent among other
controllers, and opponent selection.

Credit assignment follows the audit (docs/rl/06_audit.md): an agent learns only from its own
decisions, and everything between two of its decisions (the opponent's moves, whoever that is) is
part of the environment (TLeague, Sun et al. 2020, p.5). Its value estimates are made only at its
own decisions; rewards earned in between are added to its previous decision, with the opponent's
rewards negated (the game is zero-sum).

Opponent selection follows prioritised fictitious self-play (AlphaStar; weighting (1 - x)^2 for the
agent's win rate x against an opponent), with a fixed share of plain self-play (TLeague p.14).
"""
import collections
import random

import numpy as np

SELF = "self"


def agent_advantages(groups, values, me, shaping, gamma, lam):
    """Advantages and value targets for the decisions of controller `me`.

    groups: one dict per group of games, with arrays over [steps T, games n]:
      decider (seat 0/1 deciding), ctrl ([T, n, 2] controller id of each seat at that step),
      win (win/loss part of the reward), change (lead-change part), done (game ended at that step),
      and at the end of the slice: end_decider [n], end_value [n] (`me`'s value of the next position,
      from the side of whoever decides there).
    values: `me`'s value estimate of each of its decisions, in the order they were collected:
      group by group, step by step, games in ascending order.
    Returns (advantages, values) as arrays over the same decisions.
    """
    rewards, next_index, bootstrap = [], [], []
    k = 0
    for g in groups:
        decider, ctrl, done = g["decider"], g["ctrl"], g["done"]
        reward = g["win"] + shaping * g["change"]  # from the side of whoever decided
        steps, n = decider.shape
        slots = np.arange(n)
        open_k = np.full((n, 2), -1)
        for t in range(steps):
            d = decider[t]
            mine = np.flatnonzero(ctrl[t, slots, d] == me)
            for i in mine:  # a new decision of mine closes my previous one in this game, which bootstraps from it
                s = d[i]
                if open_k[i, s] >= 0:
                    next_index[open_k[i, s]] = k
                open_k[i, s] = k
                rewards.append(0.0)
                next_index.append(None)
                bootstrap.append(0.0)
                k += 1
            for s in (0, 1):  # the step's reward counts for every open decision of mine in the game
                live = np.flatnonzero(open_k[:, s] >= 0)
                if len(live):
                    sign = np.where(d[live] == s, 1.0, -1.0)
                    for i, x in zip(live, sign * reward[t, live]):
                        rewards[open_k[i, s]] += x
            for i in np.flatnonzero(done[t]):  # the game is over: my open decisions end here
                open_k[i] = -1
        for i in range(n):  # still open at the end of the slice: bootstrap from my value of the next position
            for s in (0, 1):
                if open_k[i, s] >= 0:
                    j = open_k[i, s]
                    next_index[j] = -1
                    bootstrap[j] = g["end_value"][i] * (1.0 if g["end_decider"][i] == s else -1.0)
    if k != len(values):
        raise ValueError(f"{k} decisions in the timeline but {len(values)} values")
    advantages = np.zeros(k, dtype=np.float32)
    for j in range(k - 1, -1, -1):  # a decision's successor always comes later, so one backward pass suffices
        nxt = next_index[j]
        if nxt is None:  # the game ended before my next decision
            delta = rewards[j] - values[j]
            advantages[j] = delta
        elif nxt == -1:  # cut off by the end of the slice
            advantages[j] = rewards[j] + gamma * bootstrap[j] - values[j]
        else:
            delta = rewards[j] + gamma * values[nxt] - values[j]
            advantages[j] = delta + gamma * lam * advantages[nxt]
    return advantages, np.asarray(values, dtype=np.float32)


class Results:
    """Recent results between pairs of controllers, for win rates."""

    def __init__(self, window=200):
        self.window = window
        self.games = collections.defaultdict(lambda: collections.deque(maxlen=window))

    def add(self, a, b, score_a):
        """score_a: 1 win, 0.5 draw, 0 loss for a."""
        self.games[(a, b)].append(score_a)
        self.games[(b, a)].append(1.0 - score_a)

    def win_rate(self, a, b, prior=0.5, prior_games=4):
        g = self.games.get((a, b), ())
        return (sum(g) + prior * prior_games) / (len(g) + prior_games)

    def count(self, a, b):
        return len(self.games.get((a, b), ()))


def pfsp_weights(rates, power=2.0):
    """Prioritised fictitious self-play, 'hard' variant: opponents the agent struggles against get more games."""
    weights = np.array([(1.0 - x) ** power for x in rates], dtype=np.float64)
    if weights.sum() <= 0:
        return np.full(len(rates), 1.0 / len(rates))
    return weights / weights.sum()


def choose_opponent(agent, candidates, results, rng, self_share):
    """SELF with probability self_share, otherwise a candidate drawn by PFSP from `agent`'s win rates."""
    if not candidates or rng.random() < self_share:
        return SELF
    weights = pfsp_weights([results.win_rate(agent, c) for c in candidates])
    return candidates[rng.choices(range(len(candidates)), weights=weights)[0]]


def new_rng(seed):
    return random.Random(seed)
