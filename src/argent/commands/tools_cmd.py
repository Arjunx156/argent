"""argent tools: what the manifest wants and what this machine has."""

import argparse
from typing import Any

from argent.paths import Env
from argent.tools import detect, load_manifest
from argent.ui import Out


def register(sub: Any) -> None:
    parser = sub.add_parser("tools", help="list manifest tools and whether each is installed")
    parser.add_argument("groups", nargs="*", help="groups to show (default: all)")
    parser.add_argument("--missing", action="store_true", help="only show what's missing")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    manifest = load_manifest(env.kit / "tools.toml")
    groups = args.groups or list(manifest.groups)
    tools = manifest.in_groups(groups)
    found = detect(tools, env)
    width = max(len(t.cmd) for t in tools)
    missing = 0
    for group in groups:
        members = [t for t in tools if t.group == group]
        if args.missing:
            members = [t for t in members if not found.has(t.cmd)]
        if not members:
            continue
        out.heading(f"{group}  {out.dim(manifest.groups[group])}")
        for tool in members:
            where = found.where(tool.cmd)
            if where:
                out.tag("ok", f"{tool.cmd:<{width}}  {out.dim(where)}")
            else:
                missing += 1
                out.tag("miss", f"{tool.cmd:<{width}}  {out.dim(tool.source)}")
    out.line()
    out.line(f"{len(tools) - missing} of {len(tools)} installed")
    if missing:
        out.line(out.dim("install what's missing with `argent install <group>`"))
    return 0
