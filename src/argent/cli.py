"""Command line entry point."""

import argparse
import sys
from collections.abc import Callable

from argent import __version__
from argent.commands import (
    deploy_cmd,
    doctor_cmd,
    install_cmd,
    projects_cmd,
    shelve_cmd,
    ship_cmd,
    tools_cmd,
)
from argent.commands.shelve_cmd import ShelfError
from argent.installer import InstallError
from argent.paths import Env, RepoNotFoundError, adopt_legacy_state
from argent.profile import ProfileError
from argent.render import TemplateError
from argent.ship import ShipError
from argent.snapshot import UnknownSnapshotError
from argent.tools import ManifestError
from argent.ui import Out

Runner = Callable[[argparse.Namespace, Env, Out], int]
EXPECTED = (
    ProfileError,
    ManifestError,
    RepoNotFoundError,
    TemplateError,
    UnknownSnapshotError,
    ShelfError,
    ShipError,
    InstallError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argent",
        description="Arjun's engineering environment: rebuild the machine, keep it honest.",
    )
    parser.add_argument("--version", action="version", version=f"argent {__version__}")
    sub = parser.add_subparsers(title="commands", metavar="<command>")
    modules = (doctor_cmd, deploy_cmd, ship_cmd, projects_cmd, tools_cmd, install_cmd, shelve_cmd)
    for module in modules:
        module.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run: Runner | None = getattr(args, "run", None)
    if run is None:
        parser.print_help()
        return 0
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]
    out = Out()
    try:
        env = Env.from_system()
        if adopt_legacy_state(env):
            out.tag("info", f"moved {env.legacy_state} to {env.state}")
        return run(args, env, out)
    except EXPECTED as err:
        out.tag("fail", str(err))
        return 2
    except KeyboardInterrupt:
        return 130
