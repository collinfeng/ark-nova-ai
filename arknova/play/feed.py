"""What a move changed and why, for the board's activity feed.

The engine records every gain with its cause while a real move is played (state.ledger, see state.py).
Payments and other direct changes are not gains, so they come from comparing the players' numbers
before and after, and are blamed on the move itself. The result is plain JSON, kept with the move
(records, ai_moves) so a saved game shows its feed again.
"""
from arknova import tables as T

STATS = ("money", "appeal", "conservation", "reputation", "xtokens")
LEDGER_KIND = {"xtoken": "xtokens"}  # gain() kind -> Player field


def stats(state):
    return {"players": [{k: getattr(p, k) for k in STATS} for p in state.players], "break": state.break_pos}


def entries(state, before, ledger, move):
    """The feed of one move: gains and spending per player, notes, the break track. `move` is
    (decision kind, option label), the cause of anything the ledger does not explain."""
    after = stats(state)
    out = []
    explained = {}
    for item in ledger:
        if item[0] == "gain":
            _, p, kind, amount, cause = item
            field = LEDGER_KIND.get(kind, kind)
            if field in STATS:
                explained[(p, field)] = explained.get((p, field), 0) + amount
            out.append({"p": p, "k": kind, "n": amount, "c": _cause(cause, move)})
        else:
            _, p, what, detail, cause = item
            out.append({"p": p, "note": what, "d": detail, "c": _cause(cause, move)})
    for p, (b, a) in enumerate(zip(before["players"], after["players"])):
        for field in STATS:
            rest = a[field] - b[field] - explained.get((p, field), 0)
            if rest == 0 or (rest < 0 and field not in ("money", "xtokens")):
                continue
            if rest < 0 and field == "xtokens" and explained.get((p, field)):  # a capped X-token gain
                continue
            kind = "xtoken" if field == "xtokens" else field
            out.append({"p": p, "k": kind, "n": rest, "c": ["move", *move]})
    if after["break"] > before["break"]:
        out.append({"p": None, "note": "break_track", "d": [after["break"], T.BREAK_TRACK[state.n]], "c": ["move", *move]})
    return out


def _cause(cause, move):
    return list(cause) if cause else ["move", *move]
