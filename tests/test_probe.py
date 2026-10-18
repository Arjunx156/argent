import pytest

from argent.probe import fresh_env


def test_child_pythons_get_a_new_shells_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # the store python injects PYTHONUSERBASE, which would point another python's user
    # site into the store's private folder
    monkeypatch.setenv("PYTHONUSERBASE", r"C:\store\local-packages")
    monkeypatch.setenv("PYTHONPATH", r"C:\somewhere")
    monkeypatch.setenv("VIRTUAL_ENV", r"D:\project\.venv")
    monkeypatch.setenv("APPDATA", r"C:\Users\t\AppData\Roaming")

    env = fresh_env()

    assert not any(k.upper().startswith("PYTHON") for k in env)
    assert "VIRTUAL_ENV" not in env
    assert env["APPDATA"] == r"C:\Users\t\AppData\Roaming"
