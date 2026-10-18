"""argent projects."""

import argparse
from typing import Any

from argent.paths import Env
from argent.profile import load_profile
from argent.projects import ago, survey
from argent.ui import Out


def register(sub: Any) -> None:
    parser = sub.add_parser("projects", help="every project under your roots, and what needs you")
    parser.add_argument("--attention", action="store_true", help="only projects that need you")
    parser.add_argument("--paths", action="store_true", help="plain paths, newest first, for fzf")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    profile = load_profile(env)
    projects = survey(profile.roots)
    if args.paths:
        for project in sorted(projects, key=lambda p: -(p.last_commit or 0)):
            out.line(str(project.path))
        return 0

    needy = [p for p in projects if p.problems]
    shown = needy if args.attention else projects
    out.heading(f"projects  {out.dim(f'{len(projects)} found, {len(needy)} need you')}")
    if not shown:
        out.line(out.dim("  nothing needs you"))
        return 0
    name_w = max(len(p.name) for p in shown)
    branch_w = max(len(p.branch) for p in shown)
    state_w = max(len(", ".join(p.problems) or "clean") for p in shown)
    for project in shown:
        state = ", ".join(project.problems) or "clean"
        row = f"{project.name:<{name_w}}  {project.branch:<{branch_w}}  {state:<{state_w}}"
        out.tag("warn" if project.problems else "ok", f"{row}  {out.dim(ago(project.last_commit))}")
    missing = [r for r in profile.roots if not r.is_dir()]
    for root in missing:
        out.tag("skip", f"{root.as_posix()}  {out.dim('root not found')}")
    return 0
