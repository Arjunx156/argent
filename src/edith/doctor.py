"""edith doctor: every claim about this machine, checked against the machine."""

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from edith.commands.deploy_cmd import Planned, make_plan
from edith.kit import pretty
from edith.merge import CHIME_MARK
from edith.paths import Env
from edith.profile import Profile, load_profile
from edith.projects import survey
from edith.render import branched_tools
from edith.state import State
from edith.tools import Detection, Manifest, detect, load_manifest, search_path

STATUSLINE_SAMPLE = json.dumps(
    {"workspace": {"current_dir": "C:/edith-doctor"}, "model": {"display_name": "Doctor"}}
).encode()
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


Runner = Callable[..., Result]


def system_runner(
    cmd: list[str] | str, stdin: bytes | None = None, shell: bool = False, timeout: float = 15
) -> Result:
    try:
        done = subprocess.run(
            cmd, input=stdin, capture_output=True, shell=shell, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return Result(127, "", f"{cmd[0] if isinstance(cmd, list) else cmd}: not found")
    except subprocess.TimeoutExpired:
        return Result(124, "", f"timed out after {timeout:.0f}s")
    return Result(done.returncode, _text(done.stdout), _text(done.stderr))


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").strip()


@dataclass(frozen=True)
class Finding:
    status: str
    title: str
    detail: str
    fix: str = ""


@dataclass
class Context:
    env: Env
    run: Runner = system_runner

    @cached_property
    def profile(self) -> Profile:
        return load_profile(self.env)

    @cached_property
    def manifest(self) -> Manifest:
        return load_manifest(self.env.kit / "tools.toml")

    @cached_property
    def found(self) -> Detection:
        return detect(self.manifest.tools, self.env)

    @cached_property
    def planned(self) -> Planned:
        return make_plan(self.env)

    @cached_property
    def claude_settings(self) -> dict[str, Any]:
        try:
            return json.loads((self.env.claude / "settings.json").read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, ValueError):
            return {}


Check = Callable[[Context], list[Finding]]


def check_profile(ctx: Context) -> list[Finding]:
    p = ctx.profile
    return [Finding("pass", "profile", f"{p.name}, GitHub {p.github}")]


def check_git_identity(ctx: Context) -> list[Finding]:
    name = ctx.run(["git", "config", "--global", "user.name"]).out
    email = ctx.run(["git", "config", "--global", "user.email"]).out
    p = ctx.profile
    if not email:
        fix = f'git config --global user.name "{p.name}"; git config --global user.email {p.email}'
        return [Finding("fail", "git identity", "git has no global identity", fix)]
    if email.lower() != p.email.lower():
        detail = f"commits go out as {name} <{email}>, the profile says {p.email}"
        fix = (
            "fine if both addresses are on your GitHub account; "
            f"otherwise git config --global user.email {p.email}"
        )
        return [Finding("warn", "git identity", detail, fix)]
    return [Finding("pass", "git identity", f"{name} <{email}>")]


def check_github(ctx: Context) -> list[Finding]:
    status = ctx.run(["gh", "auth", "status", "--hostname", "github.com"])
    if status.code == 127:
        return [Finding("fail", "github", "gh isn't installed", "edith install core")]
    text = status.out + status.err
    account = re.search(r"account (\S+)", text)
    if status.code != 0 or not account:
        return [Finding("fail", "github", "gh isn't signed in", "gh auth login")]
    if account.group(1).lower() != ctx.profile.github.lower():
        detail = f"signed in as {account.group(1)}, the profile says {ctx.profile.github}"
        return [Finding("warn", "github", detail, "gh auth switch")]
    return [Finding("pass", "github", f"signed in as {account.group(1)}")]


def check_tools(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for group in ctx.manifest.groups:
        tools = ctx.manifest.in_groups([group])
        missing = [t.cmd for t in tools if not ctx.found.has(t.cmd)]
        have = f"{len(tools) - len(missing)} of {len(tools)}"
        if not missing:
            findings.append(Finding("pass", f"tools: {group}", f"all {len(tools)} installed"))
        elif group == "core":
            detail = f"{have}; missing {', '.join(missing)}"
            findings.append(Finding("fail", "tools: core", detail, "edith install core"))
        else:
            detail = f"{have}; missing {', '.join(missing)}"
            findings.append(Finding("info", f"tools: {group}", detail, f"edith install {group}"))
    return findings


def check_kit(ctx: Context) -> list[Finding]:
    actions = ctx.planned.actions
    drift = [a for a in actions if a.kind == "drift"]
    skipped = [a for a in actions if a.kind == "skip"]
    pending = [a for a in actions if a.writes]
    findings: list[Finding] = []
    for action in drift:
        detail = f"{action.label} was edited by hand since edith wrote it"
        fix = "keep it: copy the change into the kit; drop it: edith deploy --force"
        findings.append(Finding("warn", "kit drift", detail, fix))
    for action in (a for a in actions if a.kind == "stray"):
        detail = f"{pretty(ctx.env, action.dest)} sits in a kit folder but isn't in the kit"
        fix = "keep it: add it to the kit; drop it: edith deploy --force"
        findings.append(Finding("warn", "kit drift", detail, fix))
    for action in skipped:
        findings.append(Finding("warn", "kit", f"{action.label}: {action.reason}"))
    if pending:
        detail = f"{len(pending)} files differ from the kit"
        findings.append(Finding("warn", "kit", detail, "edith diff, then edith deploy"))
    if not findings:
        findings.append(Finding("pass", "kit", f"all {len(actions)} files in place"))
    return findings


def check_claims(ctx: Context) -> list[Finding]:
    state = State.load(ctx.env)
    if not state.tools:
        return [Finding("info", "standing orders", "never deployed by edith", "edith deploy")]
    claimed = {t.cmd for t in ctx.manifest.tools if t.claim}
    for template in ctx.env.kit.rglob("*.tmpl"):
        claimed |= branched_tools(template.read_text(encoding="utf-8"))
    gone = sorted(t for t in state.tools if t in claimed and not ctx.found.has(t))
    new = sorted(t for t in claimed if ctx.found.has(t) and t not in state.tools)
    findings: list[Finding] = []
    if gone:
        detail = f"they tell Claude to use {', '.join(gone)}, which are gone"
        findings.append(Finding("fail", "standing orders", detail, "edith deploy"))
    if new:
        detail = f"{', '.join(new)} arrived since the last deploy; Claude doesn't know yet"
        findings.append(Finding("warn", "standing orders", detail, "edith deploy"))
    if not findings:
        findings.append(Finding("pass", "standing orders", "every tool they name is installed"))
    return findings


def check_statusline(ctx: Context) -> list[Finding]:
    line = ctx.claude_settings.get("statusLine") or {}
    command = line.get("command") if isinstance(line, dict) else None
    if not command:
        return [Finding("info", "status line", "none configured", "edith deploy")]
    result = ctx.run(command, stdin=STATUSLINE_SAMPLE, shell=True, timeout=10)
    if result.code != 0 or not result.out:
        first = next((ln for ln in reversed(result.err.splitlines()) if ln.strip()), "no output")
        detail = f"`{command}` exits {result.code}: {first.strip()}"
        return [Finding("fail", "status line", detail, "edith deploy")]
    return [Finding("pass", "status line", "runs and prints")]


def check_rules(ctx: Context) -> list[Finding]:
    rules = ctx.env.claude / "rules"
    always = (
        [p for p in sorted(rules.rglob("*.md")) if not _scoped_rule(p)] if rules.is_dir() else []
    )
    if not always:
        return [Finding("pass", "always-on rules", "none beside the standing orders")]
    size = sum(p.stat().st_size for p in always)
    folders = sorted({pretty(ctx.env, p.parent) for p in always})
    detail = (
        f"{len(always)} files ({size / 1024:.0f} KB) load into every session beside the standing "
        f"orders, from {', '.join(folders)}. Edith doesn't manage them, so they can contradict it"
    )
    shelf = ", ".join(sorted({f"rules/{p.relative_to(rules).parts[0]}" for p in always}))
    return [Finding("warn", "always-on rules", detail, f"edith shelve {shelf}")]


def _scoped_rule(path: Path) -> bool:
    """Rules with paths: in their frontmatter load only when matching files are touched."""
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    match = FRONTMATTER.match(head)
    return bool(match and re.search(r"(?m)^paths:", match.group(1)))


def check_hooks(ctx: Context) -> list[Finding]:
    hooks = ctx.claude_settings.get("hooks") or {}
    findings: list[Finding] = []
    for event, groups in hooks.items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = str(hook.get("command", ""))
                if CHIME_MARK in command:
                    continue
                detail = f"{event} runs {_short(command)}, which edith doesn't manage"
                findings.append(Finding("info", "hooks", detail))
    return findings


def check_skills(ctx: Context) -> list[Finding]:
    root = ctx.env.claude / "skills"
    if not root.is_dir():
        return []
    ours = {p.name for p in (ctx.env.kit / "claude" / "skills").iterdir() if p.is_dir()}
    overrides = ctx.claude_settings.get("skillOverrides") or {}
    loaded: list[tuple[str, int]] = []
    for skill in sorted(root.iterdir()):
        card = skill / "SKILL.md"
        if skill.name in ours or skill.name.startswith(".") or not card.is_file():
            continue
        if overrides.get(skill.name) == "off":
            continue
        loaded.append((skill.name, _description_size(card)))
    if not loaded:
        return [Finding("pass", "skills", "every active skill comes from the kit")]
    size = sum(n for _, n in loaded)
    names = ", ".join(name for name, _ in loaded)
    detail = (
        f"{len(loaded)} active skills outside the kit add {size / 1024:.1f} KB of descriptions "
        f"to every session: {names}"
    )
    return [Finding("info", "skills", detail, "edith shelve skills/<name> parks one")]


def _description_size(card: Path) -> int:
    match = FRONTMATTER.match(card.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return 0
    found = re.search(r"(?ms)^description:(.*?)(?=^\S|\Z)", match.group(1))
    return len(found.group(1).strip()) if found else 0


def check_path(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    local_bin = ctx.env.home / ".local" / "bin"
    user = user_path()
    if user is not None and not any(_same(p, local_bin) for p in user):
        detail = f"{pretty(ctx.env, local_bin)} isn't on your user PATH, so uv tools vanish"
        findings.append(Finding("warn", "PATH", detail, "edith install core adds it"))
    uvs = [f for f in search_path(ctx.env).split(os.pathsep) if (Path(f) / _exe("uv")).is_file()]
    if len(uvs) > 1:
        where = ", ".join(pretty(ctx.env, Path(f)) for f in uvs)
        findings.append(
            Finding("info", "PATH", f"{len(uvs)} copies of uv; the first wins: {where}")
        )
    if not findings:
        findings.append(Finding("pass", "PATH", "uv tools are reachable"))
    return findings


def check_python(ctx: Context) -> list[Finding]:
    result = ctx.run(["python", "--version"])
    version = re.search(r"(\d+)\.(\d+)", result.out + result.err)
    if result.code != 0 or not version:
        fix = "winget install Python.Python.3.13"
        return [Finding("fail", "python", "`python` doesn't run; the status line needs it", fix)]
    if (int(version.group(1)), int(version.group(2))) < (3, 10):
        detail = f"`python` is {version.group(0)}; the status line needs 3.10+"
        return [Finding("warn", "python", detail)]
    return [Finding("pass", "python", f"`python` is {version.group(0)}")]


def check_projects(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for root in ctx.profile.roots:
        if not root.is_dir():
            detail = f"{root.as_posix()} doesn't exist"
            findings.append(
                Finding("warn", "projects", detail, "fix projects.roots in profile.toml")
            )
    projects = survey(ctx.profile.roots)
    needy = [p for p in projects if p.problems]
    if not needy:
        findings.append(Finding("pass", "projects", f"all {len(projects)} committed and pushed"))
        return findings
    kinds = {
        "with uncommitted changes": sum(p.changed > 0 for p in needy),
        "with unpushed commits": sum(p.ahead > 0 for p in needy),
        "without a remote": sum(p.is_repo and not p.remotes for p in needy),
        "without git": sum(not p.is_repo for p in needy),
    }
    parts = ", ".join(f"{n} {kind}" for kind, n in kinds.items() if n)
    detail = f"{len(needy)} of {len(projects)} need you: {parts}"
    findings.append(Finding("info", "projects", detail, "edith projects --attention"))
    return findings


def check_snapshots(ctx: Context) -> list[Finding]:
    snaps = ctx.env.snapshots
    if not snaps.is_dir():
        return []
    folders = [p for p in snaps.iterdir() if p.is_dir()]
    size = sum(f.stat().st_size for f in snaps.rglob("*") if f.is_file())
    detail = f"{len(folders)} kept, {size / 1_048_576:.1f} MB in {pretty(ctx.env, snaps)}"
    return [Finding("info", "snapshots", detail, "edith restore lists them")]


CHECKS: list[tuple[str, Check]] = [
    ("profile", check_profile),
    ("git identity", check_git_identity),
    ("github", check_github),
    ("tools", check_tools),
    ("kit", check_kit),
    ("standing orders", check_claims),
    ("status line", check_statusline),
    ("python", check_python),
    ("PATH", check_path),
    ("always-on rules", check_rules),
    ("skills", check_skills),
    ("hooks", check_hooks),
    ("projects", check_projects),
    ("snapshots", check_snapshots),
]


def diagnose(ctx: Context, checks: list[tuple[str, Check]] = CHECKS) -> list[Finding]:
    findings: list[Finding] = []
    for title, check in checks:
        try:
            findings.extend(check(ctx))
        except Exception as err:
            findings.append(Finding("fail", title, f"the check itself failed: {err}"))
    return findings


def user_path() -> list[str] | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "Path")
    except OSError:
        return []
    return [os.path.expandvars(p) for p in str(value).split(";") if p]


def _same(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(str(b)))


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _short(command: str) -> str:
    """The program a hook runs, by file name: quoted paths keep their spaces."""
    command = command.strip()
    quoted = command.startswith('"')
    program = command[1:].split('"', 1)[0] if quoted else command.split(" ", 1)[0]
    return f"`{Path(program).name or program}`"
