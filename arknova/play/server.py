"""Web server for playing against the AI.

Run:  python -m arknova.play.server [--checkpoint experiments/ppo/keep/long_s0_1B.pt] [--port 8765]
      python -m arknova.play.server --remote http://127.0.0.1:9876   # AI on another server (SSH tunnel)
Then the board: cd web && pnpm dev   (Vite forwards /api here).

Each account (see auth.py) plays its own game, kept in experiments/human_games/current_<id>.json.
Every endpoint but the login wants the header  Authorization: Bearer <token>  (from /api/login).
Endpoints, all JSON:
  POST /api/login  {user, password} -> {token, user, hints}
  GET  /api/me                      who the token belongs to, and whether that account may use AI hints
  GET  /api/state                   the board (header X-Lang: zh-CN for Simplified Chinese text, English otherwise)
  POST /api/new    {seed?, human?, checkpoint?, map?}   map: "map0" (default), "plan1" ... "plan8", "plana"
  POST /api/move   {index}          take option `index` of the pending decision
  POST /api/end_turn                your turn is over (phase "end_turn"): let the AI play
  POST /api/undo                    back to your previous decision (board.undo_leaves_turn says when that
                                    goes back into your previous turn, undoing the AI's turn as well)
  POST /api/redo                    put back what the last undo took (board.can_redo)
  POST /api/restart_turn            back to the first decision of this turn (board.can_restart_turn)
  POST /api/quit                    delete this browser's game and give up its place
  POST /api/save                    write the game to experiments/human_games/
  GET  /api/checkpoints             opponents available here, the maps, and which opponents play every map
  POST /api/ai/analyse {seed, map, moves}   for a RemoteAI elsewhere: replay and analyse
"""
import argparse
import json
import re
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from arknova import engine as G

from . import auth, config, paths, view
from .admission import FULL, Admission
from . import game as gamemod
from .ai import BUILTIN_OPPONENTS, HeuristicAI, LocalNet, RemoteAI
from .game import CURRENT, Game, replay

ROOT = paths.ROOT
KEEP = ROOT / "experiments" / "ppo" / "keep"

app = FastAPI(title="Ark Nova", docs_url=None, redoc_url=None, openapi_url=None)  # no API pages in public
ctx = {"ai": None, "games": {}, "nets": {}, "remote": None}
_loading = threading.Lock()  # the board fetches the state twice on load: create the game once


class NewGame(BaseModel):
    seed: int | None = None
    human: int = 0
    checkpoint: str | None = None
    map: str = "map0"


# Maps the board offers: Map 0 first, then maps 1-8 and A.
MAPS = ["map0", *sorted(m for m in G.MAP_DEFS if m != "map0")]
# The networks the board offers, easiest first (Easy, Normal, Hard). Other files in KEEP still load for
# games saved against them, but are not offered for new ones.
OFFERED_NETWORKS = ["run5_13M.pt", "maps10_s0_1B_ema.pt", "long_s0_1B.pt"]
# Networks trained on every map. The others learned Map 0 only (and v2 networks cannot even see the map),
# so on another map the opponent is a rule policy or one of these.
ANY_MAP_NETWORKS = ["maps10_s0_1B_ema.pt"]


def _any_map(checkpoint):
    return checkpoint in BUILTIN_OPPONENTS or checkpoint in ANY_MAP_NETWORKS


def _map_network():
    """The first network here that plays every map, or None."""
    return next((n for n in ANY_MAP_NETWORKS if (KEEP / n).is_file()), None)


class Move(BaseModel):
    index: int


class Replay(BaseModel):
    seed: int
    map: str = "map0"
    moves: list


class HintModel(BaseModel):
    name: str  # "default" (the opponent's own network), a rule policy, or a network file name


MAX_REPLAY_MOVES = 2500  # a game is cut off after this many decisions (arknova.rl.env.MAX_DECISIONS)


def _network_file(name):
    """KEEP / name for a plain checkpoint file name; HTTPException for anything else (no paths, no ..)."""
    if not name or Path(name).name != name or name.startswith(".") or not name.endswith(".pt"):
        raise HTTPException(400, "no such network")
    return KEEP / name


def _hint_ai(name):
    """The adviser for a hint model name, or None for the default; HTTPException for an unknown name."""
    if name in (None, "", "default"):
        return None
    if name in BUILTIN_OPPONENTS:
        return HeuristicAI(name)  # its own copy: a beam keeps a plan per game
    if not _network_file(name).is_file():
        raise HTTPException(404, f"no hint model {name}")
    return _ai(name)


def _ai(checkpoint=None, map_name="map0"):
    """The opponent for a game on `map_name`. Off Map 0, the default and a rule policy's adviser (the network
    that judges the human's moves) is a network trained on every map, when there is one."""
    if ctx["remote"]:
        return ctx["remote"]
    if not checkpoint and map_name != "map0":
        checkpoint = _map_network()
    no_network = ctx["default"] in BUILTIN_OPPONENTS  # --checkpoint greedy: a clone without trained networks
    if checkpoint in BUILTIN_OPPONENTS:
        # Search plans belong to a game, unlike the shared read-only network weights.
        return HeuristicAI(checkpoint, None if no_network else _ai(None, map_name))
    if not checkpoint and no_network:
        return HeuristicAI(ctx["default"])
    path = str(_network_file(checkpoint)) if checkpoint else ctx["default"]
    if path not in ctx["nets"]:
        if not Path(path).exists():
            raise HTTPException(404, f"no checkpoint {Path(path).name}")  # the name only: no server paths
        ctx["nets"][path] = LocalNet(path)
    return ctx["nets"][path]


class Login(BaseModel):
    user: str
    password: str


class Player(str):
    """An account id that also knows which game of the account the request is about (`slot`).

    Everyone signed in as one account shares its hint setting, but each browser plays its own
    game: the page sends a random X-Slot id, so two people on one account do not share a game."""
    slot = "main"

    @property
    def key(self):
        return str(self) if self.slot == "main" else f"{self}.{self.slot}"


_SLOT = re.compile(r"[A-Za-z0-9]{6,32}")
MAX_LIVE_GAMES = 30  # games in memory; the rest are on disk (see Game.checkpoint) and reload on use


def _slot(value):
    return value if value and _SLOT.fullmatch(value) else "main"


LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _skip_login(request):
    """The account to use without a login, when config.json has "skip_login": that account's id.

    Only for a browser on this machine talking to the server directly: a request that came through a
    proxy (it carries X-Forwarded-* headers) or from another address still needs its token."""
    name = config.load().get("skip_login")
    if not name or request is None or request.client is None or request.client.host not in LOOPBACK:
        return None
    if any(h in request.headers for h in ("x-forwarded-for", "x-forwarded-host", "forwarded")):
        return None
    return name if auth.exists(name) else None


def _account(authorization, request=None):
    """The account of the request's token, else the skip-login account (local only), else None."""
    return auth.verify(auth.bearer(authorization)) or _skip_login(request)


def current_user(authorization: str | None = Header(None), x_slot: str | None = Header(None), request: Request = None):
    """The account of the request's token (with its game slot); 401 without a valid token."""
    user = _account(authorization, request)
    if user is None:
        raise HTTPException(401, "login required")
    who = Player(user)
    who.slot = _slot(x_slot)
    return who


admission = Admission()


def player(user: Player = Depends(current_user)):
    """The account, once it has a place to play; 503 with its place in the line while the account is full."""
    cfg = config.account(user)
    place = admission.check(str(user), user.key, cfg["max_players"], cfg["idle_minutes"], max_waiting=cfg["max_waiting"])
    if place == FULL:
        raise HTTPException(503, {"full": True, "limit": cfg["max_players"]})
    if place is not None:
        raise HTTPException(503, {"queued": place, "limit": cfg["max_players"]})
    return user


def _who(user):
    """A plain account id means its main game."""
    return user if isinstance(user, Player) else Player(user)


def _path(user):
    user = _who(user)
    return gamemod.SAVE_DIR / f"current_{user.key}.json"


def _keep(user, game):
    """Hold the game in memory, dropping the longest-idle ones beyond MAX_LIVE_GAMES."""
    user = _who(user)
    ctx["games"].pop(user.key, None)
    ctx["games"][user.key] = game
    while len(ctx["games"]) > MAX_LIVE_GAMES:
        ctx["games"].pop(next(iter(ctx["games"])))


def _game(user):
    user = _who(user)
    with _loading:
        if user.key not in ctx["games"]:
            path = _path(user)
            # The game that was in progress before there were accounts goes to the first one.
            source = path if path.exists() else CURRENT if user.slot == "main" and user == auth.first_account() and CURRENT.exists() else None
            saved = json.loads(source.read_text()) if source else None
            if saved and not saved.get("over"):
                selected = saved.get("opponent")
                if not selected:
                    old_name = saved.get("ai", "")
                    selected = old_name if old_name in BUILTIN_OPPONENTS else (
                        f"{old_name}.pt" if (KEEP / f"{old_name}.pt").is_file() else None)
                game = Game.resume(_ai(selected, saved.get("map", "map0")), saved)
            else:
                game = Game(_ai())
            if saved and saved.get("hint") and not saved.get("over"):
                try:
                    game.set_hint(_hint_ai(saved["hint"]), saved["hint"])
                except HTTPException:
                    pass  # the network is gone: the opponent's own advises again
            game.path = path
            _keep(user, game)
            game.checkpoint()
        else:
            ctx["games"][user.key] = ctx["games"].pop(user.key)  # most recently used goes last
    return ctx["games"][user.key]


def _autosave(user, game):
    """A finished game goes to the saved-games folder, unless the account may not save."""
    if config.can_save(user):
        game.save()


def clean_abandoned(now=None):
    """Delete the games of browsers (not the accounts' main games) that have not moved for long enough:
    abandoned_game_days, or finished_game_hours once the game is over (see config.py; per account)."""
    now = time.time() if now is None else now
    gone = []
    for path in gamemod.SAVE_DIR.glob("current_*.*.json"):  # current_<account>.<slot>.json
        key = path.name[len("current_"):-len(".json")]
        cfg = config.account(key.split(".")[0])
        days = cfg["abandoned_game_days"]
        days = config.load().get("abandoned_game_days", 0) if days is None else days
        idle = now - path.stat().st_mtime
        limit = days * 86400 if days else None
        if cfg["finished_game_hours"]:
            try:
                if json.loads(path.read_text()).get("over"):
                    limit = cfg["finished_game_hours"] * 3600
            except (OSError, ValueError):
                pass
        if limit is not None and idle > limit:
            path.unlink(missing_ok=True)
            ctx["games"].pop(key, None)
            gone.append(path.name)
    return gone


def _board(user, x_lang):
    out = view.board(_game(user), x_lang, hints=auth.can_hint(user))
    out["user"] = user
    out["can_save"] = config.can_save(user)
    return out


@app.middleware("http")
async def keep_current(request, call_next):
    """After every change to the game, keep it on disk (see Game.checkpoint); once an hour, drop abandoned games."""
    if time.time() - ctx.get("cleaned", 0) > 3600:
        ctx["cleaned"] = time.time()
        clean_abandoned()
    response = await call_next(request)
    if request.method == "POST" and request.url.path in ("/api/new", "/api/move", "/api/end_turn", "/api/undo",
                                                                "/api/redo", "/api/restart_turn", "/api/hint_model"):
        user = _account(request.headers.get("authorization"), request)
        if user:
            who = Player(user)
            who.slot = _slot(request.headers.get("x-slot"))
            if who.key in ctx["games"]:
                ctx["games"][who.key].checkpoint()
    return response


@app.post("/api/login")
def login(req: Login):
    user = auth.check(req.user.strip(), req.password)
    if user is None:
        time.sleep(0.5)  # slows down guessing
        raise HTTPException(401, "wrong id or password")
    return {"token": auth.token(user), "user": user, "hints": auth.can_hint(user)}


GUEST = "guest"


def _guest_open():
    return bool(config.load().get("guest_play", True)) and auth.exists(GUEST)


@app.get("/api/guest")
def guest_open():
    """Whether the login page offers "Play as a guest"."""
    return {"open": _guest_open()}


@app.post("/api/guest")
def guest_login():
    """Signs in as the guest account without a password; each browser still gets its own game (its slot)."""
    if not _guest_open():
        raise HTTPException(403, "guest play is closed")
    return {"token": auth.token(GUEST), "user": GUEST, "hints": auth.can_hint(GUEST)}


@app.get("/api/me")
def me(user: str = Depends(current_user)):
    return {"user": user, "hints": auth.can_hint(user)}


@app.get("/api/state")
def state(x_lang: str | None = Header(None), user: str = Depends(player)):
    return _board(user, x_lang)


@app.post("/api/quit")
def quit_game(user: Player = Depends(current_user)):
    """Leave: the game of this browser is deleted and its place goes to the next in line."""
    with _loading:
        ctx["games"].pop(user.key, None)
        _path(user).unlink(missing_ok=True)
    admission.leave(str(user), user.key)
    return {"ok": True}


@app.post("/api/hint_model")
def hint_model(req: HintModel, x_lang: str | None = Header(None), user: str = Depends(player)):
    if not auth.can_hint(user):
        raise HTTPException(403, "this account has no AI hints")
    name = None if req.name == "default" else req.name
    game = _game(user)
    if name and game.map_name != "map0" and not _any_map(name):
        raise HTTPException(400, "this hint model only knows Map 0")
    game.set_hint(_hint_ai(name), name)
    return _board(user, x_lang)


@app.post("/api/new")
def new(req: NewGame, x_lang: str | None = Header(None), user: str = Depends(player)):
    if req.map not in MAPS:
        raise HTTPException(400, f"no map {req.map}")
    if req.map != "map0" and req.checkpoint and not _any_map(req.checkpoint):
        raise HTTPException(400, "this opponent only plays Map 0")
    game = Game(_ai(req.checkpoint, req.map), seed=req.seed, human=req.human, map_name=req.map)
    game.path = _path(user)
    _keep(user, game)
    return _board(user, x_lang)


@app.post("/api/move")
def move(req: Move, x_lang: str | None = Header(None), user: str = Depends(player)):
    game = _game(user)
    if game.state.over or game.turn_done or game.to_move() != game.human:
        raise HTTPException(409, "not your decision")
    if not 0 <= req.index < len(game.options()):
        raise HTTPException(400, "no such option")
    game.play(req.index)
    if game.state.over:
        _autosave(user, game)
    return _board(user, x_lang)


@app.post("/api/end_turn")
def end_turn(x_lang: str | None = Header(None), user: str = Depends(player)):
    game = _game(user)
    if not game.turn_done:
        raise HTTPException(409, "your turn is not over")
    game.end_turn()
    if game.state.over:
        _autosave(user, game)
    return _board(user, x_lang)


@app.post("/api/undo")
def undo(x_lang: str | None = Header(None), user: str = Depends(player)):
    game = _game(user)
    if not game.undo():
        raise HTTPException(409, "nothing to undo")
    return _board(user, x_lang)


@app.post("/api/redo")
def redo(x_lang: str | None = Header(None), user: str = Depends(player)):
    game = _game(user)
    if not game.redo():
        raise HTTPException(409, "nothing to redo")
    return _board(user, x_lang)


@app.post("/api/restart_turn")
def restart_turn(x_lang: str | None = Header(None), user: str = Depends(player)):
    game = _game(user)
    if not game.restart_turn():
        raise HTTPException(409, "no decision to take back in this turn")
    return _board(user, x_lang)


@app.post("/api/save")
def save(user: str = Depends(player)):
    if not config.can_save(user):
        raise HTTPException(403, "saving is not allowed for this account")
    path = _game(user).save()
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name}


@app.get("/api/checkpoints")
def checkpoints(user: str = Depends(current_user)):
    names = list(BUILTIN_OPPONENTS) + [n for n in OFFERED_NETWORKS if (KEEP / n).is_file()]
    return {"checkpoints": names, "default": Path(ctx["default"]).name,
            "maps": MAPS, "any_map": [n for n in names if _any_map(n)], "map_default": _map_network(),
            "remote": "another server" if ctx["remote"] else None}  # never its address


@app.post("/api/ai/analyse")
def ai_analyse(req: Replay, user: str = Depends(current_user)):
    if not auth.can_hint(user):
        raise HTTPException(403, "this account may not use the AI's analysis")
    if req.map not in MAPS or len(req.moves) > MAX_REPLAY_MOVES:
        raise HTTPException(400, "no such game")
    try:
        state = replay(req.seed, req.map, req.moves)
    except (StopIteration, TypeError, ValueError, G.EngineError):
        raise HTTPException(400, "these moves do not make a game")
    adviser = _ai()
    if isinstance(adviser, HeuristicAI):
        adviser = adviser.adviser
    if adviser is None:
        raise HTTPException(409, "no network here to analyse with")
    a = adviser.analyse_state(state, G.legal_options(state))
    return a.to_json()


# The built page (web/dist), when there is one, is served from the same port: one process does everything.
# Mounted last, so every /api route above wins.
DIST = ROOT / "web" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=str(KEEP / "long_s0_1B.pt"),
                    help="the default opponent: a trained network (.pt), or a built-in bot: " + ", ".join(BUILTIN_OPPONENTS))
    ap.add_argument("--remote", default=None, help="URL of another game server to use as the AI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if auth.ensure():
        print(f"Made the logins: see {auth.AUTH_DIR / 'credentials.txt'}")
    ctx["default"] = args.checkpoint
    if args.remote:
        ctx["remote"] = RemoteAI(args.remote)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
