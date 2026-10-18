"""What this machine has: commands, Python modules, Node packages, Docker images.

Everything that asks the real machine lives here, behind Probe, so tests can swap in a fake.
"""

import json
import os
import subprocess
import sys
from functools import cached_property
from pathlib import Path

from argent.paths import Env

MODULE_CHECK = """
import importlib.util, json, sys
found = {}
for name in sys.argv[1:]:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        spec = None
    found[name] = (spec.origin or name) if spec else None
print(json.dumps(found))
"""


class Probe:
    """The real machine, asked lazily and at most once per question."""

    def __init__(self, env: Env) -> None:
        self.env = env

    @cached_property
    def path(self) -> str:
        return search_path(self.env)

    @cached_property
    def index(self) -> "PathIndex":
        return PathIndex(self.path)

    def which(self, cmd: str) -> str | None:
        return self.index.find(cmd)

    @cached_property
    def python(self) -> str | None:
        """The python a new shell runs, which is the one skills' scripts get."""
        return self.which("python")

    def python_modules(self, names: list[str]) -> dict[str, str]:
        """Module name to where it lives, for the ones that python can import."""
        if not self.python or not names:
            return {}
        # -E ignores PYTHON* variables; no -I or -s, because the user site is the point
        out = _output([self.python, "-E", "-c", MODULE_CHECK, *names], cwd=Path(self.python).parent)
        try:
            found: dict[str, str | None] = json.loads(out or "{}")
        except ValueError:
            return {}
        return {name: where for name, where in found.items() if where}

    @cached_property
    def user_site(self) -> str | None:
        if not self.python:
            return None
        code = "import site; print(site.getusersitepackages())"
        return _output([self.python, "-E", "-c", code], cwd=Path(self.python).parent) or None

    @cached_property
    def node_dirs(self) -> list[Path]:
        raw = [os.environ.get("NODE_PATH", ""), user_env("NODE_PATH") or ""]
        parts = [p for value in raw for p in value.split(os.pathsep) if p.strip()]
        return [Path(p) for p in dict.fromkeys(parts)]

    def docker_image(self, image: str) -> bool:
        docker = self.which("docker")
        if not docker:
            return False
        done = subprocess.run(
            [docker, "image", "inspect", image], capture_output=True, check=False, timeout=30
        )
        return done.returncode == 0


def search_path(env: Env) -> str:
    """PATH as a new shell builds it: machine, then user, so the right copy of a tool wins."""
    parts = _registry_path()
    parts += [
        str(env.home / ".local" / "bin"),
        str(env.localappdata / "Microsoft" / "WinGet" / "Links"),
    ]
    # this process's PATH last: a virtualenv here is not what a new terminal sees
    parts += os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join(dict.fromkeys(p for p in parts if p))


def _registry_path() -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg

    machine = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    keys = [(winreg.HKEY_LOCAL_MACHINE, machine), (winreg.HKEY_CURRENT_USER, "Environment")]
    found: list[str] = []
    for hive, sub in keys:
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        found += [os.path.expandvars(p) for p in str(value).split(";")]
    return found


def user_env(name: str) -> str | None:
    """A user environment variable as new shells will see it, not as this process has it."""
    if sys.platform != "win32":
        return os.environ.get(name)
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return os.path.expandvars(str(value))


class PathIndex:
    """Every file on PATH, listed once. shutil.which stats each folder for every suffix of
    every tool, thousands of calls for the manifest; this is one scandir per folder."""

    def __init__(self, path: str) -> None:
        self.names: dict[str, str] = {}
        for folder in path.split(os.pathsep):
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for entry in entries:
                self.names.setdefault(_fold(entry.name), entry.path)

    def find(self, cmd: str) -> str | None:
        if sys.platform != "win32":
            hit = self.names.get(cmd)
            return hit if hit and os.access(hit, os.X_OK) else None
        suffixes = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").lower().split(";")
        candidates = ("", *suffixes) if Path(cmd).suffix else suffixes
        return next(
            (self.names[k] for s in candidates if (k := _fold(cmd + s)) in self.names), None
        )


def _fold(name: str) -> str:
    return name.lower() if sys.platform == "win32" else name


def fresh_env() -> dict[str, str]:
    """This process's environment minus what a new shell wouldn't have. The store python
    injects PYTHONUSERBASE, and -E doesn't stop site.py reading it."""
    return {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith("PYTHON") and k.upper() != "VIRTUAL_ENV"
    }


def _output(argv: list[str], cwd: Path) -> str:
    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, cwd=cwd, env=fresh_env(), check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""
