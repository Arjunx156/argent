import argparse
import dataclasses
import io
from pathlib import Path

import pytest

from edith.commands.shelve_cmd import ShelfError, read_index, run_shelve, run_unshelve
from edith.paths import Env
from edith.ui import Out

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def claude(env: Env) -> Env:
    fake = dataclasses.replace(env, repo=REPO)
    (fake.claude / "rules" / "ecc" / "common").mkdir(parents=True)
    (fake.claude / "rules" / "ecc" / "common" / "agents.md").write_text("x", encoding="utf-8")
    (fake.claude / "skills" / "brand").mkdir(parents=True)
    return fake


def shelve(env: Env, *paths: str) -> str:
    buf = io.StringIO()
    run_shelve(argparse.Namespace(paths=list(paths)), env, Out(buf, colour=False))
    return buf.getvalue()


def unshelve(env: Env, *paths: str) -> None:
    run_unshelve(argparse.Namespace(paths=list(paths)), env, Out(io.StringIO(), colour=False))


def test_shelving_moves_it_out_and_back(claude: Env) -> None:
    shelve(claude, "rules/ecc")
    assert not (claude.claude / "rules" / "ecc").exists()
    assert (claude.shelf / "rules" / "ecc" / "common" / "agents.md").is_file()
    assert read_index(claude) == ["rules/ecc"]

    unshelve(claude, "rules/ecc")
    assert (claude.claude / "rules" / "ecc" / "common" / "agents.md").is_file()
    assert read_index(claude) == []
    assert not (claude.shelf / "rules").exists()


def test_listing_shows_what_is_parked(claude: Env) -> None:
    shelve(claude, "~/.claude/skills/brand")
    assert "skills/brand" in shelve(claude)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("CLAUDE.md", "owns that"),
        ("claude.md", "owns that"),
        ("Settings.JSON", "owns that"),
        ("Skills/Vibe", "comes from the kit"),
        ("settings.json", "owns that"),
        ("skills/vibe", "comes from the kit"),
        ("../.ssh", "inside ~/.claude"),
        ("rules/nothing-here", "nothing there"),
    ],
)
def test_refuses_what_it_must_not_touch(claude: Env, path: str, message: str) -> None:
    with pytest.raises(ShelfError, match=message):
        shelve(claude, path)


def test_unshelve_never_overwrites(claude: Env) -> None:
    shelve(claude, "skills/brand")
    (claude.claude / "skills" / "brand").mkdir()
    with pytest.raises(ShelfError, match="already lives there"):
        unshelve(claude, "skills/brand")
