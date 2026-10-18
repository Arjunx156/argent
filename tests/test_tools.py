from collections.abc import Callable
from pathlib import Path

import pytest

from argent.paths import Env
from argent.tools import ManifestError, detect, load_manifest

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


def test_detect_uses_which_then_probes(env: Env, tmp_path: Path) -> None:
    font = env.localappdata / "Microsoft" / "Windows" / "Fonts"
    font.mkdir(parents=True)
    (font / "JetBrainsMonoNerdFont-Regular.ttf").write_bytes(b"")
    manifest = load_manifest(REAL_MANIFEST)
    tools = [manifest.get("rg"), manifest.get("tectonic"), manifest.get("JetBrainsMono Nerd Font")]

    found = detect(tools, env, which=lambda cmd, _path: "/bin/rg" if cmd == "rg" else None)

    assert found.where("rg") == "/bin/rg"
    assert not found.has("tectonic")
    assert found.has("JetBrainsMono Nerd Font")


def test_search_path_includes_local_bin(env: Env) -> None:
    seen: list[str] = []
    detect(load_manifest(REAL_MANIFEST).tools[:1], env, which=lambda _c, p: seen.append(p))
    assert str(env.home / ".local" / "bin") in seen[0]


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
