"""~/.edith/state.json: the hash of every file edith wrote, which is how drift is spotted."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edith.paths import Env


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key(path: Path) -> str:
    return os.path.normcase(str(path))


@dataclass
class State:
    path: Path
    files: dict[str, dict[str, str]] = field(default_factory=dict[str, dict[str, str]])
    tools: list[str] = field(default_factory=list[str])

    @classmethod
    def load(cls, env: Env) -> "State":
        path = env.state / "state.json"
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls(path)
        except ValueError as err:
            raise ValueError(f"{path} is corrupt ({err}); move it aside and redeploy") from None
        return cls(path, files=data.get("files", {}), tools=data.get("tools", []))

    def owns(self, dest: Path) -> bool:
        return key(dest) in self.files

    def recorded(self, dest: Path) -> str | None:
        entry = self.files.get(key(dest))
        return entry["sha256"] if entry else None

    def owned_paths(self) -> list[Path]:
        return [Path(entry["path"]) for entry in self.files.values()]

    def record(self, dest: Path, content: bytes) -> None:
        self.files[key(dest)] = {"path": str(dest), "sha256": sha256(content)}

    def forget(self, dest: Path) -> None:
        self.files.pop(key(dest), None)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"version": 1, "files": dict(sorted(self.files.items())), "tools": self.tools}
        write_atomic(self.path, (json.dumps(body, indent=2) + "\n").encode("utf-8"))


def write_atomic(dest: Path, content: bytes) -> None:
    """Write beside the target, then swap, so a crash never leaves half a file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.edith-tmp")
    tmp.write_bytes(content)
    tmp.replace(dest)
