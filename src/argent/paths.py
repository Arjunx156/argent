"""Every location argent reads or writes, resolved once so tests can swap the whole machine."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path


class RepoNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class Env:
    home: Path
    appdata: Path
    localappdata: Path
    documents: Path
    programfiles: Path
    windir: Path
    repo: Path

    @classmethod
    def from_system(cls, repo: Path | None = None) -> "Env":
        home = Path.home()
        return cls(
            home=home,
            appdata=Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming"),
            localappdata=Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local"),
            documents=documents_folder(home),
            programfiles=Path(os.environ.get("PROGRAMFILES") or "C:/Program Files"),
            windir=Path(os.environ.get("WINDIR") or "C:/Windows"),
            repo=repo or find_repo(),
        )

    @property
    def kit(self) -> Path:
        return self.repo / "kit"

    @property
    def claude(self) -> Path:
        return self.home / ".claude"

    @property
    def state(self) -> Path:
        return self.home / ".argent"

    @property
    def legacy_state(self) -> Path:
        """Where argent kept its state on its first day, when it was called edith."""
        return self.home / ".edith"

    @property
    def snapshots(self) -> Path:
        return self.state / "snapshots"

    @property
    def shelf(self) -> Path:
        return self.state / "shelf"

    def expand(self, raw: str) -> Path:
        """~ means this env's home, not the real one, so fake homes stay fake."""
        if raw == "~" or raw.startswith(("~/", "~\\")):
            return self.home / raw[2:]
        return Path(raw)


def adopt_legacy_state(env: Env) -> bool:
    """Move ~/.edith to ~/.argent once, so snapshots from before the rename still restore."""
    if env.state.exists() or not env.legacy_state.is_dir():
        return False
    env.legacy_state.rename(env.state)
    return True


def find_repo() -> Path:
    override = os.environ.get("ARGENT_REPO")
    candidates = [Path(override)] if override else []
    # editable installs keep the package inside the repo: repo/src/argent/paths.py
    candidates.append(Path(__file__).resolve().parents[2])
    for candidate in candidates:
        if (candidate / "kit").is_dir() and (candidate / "profile.toml").is_file():
            return candidate
    raise RepoNotFoundError(
        "argent runs from its repository. Install it with `uv tool install --editable <repo>`, "
        "or set ARGENT_REPO to the repo folder."
    )


def documents_folder(home: Path) -> Path:
    """The real Documents folder, which OneDrive likes to move."""
    if sys.platform == "win32":
        found = _known_folder_documents()
        if found:
            return found
    return home / "Documents"


def _known_folder_documents() -> Path | None:
    import ctypes
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = (
            ("data1", wintypes.DWORD),
            ("data2", wintypes.WORD),
            ("data3", wintypes.WORD),
            ("data4", wintypes.BYTE * 8),
        )

    # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
    folder = Guid(
        0xFDD39AD0, 0x238F, 0x46AF, (wintypes.BYTE * 8)(*b"\xad\xb4\x6c\x85\x48\x03\x69\xc7")
    )
    out = ctypes.c_wchar_p()
    try:
        shell32 = ctypes.windll.shell32  # pyright: ignore[reportAttributeAccessIssue]
        ole32 = ctypes.windll.ole32  # pyright: ignore[reportAttributeAccessIssue]
    except AttributeError:
        return None
    if shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) != 0:
        return None
    try:
        return Path(out.value) if out.value else None
    finally:
        ole32.CoTaskMemFree(out)
