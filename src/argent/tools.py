"""The tool manifest, and what of it this machine actually has."""

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from argent.paths import Env
from argent.probe import Probe


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Release:
    repo: str
    asset: str
    exe: str


@dataclass(frozen=True)
class Docker:
    image: str
    build: str


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
    pylib: str | None = None
    module: str | None = None
    nodelib: str | None = None
    docker: Docker | None = None
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
        if self.pylib:
            return f"uv pip {self.pylib} (user site)"
        if self.nodelib:
            return f"npm {self.nodelib}"
        if self.docker:
            return f"docker build {self.docker.image}"
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

    def select(self, names: Iterable[str]) -> list[Tool]:
        """Groups or single tools, in manifest order, each tool once."""
        wanted: set[str] = set()
        for name in names:
            if name in self.groups:
                wanted |= {t.cmd for t in self.in_groups([name])}
            elif any(t.cmd == name for t in self.tools):
                wanted.add(name)
            else:
                known = ", ".join(self.groups)
                raise ManifestError(
                    f"{name} is neither a group ({known}) nor a tool in the manifest"
                )
        return [t for t in self.tools if t.cmd in wanted]


@dataclass(frozen=True)
class Detection:
    found: dict[str, str] = field(default_factory=dict[str, str])

    def has(self, cmd: str) -> bool:
        return cmd in self.found

    def where(self, cmd: str) -> str | None:
        return self.found.get(cmd)


TOOL_KEYS = {f.name for f in Tool.__dataclass_fields__.values()}
SOURCES = ("winget", "uv", "release", "pylib", "nodelib", "docker")


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
    sources = [k for k in SOURCES if raw.get(k)]
    if len(sources) != 1:
        raise ManifestError(f"{cmd}: needs exactly one of {', '.join(SOURCES)}")
    if bool(raw.get("pylib")) != bool(raw.get("module")):
        raise ManifestError(f"{cmd}: pylib and module go together")

    release = raw.get("release")
    if release and not str(release.get("asset", "")).endswith(".zip"):
        raise ManifestError(f"{cmd}: release assets must be .zip archives")
    return Tool(
        cmd=cmd,
        group=raw["group"],
        about=raw["about"],
        winget=raw.get("winget"),
        uv=raw.get("uv"),
        uv_with=tuple(raw.get("uv_with", ())),
        release=Release(**release) if release else None,
        pylib=raw.get("pylib"),
        module=raw.get("module"),
        nodelib=raw.get("nodelib"),
        docker=Docker(**raw["docker"]) if raw.get("docker") else None,
        probes=tuple(raw.get("probes", ())),
        after=tuple(raw.get("after", ())),
        area=raw.get("area"),
        claim=raw.get("claim"),
    )


def satisfied(manifest: Manifest, found: Detection, name: str) -> bool:
    """A tool by name, or `group:<name>` for every tool in a group."""
    if name.startswith("group:"):
        return all(found.has(t.cmd) for t in manifest.in_groups([name.removeprefix("group:")]))
    return found.has(name)


def expand(manifest: Manifest, name: str) -> set[str]:
    if name.startswith("group:"):
        return {t.cmd for t in manifest.in_groups([name.removeprefix("group:")])}
    return {name}


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


def detect(tools: Iterable[Tool], env: Env, probe: Probe | None = None) -> Detection:
    probe = probe or Probe(env)
    tools = list(tools)
    modules = probe.python_modules([t.module for t in tools if t.pylib and t.module])
    found: dict[str, str] = {}
    for tool in tools:
        hit = _find(tool, env, probe, modules)
        if hit:
            found[tool.cmd] = hit
    return Detection(found)


def _find(tool: Tool, env: Env, probe: Probe, modules: dict[str, str]) -> str | None:
    if tool.pylib:
        return modules.get(tool.module or "")
    if tool.nodelib:
        package = (d / tool.nodelib for d in probe.node_dirs)
        return next((str(p) for p in package if (p / "package.json").is_file()), None)
    if tool.docker:
        image = tool.docker.image
        return f"docker image {image}" if probe.docker_image(image) else None
    hit = probe.which(tool.cmd)
    if hit:
        return hit
    probes = (probe_path(raw, env) for raw in tool.probes)
    return next((str(p) for p in probes if p.exists()), None)
