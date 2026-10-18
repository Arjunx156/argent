import sys
from pathlib import Path

import pytest

from argent.paths import Env, RepoNotFoundError, adopt_legacy_state, documents_folder, find_repo


def test_argent_repo_override_is_honoured(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGENT_REPO", str(env.repo))
    assert find_repo() == env.repo


def test_a_folder_without_kit_is_not_a_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGENT_REPO", str(tmp_path))
    monkeypatch.setattr("argent.paths.__file__", str(tmp_path / "a" / "b" / "paths.py"))
    with pytest.raises(RepoNotFoundError, match="uv tool install"):
        find_repo()


def test_state_lives_under_the_home(env: Env) -> None:
    assert env.snapshots == env.home / ".argent" / "snapshots"
    assert env.claude == env.home / ".claude"


@pytest.mark.skipif(sys.platform != "win32", reason="known folders are a Windows thing")
def test_documents_folder_is_real_on_windows() -> None:
    assert documents_folder(Path.home()).is_dir()


def test_state_from_the_edith_days_moves_over_once(env: Env) -> None:
    (env.legacy_state / "snapshots" / "20261018-090929").mkdir(parents=True)
    (env.legacy_state / "state.json").write_text("{}", encoding="utf-8")

    assert adopt_legacy_state(env) is True
    assert (env.snapshots / "20261018-090929").is_dir()
    assert not env.legacy_state.exists()
    assert adopt_legacy_state(env) is False


def test_existing_argent_state_is_never_overwritten(env: Env) -> None:
    env.legacy_state.mkdir(parents=True)
    env.state.mkdir(parents=True)
    assert adopt_legacy_state(env) is False
    assert env.legacy_state.exists()
