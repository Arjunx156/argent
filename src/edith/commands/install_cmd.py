"""edith install."""

import argparse
from typing import Any

from edith.installer import InstallError, ensure_user_path, install
from edith.paths import Env
from edith.tools import detect, load_manifest
from edith.ui import Out


def register(sub: Any) -> None:
    parser = sub.add_parser("install", help="install what a tool group is missing")
    parser.add_argument("groups", nargs="*", default=["core"], help="groups (default: core)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be installed")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    manifest = load_manifest(env.kit / "tools.toml")
    tools = manifest.in_groups(args.groups)
    found = detect(tools, env)
    missing = [t for t in tools if not found.has(t.cmd)]

    out.heading(f"install  {out.dim(', '.join(args.groups))}")
    if not missing:
        out.line(out.dim(f"  all {len(tools)} already installed"))
        return 0
    width = max(len(t.cmd) for t in missing)
    for tool in missing:
        out.tag("get", f"{tool.cmd:<{width}}  {out.dim(tool.source)}")
    if args.dry_run:
        out.line()
        out.line(out.dim("dry run: nothing installed"))
        return 0

    local_bin = env.home / ".local" / "bin"
    if ensure_user_path(local_bin):
        out.tag("set", f"{local_bin} added to your user PATH")

    failed = 0
    for tool in missing:
        try:
            install(tool, env)
        except InstallError as err:
            failed += 1
            out.tag("fail", f"{tool.cmd}  {err}")
            continue
        if detect([tool], env).has(tool.cmd):
            out.tag("pass", tool.cmd)
        else:
            failed += 1
            out.tag("warn", f"{tool.cmd}  installed, but not found yet; open a new terminal")

    out.line()
    if failed:
        out.line(out.dim(f"{failed} need attention; `edith tools --missing` shows the rest"))
    out.line(out.dim("then `edith deploy`, so the standing orders learn what's new"))
    return 1 if failed else 0
