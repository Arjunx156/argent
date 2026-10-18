import dataclasses
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from argent.commands.harden_cmd import applied, harden
from argent.paths import Env
from argent.privacy import (
    DWORD,
    Current,
    PrivacyError,
    load_settings,
    pending,
    undo_script,
)
from argent.snapshot import list_snapshots, restore
from argent.ui import Out

REPO = Path(__file__).resolve().parents[1]
SETTINGS = load_settings(REPO / "kit" / "privacy.toml")
REG_SZ = 1


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], tuple[int | str, int]] = {}

    def read(self, scope: str, key: str, name: str) -> Current:
        return self.values.get((scope, key, name))

    def write(self, scope: str, key: str, name: str, data: int | str, kind: int) -> None:
        self.values[(scope, key, name)] = (data, kind)

    def delete(self, scope: str, key: str, name: str) -> None:
        self.values.pop((scope, key, name), None)


FIREWALL_BEFORE = [
    {"Name": "Domain", "Enabled": "True", "Inbound": "NotConfigured"},
    {"Name": "Public", "Enabled": "True", "Inbound": "NotConfigured"},
]


class FakeShell:
    """Answers the capture scripts with canned state and records everything it runs."""

    def __init__(self, defender_fails: bool = False) -> None:
        self.ran: list[str] = []
        self.defender_fails = defender_fails

    def __call__(self, script: str) -> tuple[int, str]:
        self.ran.append(script)
        if script.startswith("Get-NetFirewallProfile"):
            return 0, json.dumps(FIREWALL_BEFORE)
        if script.startswith("Get-MpPreference"):
            return 0, json.dumps({"Pua": 0, "Network": 0})
        if script.startswith("Set-MpPreference -PUAProtection 1") and self.defender_fails:
            return 1, "another antivirus is in charge"
        if script.startswith("manage-bde"):
            return 1, "needs elevation"
        return 0, ""


@pytest.fixture
def kit_env(env: Env) -> Env:
    return dataclasses.replace(env, repo=REPO)


# a second apart per call, so snapshot names never collide
TICKS = (datetime(2026, 10, 18, 10, 0, 0) + timedelta(seconds=i) for i in range(10_000))


def clock() -> datetime:
    return next(TICKS)


def run(env: Env, registry: FakeRegistry, shell: FakeShell, **kw: bool) -> tuple[int, str]:
    buf = io.StringIO()
    options = {"machine": False, "dns": False, "dry_run": False, "admin": False, **kw}
    code = harden(
        env, Out(buf, colour=False), registry=registry, shell=shell, clock=clock, **options
    )
    return code, buf.getvalue()


def test_the_shipped_settings_load_and_cover_both_scopes() -> None:
    scopes = {v.scope for v in SETTINGS}
    assert scopes == {"user", "machine"}
    assert all(v.why for v in SETTINGS)
    names = {(v.key, v.name) for v in SETTINGS}
    assert len(names) == len(SETTINGS)


def test_a_dry_run_writes_nothing(kit_env: Env) -> None:
    registry = FakeRegistry()
    code, output = run(kit_env, registry, FakeShell(), dry_run=True)
    assert code == 0
    assert registry.values == {}
    assert "No advertising ID" in output
    assert list_snapshots(kit_env) == []


def test_user_hardening_applies_every_user_value_and_restore_undoes_it(kit_env: Env) -> None:
    registry = FakeRegistry()
    advertising = ("user", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled")
    registry.values[advertising] = (1, DWORD)
    extensions = ("user", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden")

    code, _ = run(kit_env, registry, FakeShell())

    assert code == 0
    user = [v for v in SETTINGS if v.scope == "user"]
    assert pending(user, registry) == []
    assert not any(scope == "machine" for scope, _, _ in registry.values)

    restore(kit_env, list_snapshots(kit_env)[-1].name, clock, registry=registry)
    assert registry.values[advertising] == (1, DWORD)
    assert extensions not in registry.values


def test_restore_keeps_a_values_original_type(kit_env: Env) -> None:
    registry = FakeRegistry()
    odd = ("user", r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod")
    registry.values[odd] = ("legacy", REG_SZ)
    run(kit_env, registry, FakeShell())
    restore(kit_env, list_snapshots(kit_env)[-1].name, clock, registry=registry)
    assert registry.values[odd] == ("legacy", REG_SZ)


def test_a_second_run_has_nothing_to_do(kit_env: Env) -> None:
    registry = FakeRegistry()
    run(kit_env, registry, FakeShell())
    code, output = run(kit_env, registry, FakeShell())
    assert code == 0
    assert "already hardened" in output
    assert len(list_snapshots(kit_env)) == 1


def test_machine_hardening_needs_an_elevated_terminal(kit_env: Env) -> None:
    with pytest.raises(PrivacyError, match="elevated terminal"):
        run(kit_env, FakeRegistry(), FakeShell(), machine=True, admin=False)


def test_machine_hardening_journals_system_state_and_restore_replays_it(kit_env: Env) -> None:
    registry, shell = FakeRegistry(), FakeShell()

    code, _ = run(kit_env, registry, shell, machine=True, admin=True)

    assert code == 0
    assert any(
        s.startswith("Set-NetFirewallProfile -Profile Domain,Private,Public") for s in shell.ran
    )
    assert {scope for scope, _, _ in registry.values} == {"machine"}

    undo = FakeShell()
    restore(kit_env, list_snapshots(kit_env)[-1].name, clock, registry=registry, shell=undo)
    assert (
        "Set-NetFirewallProfile -Name Domain -Enabled True -DefaultInboundAction NotConfigured"
        in (" ".join(undo.ran))
    )
    assert any(
        "Set-MpPreference -PUAProtection 0 -EnableNetworkProtection 0" in s for s in undo.ran
    )
    assert registry.values == {}


def test_a_failing_step_is_reported_without_stopping_the_rest(kit_env: Env) -> None:
    shell = FakeShell(defender_fails=True)
    code, output = run(kit_env, FakeRegistry(), shell, machine=True, admin=True)
    assert code == 1
    assert "another antivirus" in output
    assert list_snapshots(kit_env)[-1].count > 0


def test_dns_needs_the_machine_flag(kit_env: Env) -> None:
    from argent.commands import harden_cmd

    args = type("Args", (), {"dns": True, "machine": False, "dry_run": True})()
    with pytest.raises(PrivacyError, match="goes with --machine"):
        harden_cmd.run(args, kit_env, Out(io.StringIO(), colour=False))  # pyright: ignore[reportArgumentType]


def test_dns_undo_resets_automatic_adapters_and_restores_static_ones() -> None:
    state = [
        {"Index": 12, "Alias": "Wi-Fi", "Static": ""},
        {"Index": 7, "Alias": "Ethernet", "Static": "1.1.1.1,8.8.8.8"},
    ]
    script = undo_script("dns", state)
    assert "Set-DnsClientServerAddress -InterfaceIndex 12 -ResetServerAddresses" in script
    assert (
        "Set-DnsClientServerAddress -InterfaceIndex 7 -ServerAddresses '1.1.1.1','8.8.8.8'"
        in script
    )


def test_applied_reads_captured_state() -> None:
    assert not applied("firewall", FIREWALL_BEFORE)
    hardened = [{"Name": "Domain", "Enabled": "True", "Inbound": "Block"}]
    assert applied("firewall", hardened)
    assert applied("defender", {"Pua": 1, "Network": 1})
    assert applied("dns", [{"Index": 1, "Static": "9.9.9.9,149.112.112.112"}])


class WarpShell(FakeShell):
    def __call__(self, script: str) -> tuple[int, str]:
        if script.startswith("$out = @(Get-NetAdapter"):
            self.ran.append(script)
            return 0, json.dumps([{"Index": 11, "Alias": "Wi-Fi", "Static": "127.0.2.2,127.0.2.3"}])
        return super().__call__(script)


def test_dns_leaves_cloudflare_warp_alone(kit_env: Env) -> None:
    shell = WarpShell()
    with pytest.raises(PrivacyError, match="WARP"):
        run(kit_env, FakeRegistry(), shell, machine=True, admin=True, dns=True)
    assert not any(s.startswith("Set-") for s in shell.ran)
    assert list_snapshots(kit_env) == []
