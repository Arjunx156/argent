import dataclasses
import subprocess
from pathlib import Path

import pytest

from argent.library import (
    LibraryError,
    Repo,
    find,
    frontmatter,
    index,
    library_dir,
    load_repos,
    sync_repo,
)
from argent.paths import Env

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("text", "name", "description"),
    [
        ("---\nname: pdf\ndescription: Work with PDFs.\n---\nbody", "pdf", "Work with PDFs."),
        # yaml escapes a quote inside single quotes by doubling it
        ("---\nname: \"quoted\"\ndescription: 'It''s fine'\n---\n", "quoted", "It's fine"),
        (
            "---\nname: folded\ndescription: >\n  Spans two\n  lines.\nlicense: MIT\n---\n",
            "folded",
            "Spans two lines.",
        ),
        (
            "---\nname: wrapped\ndescription: Starts here\n  and goes on.\n---\n",
            "wrapped",
            "Starts here and goes on.",
        ),
    ],
)
def test_frontmatter_reads_the_ways_skills_write_it(text: str, name: str, description: str) -> None:
    meta = frontmatter(text)
    assert meta["name"] == name
    assert meta["description"] == description


def test_no_frontmatter_means_nothing() -> None:
    assert frontmatter("# just a title\n") == {}


def test_the_shipped_repo_list_is_valid() -> None:
    repos = load_repos(REPO / "kit" / "library.toml")
    assert len(repos) == 10
    assert all(r.why for r in repos)


def test_repo_names_are_checked(tmp_path: Path) -> None:
    bad = tmp_path / "library.toml"
    bad.write_text('[[repo]]\nname = "https://evil.example/x"\n', encoding="utf-8")
    with pytest.raises(LibraryError, match="owner/name"):
        load_repos(bad)


def fake_library(env: Env) -> list[Repo]:
    repos = [Repo("acme/skills", "Acme's skills"), Repo("solo/one", "one skill")]
    root = library_dir(env)
    for rel, name, desc in [
        ("acme__skills/pdf/SKILL.md", "pdf", "Fill and merge PDF forms."),
        ("acme__skills/deep/nested/review/SKILL.md", "review", "Review a pull request."),
        ("acme__skills/.git/SKILL.md", "ignored", "inside .git"),
        ("solo__one/SKILL.md", "pdf-ocr", "Read scanned PDFs."),
    ]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {name}\ndescription: {desc}\n---\n", encoding="utf-8")
    return repos


def test_index_finds_skills_at_any_depth_but_not_in_git(env: Env) -> None:
    cards = index(env, fake_library(env))
    assert sorted(c.name for c in cards) == ["pdf", "pdf-ocr", "review"]


def test_find_needs_every_word_and_ranks_names_first(env: Env) -> None:
    cards = index(env, fake_library(env))
    assert [c.name for c in find(cards, ["pdf"])] == ["pdf", "pdf-ocr"]
    assert [c.name for c in find(cards, ["pdf", "scanned"])] == ["pdf-ocr"]
    assert find(cards, ["nothing"]) == []


def test_cloning_never_runs_hooks_symlinks_or_other_protocols(env: Env) -> None:
    seen: list[list[str]] = []

    def git(argv: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    assert sync_repo(env, Repo("acme/skills", ""), git) == "new"
    clone = " ".join(seen[0])
    assert "core.hooksPath=" in clone
    assert "core.symlinks=false" in clone
    assert "protocol.allow=never" in clone
    assert "--no-recurse-submodules" in clone
    assert "--depth 1" in clone
    assert clone.endswith(str(library_dir(env) / "acme__skills"))


def test_a_failed_clone_names_the_repo(env: Env) -> None:
    def git(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 128, "", "fatal: repository not found\n")

    with pytest.raises(
        LibraryError, match="acme/skills: git clone failed: fatal: repository not found"
    ):
        sync_repo(env, Repo("acme/skills", ""), git)


def test_status_and_find_handle_an_empty_library(env: Env) -> None:
    import io

    from argent.commands.library_cmd import run
    from argent.ui import Out

    kit_env = dataclasses.replace(env, repo=REPO)
    buf = io.StringIO()
    args = type("Args", (), {"action": "find", "words": ["pdf"]})()
    assert run(args, kit_env, Out(buf, colour=False)) == 0  # pyright: ignore[reportArgumentType]
    assert "argent library sync" in buf.getvalue()
