"""Accounts for the board: a login, a signed token, and what each account may see.

Accounts live in experiments/auth/users.json (salted password hashes, never the passwords). The first time
the server runs it makes two accounts and writes their ids and passwords to experiments/auth/credentials.txt
(git-ignored): one that may use the AI's hints and win chances, one that may not. The server's config.json
can change that per account (config.py; by default the guest account does see hints). Each account plays its
own game. Tokens are signed with experiments/auth/secret.key, so logins survive a server restart.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from . import config, paths

AUTH_DIR = paths.DATA / "auth"
ACCOUNTS = [("player", True), ("guest", False)]  # (id, may use the AI's hints); the first also takes over an older game
TOKEN_DAYS = 30
ITERATIONS = 200_000


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()


def _users_file():
    return AUTH_DIR / "users.json"


def ensure():
    """Create the accounts and the signing key the first time; returns True if it just did."""
    if _users_file().exists():
        return False
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    users, lines = {}, ["Ark Nova board logins (this file is git-ignored; passwords are stored only as hashes)\n"]
    for name, hints in ACCOUNTS:
        password = secrets.token_urlsafe(12)
        salt = secrets.token_bytes(16)
        users[name] = {"salt": salt.hex(), "hash": _hash(password, salt), "hints": hints}
        lines.append(f"id: {name}\npassword: {password}\nAI hints: {'yes' if hints else 'no'}\n")
    (AUTH_DIR / "secret.key").write_text(secrets.token_hex(32))
    _users_file().write_text(json.dumps(users, indent=1))
    cred = AUTH_DIR / "credentials.txt"
    cred.write_text("\n".join(lines))
    os.chmod(cred, 0o600)
    os.chmod(AUTH_DIR / "secret.key", 0o600)
    os.chmod(_users_file(), 0o600)
    return True


def _users():
    ensure()
    return json.loads(_users_file().read_text())


def exists(name):
    return name in _users()


def first_account():
    return ACCOUNTS[0][0]


def check(name, password):
    """The account if the id and password are right, else None."""
    user = _users().get(name or "")
    salt = bytes.fromhex(user["salt"]) if user else b"\0" * 16
    ok = hmac.compare_digest(_hash(password or "", salt), user["hash"] if user else "")
    return name if user and ok else None


def can_hint(name):
    """The settings file decides when it says so; otherwise the flag the account was made with."""
    user = _users().get(name or "")
    override = config.account(name).get("hints")
    return bool(user and (user.get("hints") if override is None else override))


def _sign(payload):
    key = (AUTH_DIR / "secret.key").read_bytes()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def token(name):
    payload = base64.urlsafe_b64encode(f"{name}|{int(time.time())}".encode()).decode()
    return f"{payload}.{_sign(payload)}"


def verify(tok):
    """The account a token belongs to, or None (bad signature, expired, account gone)."""
    try:
        payload, sig = (tok or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        name, issued = base64.urlsafe_b64decode(payload.encode()).decode().rsplit("|", 1)
        if time.time() - int(issued) > TOKEN_DAYS * 86400 or name not in _users():
            return None
        return name
    except (ValueError, OSError):
        return None


def bearer(header):
    return header[7:] if header and header.lower().startswith("bearer ") else None
