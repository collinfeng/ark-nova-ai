"""A limit on how many browsers of an account play at once; the others wait their turn.

A browser holds a place while it keeps sending requests, and gives it up after `idle_minutes` of silence.
A waiting browser keeps its place in line only while its page keeps asking (the page asks every few seconds).
The line itself may be capped: a browser that would stand behind `max_waiting` others is told the line is full."""
import threading
import time

WAIT_TTL = 30  # seconds without asking and a waiting browser drops out of the line
FULL = 0  # check's answer when the line is full too


class Admission:
    def __init__(self):
        self.lock = threading.Lock()
        self.playing = {}  # account -> {game key: last seen}
        self.waiting = {}  # account -> {game key: last asked}, in arrival order

    def check(self, account, key, limit, idle_minutes, now=None, max_waiting=0):
        """None if this browser may play; otherwise its place in the line (1 = next), or FULL (max_waiting 0 = no cap)."""
        if limit <= 0:
            return None
        now = time.time() if now is None else now
        with self.lock:
            playing = self.playing.setdefault(account, {})
            waiting = self.waiting.setdefault(account, {})
            for k in [k for k, t in playing.items() if now - t > idle_minutes * 60]:
                del playing[k]
            for k in [k for k, t in waiting.items() if now - t > WAIT_TTL]:
                del waiting[k]
            if key in playing:
                playing[key] = now
                return None
            waiting[key] = now  # keeps its old place in the dict order
            line = list(waiting)
            if line.index(key) < limit - len(playing):
                del waiting[key]
                playing[key] = now
                return None
            place = line.index(key) + 1
            if max_waiting > 0 and place > max_waiting:
                del waiting[key]
                return FULL
            return place

    def leave(self, account, key):
        with self.lock:
            self.playing.get(account, {}).pop(key, None)
            self.waiting.get(account, {}).pop(key, None)
