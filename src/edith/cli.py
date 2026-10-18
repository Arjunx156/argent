"""Command line entry point."""

import argparse

from edith import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edith",
        description="Arjun's engineering environment: rebuild the machine, keep it honest.",
    )
    parser.add_argument("--version", action="version", version=f"edith {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
