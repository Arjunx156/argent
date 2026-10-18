"""Builds for files edith shares with the user: JSON settings and managed shell blocks.

Each function takes the file's current bytes and returns the bytes it should hold. When
nothing edith owns has changed, the original bytes come back untouched, so a file with
odd formatting isn't rewritten on every deploy.
"""

import copy
import json
from typing import Any

from edith.deploy import SkipTargetError

CHIME_MARK = "Media.SoundPlayer"
CHIMES = {"Stop": "Windows Notify Calendar", "Notification": "Windows Notify Messaging"}


def load_json(current: bytes | None, label: str) -> dict[str, Any]:
    if current is None or not current.strip():
        return {}
    try:
        data = json.loads(current.decode("utf-8-sig"))
    except ValueError:
        raise SkipTargetError(f"{label} isn't plain JSON (comments?); merge it by hand") from None
    if not isinstance(data, dict):
        raise SkipTargetError(f"{label} should hold a JSON object")
    return data  # pyright: ignore[reportUnknownVariableType]


def dump_json(
    current: bytes | None, before: dict[str, Any], after: dict[str, Any], indent: int
) -> bytes:
    if current is not None and before == after:
        return current
    return (json.dumps(after, indent=indent, ensure_ascii=False) + "\n").encode("utf-8")


def claude_settings(current: bytes | None, statusline: str, chimes: bool) -> bytes:
    before = load_json(current, "Claude settings.json")
    after = copy.deepcopy(before)
    # quoted: the home folder has a space, and an unquoted path splits at it
    after["statusLine"] = {"type": "command", "command": f'python -I "{statusline}"', "padding": 0}
    after["attribution"] = {"commit": "", "pr": "", "sessionUrl": False}
    after.setdefault("env", {})["DO_NOT_TRACK"] = "1"

    hooks: dict[str, Any] = after.setdefault("hooks", {})
    for event, sound in CHIMES.items():
        kept = [g for g in hooks.get(event, []) if CHIME_MARK not in json.dumps(g)]
        if chimes:
            play = f"(New-Object Media.SoundPlayer 'C:/Windows/Media/{sound}.wav').PlaySync()"
            hook = {"type": "command", "command": play, "shell": "powershell", "async": True}
            kept.append({"hooks": [hook]})
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        after.pop("hooks")
    return dump_json(current, before, after, indent=2)


def terminal_settings(current: bytes | None, theme: dict[str, Any]) -> bytes:
    before = load_json(current, "Windows Terminal settings.json")
    after = copy.deepcopy(before)
    scheme = theme["scheme"]
    retired = {scheme["name"], *theme.get("supersedes", [])}

    after["schemes"] = [s for s in after.get("schemes", []) if s.get("name") not in retired]
    after["schemes"].append(scheme)

    profiles = after.setdefault("profiles", {})
    if isinstance(profiles, list):
        raise SkipTargetError("Windows Terminal uses the old profiles list; merge by hand")
    profiles.setdefault("defaults", {}).update(theme["defaults"])
    # a profile still pointing at a retired scheme would make the terminal complain
    for profile in profiles.get("list", []):
        if profile.get("colorScheme") in retired:
            profile["colorScheme"] = scheme["name"]

    source = theme.get("defaultProfileSource")
    pwsh = [p for p in profiles.get("list", []) if p.get("source") == source and "guid" in p]
    if pwsh:
        after["defaultProfile"] = pwsh[0]["guid"]
    return dump_json(current, before, after, indent=4)


def editor_settings(current: bytes | None, wanted: dict[str, Any]) -> bytes:
    before = load_json(current, "editor settings.json")
    after = {**before, **wanted}
    return dump_json(current, before, after, indent=4)


def managed_block(
    current: bytes | None, body: str, name: str = "edith", supersedes: tuple[str, ...] = ()
) -> bytes:
    """Own one marked block in a shared file; retire blocks from tools edith replaces."""
    raw = current or b""
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    newline = "\n" if raw and b"\r\n" not in raw else "\r\n"

    kept: list[str] = []
    insert_at: int | None = None
    inside: str | None = None
    for line in text.splitlines():
        marker = line.strip()
        if inside:
            if marker == f"# <<< {inside} <<<":
                inside = None
            continue
        opened = next((n for n in (name, *supersedes) if marker == f"# >>> {n} >>>"), None)
        if opened:
            inside = opened
            insert_at = len(kept) if insert_at is None else insert_at
            continue
        kept.append(line)
    if inside:
        raise SkipTargetError(f"'# >>> {inside} >>>' is never closed; fix the file by hand")

    block = [f"# >>> {name} >>>", *body.strip("\r\n").splitlines(), f"# <<< {name} <<<"]
    if insert_at is None:
        while kept and not kept[-1].strip():
            kept.pop()
        insert_at = len(kept)
        if kept:
            block.insert(0, "")
    kept[insert_at:insert_at] = block

    result = (newline.join(kept) + newline).encode("utf-8")
    return (b"\xef\xbb\xbf" if bom else b"") + result
