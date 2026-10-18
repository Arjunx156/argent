import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from argent.installer import (
    ALREADY_INSTALLED,
    InstallError,
    Places,
    install,
    install_release,
    steps_for,
    verified_exe,
)
from argent.paths import Env
from argent.tools import Release, load_manifest

KIT = Path(__file__).resolve().parents[1] / "kit"
MANIFEST = load_manifest(KIT / "tools.toml")
PLACES = Places("C:/Py/python.exe", "C:/Users/t/site-packages", Path("C:/Users/t/.argent/node"))


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


def test_no_tool_ever_installs_through_pip_itself() -> None:
    for tool in MANIFEST.tools:
        for step in steps_for(tool, PLACES):
            assert step.argv[0] not in {"pip", "pip3", "python", "py"}, tool.cmd
            assert "-m pip" not in " ".join(step.argv), tool.cmd


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

    dest = install_release(release, tmp_path / "bin" / "tectonic.exe", pages.__getitem__)

    assert dest.read_bytes() == b"MZ binary"


def test_python_libraries_go_into_the_user_site_through_uv() -> None:
    [step] = steps_for(MANIFEST.get("python-pptx"), PLACES)
    assert step.argv[:3] == ("uv", "pip", "install")
    assert step.argv[4:6] == ("--python", "C:/Py/python.exe")
    assert step.argv[6:8] == ("--target", "C:/Users/t/site-packages")
    assert step.argv[-1] == "python-pptx"


def test_python_libraries_need_a_python() -> None:
    with pytest.raises(InstallError, match="no python"):
        steps_for(MANIFEST.get("pypdf"), Places(None, None, Path("n")))


def test_node_libraries_install_into_the_argent_prefix_and_node_path(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    remembered: list[tuple[str, Path]] = []
    # never let a test write the real user environment
    monkeypatch.setattr(
        "argent.installer.ensure_user_list", lambda name, folder: remembered.append((name, folder))
    )
    ran: list[list[str]] = []
    places = Places(None, None, env.state / "node")

    install(MANIFEST.get("node:pptxgenjs"), env, places, run=lambda argv: ran.append(argv) or 0)

    assert ran[0][:4] == ["npm", "install", "--prefix", str(env.state / "node")]
    assert ran[0][-1] == "pptxgenjs"
    assert remembered == [("NODE_PATH", env.state / "node" / "node_modules")]


def test_uv_tools_can_pin_a_python() -> None:
    [step] = steps_for(MANIFEST.get("theHarvester"))
    assert step.argv[:5] == ("uv", "tool", "install", "--quiet", "--python")
    assert step.argv[5] == "3.14"
    assert step.argv[-1].startswith("git+https://github.com/laramies/theHarvester")


def test_releases_install_under_the_tools_own_name(env: Env) -> None:
    archive = zipped("httpx.exe", b"MZ httpx")
    meta = {
        "tag_name": "v1",
        "assets": [
            {
                "name": "httpx_1_windows_amd64.zip",
                "browser_download_url": "u/zip",
                "digest": digest(archive),
            }
        ],
    }
    pages = {
        "https://api.github.com/repos/projectdiscovery/httpx/releases/latest": json.dumps(
            meta
        ).encode(),
        "u/zip": archive,
    }
    install(MANIFEST.get("httpx-toolkit"), env, fetch=pages.__getitem__)
    assert (env.home / ".local" / "bin" / "httpx-toolkit.exe").read_bytes() == b"MZ httpx"


def test_docker_images_explain_a_stopped_docker(env: Env) -> None:
    def docker_down(argv: list[str]) -> int:
        return 1 if argv[:2] == ["docker", "info"] else 0

    with pytest.raises(InstallError, match="Docker Desktop isn't running"):
        install(MANIFEST.get("spiderfoot"), env, run=docker_down)
