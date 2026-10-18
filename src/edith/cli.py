"""Command line entry point."""

import argparse
import sys
from collections.abc import Callable

from edith import __version__
from edith.commands import deploy_cmd, doctor_cmd, shelve_cmd, tools_cmd
from edith.commands.shelve_cmd import ShelfError
from edith.paths import Env, RepoNotFoundError
from edith.profile import ProfileError
from edith.render import TemplateError
from edith.snapshot import UnknownSnapshotError
from edith.tools import ManifestError
from edith.ui import Out

Runner = Callable[[argparse.Namespace, Env, Out], int]
EXPECTED = (
    ProfileError,
    ManifestError,
    RepoNotFoundError,
    TemplateError,
    UnknownSnapshotError,
    ShelfError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edith",
        description="Arjun's engineering environment: rebuild the machine, keep it honest.",
    )
    parser.add_argument("--version", action="version", version=f"edith {__version__}")
    sub = parser.add_subparsers(title="commands", metavar="<command>")
    for module in (doctor_cmd, deploy_cmd, tools_cmd, shelve_cmd):
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
        return run(args, Env.from_system(), out)
    except EXPECTED as err:
        out.tag("fail", str(err))
        return 2
    except KeyboardInterrupt:
        return 130
