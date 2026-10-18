"""The tool manifest, and what of it this machine actually has."""

import os
import sys
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edith.paths import Env

Which = Callable[[str, str], str | None]


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Release:
    repo: str
    asset: str
    exe: str


@dataclass(frozen=True)
class Area:
    name: str
    note: str | None = None


@dataclass(frozen=True)
class Tool:
    cmd: str
    group: str
    about: str
    winget: str | None = None
    uv: str | None = None
    uv_with: tuple[str, ...] = ()
    release: Release | None = None
    probes: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    area: str | None = None
    claim: str | None = None

    @property
    def source(self) -> str:
        if self.winget:
            return f"winget {self.winget}"
        if self.uv:
            return f"uv tool {self.uv}"
        if self.release:
            return f"release {self.release.repo}"
        return "manual"


@dataclass(frozen=True)
class Manifest:
    groups: dict[str, str]
    areas: tuple[Area, ...]
    tools: tuple[Tool, ...]

    def get(self, cmd: str) -> Tool:
        for tool in self.tools:
            if tool.cmd == cmd:
                return tool
        raise KeyError(cmd)

    def in_groups(self, groups: Iterable[str]) -> list[Tool]:
        wanted = list(groups)
        unknown = [g for g in wanted if g not in self.groups]
        if unknown:
            known = ", ".join(self.groups)
            raise ManifestError(f"no such group: {', '.join(unknown)} (known: {known})")
        return [t for t in self.tools if t.group in wanted]


@dataclass(frozen=True)
class Detection:
    found: dict[str, str] = field(default_factory=dict[str, str])

    def has(self, cmd: str) -> bool:
        return cmd in self.found

    def where(self, cmd: str) -> str | None:
        return self.found.get(cmd)


TOOL_KEYS = {f.name for f in Tool.__dataclass_fields__.values()}


def load_manifest(path: Path) -> Manifest:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(f"{path} is missing") from None
    except tomllib.TOMLDecodeError as err:
        raise ManifestError(f"{path} is not valid TOML: {err}") from None

    groups = data.get("groups", {})
    areas = tuple(Area(a["name"], a.get("note")) for a in data.get("area", []))
    area_names = {a.name for a in areas}
    tools = tuple(_tool(raw, groups, area_names) for raw in data.get("tool", []))

    seen: set[str] = set()
    for tool in tools:
        if tool.cmd in seen:
            raise ManifestError(f"{tool.cmd} is listed twice")
        seen.add(tool.cmd)
    return Manifest(groups=groups, areas=areas, tools=tools)


def _tool(raw: dict[str, Any], groups: dict[str, str], areas: set[str]) -> Tool:
    cmd = raw.get("cmd", "?")
    extra = set(raw) - TOOL_KEYS
    if extra:
        raise ManifestError(f"{cmd}: unknown keys {sorted(extra)}")
    if raw.get("group") not in groups:
        raise ManifestError(f"{cmd}: group {raw.get('group')!r} isn't declared in [groups]")
    if not raw.get("about"):
        raise ManifestError(f"{cmd}: needs an about line")
    if bool(raw.get("claim")) != bool(raw.get("area")):
        raise ManifestError(f"{cmd}: claim and area go together")
    if raw.get("area") and raw["area"] not in areas:
        raise ManifestError(f"{cmd}: area {raw['area']!r} isn't declared")
    sources = [k for k in ("winget", "uv", "release") if raw.get(k)]
    if len(sources) != 1:
        raise ManifestError(f"{cmd}: needs exactly one of winget, uv or release")

    release = raw.get("release")
    return Tool(
        cmd=cmd,
        group=raw["group"],
        about=raw["about"],
        winget=raw.get("winget"),
        uv=raw.get("uv"),
        uv_with=tuple(raw.get("uv_with", ())),
        release=Release(**release) if release else None,
        probes=tuple(raw.get("probes", ())),
        after=tuple(raw.get("after", ())),
        area=raw.get("area"),
        claim=raw.get("claim"),
    )


def search_path(env: Env) -> str:
    """PATH as a fresh shell would see it, so tools installed a minute ago count."""
    parts = os.environ.get("PATH", "").split(os.pathsep)
    parts += _registry_path()
    parts += [
        str(env.home / ".local" / "bin"),
        str(env.localappdata / "Microsoft" / "WinGet" / "Links"),
    ]
    unique = dict.fromkeys(p for p in parts if p)
    return os.pathsep.join(unique)


def _registry_path() -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg

    keys = [
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    found: list[str] = []
    for hive, sub in keys:
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        found += [os.path.expandvars(p) for p in str(value).split(";")]
    return found


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

    def find(self, cmd: str, _path: str = "") -> str | None:
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


def probe_path(raw: str, env: Env) -> Path:
    return Path(
        raw.format(
            home=env.home,
            appdata=env.appdata,
            localappdata=env.localappdata,
            programfiles=env.programfiles,
            windir=env.windir,
        )
    )


def detect(tools: Iterable[Tool], env: Env, which: Which | None = None) -> Detection:
    path = search_path(env)
    if which is None:
        which = PathIndex(path).find
    found: dict[str, str] = {}
    for tool in tools:
        hit = which(tool.cmd, path)
        if not hit:
            probes = (probe_path(raw, env) for raw in tool.probes)
            hit = next((str(p) for p in probes if p.exists()), None)
        if hit:
            found[tool.cmd] = hit
    return Detection(found)
