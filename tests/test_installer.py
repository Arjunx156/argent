import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from edith.installer import (
    ALREADY_INSTALLED,
    InstallError,
    install,
    install_release,
    steps_for,
    verified_exe,
)
from edith.paths import Env
from edith.tools import Release, load_manifest

KIT = Path(__file__).resolve().parents[1] / "kit"
MANIFEST = load_manifest(KIT / "tools.toml")


def zipped(name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(f"bundle/{name}", content)
    return buf.getvalue()


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_winget_tools_install_silently_and_accept_already_installed() -> None:
    [step] = steps_for(MANIFEST.get("starship"))
    assert step.argv[:4] == ("winget", "install", "--id", "Starship.Starship")
    assert "--silent" in step.argv
    assert ALREADY_INSTALLED in step.ok_codes


def test_uv_tools_carry_extras_and_follow_up_steps() -> None:
    fonttools = steps_for(MANIFEST.get("pyftsubset"))
    assert fonttools[0].argv == (
        "uv",
        "tool",
        "install",
        "--quiet",
        "--with",
        "brotli",
        "fonttools",
    )
    playwright = steps_for(MANIFEST.get("playwright"))
    assert playwright[-1].argv == ("playwright", "install", "chromium")


def test_no_tool_ever_installs_through_pip() -> None:
    for tool in MANIFEST.tools:
        for step in steps_for(tool):
            assert "pip" not in step.argv


def test_a_failing_step_names_the_command(env: Env) -> None:
    with pytest.raises(InstallError, match="exited 1"):
        install(MANIFEST.get("ruff"), env, run=lambda _argv: 1)


def test_verified_exe_unpacks_only_a_matching_archive() -> None:
    archive = zipped("tectonic.exe", b"MZ binary")
    assert verified_exe(archive, digest(archive), "tectonic.exe") == b"MZ binary"
    with pytest.raises(InstallError, match="doesn't match"):
        verified_exe(archive, digest(b"something else"), "tectonic.exe")
    with pytest.raises(InstallError, match="no sha256"):
        verified_exe(archive, None, "tectonic.exe")


def test_release_install_end_to_end_without_the_network(tmp_path: Path) -> None:
    archive = zipped("tectonic.exe", b"MZ binary")
    meta = {
        "tag_name": "v0.15",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "u/notes"},
            {
                "name": "tectonic-0.15-x86_64-pc-windows-msvc.zip",
                "browser_download_url": "u/zip",
                "digest": digest(archive),
            },
        ],
    }
    pages = {
        "https://api.github.com/repos/t/t/releases/latest": json.dumps(meta).encode(),
        "u/zip": archive,
    }
    release = Release("t/t", "*x86_64-pc-windows-msvc.zip", "tectonic.exe")

    dest = install_release(release, tmp_path / "bin", pages.__getitem__)

    assert dest.read_bytes() == b"MZ binary"
