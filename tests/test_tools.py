import os
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import FakeProbe

from argent.paths import Env
from argent.probe import search_path
from argent.tools import Detection, ManifestError, detect, expand, load_manifest, satisfied

REAL_MANIFEST = Path(__file__).resolve().parents[1] / "kit" / "tools.toml"

MINIMAL = """\
[groups]
core = "the basics"

[[area]]
name = "Search"

[[tool]]
cmd = "rg"
group = "core"
winget = "BurntSushi.ripgrep.MSVC"
area = "Search"
claim = "`rg` for text"
about = "Searches."
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "tools.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_shipped_manifest_is_valid() -> None:
    manifest = load_manifest(REAL_MANIFEST)
    assert manifest.get("rg").group == "core"
    assert manifest.get("tectonic").release is not None
    claimed_areas = {t.area for t in manifest.tools if t.claim}
    assert claimed_areas <= {a.name for a in manifest.areas}


def test_detect_uses_which_then_probes(env: Env) -> None:
    font = env.localappdata / "Microsoft" / "Windows" / "Fonts"
    font.mkdir(parents=True)
    (font / "JetBrainsMonoNerdFont-Regular.ttf").write_bytes(b"")
    manifest = load_manifest(REAL_MANIFEST)
    tools = [manifest.get("rg"), manifest.get("tectonic"), manifest.get("JetBrainsMono Nerd Font")]

    found = detect(tools, env, FakeProbe(env, commands={"rg": "/bin/rg"}))

    assert found.where("rg") == "/bin/rg"
    assert not found.has("tectonic")
    assert found.has("JetBrainsMono Nerd Font")


def test_libraries_are_found_where_their_language_looks(env: Env, tmp_path: Path) -> None:
    node_dir = tmp_path / "node_modules"
    (node_dir / "docx").mkdir(parents=True)
    (node_dir / "docx" / "package.json").write_text("{}", encoding="utf-8")
    manifest = load_manifest(REAL_MANIFEST)
    tools = [manifest.get("python-pptx"), manifest.get("pypdf"), manifest.get("node:docx")]
    probe = FakeProbe(env, modules={"pptx": "site/pptx/__init__.py"}, node_dirs=[node_dir])

    found = detect(tools, env, probe)

    assert found.has("python-pptx")
    assert not found.has("pypdf")
    assert found.has("node:docx")


def test_groups_are_satisfied_only_when_whole(env: Env) -> None:
    manifest = load_manifest(REAL_MANIFEST)
    privacy = {t.cmd: "x" for t in manifest.in_groups(["privacy"])}
    assert satisfied(manifest, Detection(privacy), "group:privacy")
    assert not satisfied(manifest, Detection({"bw": "x"}), "group:privacy")
    assert expand(manifest, "group:privacy") == set(privacy)
    assert expand(manifest, "rg") == {"rg"}


def test_search_path_puts_machine_and_user_before_this_process(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", r"C:\some\venv\Scripts")
    parts = search_path(env).split(os.pathsep)
    assert str(env.home / ".local" / "bin") in parts
    assert parts[-1] == r"C:\some\venv\Scripts"


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        (
            lambda t: t.replace('about = "Searches."', 'about = "Searches."\ncolour = "red"'),
            "unknown",
        ),
        (lambda t: t.replace('winget = "BurntSushi.ripgrep.MSVC"\n', ""), "exactly one"),
        (lambda t: t.replace('group = "core"', 'group = "nope"'), "isn't declared"),
        (lambda t: t.replace('area = "Search"\n', ""), "go together"),
        (lambda t: t + t[t.index("[[tool]]") :], "twice"),
        (lambda t: t.replace('winget = "BurntSushi.ripgrep.MSVC"', 'pylib = "x"'), "go together"),
    ],
)
def test_manifest_mistakes_are_caught(
    tmp_path: Path, patch: Callable[[str], str], message: str
) -> None:
    with pytest.raises(ManifestError, match=message):
        load_manifest(write(tmp_path, patch(MINIMAL)))


def test_unknown_group_names_the_known_ones(tmp_path: Path) -> None:
    manifest = load_manifest(write(tmp_path, MINIMAL))
    with pytest.raises(ManifestError, match="known: core"):
        manifest.in_groups(["web"])


def test_select_takes_groups_and_single_tools_once() -> None:
    manifest = load_manifest(REAL_MANIFEST)
    picked = [t.cmd for t in manifest.select(["privacy", "bw", "rg"])]
    assert picked == ["rg", "bw", "autoruns"]
    with pytest.raises(ManifestError, match="neither a group"):
        manifest.select(["nope"])
