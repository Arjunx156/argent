"""Plan what a deploy would change, then apply it behind a snapshot.

A target says what a file should contain, given what it contains now. Whole targets are
files argent owns outright; partial ones (merged JSON, a managed block) share the file
with the user, so only whole targets can drift.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from argent.paths import Env
from argent.snapshot import Snapshot
from argent.state import State, key, sha256, write_atomic

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
                reason = "in a kit folder but not in the kit; --force removes it"
                actions.append(Action("stray", stray, stray.name, read(stray), None, True, reason))
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
        return act("adopt", desired, "not written by argent; the original goes in the snapshot")
    if recorded == sha256(current):
        return act("update", desired)
    return act("drift", desired, "edited since argent wrote it; --force overwrites")


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
    forced = [a for a in actions if force and _forceable(a)]
    todo = [a for a in actions if a.writes] + forced
    forgotten = [a for a in actions if a.kind == "forget"]
    # files that already match the kit are owned from now on, so later hand edits count as drift
    unowned = [a for a in actions if a.kind == "ok" and a.whole and not state.owns(a.dest)]
    if dry_run or not (todo or forgotten or unowned):
        return None

    snapshot = None
    if todo:
        snapshot = Snapshot.create(env, reason, clock)
        for action in todo:
            snapshot.keep(action.dest)
        snapshot.save()

    try:
        for action in todo:
            if action.desired is None:
                action.dest.unlink(missing_ok=True)
                state.forget(action.dest)
                _prune_empty(action.dest.parent, stop=env.home)
                continue
            write_atomic(action.dest, action.desired)
            if action.whole:
                state.record(action.dest, action.desired)
        for action in forgotten:
            state.forget(action.dest)
        for action in unowned:
            state.record(action.dest, action.current or b"")
    finally:
        # a failed write mid-run must not orphan the hashes of the writes before it
        state.save()
    return snapshot.path if snapshot else None


def _prune_empty(folder: Path, stop: Path) -> None:
    """Folders emptied by a removal go too, so a dropped skill leaves no husk behind."""
    while folder != stop and folder.is_relative_to(stop) and folder.is_dir():
        if any(folder.iterdir()):
            return
        folder.rmdir()
        folder = folder.parent


def _forceable(action: Action) -> bool:
    if action.kind == "stray":
        return True
    return action.kind == "drift" and action.desired is not None
