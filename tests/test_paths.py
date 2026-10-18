import sys
from pathlib import Path

import pytest

from edith.paths import Env, RepoNotFoundError, documents_folder, find_repo


def test_edith_repo_override_is_honoured(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDITH_REPO", str(env.repo))
    assert find_repo() == env.repo


def test_a_folder_without_kit_is_not_a_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITH_REPO", str(tmp_path))
    monkeypatch.setattr("edith.paths.__file__", str(tmp_path / "a" / "b" / "paths.py"))
    with pytest.raises(RepoNotFoundError, match="uv tool install"):
        find_repo()


def test_state_lives_under_the_home(env: Env) -> None:
    assert env.snapshots == env.home / ".edith" / "snapshots"
    assert env.claude == env.home / ".claude"


@pytest.mark.skipif(sys.platform != "win32", reason="known folders are a Windows thing")
def test_documents_folder_is_real_on_windows() -> None:
    assert documents_folder(Path.home()).is_dir()
