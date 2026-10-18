"""Plan what a deploy would change, then apply it behind a snapshot.

A target says what a file should contain, given what it contains now. Whole targets are
files edith owns outright; partial ones (merged JSON, a managed block) share the file
with the user, so only whole targets can drift.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from edith.paths import Env
from edith.snapshot import Snapshot
from edith.state import State, key, sha256, write_atomic

Build = Callable[[bytes | None], bytes | None]
WRITES = {"new", "update", "adopt", "remove"}
IGNORED_DIRS = {"__pycache__"}


class SkipTargetError(Exception):
    """Raised by a build when it can't safely produce content; the reason is shown."""


@dataclass(frozen=True)
class Target:
    dest: Path
    label: str
    build: Build
    whole: bool = True


@dataclass(frozen=True)
class Action:
    kind: str
    dest: Path
    label: str
    current: bytes | None
    desired: bytes | None
    whole: bool
    reason: str = ""

    @property
    def writes(self) -> bool:
        return self.kind in WRITES


def read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def plan(targets: Iterable[Target], state: State, mirror: Iterable[Path] = ()) -> list[Action]:
    actions: list[Action] = []
    wanted: set[str] = set()
    for target in targets:
        wanted.add(key(target.dest))
        actions.append(_plan_one(target, state))

    for dest in state.owned_paths():
        if key(dest) not in wanted:
            actions.append(_plan_stale(dest, state))

    for folder in mirror:
        for stray in _files_under(folder):
            if key(stray) not in wanted and not state.owns(stray):
                content = read(stray)
                actions.append(Action("remove", stray, stray.name, content, None, True))
    return actions


def _plan_one(target: Target, state: State) -> Action:
    current = read(target.dest)

    def act(kind: str, desired: bytes | None, reason: str = "") -> Action:
        return Action(kind, target.dest, target.label, current, desired, target.whole, reason)

    try:
        desired = target.build(current)
    except SkipTargetError as err:
        return act("skip", None, str(err))

    if desired == current:
        return act("ok", desired)
    if desired is None:
        return act("remove", None)
    if current is None:
        return act("new", desired)
    if not target.whole:
        return act("update", desired)
    recorded = state.recorded(target.dest)
    if recorded is None:
        return act("adopt", desired, "not written by edith; the original goes in the snapshot")
    if recorded == sha256(current):
        return act("update", desired)
    return act("drift", desired, "edited since edith wrote it; --force overwrites")


def _plan_stale(dest: Path, state: State) -> Action:
    current = read(dest)
    if current is None:
        return Action("forget", dest, dest.name, None, None, True)
    if state.recorded(dest) == sha256(current):
        return Action("remove", dest, dest.name, current, None, True, "no longer in the kit")
    reason = "no longer in the kit, but edited since; left alone"
    return Action("drift", dest, dest.name, current, None, True, reason)


def _files_under(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [
        p
        for p in folder.rglob("*")
        if p.is_file() and not IGNORED_DIRS & set(p.relative_to(folder).parts)
    ]


def apply(
    actions: list[Action],
    env: Env,
    state: State,
    *,
    clock: Callable[[], datetime],
    force: bool = False,
    dry_run: bool = False,
    reason: str = "deploy",
) -> Path | None:
    """Carry out a plan. Returns the snapshot folder, or None when nothing was written."""
    forced = [a for a in actions if force and a.kind == "drift" and a.desired is not None]
    todo = [a for a in actions if a.writes] + forced
    forgotten = [a for a in actions if a.kind == "forget"]
    if dry_run or not (todo or forgotten):
        return None

    snapshot = None
    if todo:
        snapshot = Snapshot.create(env, reason, clock)
        for action in todo:
            snapshot.keep(action.dest)
        snapshot.save()

    for action in todo:
        if action.desired is None:
            action.dest.unlink(missing_ok=True)
            state.forget(action.dest)
            continue
        write_atomic(action.dest, action.desired)
        if action.whole:
            state.record(action.dest, action.desired)
    for action in forgotten:
        state.forget(action.dest)
    state.save()
    return snapshot.path if snapshot else None
