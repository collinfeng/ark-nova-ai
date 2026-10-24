"""Server settings kept in a file, so they can change without touching the code.

The file is $ARKNOVA_DATA/config.json (experiments/config.json on a laptop); it is read again whenever it
changes, so an edit takes effect without a restart. Anything missing falls back to DEFAULTS. Example:

  {"abandoned_game_days": 7,
   "guest_play": true,
   "accounts": {"guest": {"hints": true, "can_save": false, "max_players": 6, "max_waiting": 10, "idle_minutes": 5,
                          "abandoned_game_days": 1, "finished_game_hours": 1}}}

guest_play            true: the login page has a "Play as a guest" button that signs in as the guest account
                      without a password (false hides it, and the button stops working)
skip_login            an account id: a browser on this machine is signed in as it without a login (never through a proxy)
hints                 may see the AI's preferred moves and win chances (when left out, the value in users.json)
abandoned_game_days   a browser's game that has not moved for this long is deleted (0 keeps them all)
can_save              false: the Save button is hidden and games are never written to the saved-games folder
max_players           how many browsers of the account may play at once; the rest wait in a queue
max_waiting           how many may wait in that queue; the next one is told to come back later (0 = no cap)
idle_minutes          a player who has sent nothing for this long gives the place up
abandoned_game_days   (per account) overrides the global value for that account's browser games
finished_game_hours   (per account) a finished game is deleted this long after its last move (0 keeps it)
"""
import json

from . import paths

DEFAULTS = {
    "abandoned_game_days": 7,
    "guest_play": True,
    "accounts": {"guest": {"hints": True, "can_save": False, "max_players": 6, "max_waiting": 10, "idle_minutes": 5,
                         "abandoned_game_days": 1, "finished_game_hours": 1}},
}
ACCOUNT_DEFAULTS = {"can_save": True, "max_players": 0, "max_waiting": 0, "idle_minutes": 10,  # 0 = no limit
                    "abandoned_game_days": None, "finished_game_hours": 0}  # None: the global value; 0: never

_cache = {"mtime": None, "data": DEFAULTS}


def _file():
    return paths.DATA / "config.json"


def load():
    try:
        mtime = _file().stat().st_mtime
    except OSError:
        mtime = None
    if (_file(), mtime) != _cache["mtime"]:
        data = DEFAULTS
        if mtime is not None:
            try:
                data = _merge(json.loads(_file().read_text()))
            except ValueError:
                data = DEFAULTS  # a broken edit must not take the board down
        _cache.update(mtime=(_file(), mtime), data=data)
    return _cache["data"]


def _merge(user):
    """DEFAULTS overlaid with the file; accounts are merged one by one and setting by setting, so a file that
    changes one setting of an account keeps that account's other defaults (its limits, can_save)."""
    accounts = {name: dict(settings) for name, settings in DEFAULTS["accounts"].items()}
    for name, settings in (user.get("accounts") or {}).items():
        accounts[name] = {**accounts.get(name, {}), **settings}
    return {**DEFAULTS, **user, "accounts": accounts}


def account(name):
    """The settings of one account, with defaults filled in."""
    return {**ACCOUNT_DEFAULTS, **load().get("accounts", {}).get(name, {})}


def can_save(name):
    return bool(account(name)["can_save"])
