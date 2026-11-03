"""Named desk users (DPM-12). No passwords are stored in the repository.

Roles are fixed by the runbook:
  emmanuel -> requester   (creates dose requests)
  thabani  -> approver    (approves another person's request)
  tranos   -> operator    (lab operator; may execute approved changes)

Each person sets their own password once on the demo laptop:
  .\\.venv\\Scripts\\python.exe -m plant.desk_users set emmanuel
Only a salted hash is saved, in .env.desk-users.json (ignored by Git via .env.*).
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_USERS_FILE = ROOT / ".env.desk-users.json"
MIN_PASSWORD_LENGTH = 10


@dataclass(frozen=True)
class DeskUser:
    user_id: str
    display_name: str
    role: str  # requester / approver / operator


USERS = {
    "emmanuel": DeskUser("emmanuel", "Emmanuel", "requester"),
    "thabani": DeskUser("thabani", "Thabani", "approver"),
    "tranos": DeskUser("tranos", "Tranos", "operator"),
}


def users_file() -> Path:
    return Path(os.environ.get("MVP_DESK_USERS_FILE", DEFAULT_USERS_FILE))


def _load_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def set_password(user_id: str, password: str, path: Path | None = None) -> None:
    if user_id not in USERS:
        raise ValueError(f"unknown desk user: {user_id}")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    path = path or users_file()
    hashes = _load_hashes(path)
    hashes[user_id] = generate_password_hash(password)
    path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def authenticate(user_id: str, password: str, path: Path | None = None) -> DeskUser | None:
    """Return the user if the password matches its stored hash, else None."""
    user = USERS.get((user_id or "").strip().lower())
    if user is None:
        return None
    stored = _load_hashes(path or users_file()).get(user.user_id)
    if not stored or not check_password_hash(stored, password or ""):
        return None
    return user


def _cli(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "set" or argv[1] not in USERS:
        print("Usage: python -m plant.desk_users set <emmanuel|thabani|tranos>")
        return 2
    first = getpass.getpass(f"New password for {argv[1]}: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        print("Passwords did not match; nothing saved.")
        return 1
    try:
        set_password(argv[1], first)
    except ValueError as exc:
        print(exc)
        return 1
    print(f"Saved a password hash for {argv[1]} in {users_file().name} (not tracked by Git).")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
