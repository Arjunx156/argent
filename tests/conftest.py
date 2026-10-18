from pathlib import Path

import pytest

from edith.paths import Env

PROFILE = """\
[me]
name = "Test Person"
email = "test@example.com"
github = "testperson"
about = "Builds things."
university = "Test University"

[projects]
roots = ["~/code"]

[claude]
chimes = true
"""


@pytest.fixture
def env(tmp_path: Path) -> Env:
    """A whole fake machine: home, app data, documents and an edith repo."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    fake = Env(
        home=home,
        appdata=home / "AppData" / "Roaming",
        localappdata=home / "AppData" / "Local",
        documents=home / "Documents",
        repo=repo,
    )
    for folder in (fake.appdata, fake.localappdata, fake.documents, fake.kit):
        folder.mkdir(parents=True)
    (repo / "profile.toml").write_text(PROFILE, encoding="utf-8")
    return fake
