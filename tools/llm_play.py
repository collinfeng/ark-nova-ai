"""Two LLM agents play Ark Nova through the engine, to read how they reason about the game.

Each decision with more than one legal option becomes one stateless request: a fixed rules
primer (system prompt, cache-friendly), then the current state as text, the recent moves, the
agent's own plan from its previous decision, and the numbered options. The reply is JSON
{"choice": n, "plan": "...", "reason": "..."}. Every decision is written to a JSONL log with the
reason, so the game can be read afterwards.

Usage:
  python tools/llm_play.py --dry-run --games 3          # greedy bots choose; measure prompt sizes and cost
  python tools/llm_play.py --model deepseek/deepseek-v4.1-flash --seed 0
  python tools/llm_play.py --p0 net:experiments/ppo/keep/long_s0_1B.pt --p1 llm --seed 5   # our network vs the LLM

Prices are per million tokens (input, output); the cost estimate ignores prompt caching, which
only makes the system prompt cheaper.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arknova import bot as B  # noqa: E402
from arknova import cards as C  # noqa: E402
from arknova import engine as G  # noqa: E402
from arknova import tables as T  # noqa: E402

PRICES = {"deepseek/deepseek-v4.1-flash": (0.15, 0.60), "deepseek/deepseek-v4-flash": (0.091, 0.182),
          "deepseek/deepseek-v4-pro": (0.209, 0.418)}
CHARS_PER_TOKEN = 3.5  # rough, for the dry-run estimate only

PRIMER = """You are an expert Ark Nova player (base game, 2 players, Map 0). Play to win.

SCORING. Two tracks: appeal and conservation. "points now" = appeal minus the appeal value that
your conservation marker points at (early on each conservation point is worth 2 appeal, from 10
conservation on, 3). The game ends when a player's points reach 0 or more (the markers cross); the
other player gets one final turn, then endgame effects (final scoring cards, some sponsors) add
conservation. Highest points win. The race speeds up late: income, upgrades and played cards
compound, so the last rounds decide the game and tempo matters.

TURN. Pick one of your five action cards (slots 1-5). Strength = slot number (+1 per X-token spent).
The used card then moves to slot 1 and the others shift right, so a card you skip grows stronger.
Instead of acting, you may take an X-token with any card (max 5 X-tokens); the card still moves to
slot 1. Upgraded cards (II) are stronger; you upgrade through partner zoo/university bonuses,
conservation track spaces, reputation 5, and some cards.

ACTIONS.
- Cards: advance the break track 2; draw by strength. Side I: s1 draw 1 discard 1, s2 draw 1, s3 draw 2
  discard 1, s4 draw 2, s5 draw 3 discard 1 or snap 1 display card. Side II draws more and may take from
  the display within reputation range.
- Build: side I builds one building of size <= strength; side II several different ones, total size
  <= strength, and special buildings (reptile house 5, large bird aviary 5). Cost 2 money per space.
  Kiosk (1): +1 money each break per adjacent pavilion, special building or occupied enclosure.
  Pavilion (1): +1 appeal now. Enclosures 1-5; petting zoo 3. Covering map bonus spaces gives their
  bonus; covering the whole map gives +7 appeal. Placement on the map is chosen for you.
- Animals: play animal cards from hand (side II also from the display in reputation range, paying the
  folder number extra). Number of animals: side I s1 0, s2-4 1, s5 2; side II s1-2 1, s3-5 2 (s5 also
  +1 reputation). An animal needs a free standard enclosure of at least its size (with the rock/water
  it needs next to it) or room in its special building. Cost is the card cost minus 3 per partner zoo
  on its continent. Animals give appeal, sometimes conservation/reputation, icons, and abilities.
- Association: send a worker to a task of value <= strength: reputation +2 (2), partner zoo (3),
  university (4), support a conservation project (5). Side II does several different tasks with total
  value <= strength, and may donate money for 1 conservation. Workers return at the break. A task
  already used since the break needs 2 workers.
- Sponsors: play one sponsor of level <= strength (side II: level <= strength+1, more cards) paying
  nothing extra, or instead advance the break track by strength and gain that much money (side II
  double).

BREAK. When the break track is full: discard to the hand limit (3, or 5 with that university), workers
return, display folders 1-2 discarded, income: money by appeal (5 at 0 appeal, 10 at 5, 15 at 15, 20
at 29, ...) plus kiosks, plus income effects of your cards. The player who fills the track gets an X-token.

REPUTATION sets how many display folders you can take from (rep 1: folder 1, 3: 2, 6: 3, 9: 4, 12: 5,
15: 6) and gives bonuses at 5 (upgrade), 8 (worker), 10, 11, 12, 13, 14, 15. Max 9 without Cards II.

CONSERVATION PROJECTS: support one with the association action when you have the icons it needs; the
slot gives conservation (higher slots need more icons). Conservation spaces 2/5/8 give bonuses.

THINK AHEAD. Before choosing, consider your next 2-3 turns (which action cards will be strong, what
money and enclosures you will need, when the break comes) and what the opponent is likely to do next.

Reply ONLY with JSON:
{"choice": <option number>,
 "plan": "<your plan for the next 2-3 turns>",
 "opponent": "<what you expect the opponent to do on their next turn>",
 "reason": "<why this option, one or two sentences>"}"""


def card_line(cid, cost=None):
    c = C.card(cid)
    kind = c["type"]
    parts = [f"[{cid}] {c['name']} ({kind}"]
    if kind == "animal":
        parts.append(f", cost {c['cost']}, size {c['size']}")
        enc = c.get("enclosure", {})
        if enc.get("rock") or enc.get("water"):
            parts.append(f", needs {enc.get('rock', 0)} rock and {enc.get('water', 0)} water next to it")
        homes = []
        if enc.get("standard_size") is not None:
            homes.append(f"enclosure size {enc['standard_size']}+")
        homes += [f"{sp['type']} ({sp['size']} space{'s' if sp['size'] != 1 else ''})" for sp in enc.get("special", [])]
        if homes:
            parts.append(", lives in " + " or ".join(homes))
    elif kind == "sponsor":
        parts.append(f", level {c.get('level')}")
    parts.append(")")
    if cost is not None:
        parts.append(f" display cost {cost}")
    gains = [f"{k} +{c[k]}" for k in ("appeal", "conservation", "reputation") if c.get(k)]
    if gains:
        parts.append(" gives " + ", ".join(gains))
    if c.get("tags"):
        parts.append(" icons " + ",".join(c["tags"]))
    if c.get("requirements"):
        parts.append(" requires " + ",".join(map(str, c["requirements"])))
    text = []
    for a in c.get("abilities", []):
        text.append(f"{a.get('name')}: {a.get('text')}")
    for e in c.get("effects", []):
        text.append(f"{e.get('timing')}: {e.get('text')}")
    if kind in ("project", "endgame") and c.get("text"):
        text.append(c["text"])
    if text:
        parts.append(" | " + " ; ".join(text))
    return re.sub(r"\*\*", "", "".join(parts))


def player_lines(state, p, me):
    pl = state.players[p]
    who = "You" if p == me else "Opponent"
    out = [f"{who} (P{p}): appeal {pl.appeal}, conservation {pl.conservation}, reputation {pl.reputation}, "
           f"money {pl.money}, x-tokens {pl.xtokens}, workers {pl.active_workers}/{pl.workers}, "
           f"points now {pl.victory_points}"]
    slots = ", ".join(f"{i + 1}:{a}{' II' if a in pl.upgraded else ''}" for i, a in enumerate(pl.slots))
    out.append(f"  action slots {slots}")
    blds = [f"{b.kind}{b.capacity}{'(full)' if b.kind == 'enclosure' and b.occupied else ''}"
            for b in pl.zoo.buildings]
    out.append(f"  buildings: {', '.join(blds) or 'none'}")
    if pl.zoo_cards:
        out.append("  zoo cards: " + "; ".join(C.card(c)["name"] for c in pl.zoo_cards))
    icons = C.icons(pl)
    if icons:
        out.append("  icons: " + ", ".join(f"{k} {v}" for k, v in sorted(icons.items()) if v))
    if pl.partner_zoos or pl.universities:
        out.append(f"  partner zoos {pl.partner_zoos}, universities {pl.universities}")
    if p == me:
        out.append("  hand:")
        out += ["    " + card_line(c) for c in pl.hand]
        if pl.final_cards:
            out.append("  final scoring cards:")
            out += ["    " + card_line(c) for c in pl.final_cards]
    else:
        known = [c for c in pl.public_hand if c in pl.hand]
        out.append(f"  hand size {len(pl.hand)}" + (f", known: {'; '.join(C.card(c)['name'] for c in known)}" if known else ""))
    return out


def describe(state, me):
    lines = [f"Break track {state.break_pos}/{T.BREAK_TRACK[state.n]}, deck {len(state.deck)} cards."]
    for p in [me, 1 - me]:
        lines += player_lines(state, p, me)
    lines.append("Display (folder 1..6; folder number costs reputation range):")
    lines += [f"  {i + 1}. " + card_line(c) for i, c in enumerate(state.display) if c is not None]
    lines.append("Conservation projects:")
    lines += ["  " + card_line(c) + f" tokens {state.project_tokens.get(c, {})}"
              for c in state.base_projects + state.projects]
    return "\n".join(lines)


def recent_moves(state, n=12):
    return [m for m in (state.log or []) if m.startswith("P")][-n:]


def collapse_placements(state, options):
    """Placement options differ only by hex cells, which the model cannot see. Keep one per building
    kind and size (the greedy bot's preferred cells) and return (shown, real option for each)."""
    zoo = state.players[state.stack[-1].player].zoo
    best = {}
    shown = []
    for o in options:
        k = o.key
        cells = next((x for x in k if isinstance(x, tuple) and x and all(isinstance(c, tuple) for c in x)), None)
        if cells is not None:
            # Same choice apart from where: building placements ("build", kind, size, cells) and
            # sponsor-building or free-building spots ("place", ..., cells).
            group = tuple(x for x in k if x is not cells)
            kind = k[1] if len(k) > 2 and isinstance(k[1], str) else "unique"
            if group not in best:
                best[group] = (o, cells, kind)
                shown.append(group)
            elif B._placement_score(zoo, cells, kind) > B._placement_score(zoo, best[group][1], kind):
                best[group] = (o, cells, kind)
        else:
            shown.append(o)
    real = [best[x][0] if isinstance(x, tuple) else x for x in shown]
    labels = [re.sub(r" at \(\(.*?\)(,\)|\))", "", o.label) for o in real]
    return real, labels


def build_prompt(state, options, plan, labels=None):
    frame = state.stack[-1]
    me = frame.player
    parts = [describe(state, me), "", "Recent moves:", *recent_moves(state), ""]
    if plan:
        parts.append(f"Your plan from your last decision: {plan}")
    parts.append(f"Decision ({frame.kind}) for you, P{me}. Options:")
    labels = labels or [o.label or str(o.key) for o in options]
    parts += [f"{i}. {lab}" for i, lab in enumerate(labels)]
    return "\n".join(parts)


def call(model, prompt, key, reasoning, providers=None):
    body = {"model": model, "messages": [{"role": "system", "content": PRIMER},
                                         {"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}, "usage": {"include": True}}
    if providers:
        # Cheapest hosts first; fall back to others only below the price cap (the model's list price).
        cap = PRICES.get(model)
        body["provider"] = {"order": providers, "allow_fallbacks": True, "require_parameters": True}
        if cap:
            body["provider"]["max_price"] = {"prompt": cap[0], "completion": cap[1]}
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except Exception as e:  # network or rate limit: back off and retry
            if attempt == 3:
                raise
            print(f"  retry after {e}", file=sys.stderr)
            time.sleep(2 ** attempt * 3)


def parse(text, n):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0))
        choice = int(d["choice"])
        if 0 <= choice < n:
            return choice, d.get("plan", ""), d.get("reason", ""), d.get("opponent", "")
    except Exception:
        pass
    return None, "", "", ""


class NetPlayer:
    """One of our trained networks, playing its most likely option (as in benchmarks)."""

    def __init__(self, checkpoint):
        import torch
        from arknova.rl import match, model as model_v3
        self.torch, self.model_v3 = torch, model_v3
        self.net, self.encoder = match.load(checkpoint, "cpu")
        self.name = Path(checkpoint).stem

    def choose(self, state, options):
        """(index, probability of that option, value estimate for the player to move)."""
        extra = {"lookahead": True} if getattr(self.net, "lookahead", False) else {}
        batch = self.model_v3.to_tensors(self.encoder.collate([self.encoder.observe(state, options, **extra)]), "cpu")
        with self.torch.no_grad():
            logits, _, value = self.net(batch)
        probs = self.torch.softmax(logits, 0)
        index = int(probs.argmax())
        return index, float(probs[index]), float(value.flatten()[0])


def make_seat(spec, args):
    """'llm' (the --model), 'llm:<openrouter model>', 'net:<checkpoint>' or 'greedy'."""
    kind, _, arg = spec.partition(":")
    if kind == "llm":
        return ("llm", arg or args.model)
    if kind == "net":
        return ("net", NetPlayer(arg))
    if kind == "greedy":
        return ("greedy", None)
    raise SystemExit(f"unknown seat {spec}")


def seat_name(seat):
    return seat[1] if seat[0] == "llm" else seat[1].name if seat[0] == "net" else "greedy"


def play(args, seed, out, seats):
    rng = random.Random(seed)
    state = G.new_game(2, seed=seed)
    greedy = B.GreedyBot()
    key = os.environ.get("OPENROUTER_API_KEY")
    plans = {0: "", 1: ""}
    stats = {"decisions": 0, "calls": 0, "prompt_chars": 0, "in_tokens": 0, "out_tokens": 0, "cost": 0.0,
             "invalid": 0, "max_options": 0}
    while not state.over:
        frame = state.stack[-1]
        options = G.legal_options(state, extras=False)
        stats["decisions"] += 1
        if len(options) == 1:
            G.step(state, options[0])
            continue
        seat = seats[frame.player]
        if seat[0] != "llm" and not args.dry_run:
            record = {"seed": seed, "player": frame.player, "seat": seat_name(seat), "kind": frame.kind,
                      "options": len(options)}
            if seat[0] == "net":
                full = G.legal_options(state)  # the networks were trained on the full option list
                index, prob, value = seat[1].choose(state, full)
                option = full[index]
                record.update(prob=round(prob, 3), value=round(value, 3))
            else:
                option = greedy.choose(state, rng)
            record["chose"] = option.label or str(option.key)
            record["state"] = {f"P{i}": [pl.appeal, pl.conservation, pl.reputation, pl.money, pl.victory_points]
                               for i, pl in enumerate(state.players)}
            out.write(json.dumps(record) + "\n")
            G.step(state, option)
            continue
        options, labels = collapse_placements(state, options)
        if len(options) == 1:
            G.step(state, options[0])
            continue
        prompt = build_prompt(state, options, plans[frame.player], labels)
        stats["calls"] += 1
        stats["prompt_chars"] += len(prompt) + len(PRIMER)
        stats["max_options"] = max(stats["max_options"], len(options))
        record = {"seed": seed, "player": frame.player, "seat": seat_name(seat), "kind": frame.kind,
                  "options": len(options)}
        if args.dry_run:
            option = greedy.choose(state, rng)
            choice = options.index(option) if option in options else 0
        else:
            r = call(seat[1], prompt, key, args.reasoning, args.providers)
            message = r["choices"][0]["message"]
            text = message.get("content", "")
            usage = r.get("usage", {})
            stats["in_tokens"] += usage.get("prompt_tokens", 0)
            stats["out_tokens"] += usage.get("completion_tokens", 0)
            stats["cost"] += usage.get("cost", 0.0) or 0.0
            choice, plan, reason, expect = parse(text, len(options))
            if choice is None:
                stats["invalid"] += 1
                g = greedy.choose(state, rng)
                choice = options.index(g) if g in options else 0
                reason = f"(invalid reply, fallback chose) {text[:200]}"
            else:
                plans[frame.player] = plan
            record.update(plan=plan, opponent=expect, reason=reason, thinking=message.get("reasoning") or "",
                          cost=usage.get("cost", 0.0), provider=r.get("provider"))
            if args.verbose:
                print(f"P{frame.player} {frame.kind}: {options[choice].label} -- {reason}")
        record["chose"] = labels[choice]
        record["turn"] = stats["calls"]
        record["state"] = {f"P{i}": [pl.appeal, pl.conservation, pl.reputation, pl.money, pl.victory_points]
                           for i, pl in enumerate(state.players)}
        if args.save_prompts:
            record["prompt"] = prompt
        out.write(json.dumps(record) + "\n")
        out.flush()
        G.step(state, options[choice])
    stats["scores"] = state.scores
    stats["seats"] = [seat_name(x) for x in seats]
    out.write(json.dumps({"seed": seed, "result": state.scores, "seats": stats["seats"], "cost": stats["cost"]}) + "\n")
    return stats


def load_env(path=Path(__file__).resolve().parent.parent / ".env"):
    """KEY=value lines from the git-ignored .env, without overriding the environment."""
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek/deepseek-v4.1-flash")
    ap.add_argument("--games", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="greedy bots choose; only measure prompts")
    ap.add_argument("--reasoning", default=None, help="OpenRouter reasoning effort (low/medium/high); off by default")
    ap.add_argument("--providers", type=lambda s: s.split(",") if s else None,
                    default="decart,sail-research,deepinfra,morph",
                    help="OpenRouter providers to try in order (comma-separated; empty for OpenRouter's choice)")
    ap.add_argument("--p0", default="llm", help="seat 0: llm, llm:<model>, net:<checkpoint> or greedy")
    ap.add_argument("--p1", default="llm", help="seat 1, same choices")
    ap.add_argument("--save-prompts", action=argparse.BooleanOptionalAction, default=True,
                    help="log the prompt each LLM saw (about 6k characters per decision)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default="experiments/llm/games.jsonl")
    args = ap.parse_args()
    if not args.dry_run and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("put OPENROUTER_API_KEY in .env")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    price_in, price_out = PRICES.get(args.model, (0.15, 0.60))
    with open(args.out, "a") as out:
        for g in range(args.games):
            s = play(args, args.seed + g, out, [make_seat(args.p0, args), make_seat(args.p1, args)])
            if args.dry_run:
                tokens = s["prompt_chars"] / CHARS_PER_TOKEN
                s["est_in_tokens"] = round(tokens)
                s["est_cost_no_reasoning"] = round(tokens / 1e6 * price_in + s["calls"] * 80 / 1e6 * price_out, 3)
            print(json.dumps(s))


if __name__ == "__main__":
    main()
