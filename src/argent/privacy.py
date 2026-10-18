"""argent harden: privacy settings in the registry, plus firewall, Defender and DNS.

Everything goes through Registry and Shell, so tests never touch the real machine, and
every change is journaled into a snapshot first, so `argent restore` undoes it.
"""

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DWORD = 4  # winreg.REG_DWORD
SCOPES = ("user", "machine")


class PrivacyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Value:
    scope: str
    key: str
    name: str
    data: int
    why: str


Current = tuple[int | str, int] | None  # (data, registry type), or None when absent


class Registry(Protocol):
    def read(self, scope: str, key: str, name: str) -> Current: ...
    def write(self, scope: str, key: str, name: str, data: int | str, kind: int) -> None: ...
    def delete(self, scope: str, key: str, name: str) -> None: ...


class Shell(Protocol):
    def __call__(self, script: str) -> tuple[int, str]: ...


def load_settings(path: Path) -> list[Value]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PrivacyError(f"{path} is missing") from None
    values: list[Value] = []
    for setting in data.get("setting", []):
        scope, key, why = setting.get("scope"), setting.get("key"), setting.get("why")
        if scope not in SCOPES or not key or not why:
            raise PrivacyError(f"{path}: every setting needs scope (user or machine), key and why")
        for name, wanted in setting.get("values", {}).items():
            if not isinstance(wanted, int):
                raise PrivacyError(f"{path}: {key}\\{name} must be a whole number")
            values.append(Value(scope, key, name, wanted, why))
    return values


def pending(values: list[Value], registry: Registry) -> list[tuple[Value, Current]]:
    """The values that differ from what's wanted, with what's there now."""
    found = [(v, registry.read(v.scope, v.key, v.name)) for v in values]
    return [(v, now) for v, now in found if now != (v.data, DWORD)]


class WinRegistry:
    def _hive(self, scope: str) -> Any:
        import winreg

        return winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE

    def read(self, scope: str, key: str, name: str) -> Current:
        import winreg

        try:
            with winreg.OpenKey(self._hive(scope), key) as handle:
                data, kind = winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            return None
        return (data, kind)

    def write(self, scope: str, key: str, name: str, data: int | str, kind: int) -> None:
        import winreg

        try:
            with winreg.CreateKeyEx(self._hive(scope), key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.SetValueEx(handle, name, 0, kind, data)
        except PermissionError:
            raise PrivacyError(f"{scope} settings need an elevated terminal") from None

    def delete(self, scope: str, key: str, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(self._hive(scope), key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            return
        except PermissionError:
            raise PrivacyError(f"{scope} settings need an elevated terminal") from None


def powershell(script: str) -> tuple[int, str]:
    """Windows PowerShell 5.1: it carries the firewall, Defender and DNS modules natively."""
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    return done.returncode, (done.stdout or done.stderr).strip()


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    return bool(ctypes.windll.shell32.IsUserAnAdmin())  # pyright: ignore[reportAttributeAccessIssue]


@dataclass(frozen=True)
class SystemStep:
    """A machine setting outside the registry: read it, change it, and put it back."""

    name: str
    why: str
    capture: str
    apply: str


QUAD9 = ("9.9.9.9", "149.112.112.112")

FIREWALL = SystemStep(
    name="firewall",
    why="On for every network, refusing inbound connections unless an app is allowed",
    capture=(
        "Get-NetFirewallProfile | Select-Object Name, "
        "@{n='Enabled';e={\"$($_.Enabled)\"}}, "
        "@{n='Inbound';e={\"$($_.DefaultInboundAction)\"}} | ConvertTo-Json -Compress"
    ),
    apply="Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True "
    "-DefaultInboundAction Block",
)

DEFENDER = SystemStep(
    name="defender",
    why="Defender blocks potentially unwanted apps and known malicious domains",
    capture=(
        "Get-MpPreference | Select-Object @{n='Pua';e={[int]$_.PUAProtection}}, "
        "@{n='Network';e={[int]$_.EnableNetworkProtection}} | ConvertTo-Json -Compress"
    ),
    apply="Set-MpPreference -PUAProtection 1 -EnableNetworkProtection 1",
)

DNS = SystemStep(
    name="dns",
    why="DNS goes to Quad9 over HTTPS, so the network can't read or rewrite lookups",
    capture=(
        "$out = @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | ForEach-Object { "
        "$key = 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\'"
        " + $_.InterfaceGuid; "
        "$static = (Get-ItemProperty -Path $key -Name NameServer -ErrorAction SilentlyContinue)"
        ".NameServer; "
        '[pscustomobject]@{ Index = $_.ifIndex; Alias = $_.Name; Static = "$static" } }); '
        "ConvertTo-Json -Compress -InputObject $out"
    ),
    apply=(
        "foreach ($s in '9.9.9.9','149.112.112.112') { "
        "$doh = @{ DohTemplate = 'https://dns.quad9.net/dns-query'; AllowFallbackToUdp = $false;"
        " AutoUpgrade = $true }; "
        "if (Get-DnsClientDohServerAddress -ServerAddress $s -ErrorAction SilentlyContinue) "
        "{ Set-DnsClientDohServerAddress -ServerAddress $s @doh } "
        "else { Add-DnsClientDohServerAddress -ServerAddress $s @doh } }; "
        "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | ForEach-Object { "
        "Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex "
        "-ServerAddresses '9.9.9.9','149.112.112.112' }; Clear-DnsClientCache"
    ),
)

STEPS = {step.name: step for step in (FIREWALL, DEFENDER, DNS)}


def capture(step: SystemStep, shell: Shell) -> Any:
    code, out = shell(step.capture)
    if code != 0:
        raise PrivacyError(f"couldn't read the {step.name} settings: {out}")
    try:
        return json.loads(out or "null")
    except ValueError:
        raise PrivacyError(f"the {step.name} settings came back unreadable: {out[:80]}") from None


def undo_script(step_name: str, state: Any) -> str:
    """The PowerShell that puts a step back the way capture() saw it."""
    items: list[dict[str, Any]] = state if isinstance(state, list) else [state] if state else []
    if step_name == "firewall":
        return "; ".join(
            f"Set-NetFirewallProfile -Name {p['Name']} -Enabled {p['Enabled']} "
            f"-DefaultInboundAction {p['Inbound']}"
            for p in items
        )
    if step_name == "defender":
        return "; ".join(
            f"Set-MpPreference -PUAProtection {int(p['Pua'])} "
            f"-EnableNetworkProtection {int(p['Network'])}"
            for p in items
        )
    if step_name == "dns":
        lines: list[str] = []
        for adapter in items:
            servers = [s for s in str(adapter["Static"]).replace(" ", ",").split(",") if s]
            index = int(adapter["Index"])
            if servers:
                quoted = ",".join(f"'{s}'" for s in servers)
                lines.append(
                    f"Set-DnsClientServerAddress -InterfaceIndex {index} -ServerAddresses {quoted}"
                )
            else:
                lines.append(
                    f"Set-DnsClientServerAddress -InterfaceIndex {index} -ResetServerAddresses"
                )
        return "; ".join([*lines, "Clear-DnsClientCache"]) if lines else ""
    raise PrivacyError(f"no way to undo a step called {step_name!r}")


def encryption_status(shell: Shell) -> str | None:
    """'on', 'off', or None when it can't be read (manage-bde needs an elevated terminal)."""
    code, out = shell("manage-bde -status C:")
    if code != 0:
        return None
    return "on" if "Protection On" in out else "off"
