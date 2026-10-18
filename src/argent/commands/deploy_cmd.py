"""edith deploy, diff and restore."""

import argparse
import difflib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from edith.deploy import Action, apply, plan
from edith.kit import Kit, build_kit, pretty
from edith.paths import Env
from edith.profile import load_profile
from edith.snapshot import list_snapshots, restore
from edith.state import State
from edith.tools import Detection, detect, load_manifest
from edith.ui import DIM, MINT, RED, Out

ORDER = {"skip": 0, "drift": 1, "stray": 1, "remove": 2, "adopt": 3, "update": 4, "new": 5}


def register(sub: Any) -> None:
    deploy = sub.add_parser("deploy", help="put the kit in place, snapshotting first")
    deploy.add_argument("--dry-run", action="store_true", help="show the plan, write nothing")
    deploy.add_argument(
        "--force", action="store_true", help="also overwrite files edited since edith wrote them"
    )
    deploy.set_defaults(run=run_deploy)

    diff = sub.add_parser("diff", help="show what deploy would change, line by line")
    diff.add_argument("filter", nargs="?", default="", help="only paths containing this text")
    diff.set_defaults(run=run_diff)

    undo = sub.add_parser("restore", help="list snapshots, or put one back")
    undo.add_argument("name", nargs="?", help="snapshot to restore (default: list them)")
    undo.set_defaults(run=run_restore)


@dataclass(frozen=True)
class Planned:
    kit: Kit
    found: Detection
    state: State
    actions: list[Action]


def make_plan(env: Env) -> Planned:
    profile = load_profile(env)
    manifest = load_manifest(env.kit / "tools.toml")
    found = detect(manifest.tools, env)
    kit = build_kit(env, profile, manifest, found)
    state = State.load(env)
    return Planned(kit, found, state, plan(kit.targets, state, mirror=kit.mirror))


def run_deploy(args: argparse.Namespace, env: Env, out: Out) -> int:
    planned = make_plan(env)
    actions = planned.actions
    changes = [a for a in actions if a.kind != "ok"]
    in_place = len(actions) - len(changes)

    out.heading(f"deploy  {out.dim(f'{len(changes)} to change, {in_place} in place')}")
    for kind, label, reason, count in summarize(changes, planned.kit.mirror, env):
        files = out.dim(f" ({count} files)") if count > 1 else ""
        out.tag(kind, f"{label}{files}{'  ' + out.dim(reason) if reason else ''}")

    if args.dry_run:
        out.line()
        out.line(out.dim("dry run: nothing written. `edith diff` shows the lines."))
        return 0

    state = planned.state
    tools = sorted(planned.found.found)
    snapshot = apply(actions, env, state, clock=datetime.now, force=args.force)
    if state.tools != tools:
        state.tools = tools
        state.save()

    out.line()
    if snapshot:
        out.line(f"snapshot {snapshot.name}  {out.dim(f'undo: edith restore {snapshot.name}')}")
    else:
        out.line(out.dim("everything already in place"))
    drifted = [a for a in actions if a.kind in ("drift", "stray")]
    if drifted and not args.force:
        out.tag("warn", f"{len(drifted)} edited by hand and left alone")
        out.line(out.dim("`edith diff` shows them; `edith deploy --force` overwrites them."))
        return 1
    return 0


def summarize(
    actions: list[Action], mirror: list[Path], env: Env
) -> list[tuple[str, str, str, int]]:
    """One row per file, except files inside a mirrored folder, which share one row per kind."""
    rows: dict[tuple[str, str], list[Action]] = {}
    for action in actions:
        folder = next((m for m in mirror if action.dest.is_relative_to(m)), None)
        label = f"{pretty(env, folder)}/" if folder else action.label
        rows.setdefault((action.kind, label), []).append(action)
    result: list[tuple[str, str, str, int]] = []
    for (kind, label), group in sorted(
        rows.items(), key=lambda r: (ORDER.get(r[0][0], 9), r[0][1])
    ):
        reasons = {a.reason for a in group}
        result.append((kind, label, reasons.pop() if len(reasons) == 1 else "", len(group)))
    return result


def run_diff(args: argparse.Namespace, env: Env, out: Out) -> int:
    planned = make_plan(env)
    shown = 0
    for action in planned.actions:
        if action.kind == "ok" or args.filter.lower() not in action.label.lower():
            continue
        shown += 1
        out.heading(f"{action.kind}  {action.label}")
        for line in diff_lines(action):
            colour = MINT if line.startswith("+") else RED if line.startswith("-") else DIM
            out.line(out.paint(line, colour) if line[:1] in "+-@" else line)
    if not shown:
        out.line(out.dim("no differences"))
    return 0


def diff_lines(action: Action) -> list[str]:
    before, after = action.current or b"", action.desired or b""
    if action.kind == "skip":
        return [action.reason]
    if b"\0" in before + after:
        return [f"binary content differs ({len(before)} -> {len(after)} bytes)"]
    old = before.decode("utf-8", "replace").splitlines()
    new = after.decode("utf-8", "replace").splitlines()
    return list(difflib.unified_diff(old, new, "on disk", "from the kit", lineterm=""))


def run_restore(args: argparse.Namespace, env: Env, out: Out) -> int:
    if not args.name:
        snapshots = list_snapshots(env)
        if not snapshots:
            out.line(out.dim("no snapshots yet; edith takes one before every deploy"))
            return 0
        out.heading("snapshots")
        for snap in snapshots:
            out.tag("info", f"{snap.name}  {out.dim(f'{snap.reason}, {snap.count} files')}")
        out.line()
        out.line(out.dim("put one back with `edith restore <name>`"))
        return 0
    touched = restore(env, args.name, clock=datetime.now)
    out.heading(f"restored {args.name}")
    for path in touched:
        out.tag("set", pretty(env, path))
    out.line()
    out.line(out.dim("restoring took its own snapshot, so this can be undone too"))
    return 0
