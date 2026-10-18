"""Install manifest tools: winget, uv tool, a digest-checked GitHub release, a Python or Node
library for the document skills, or a Docker image."""

import fnmatch
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argent.paths import Env
from argent.state import write_atomic
from argent.tools import Release, Tool

ALREADY_INSTALLED = -1978335189  # winget's 0x8A15002B: nothing newer to install
WINGET = [
    "--exact",
    "--silent",
    "--disable-interactivity",
    "--accept-source-agreements",
    "--accept-package-agreements",
]


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Step:
    """One command to run, and the exit codes that mean it worked."""

    argv: tuple[str, ...]
    ok_codes: tuple[int, ...] = (0,)


@dataclass(frozen=True)
class Places:
    """Where library installs land: the user site of the python skills run, and a node prefix."""

    python: str | None
    user_site: str | None
    node_prefix: Path

    @property
    def node_modules(self) -> Path:
        return self.node_prefix / "node_modules"


Run = Callable[[list[str]], int]
Fetch = Callable[[str], bytes]


def steps_for(tool: Tool, places: Places | None = None) -> list[Step]:
    if tool.winget:
        argv = ("winget", "install", "--id", tool.winget, *WINGET)
        return [Step(argv, (0, ALREADY_INSTALLED))]
    if tool.uv:
        extra = [arg for dep in tool.uv_with for arg in ("--with", dep)]
        steps = [Step(("uv", "tool", "install", "--quiet", *extra, tool.uv))]
        if tool.after:
            steps.append(Step(tool.after))
        return steps
    if tool.pylib:
        if not places or not places.python or not places.user_site:
            raise InstallError("no python on PATH to install into; install Python 3.12+ first")
        # into the user site of the python a new shell runs, through uv rather than pip
        target = ("--python", places.python, "--target", places.user_site)
        return [Step(("uv", "pip", "install", "--quiet", *target, tool.pylib))]
    if tool.nodelib:
        if not places:
            raise InstallError("no node prefix to install into")
        prefix = ("--prefix", str(places.node_prefix), "--no-audit", "--no-fund", "--silent")
        return [Step(("npm", "install", *prefix, tool.nodelib))]
    if tool.docker:
        return [Step(("docker", "build", "--quiet", "-t", tool.docker.image, tool.docker.build))]
    return []


def run_quietly(argv: list[str]) -> int:
    exe = shutil.which(argv[0]) or argv[0]
    try:
        return subprocess.run(
            [exe, *argv[1:]], capture_output=True, check=False, timeout=1800
        ).returncode
    except FileNotFoundError:
        raise InstallError(f"{argv[0]} isn't installed") from None


def install(
    tool: Tool,
    env: Env,
    places: Places | None = None,
    run: Run = run_quietly,
    fetch: Fetch | None = None,
) -> None:
    if tool.release:
        bin_dir = env.home / ".local" / "bin"
        install_release(tool.release, bin_dir / f"{tool.cmd}.exe", fetch or http_get)
        return
    for step in steps_for(tool, places):
        code = run(list(step.argv))
        if code not in step.ok_codes:
            raise InstallError(f"`{' '.join(step.argv[:4])}` exited {code}")
    if tool.nodelib and places:
        # node finds packages outside a project only through NODE_PATH
        ensure_user_list("NODE_PATH", places.node_modules)


def install_release(release: Release, dest: Path, fetch: Fetch) -> Path:
    meta = json.loads(fetch(f"https://api.github.com/repos/{release.repo}/releases/latest"))
    asset = next((a for a in meta["assets"] if fnmatch.fnmatch(a["name"], release.asset)), None)
    if asset is None:
        raise InstallError(f"{release.repo} {meta.get('tag_name')} has no {release.asset}")
    payload = fetch(asset["browser_download_url"])
    exe = verified_exe(payload, asset.get("digest"), release.exe)
    try:
        write_atomic(dest, exe)
    except PermissionError:
        raise InstallError(f"{dest.name} is in use; close it and run install again") from None
    return dest


def verified_exe(archive: bytes, digest: str | None, exe: str) -> bytes:
    """Only an archive whose sha256 matches the published digest gets unpacked."""
    if not digest or not digest.startswith("sha256:"):
        raise InstallError("the release publishes no sha256 digest, so it can't be verified")
    actual = hashlib.sha256(archive).hexdigest()
    if actual != digest.removeprefix("sha256:").lower():
        raise InstallError("the download doesn't match its published sha256; not installed")
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        member = next((n for n in zipped.namelist() if Path(n).name == exe), None)
        if member is None:
            raise InstallError(f"the archive has no {exe}")
        return zipped.read(member)


def http_get(url: str) -> bytes:
    """GitHub through gh when signed in (no rate limit), plain HTTPS otherwise."""
    if url.startswith("https://api.github.com/") and shutil.which("gh"):
        done = subprocess.run(
            ["gh", "api", url.removeprefix("https://api.github.com/")],
            capture_output=True,
            check=False,
        )
        if done.returncode == 0:
            return done.stdout
    request = urllib.request.Request(url, headers={"User-Agent": "argent"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def ensure_user_list(name: str, folder: Path) -> bool:
    """Add a folder to a ;-separated user variable (PATH, NODE_PATH) for new shells, and for
    this process too. True when it had to be added."""
    current = os.environ.get(name, "")
    if str(folder) not in current.split(os.pathsep):
        os.environ[name] = os.pathsep.join(p for p in (current, str(folder)) if p)
    if sys.platform != "win32":
        return False
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
        try:
            value, kind = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            value, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in str(value).split(";") if p]
        expanded = {os.path.normcase(os.path.expandvars(p).rstrip("\\")) for p in parts}
        if os.path.normcase(str(folder)) in expanded:
            return False
        winreg.SetValueEx(key, name, 0, kind, ";".join([*parts, str(folder)]))
    _broadcast_environment_change()
    return True


def _broadcast_environment_change() -> None:
    import ctypes

    user32: Any = ctypes.windll.user32  # pyright: ignore[reportAttributeAccessIssue]
    result = ctypes.c_ulong()
    # HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG: new terminals pick up the PATH
    user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(result))
