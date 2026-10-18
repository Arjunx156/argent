"""edith doctor."""

import argparse
from typing import Any

from edith.doctor import Context, Finding, diagnose
from edith.paths import Env
from edith.ui import Out

ORDER = {"fail": 0, "warn": 1, "info": 2, "pass": 3}


def register(sub: Any) -> None:
    parser = sub.add_parser("doctor", help="check every claim edith makes about this machine")
    parser.add_argument("--quiet", action="store_true", help="hide the checks that passed")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    findings = diagnose(Context(env))
    report(findings, out, quiet=args.quiet)
    return 1 if any(f.status == "fail" for f in findings) else 0


def report(findings: list[Finding], out: Out, quiet: bool = False) -> None:
    shown = [f for f in findings if not (quiet and f.status == "pass")]
    width = max((len(f.title) for f in shown), default=0)
    out.heading("doctor")
    for finding in sorted(shown, key=lambda f: ORDER.get(f.status, 9)):
        out.tag(finding.status, f"{finding.title:<{width}}  {finding.detail}")
        if finding.fix and finding.status != "pass":
            out.line(f"         {' ' * width}  {out.dim('fix: ' + finding.fix)}")
    counts = {s: sum(f.status == s for f in findings) for s in ORDER}
    out.line()
    summary = ", ".join(f"{n} {s}" for s, n in counts.items() if n)
    out.line(out.dim(summary))
