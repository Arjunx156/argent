import pytest

from argent import __version__
from argent.cli import main


def test_version_prints_and_exits_clean(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_store_python_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # the store build sees a private copy of AppData and the registry, so every read lies
    store = r"C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_3.12.2800.0_x64__q"
    monkeypatch.setattr("sys.base_prefix", store)
    assert main(["doctor"]) == 2
    assert "Microsoft Store" in capsys.readouterr().out
