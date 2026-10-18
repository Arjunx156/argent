import io
import shutil
import subprocess
from pathlib import Path

import pytest

from argent.ship import Outcome, ShipError, message_problems, ship
from argent.ui import Out

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="needs git")
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@x"]


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with one pushed commit and a bare origin."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@x")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@x")
    remote = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    (work / "a.txt").write_text("a", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "first")
    git(work, "push", "-q", "-u", "origin", "main")
    return work


def clean(_repo: Path, _args: list[str]) -> Outcome:
    return Outcome(True)


def leaky(_repo: Path, _args: list[str]) -> Outcome:
    return Outcome(False, "leak: cfg.py:1")


def passing(_repo: Path) -> Outcome:
    return Outcome(True)


def failing(_repo: Path) -> Outcome:
    return Outcome(False, "1 failed")


def run(repo: Path, message: str, **kw: object) -> str:
    buf = io.StringIO()
    options = {"scan": clean, "check": passing, **kw}
    ship(repo, message, Out(buf, colour=False), **options)  # pyright: ignore[reportArgumentType]
    return buf.getvalue()


def remote_head(repo: Path) -> str:
    return git(repo, "rev-parse", "origin/main")


def test_ships_everything_when_nothing_is_staged(repo: Path) -> None:
    (repo / "b.txt").write_text("b", encoding="utf-8")
    output = run(repo, "add b")
    assert "push     origin/main" in output
    assert git(repo, "log", "-1", "--format=%s") == "add b"
    assert remote_head(repo) == git(repo, "rev-parse", "HEAD")


def test_respects_a_deliberate_partial_stage(repo: Path) -> None:
    (repo / "b.txt").write_text("b", encoding="utf-8")
    (repo / "c.txt").write_text("c", encoding="utf-8")
    git(repo, "add", "b.txt")
    run(repo, "add b only", push=False)
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "b.txt"
    assert "c.txt" in git(repo, "status", "--porcelain")


def test_a_leak_stops_everything_and_unstages(repo: Path) -> None:
    (repo / "cfg.py").write_text("token", encoding="utf-8")
    before = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ShipError, match="secrets failed"):
        run(repo, "add config", scan=leaky)
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "diff", "--cached", "--name-only") == ""


def test_failing_checks_stop_the_commit(repo: Path) -> None:
    (repo / "b.txt").write_text("b", encoding="utf-8")
    with pytest.raises(ShipError, match="checks failed"):
        run(repo, "add b", check=failing)
    assert git(repo, "log", "-1", "--format=%s") == "first"


def test_any_failure_unstages_what_ship_staged(repo: Path) -> None:
    (repo / "b.txt").write_text("b", encoding="utf-8")

    def explodes(_repo: Path) -> Outcome:
        raise OSError("just vanished")

    with pytest.raises(OSError):
        run(repo, "add b", check=explodes)
    assert git(repo, "diff", "--cached", "--name-only") == ""


def test_earlier_unpushed_commits_get_pushed_too(repo: Path) -> None:
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "local")
    output = run(repo, "anything")
    assert "push     origin/main" in output
    assert remote_head(repo) == git(repo, "rev-parse", "HEAD")


def test_nothing_to_do_says_so(repo: Path) -> None:
    assert "nothing to commit or push" in run(repo, "noop")


def test_no_remote_commits_and_explains(tmp_path: Path, repo: Path) -> None:
    git(repo, "remote", "remove", "origin")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    output = run(repo, "add b")
    assert "no remote yet" in output
    assert git(repo, "log", "-1", "--format=%s") == "add b"


@pytest.mark.parametrize(
    ("message", "problem"),
    [
        ("", "empty"),
        ("x" * 61, "61 characters"),
        ("fix the parser.", "period"),
        ("add docs\n\nCo-Authored-By: Claude <noreply@anthropic.com>", "credits"),
        ("Generated with a tool", "credits"),
        ("ship it \U0001f680", "emoji"),
    ],
)
def test_message_rules(message: str, problem: str) -> None:
    assert any(problem in p for p in message_problems(message))


def test_a_plain_message_passes() -> None:
    assert message_problems("fix off-by-one in the merge loop") == []
