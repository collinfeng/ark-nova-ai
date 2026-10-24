"""Where the board keeps what it writes. ARKNOVA_DATA moves it out of the code folder (the server on a
host keeps saves and logins in /var/lib/arknova, so a redeploy never touches them)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = Path(os.environ["ARKNOVA_DATA"]) if os.environ.get("ARKNOVA_DATA") else ROOT / "experiments"
