"""argent harden: privacy settings, each one recorded first so `argent restore` undoes it."""

import argparse
from collections.abc import Callable
from datetime import datetime
from typing import Any

from argent.paths import Env
from argent.privacy import (
    DEFENDER,
    DNS,
    DWORD,
    FIREWALL,
    QUAD9,
    Current,
    PrivacyError,
    Registry,
    Shell,
    SystemStep,
    Value,
    WinRegistry,
    capture,
    encryption_status,
    is_admin,
    load_settings,
    pending,
    powershell,
)
from argent.snapshot import Snapshot
from argent.ui import Out


def register(sub: Any) -> None:
    parser = sub.add_parser(
        "harden", help="privacy settings, recorded first so restore undoes them"
    )
    parser.add_argument(
        "--machine",
        action="store_true",
        help="system-wide policies, firewall and Defender (needs an elevated terminal)",
    )
    parser.add_argument("--dns", action="store_true", help="with --machine: Quad9 over HTTPS")
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    if args.dns and not args.machine:
        raise PrivacyError("--dns changes the whole machine, so it goes with --machine")
    return harden(
        env,
        out,
        machine=args.machine,
        dns=args.dns,
        dry_run=args.dry_run,
        registry=WinRegistry(),
        shell=powershell,
        admin=is_admin(),
        clock=datetime.now,
    )


def harden(
    env: Env,
    out: Out,
    *,
    machine: bool,
    dns: bool,
    dry_run: bool,
    registry: Registry,
    shell: Shell,
    admin: bool,
    clock: Callable[[], datetime],
) -> int:
    scope = "machine" if machine else "user"
    if machine and not admin:
        raise PrivacyError(
            "--machine needs an elevated terminal: open Windows Terminal with Run as "
            "administrator, then run argent harden --machine again"
        )
    values = [v for v in load_settings(env.kit / "privacy.toml") if v.scope == scope]
    todo = pending(values, registry)
    steps = [FIREWALL, DEFENDER, *([DNS] if dns else [])] if machine else []
    states = {step.name: capture(step, shell) for step in steps}
    if dns and uses_warp(states["dns"]):
        raise PrivacyError(
            "Cloudflare WARP is handling DNS here (127.0.2.2), and it's already encrypted while "
            "WARP is connected. --dns would fight it, so leave --dns off, or quit WARP first"
        )
    changing = [step for step in steps if not applied(step.name, states[step.name])]

    changes = len(todo) + len(changing)
    out.heading(f"harden {scope}  {out.dim(f'{changes} to change')}")
    show_plan(out, values, todo, steps, changing)
    if dry_run or not changes:
        out.line()
        out.line(out.dim("dry run: nothing changed" if dry_run else "already hardened"))
        return 0

    snapshot = Snapshot.create(env, f"harden {scope}", clock)
    for value, current in todo:
        snapshot.keep_registry(value.scope, value.key, value.name, current)
    for step in changing:
        snapshot.keep_system(step.name, states[step.name])
    snapshot.save()

    for value, _ in todo:
        registry.write(value.scope, value.key, value.name, value.data, DWORD)
    failed = 0
    for step in changing:
        code, said = shell(step.apply)
        if code != 0:
            failed += 1
            out.tag("fail", f"{step.name}  {said.splitlines()[0] if said else f'exit {code}'}")

    out.line()
    if machine:
        report_encryption(out, shell)
    out.line(
        f"snapshot {snapshot.path.name}  {out.dim(f'undo: argent restore {snapshot.path.name}')}"
    )
    if not machine:
        out.line(out.dim("sign out and back in for the Explorer and Start changes"))
    return 1 if failed else 0


def show_plan(
    out: Out,
    values: list[Value],
    todo: list[tuple[Value, Current]],
    steps: list[SystemStep],
    changing: list[SystemStep],
) -> None:
    """One line per reason, not per registry value: that's what a person decides on."""
    waiting = {(v.key, v.name) for v, _ in todo}
    reasons: dict[str, bool] = {}
    for value in values:
        reasons[value.why] = reasons.get(value.why, False) or (value.key, value.name) in waiting
    for why, change in reasons.items():
        out.tag("set" if change else "ok", why)
    for step in steps:
        out.tag("set" if step in changing else "ok", step.why)


def applied(step: str, state: Any) -> bool:
    items: list[dict[str, Any]] = state if isinstance(state, list) else [state] if state else []
    if not items:
        return False
    if step == "firewall":
        return all(p.get("Enabled") == "True" and p.get("Inbound") == "Block" for p in items)
    if step == "defender":
        return all(p.get("Pua") == 1 and p.get("Network") == 1 for p in items)
    if step == "dns":
        quad9 = ",".join(QUAD9)
        return all(str(p.get("Static", "")).replace(" ", ",") == quad9 for p in items)
    return False


def uses_warp(state: Any) -> bool:
    """WARP points adapters at its own local resolver, 127.0.2.2 and 127.0.2.3."""
    items: list[dict[str, Any]] = state if isinstance(state, list) else [state] if state else []
    return any("127.0.2." in str(item.get("Static", "")) for item in items)


def report_encryption(out: Out, shell: Shell) -> None:
    status = encryption_status(shell)
    if status == "on":
        out.tag("pass", "C: is encrypted")
    elif status == "off":
        out.tag(
            "warn", "C: isn't encrypted; turn on Settings > Privacy & security > Device encryption"
        )
