import pytest

from argent.paths import Env
from argent.profile import ProfileError, load_profile


def write_profile(env: Env, text: str) -> None:
    (env.repo / "profile.toml").write_text(text, encoding="utf-8")


def test_loads_identity_and_expands_roots_against_the_fake_home(env: Env) -> None:
    profile = load_profile(env)
    assert profile.name == "Test Person"
    assert profile.roots == (env.home / "code",)
    assert profile.chimes is True
    assert profile.context()["me.github"] == "testperson"


def test_missing_profile_names_the_file(env: Env) -> None:
    (env.repo / "profile.toml").unlink()
    with pytest.raises(ProfileError, match="missing"):
        load_profile(env)


def test_broken_toml_is_reported_not_raised_raw(env: Env) -> None:
    write_profile(env, "[me\nname = ")
    with pytest.raises(ProfileError, match="not valid TOML"):
        load_profile(env)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("email", '"not-an-email"', "email"),
        ("github", '"two words"', "spaces"),
        ("name", '"   "', "me.name"),
    ],
)
def test_rejects_bad_identity_fields(env: Env, field: str, value: str, message: str) -> None:
    text = (env.repo / "profile.toml").read_text(encoding="utf-8")
    lines = [
        f"{field} = {value}" if line.startswith(f"{field} =") else line
        for line in text.splitlines()
    ]
    write_profile(env, "\n".join(lines))
    with pytest.raises(ProfileError, match=message):
        load_profile(env)


def test_expand_leaves_absolute_paths_alone(env: Env) -> None:
    assert env.expand("D:/Personal projects2.0").as_posix() == "D:/Personal projects2.0"
    assert env.expand("~") == env.home / ""


def test_retired_hooks_default_to_none_and_must_be_text(env: Env) -> None:
    assert load_profile(env).retire_hooks == ()
    text = (env.repo / "profile.toml").read_text(encoding="utf-8")
    write_profile(env, text + 'retire_hooks = ["superpowers-plugin"]\n')
    assert load_profile(env).retire_hooks == ("superpowers-plugin",)
    write_profile(env, text + "retire_hooks = [1]\n")
    with pytest.raises(ProfileError, match="retire_hooks"):
        load_profile(env)
