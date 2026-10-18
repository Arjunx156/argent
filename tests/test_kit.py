import dataclasses
import json
from datetime import datetime
from pathlib import Path

import pytest

from edith.commands.deploy_cmd import make_plan
from edith.deploy import apply
from edith.kit import build_kit
from edith.paths import Env
from edith.profile import load_profile
from edith.render import render
from edith.tools import Detection, load_manifest

REPO = Path(__file__).resolve().parents[1]
TADASHI_PROFILE = "# >>> tadashi >>>\r\nfunction spiderfoot {}\r\n# <<< tadashi <<<\r\n"
WT = "Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"


@pytest.fixture
def machine(env: Env) -> Env:
    """A fake machine with the real kit, left the way Tadashi leaves one."""
    fake = dataclasses.replace(env, repo=REPO)
    claude = fake.claude
    claude.mkdir(parents=True)
    (claude / "CLAUDE.md").write_text("# Standing orders\nRitesh's\n", encoding="utf-8")
    statusline = {"type": "command", "command": "python -I C:/Users/A B/.claude/statusline.py"}
    (claude / "settings.json").write_text(json.dumps({"statusLine": statusline}), "utf-8")
    for shell in ("PowerShell", "WindowsPowerShell"):
        (fake.documents / shell).mkdir()
        (fake.documents / shell / "profile.ps1").write_bytes(TADASHI_PROFILE.encode())
    wt = fake.localappdata / WT
    wt.parent.mkdir(parents=True)
    wt.write_text(json.dumps({"schemes": [{"name": "Tadashi Neon"}], "profiles": {}}), "utf-8")
    (fake.appdata / "Code" / "User").mkdir(parents=True)
    return fake


def test_every_template_in_the_kit_renders_with_and_without_tools(machine: Env) -> None:
    env = machine
    profile = load_profile(env)
    manifest = load_manifest(env.kit / "tools.toml")
    for found in (Detection(), Detection({t.cmd: "x" for t in manifest.tools})):
        kit = build_kit(env, profile, manifest, found)
        for target in kit.targets:
            assert not target.dest.name.endswith(".tmpl")
    for template in (REPO / "kit").rglob("*.tmpl"):
        text = template.read_text(encoding="utf-8")
        context = {k: "x" for k in ("tools", "projects.roots", "edith.repo")}
        context |= profile.context()
        render(text, context, lambda _t: True, template.name)
        render(text, context, lambda _t: False, template.name)


def test_first_deploy_takes_over_from_tadashi(machine: Env) -> None:
    planned = make_plan(machine)
    apply(planned.actions, machine, planned.state, clock=datetime.now)

    orders = (machine.claude / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Arjun Krishnan" in orders
    assert "Ritesh" not in orders
    assert "{{" not in orders

    settings = json.loads((machine.claude / "settings.json").read_text(encoding="utf-8"))
    assert settings["statusLine"]["command"].endswith('statusline.py"')

    profile = (machine.documents / "PowerShell" / "profile.ps1").read_bytes()
    assert b"tadashi" not in profile
    assert b"# >>> edith >>>\r\n" in profile

    wt = json.loads((machine.localappdata / WT).read_text(encoding="utf-8"))
    assert [s["name"] for s in wt["schemes"]] == ["Edith"]

    authorship = machine.claude / "skills" / "authorship" / "SKILL.md"
    assert "Arjun Krishnan" in authorship.read_text(encoding="utf-8")
    folio = machine.appdata / "typst" / "packages" / "local" / "folio" / "1.0.0" / "lib.typ"
    assert folio.is_file()


def test_second_deploy_changes_nothing(machine: Env) -> None:
    planned = make_plan(machine)
    apply(planned.actions, machine, planned.state, clock=datetime.now)

    again = make_plan(machine)
    assert [a.label for a in again.actions if a.kind != "ok"] == []


def test_standing_orders_only_claim_detected_tools(machine: Env) -> None:
    planned = make_plan(machine)
    orders = next(a for a in planned.actions if a.dest == machine.claude / "CLAUDE.md")
    text = (orders.desired or b"").decode()
    for tool in load_manifest(REPO / "kit" / "tools.toml").tools:
        if tool.claim and not planned.found.has(tool.cmd):
            assert tool.claim not in text
