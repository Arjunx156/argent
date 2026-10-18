from pathlib import Path

import pytest

from argent.paths import Env
from argent.probe import Probe

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
    """A whole fake machine: home, app data, documents and an argent repo."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    fake = Env(
        home=home,
        appdata=home / "AppData" / "Roaming",
        localappdata=home / "AppData" / "Local",
        documents=home / "Documents",
        programfiles=tmp_path / "Program Files",
        windir=tmp_path / "Windows",
        repo=repo,
    )
    for folder in (fake.appdata, fake.localappdata, fake.documents, fake.kit):
        folder.mkdir(parents=True)
    (repo / "profile.toml").write_text(PROFILE, encoding="utf-8")
    return fake


class FakeProbe(Probe):
    """A machine that has exactly what a test says it has."""

    def __init__(
        self,
        env: Env,
        commands: dict[str, str] | None = None,
        modules: dict[str, str] | None = None,
        node_dirs: list[Path] | None = None,
        images: tuple[str, ...] = (),
    ) -> None:
        super().__init__(env)
        self.commands = commands or {}
        self.modules = modules or {}
        self.images = set(images)
        # cached properties live in __dict__, so this is how a fake fills them
        self.__dict__["node_dirs"] = node_dirs or []
        self.__dict__["python"] = "C:/Python/python.exe"
        self.__dict__["user_site"] = "C:/Users/t/AppData/Roaming/Python/site-packages"

    def which(self, cmd: str) -> str | None:
        return self.commands.get(cmd)

    def python_modules(self, names: list[str]) -> dict[str, str]:
        return {n: self.modules[n] for n in names if n in self.modules}

    def docker_image(self, image: str) -> bool:
        return image in self.images
