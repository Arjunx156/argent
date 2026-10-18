"""profile.toml: who edith works for and where their projects live."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from edith.paths import Env


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    email: str
    github: str
    about: str
    university: str
    roots: tuple[Path, ...]
    chimes: bool

    def context(self) -> dict[str, str]:
        """What templates may refer to as {{ me.* }}."""
        return {
            "me.name": self.name,
            "me.email": self.email,
            "me.github": self.github,
            "me.about": self.about,
            "me.university": self.university,
        }


def load_profile(env: Env) -> Profile:
    path = env.repo / "profile.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProfileError(f"{path} is missing") from None
    except tomllib.TOMLDecodeError as err:
        raise ProfileError(f"{path} is not valid TOML: {err}") from None

    me = _table(data, "me")
    projects = _table(data, "projects")
    claude = data.get("claude", {})

    email = _text(me, "me.email")
    if "@" not in email:
        raise ProfileError(f"me.email doesn't look like an email address: {email!r}")
    github = _text(me, "me.github")
    if any(c.isspace() for c in github):
        raise ProfileError(f"me.github is a username and can't contain spaces: {github!r}")

    roots = projects.get("roots", [])
    if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
        raise ProfileError("projects.roots must be a list of folder paths")

    chimes = claude.get("chimes", False)
    if not isinstance(chimes, bool):
        raise ProfileError("claude.chimes must be true or false")

    return Profile(
        name=_text(me, "me.name"),
        email=email,
        github=github,
        about=_text(me, "me.about"),
        university=_text(me, "me.university"),
        roots=tuple(env.expand(r) for r in roots),
        chimes=chimes,
    )


def _table(data: dict[str, object], key: str) -> dict[str, object]:
    table = data.get(key)
    if not isinstance(table, dict):
        raise ProfileError(f"profile.toml needs a [{key}] table")
    return table  # pyright: ignore[reportUnknownVariableType]


def _text(table: dict[str, object], dotted: str) -> str:
    value = table.get(dotted.split(".")[-1])
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{dotted} must be a non-empty string")
    return value.strip()
