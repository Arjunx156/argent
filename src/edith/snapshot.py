"""Snapshots: a copy of everything a run is about to touch, and a journal to undo it."""

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from edith.paths import Env
from edith.state import State, write_atomic

Clock = Callable[[], datetime]
JOURNAL = "journal.json"


@dataclass(frozen=True)
class SnapshotInfo:
    name: str
    path: Path
    reason: str
    count: int


class Snapshot:
    def __init__(self, path: Path, reason: str, created: datetime) -> None:
        self.path = path
        self.reason = reason
        self.created = created
        self.entries: list[dict[str, object]] = []
        self._seen: set[str] = set()

    @classmethod
    def create(cls, env: Env, reason: str, clock: Clock) -> "Snapshot":
        now = clock()
        base = now.strftime("%Y%m%d-%H%M%S")
        path, n = env.snapshots / base, 2
        while path.exists():
            path, n = env.snapshots / f"{base}-{n}", n + 1
        (path / "files").mkdir(parents=True)
        return cls(path, reason, now)

    def keep(self, dest: Path) -> None:
        if str(dest) in self._seen:
            return
        self._seen.add(str(dest))
        stored = None
        if dest.is_file():
            stored = f"files/{len(self.entries) + 1:04d}"
            shutil.copy2(dest, self.path / stored)
        self.entries.append({"dest": str(dest), "existed": stored is not None, "stored": stored})

    def save(self) -> None:
        body = {"reason": self.reason, "created": self.created.isoformat(), "files": self.entries}
        write_atomic(self.path / JOURNAL, (json.dumps(body, indent=2) + "\n").encode("utf-8"))


def list_snapshots(env: Env) -> list[SnapshotInfo]:
    if not env.snapshots.is_dir():
        return []
    found: list[SnapshotInfo] = []
    for path in sorted(env.snapshots.iterdir()):
        journal = path / JOURNAL
        if not journal.is_file():
            continue
        data = json.loads(journal.read_text(encoding="utf-8"))
        found.append(SnapshotInfo(path.name, path, data.get("reason", ""), len(data["files"])))
    return found


def restore(env: Env, name: str, clock: Clock) -> list[Path]:
    """Put every journaled file back as it was, and delete the ones that didn't exist."""
    journal = env.snapshots / name / JOURNAL
    if not journal.is_file():
        raise FileNotFoundError(f"no snapshot named {name!r}; `edith restore` lists them")
    entries = json.loads(journal.read_text(encoding="utf-8"))["files"]

    undo = Snapshot.create(env, f"restore {name}", clock)
    state = State.load(env)
    touched: list[Path] = []
    for entry in entries:
        dest = Path(entry["dest"])
        undo.keep(dest)
        if entry["existed"]:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(env.snapshots / name / entry["stored"], dest)
        elif dest.exists():
            dest.unlink()
        state.forget(dest)
        touched.append(dest)
    undo.save()
    state.save()
    return touched
