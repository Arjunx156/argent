import json
from pathlib import Path

from argent.context import TARGET, measure
from argent.paths import Env


def skill(root: Path, name: str, description: str) -> None:
    (root / name).mkdir(parents=True)
    card = f"---\nname: {name}\ndescription: {description}\n---\n" + "body " * 500
    (root / name / "SKILL.md").write_text(card, encoding="utf-8")


def claude_home(env: Env) -> Path:
    claude = env.claude
    claude.mkdir(parents=True)
    (claude / "CLAUDE.md").write_text("x" * 400, encoding="utf-8")
    rules = claude / "rules" / "ecc"
    (rules / "python").mkdir(parents=True)
    (rules / "always.md").write_text("y" * 800, encoding="utf-8")
    scoped = '---\npaths:\n  - "**/*.py"\n---\n' + "z" * 5000
    (rules / "python" / "style.md").write_text(scoped, encoding="utf-8")
    skill(claude / "skills", "kept", "d" * 100)
    skill(claude / "skills", "muted", "m" * 100)
    (claude / "commands").mkdir()
    (claude / "commands" / "plan.md").write_text(
        "---\ndescription: plan it\n---\nlong body\n", encoding="utf-8"
    )
    settings = {
        "skillOverrides": {"muted": "off"},
        "enabledPlugins": {"on@market": True, "off@market": False},
    }
    (claude / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    plugins = claude / "plugins"
    for name in ("on", "off"):
        skill(plugins / "cache" / name / "skills", f"{name}-skill", "p" * 200)
    installed = {
        "plugins": {
            f"{n}@market": [{"installPath": str(plugins / "cache" / n)}] for n in ("on", "off")
        }
    }
    (plugins / "installed_plugins.json").write_text(json.dumps(installed), encoding="utf-8")
    return claude


def test_only_what_loads_every_session_is_counted(env: Env) -> None:
    claude_home(env)
    sources = {s.name: s for s in measure(env)}

    assert sources["standing orders"].chars == 400
    assert sources["always-on rules"].chars == 800
    assert sources["skills"].items == 1
    assert sources["skills"].chars == len("kept") + 100
    assert sources["slash commands"].items == 1
    assert sources["plugins"].items == 1
    assert sources["plugins"].chars == len("on-skill") + 200


def test_a_bare_machine_measures_zero(env: Env) -> None:
    assert sum(s.chars for s in measure(env)) == 0


def test_the_target_leaves_room_for_argents_own_kit() -> None:
    # standing orders plus twenty skill descriptions come to about 2,700 tokens
    assert TARGET >= 4_000
