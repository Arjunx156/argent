from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from argent.deploy import Action, SkipTargetError, Target, apply, plan
from argent.paths import Env
from argent.snapshot import UnknownSnapshotError, list_snapshots, restore
from argent.state import State

Clock = Callable[[], datetime]


@pytest.fixture
def clock() -> Clock:
    """Each call is one second later, so snapshot names never collide by accident."""
    ticks = iter(datetime(2026, 10, 18, 8, 0, 0) + timedelta(seconds=i) for i in range(1000))
    return lambda: next(ticks)


def fixed(content: bytes) -> Callable[[bytes | None], bytes | None]:
    return lambda _current: content


def target(dest: Path, content: bytes, *, whole: bool = True) -> Target:
    return Target(dest=dest, label=dest.name, build=fixed(content), whole=whole)


def kinds(actions: list[Action]) -> dict[str, str]:
    return {a.dest.name: a.kind for a in actions}


def deploy(env: Env, targets: list[Target], clock: Clock, **kw: object) -> list[Action]:
    state = State.load(env)
    actions = plan(targets, state)
    apply(actions, env, state, clock=clock, **kw)  # pyright: ignore[reportArgumentType]
    return actions


def test_new_file_is_written_and_owned(env: Env, clock: Clock) -> None:
    dest = env.home / ".claude" / "CLAUDE.md"
    actions = deploy(env, [target(dest, b"orders\n")], clock)

    assert kinds(actions) == {"CLAUDE.md": "new"}
    assert dest.read_bytes() == b"orders\n"
    assert State.load(env).owns(dest)


def test_second_run_is_a_no_op_without_a_snapshot(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    deploy(env, [target(dest, b"x")], clock)
    before = list_snapshots(env)

    actions = deploy(env, [target(dest, b"x")], clock)

    assert kinds(actions) == {"a.txt": "ok"}
    assert list_snapshots(env) == before


def test_untouched_file_updates_when_the_kit_changes(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    deploy(env, [target(dest, b"v1")], clock)
    actions = deploy(env, [target(dest, b"v2")], clock)
    assert kinds(actions) == {"a.txt": "update"}
    assert dest.read_bytes() == b"v2"


def test_hand_edits_are_drift_and_survive_until_forced(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    deploy(env, [target(dest, b"v1")], clock)
    dest.write_bytes(b"my edit")

    actions = deploy(env, [target(dest, b"v2")], clock)
    assert kinds(actions) == {"a.txt": "drift"}
    assert dest.read_bytes() == b"my edit"

    deploy(env, [target(dest, b"v2")], clock, force=True)
    assert dest.read_bytes() == b"v2"
    newest = list_snapshots(env)[-1]
    restore(env, newest.name, clock=clock)
    assert dest.read_bytes() == b"my edit"


def test_foreign_files_are_adopted_with_a_backup(env: Env, clock: Clock) -> None:
    dest = env.home / "settings.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"tadashi wrote this")

    actions = deploy(env, [target(dest, b"argent")], clock)

    assert kinds(actions) == {"settings.txt": "adopt"}
    snapshot = list_snapshots(env)[-1]
    assert snapshot.count == 1


def test_files_dropped_from_the_kit_are_removed_if_untouched(env: Env, clock: Clock) -> None:
    keep, gone, edited = env.home / "keep", env.home / "gone", env.home / "edited"
    deploy(env, [target(keep, b"k"), target(gone, b"g"), target(edited, b"e")], clock)
    edited.write_bytes(b"mine now")

    actions = deploy(env, [target(keep, b"k")], clock)

    assert kinds(actions) == {"keep": "ok", "gone": "remove", "edited": "drift"}
    assert not gone.exists()
    assert edited.read_bytes() == b"mine now"
    assert not State.load(env).owns(gone)


def test_mirror_strays_are_kept_until_forced_and_caches_always(env: Env, clock: Clock) -> None:
    skill = env.home / ".claude" / "skills" / "vibe"
    (skill / "__pycache__").mkdir(parents=True)
    (skill / "__pycache__" / "x.pyc").write_bytes(b"")
    (skill / "my-notes.md").write_bytes(b"mine")

    state = State.load(env)
    actions = plan([target(skill / "SKILL.md", b"vibe")], state, mirror=[skill])
    apply(actions, env, state, clock=clock)
    assert kinds(actions) == {"SKILL.md": "new", "my-notes.md": "stray"}
    assert (skill / "my-notes.md").exists()

    state = State.load(env)
    actions = plan([target(skill / "SKILL.md", b"vibe")], state, mirror=[skill])
    apply(actions, env, state, clock=clock, force=True)
    assert not (skill / "my-notes.md").exists()
    assert (skill / "__pycache__" / "x.pyc").exists()


def test_files_already_in_place_become_owned(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"same")
    deploy(env, [target(dest, b"same")], clock)
    assert State.load(env).owns(dest)

    dest.write_bytes(b"hand edit")
    actions = deploy(env, [target(dest, b"kit v2")], clock)
    assert kinds(actions) == {"a.txt": "drift"}
    assert dest.read_bytes() == b"hand edit"


def test_a_failing_write_still_saves_what_was_written(
    env: Env, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = env.home / "first.txt", env.home / "second.txt"
    import argent.deploy

    real = argent.deploy.write_atomic

    def flaky(dest: Path, content: bytes) -> None:
        if dest == second:
            raise PermissionError("locked")
        real(dest, content)

    monkeypatch.setattr(argent.deploy, "write_atomic", flaky)
    with pytest.raises(PermissionError):
        deploy(env, [target(first, b"1"), target(second, b"2")], clock)
    assert State.load(env).owns(first)


def test_dry_run_touches_nothing(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    actions = deploy(env, [target(dest, b"x")], clock, dry_run=True)
    assert kinds(actions) == {"a.txt": "new"}
    assert not dest.exists()
    assert not env.state.exists()


def test_merged_files_never_drift(env: Env, clock: Clock) -> None:
    dest = env.home / "settings.json"
    deploy(env, [target(dest, b"{}", whole=False)], clock)
    dest.write_bytes(b'{"user": 1}')
    actions = deploy(env, [target(dest, b'{"user": 1, "argent": 1}', whole=False)], clock)
    assert kinds(actions) == {"settings.json": "update"}


def test_targets_can_skip_with_a_reason(env: Env, clock: Clock) -> None:
    def refuse(_current: bytes | None) -> bytes | None:
        raise SkipTargetError("has comments; merge by hand")

    dest = env.home / "settings.json"
    actions = deploy(env, [Target(dest=dest, label="s", build=refuse, whole=False)], clock)
    assert actions[0].kind == "skip"
    assert "comments" in actions[0].reason


def test_restore_puts_back_what_was_there_and_deletes_what_wasnt(env: Env, clock: Clock) -> None:
    old, fresh = env.home / "old.txt", env.home / "new.txt"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"original")
    deploy(env, [target(old, b"argent"), target(fresh, b"argent")], clock)
    name = list_snapshots(env)[-1].name

    restored = restore(env, name, clock=clock)

    assert sorted(p.name for p in restored) == ["new.txt", "old.txt"]
    assert old.read_bytes() == b"original"
    assert not fresh.exists()
    assert not State.load(env).owns(old)
    # restoring is itself undoable
    assert list_snapshots(env)[-1].reason == f"restore {name}"


def test_restore_journals_before_it_touches_anything(env: Env, clock: Clock) -> None:
    dest = env.home / "a.txt"
    deploy(env, [target(dest, b"argent")], clock)
    name = list_snapshots(env)[-1].name
    dest.unlink()
    dest.mkdir()  # a folder where the snapshot expects to delete a file

    with pytest.raises(OSError):
        restore(env, name, clock=clock)
    assert list_snapshots(env)[-1].reason == f"restore {name}"


def test_unknown_snapshot_is_a_clear_error(env: Env, clock: Clock) -> None:
    with pytest.raises(UnknownSnapshotError, match="no snapshot named"):
        restore(env, "19990101-000000", clock=clock)


def test_removing_a_folders_last_file_removes_the_folder(env: Env, clock: Clock) -> None:
    skills = env.home / ".claude" / "skills"
    old, kept = skills / "old" / "SKILL.md", skills / "kept" / "SKILL.md"
    deploy(env, [target(old, b"o"), target(kept, b"k")], clock)

    deploy(env, [target(kept, b"k")], clock)

    assert not (skills / "old").exists()
    assert kept.is_file()
