"""argent ship."""

import argparse
from pathlib import Path
from typing import Any

from argent.paths import Env
from argent.ship import Outcome, gitleaks_scan, just_check, repo_root, ship
from argent.ui import Out


def register(sub: Any) -> None:
    parser = sub.add_parser("ship", help="scan for secrets, run just check, commit and push")
    parser.add_argument(
        "-m", "--message", action="append", required=True, help="commit message; repeat for a body"
    )
    parser.add_argument("--no-check", action="store_true", help="skip the project's just check")
    parser.add_argument("--no-push", action="store_true", help="commit, but don't push")
    parser.add_argument("-C", "--repo", type=Path, default=Path.cwd(), help="repository to ship")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, _env: Env, out: Out) -> int:
    repo = repo_root(args.repo)
    message = "\n\n".join(m.strip() for m in args.message)
    out.heading(f"ship  {out.dim(repo.name)}")
    check = no_check if args.no_check else just_check
    ship(repo, message, out, scan=gitleaks_scan, check=check, push=not args.no_push)
    return 0


def no_check(_repo: Path) -> Outcome | None:
    return None
