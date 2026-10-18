import io

import pytest

from edith.ui import Out, wants_colour


def test_plain_output_has_aligned_tags_and_no_escapes() -> None:
    buf = io.StringIO()
    out = Out(buf, colour=False)
    out.tag("ok", "first")
    out.tag("update", "second")
    assert buf.getvalue() == "  ok     first\n  update second\n"


def test_colour_wraps_the_tag_only() -> None:
    buf = io.StringIO()
    Out(buf, colour=True).tag("fail", "broken")
    assert buf.getvalue().startswith("  \033[")
    assert buf.getvalue().endswith("broken\n")


def test_no_color_wins_over_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert wants_colour(io.StringIO()) is False


def test_pipes_stay_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert wants_colour(io.StringIO()) is False
