import dataclasses
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from argent.doctor import (
    Context,
    Finding,
    Result,
    _short,
    check_claims,
    check_git_identity,
    check_rules,
    check_skills,
    check_statusline,
    diagnose,
    system_runner,
)
from argent.merge import claude_settings
from argent.paths import Env
from argent.state import State

REPO = Path(__file__).resolve().parents[1]


def scripted(answers: dict[str, Result]) -> Callable[..., Result]:
    def run(cmd: list[str] | str, **_kw: object) -> Result:
        joined = cmd if isinstance(cmd, str) else " ".join(cmd)
        return next((r for k, r in answers.items() if k in joined), Result(1, "", "unexpected"))

    return run


@pytest.fixture
def spaced(tmp_path: Path, env: Env) -> Env:
    """The home folder has a space in it, like the real one."""
    home = tmp_path / "ARJUN KRISHNAN"
    fake = dataclasses.replace(env, home=home, repo=REPO)
    fake.claude.mkdir(parents=True)
    shutil.copy(REPO / "kit" / "claude" / "statusline.py", fake.claude / "statusline.py")
    return fake


def write_settings(env: Env, data: dict[str, object]) -> None:
    (env.claude / "settings.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.skipif(not shutil.which("python"), reason="the status line runs `python`")
def test_unquoted_statusline_in_a_spaced_home_fails_for_real(spaced: Env) -> None:
    script = (spaced.claude / "statusline.py").as_posix()
    write_settings(spaced, {"statusLine": {"command": f"python -I {script}"}})
    [finding] = check_statusline(Context(spaced, run=system_runner))
    assert finding.status == "fail"


@pytest.mark.skipif(not shutil.which("python"), reason="the status line runs `python`")
def test_argent_statusline_runs_in_a_spaced_home(spaced: Env) -> None:
    script = (spaced.claude / "statusline.py").as_posix()
    merged = claude_settings(None, script, chimes=False)
    (spaced.claude / "settings.json").write_bytes(merged)
    [finding] = check_statusline(Context(spaced, run=system_runner))
    assert finding.status == "pass", finding.detail


def test_git_email_mismatch_is_a_warning_with_the_fix(env: Env) -> None:
    run = scripted(
        {"user.name": Result(0, "someone", ""), "user.email": Result(0, "other@x.com", "")}
    )
    [finding] = check_git_identity(Context(env, run=run))
    assert finding.status == "warn"
    assert "test@example.com" in finding.fix


def test_only_unscoped_rules_count_as_always_on(env: Env) -> None:
    rules = env.claude / "rules" / "ecc"
    (rules / "common").mkdir(parents=True)
    (rules / "python").mkdir()
    (rules / "common" / "agents.md").write_text("# always\n" * 100, encoding="utf-8")
    scoped = '---\npaths:\n  - "**/*.py"\n---\n# python\n'
    (rules / "python" / "style.md").write_text(scoped, encoding="utf-8")

    [finding] = check_rules(Context(env))

    assert finding.status == "warn"
    assert finding.detail.startswith("1 files")
    assert finding.fix == "argent shelve rules/ecc"


def test_skills_switched_off_or_from_the_kit_cost_nothing(env: Env) -> None:
    env = dataclasses.replace(env, repo=REPO)
    for name, desc in (("brand", "x" * 400), ("muted", "y" * 400), ("vibe", "z" * 400)):
        (env.claude / "skills" / name).mkdir(parents=True)
        card = f"---\nname: {name}\ndescription: {desc}\n---\nbody\n"
        (env.claude / "skills" / name / "SKILL.md").write_text(card, encoding="utf-8")
    write_settings(env, {"skillOverrides": {"muted": "off"}})

    [finding] = check_skills(Context(env))

    assert finding.detail.endswith(": brand")
    assert "0.4 KB" in finding.detail


def test_tools_named_in_the_orders_but_gone_are_failures(env: Env) -> None:
    env = dataclasses.replace(env, repo=REPO)
    state = State.load(env)
    state.tools = ["rg", "tectonic"]
    state.save()
    ctx = Context(env)
    ctx.__dict__["found"] = dataclasses.replace(ctx.found, found={"rg": "x"})

    findings = check_claims(ctx)

    assert [f.status for f in findings] == ["fail"]
    assert "tectonic" in findings[0].detail


def test_a_crashing_check_becomes_a_failure_not_a_traceback(env: Env) -> None:
    def broken(_ctx: Context) -> list[Finding]:
        raise RuntimeError("boom")

    [finding] = diagnose(Context(env), [("broken", broken)])
    assert finding.status == "fail"
    assert "boom" in finding.detail


@pytest.mark.parametrize(
    ("command", "name"),
    [
        ('"C:\\Users\\ARJUN KRISHNAN\\.claude\\hooks\\start.cmd"', "`start.cmd`"),
        ("node C:/hooks/run.js --fast", "`node`"),
    ],
)
def test_hook_programs_are_named_by_file(command: str, name: str) -> None:
    assert _short(command) == name


def test_runner_reports_missing_programs() -> None:
    result = system_runner(["argent-no-such-program-anywhere"])
    assert result.code == 127
