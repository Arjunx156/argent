import json

import pytest

from argent.deploy import SkipTargetError
from argent.merge import claude_settings, editor_settings, managed_block, terminal_settings

STATUSLINE = "C:/Users/A B/.claude/statusline.py"
TADASHI_SETTINGS = {
    "model": "opus",
    "statusLine": {"type": "command", "command": "python -I C:/Users/A B/.claude/statusline.py"},
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "sp-session-start"}]}]},
}


def as_bytes(data: object, indent: int = 2) -> bytes:
    return (json.dumps(data, indent=indent) + "\n").encode()


def test_claude_settings_quote_the_statusline_and_keep_the_users_keys() -> None:
    merged = json.loads(claude_settings(as_bytes(TADASHI_SETTINGS), STATUSLINE, chimes=True))
    assert merged["statusLine"]["command"] == f'python -I "{STATUSLINE}"'
    assert merged["model"] == "opus"
    assert merged["hooks"]["SessionStart"] == TADASHI_SETTINGS["hooks"]["SessionStart"]
    assert merged["attribution"]["commit"] == ""
    assert len(merged["hooks"]["Stop"]) == 1


def test_claude_settings_are_idempotent_byte_for_byte() -> None:
    once = claude_settings(as_bytes(TADASHI_SETTINGS), STATUSLINE, chimes=True)
    assert claude_settings(once, STATUSLINE, chimes=True) is once


def test_turning_chimes_off_removes_only_ours() -> None:
    mine = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "notify-me"}]}]}}
    with_chimes = claude_settings(as_bytes(mine), STATUSLINE, chimes=True)
    without = json.loads(claude_settings(with_chimes, STATUSLINE, chimes=False))
    assert without["hooks"]["Stop"] == mine["hooks"]["Stop"]
    assert "Notification" not in without["hooks"]


def test_settings_with_comments_are_skipped_not_mangled() -> None:
    with pytest.raises(SkipTargetError, match="comments"):
        claude_settings(b'{ // mine\n "a": 1 }', STATUSLINE, chimes=False)


THEME = {
    "scheme": {"name": "Argent", "background": "#07090D"},
    "supersedes": ["Tadashi Neon"],
    "defaults": {"colorScheme": "Argent"},
    "defaultProfileSource": "Windows.Terminal.PowershellCore",
}


def terminal(with_pwsh: bool) -> dict[str, object]:
    profiles = [{"guid": "{ps5}", "name": "Windows PowerShell", "colorScheme": "Tadashi Neon"}]
    if with_pwsh:
        profiles.append({"guid": "{ps7}", "source": "Windows.Terminal.PowershellCore"})
    return {
        "defaultProfile": "{ps5}",
        "profiles": {"defaults": {"colorScheme": "Tadashi Neon"}, "list": profiles},
        "schemes": [{"name": "Tadashi Neon"}, {"name": "Mine"}],
    }


def test_terminal_retires_tadashi_and_repoints_profiles() -> None:
    merged = json.loads(terminal_settings(as_bytes(terminal(True), 4), THEME))
    assert [s["name"] for s in merged["schemes"]] == ["Mine", "Argent"]
    assert merged["profiles"]["defaults"]["colorScheme"] == "Argent"
    assert merged["profiles"]["list"][0]["colorScheme"] == "Argent"
    assert merged["defaultProfile"] == "{ps7}"


def test_terminal_leaves_the_default_alone_without_powershell_7() -> None:
    merged = json.loads(terminal_settings(as_bytes(terminal(False), 4), THEME))
    assert merged["defaultProfile"] == "{ps5}"


def test_terminal_merge_is_idempotent() -> None:
    once = terminal_settings(as_bytes(terminal(True), 4), THEME)
    assert terminal_settings(once, THEME) is once


def test_editor_settings_only_rewrite_when_something_changes() -> None:
    oddly_formatted = b'{"editor.fontSize":14,  "mine":true}'
    assert editor_settings(oddly_formatted, {"editor.fontSize": 14}) is oddly_formatted
    merged = json.loads(editor_settings(oddly_formatted, {"editor.fontSize": 15}))
    assert merged == {"editor.fontSize": 15, "mine": True}


BODY = "Set-Alias lg lazygit"


def test_block_is_appended_to_a_new_profile_with_crlf() -> None:
    assert (
        managed_block(None, BODY)
        == b"# >>> argent >>>\r\nSet-Alias lg lazygit\r\n# <<< argent <<<\r\n"
    )


def test_block_replaces_tadashi_in_place_and_keeps_the_rest() -> None:
    profile = (
        b"Import-Module posh\r\n# >>> tadashi >>>\r\nold stuff\r\n# <<< tadashi <<<\r\n$x = 1\r\n"
    )
    merged = managed_block(profile, BODY, supersedes=("tadashi",))
    assert merged == (
        b"Import-Module posh\r\n# >>> argent >>>\r\nSet-Alias lg lazygit\r\n# <<< argent <<<\r\n"
        b"$x = 1\r\n"
    )


def test_block_keeps_lf_files_lf_and_bom_files_bom() -> None:
    lf = managed_block(b"$a = 1\n", BODY)
    assert b"\r\n" not in lf
    assert lf.startswith(b"$a = 1\n\n# >>> argent >>>\n")
    bom = managed_block(b"\xef\xbb\xbf$a = 1\r\n", BODY)
    assert bom.startswith(b"\xef\xbb\xbf$a = 1\r\n")


def test_block_is_idempotent() -> None:
    once = managed_block(b"$a = 1\r\n", BODY, supersedes=("tadashi",))
    assert managed_block(once, BODY, supersedes=("tadashi",)) == once


def test_unclosed_block_is_refused() -> None:
    with pytest.raises(SkipTargetError, match="never closed"):
        managed_block(b"# >>> argent >>>\r\nhalf a block\r\n", BODY)


def test_terminal_handles_light_and_dark_scheme_pairs() -> None:
    settings = terminal(True)
    first = settings["profiles"]["list"][0]  # pyright: ignore[reportIndexIssue]
    first["colorScheme"] = {"dark": "Tadashi Neon", "light": "Mine"}
    merged = json.loads(terminal_settings(as_bytes(settings, 4), THEME))
    assert merged["profiles"]["list"][0]["colorScheme"] == {"dark": "Argent", "light": "Mine"}


def test_a_profile_that_isnt_utf8_is_skipped() -> None:
    with pytest.raises(SkipTargetError, match="UTF-8"):
        managed_block("# café\r\n".encode("utf-16"), BODY)


def test_odd_claude_settings_shapes_are_skipped() -> None:
    with pytest.raises(SkipTargetError, match="hooks"):
        claude_settings(b'{"hooks": []}', STATUSLINE, chimes=True)


def test_block_keeps_form_feeds_inside_lines() -> None:
    merged = managed_block(b"$a = 'x\x0cy'\r\n", BODY)
    assert merged.startswith(b"$a = 'x\x0cy'\r\n")


SUPERPOWERS = {
    "matcher": "startup|clear|compact",
    "hooks": [
        {
            "type": "command",
            "command": r'"C:\Users\A B\.claude\superpowers-plugin\hooks\sp-session-start.cmd"',
        }
    ],
}
MINE = {"hooks": [{"type": "command", "command": "my-own-hook"}]}


def test_retired_hooks_are_removed_and_the_rest_kept() -> None:
    settings = {"hooks": {"SessionStart": [SUPERPOWERS, MINE]}}
    merged = json.loads(
        claude_settings(
            as_bytes(settings), STATUSLINE, chimes=False, retire=("superpowers-plugin",)
        )
    )
    assert merged["hooks"]["SessionStart"] == [MINE]


def test_retiring_the_only_hook_drops_the_event() -> None:
    settings = {"hooks": {"SessionStart": [SUPERPOWERS]}}
    once = claude_settings(
        as_bytes(settings), STATUSLINE, chimes=False, retire=("superpowers-plugin",)
    )
    assert "hooks" not in json.loads(once)
    assert claude_settings(once, STATUSLINE, chimes=False, retire=("superpowers-plugin",)) is once
