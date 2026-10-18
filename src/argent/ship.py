"""edith ship: message rules, secret scan, project checks, commit, push. In that order."""

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from edith.ui import Out

SUBJECT_MAX = 60
ATTRIBUTION = re.compile(
    r"co-authored-by:|generated (with|by)|written (with|by) (ai|claude|chatgpt|an ai)|"
    r"assisted by|\bas an ai\b",
    re.IGNORECASE,
)
EMOJI = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f000-\U0001f2ff]")


class ShipError(RuntimeError):
    pass


@dataclass(frozen=True)
class Outcome:
    ok: bool
    text: str = ""


Scan = Callable[[Path, list[str]], Outcome]
Check = Callable[[Path], Outcome | None]


def message_problems(message: str) -> list[str]:
    """The authorship rules, enforced: short plain subject, no AI credit, no emoji."""
    lines = message.strip().splitlines()
    if not lines or not lines[0].strip():
        return ["the message is empty"]
    subject = lines[0].strip()
    problems: list[str] = []
    if len(subject) > SUBJECT_MAX:
        problems.append(f"the subject is {len(subject)} characters; keep it to {SUBJECT_MAX}")
    if subject.endswith("."):
        problems.append("the subject ends with a period")
    if ATTRIBUTION.search(message):
        problems.append("it credits an AI or a co-author; the work is yours alone")
    if EMOJI.search(message):
        problems.append("it has emoji")
    return problems


def git(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def repo_root(start: Path) -> Path:
    found = git(start, "rev-parse", "--show-toplevel")
    if found.returncode != 0:
        raise ShipError(f"{start} isn't inside a git repository")
    return Path(found.stdout.strip())


def ship(
    repo: Path, message: str, out: Out, *, scan: Scan, check: Check, push: bool = True
) -> None:
    problems = message_problems(message)
    if problems:
        raise ShipError("the commit message won't do: " + "; ".join(problems))
    out.tag("pass", f"message  {out.dim(message.strip().splitlines()[0])}")

    we_staged = not _staged(repo)
    if we_staged:
        added = git(repo, "add", "-A")
        if added.returncode != 0:
            raise ShipError(f"git add failed: {_tail(added.stderr)}")
    staged = _staged(repo)
    unpushed = _unpushed(repo)
    if not staged and not unpushed:
        out.tag("ok", "nothing to commit or push")
        return

    committed = False
    try:
        if staged:
            _gate(out, "secrets", scan(repo, ["--pre-commit", "--staged"]), f"{len(staged)} files")
            outcome = check(repo)
            if outcome is not None:
                _gate(out, "checks", outcome, "just check")
            done = git(repo, "commit", "-q", "-F", "-", stdin=message.strip() + "\n")
            if done.returncode != 0:
                raise ShipError(f"git commit failed: {_tail(done.stderr or done.stdout)}")
            committed = True
            head = git(repo, "log", "-1", "--format=%h %s").stdout.strip()
            out.tag("set", f"commit   {head}")
    finally:
        # whatever stopped us (a gate, a hook, ctrl-c), don't leave the user's tree staged
        if we_staged and staged and not committed:
            git(repo, "reset", "-q")

    if push:
        _push(repo, out, scan)


def _push(repo: Path, out: Out, scan: Scan) -> None:
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode == 0:
        target, args, commits = upstream.stdout.strip(), ["push", "-q"], "@{u}..HEAD"
    elif "origin" in git(repo, "remote").stdout.split():
        target, args, commits = (
            "origin (new branch)",
            ["push", "-q", "-u", "origin", "HEAD"],
            "HEAD",
        )
    else:
        out.tag("skip", f"push     {out.dim('no remote yet; `gh repo create` makes one')}")
        return
    found = scan(repo, [f"--log-opts={commits}"])
    _gate(
        out, "secrets", found, "commits being pushed", "nothing was pushed; the commit stays local"
    )
    pushed = git(repo, *args)
    if pushed.returncode != 0:
        raise ShipError(f"git push failed: {_tail(pushed.stderr)}")
    out.tag("set", f"push     {target}")


def _gate(
    out: Out, name: str, outcome: Outcome, what: str, after: str = "nothing was committed or pushed"
) -> None:
    if not outcome.ok:
        out.tag("fail", f"{name:<8} {what}")
        if outcome.text:
            out.line(outcome.text)
        raise ShipError(f"{name} failed, so {after}")
    out.tag("pass", f"{name:<8} {out.dim(what)}")


def _staged(repo: Path) -> list[str]:
    return git(repo, "diff", "--cached", "--name-only").stdout.split("\n")[:-1]


def _unpushed(repo: Path) -> int:
    counted = git(repo, "rev-list", "--count", "@{u}..HEAD")
    if counted.returncode == 0:
        return int(counted.stdout.strip() or 0)
    has_commits = git(repo, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    return 1 if has_commits and "origin" in git(repo, "remote").stdout.split() else 0


def _tail(text: str) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "no output"


def gitleaks_scan(repo: Path, args: list[str]) -> Outcome:
    exe = shutil.which("gitleaks")
    if not exe:
        raise ShipError("gitleaks isn't installed, and nothing ships unscanned: edith install core")
    done = subprocess.run(
        [exe, "git", "--no-banner", "--redact", *args, str(repo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return Outcome(done.returncode == 0, (done.stdout + done.stderr).strip())


def just_check(repo: Path) -> Outcome | None:
    """The project's own gate, when it has one."""
    exe = shutil.which("just")
    if not exe or not any(
        (repo / name).is_file() for name in ("justfile", "Justfile", ".justfile")
    ):
        return None
    recipes = subprocess.run(
        [exe, "--summary"], cwd=repo, capture_output=True, text=True, check=False
    ).stdout.split()
    if "check" not in recipes:
        return None
    done = subprocess.run(
        [exe, "check"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-25:])
    return Outcome(done.returncode == 0, tail)
