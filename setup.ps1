<#
  Edith / setup
  A fresh Windows laptop to Arjun's machine: uv, then edith itself, then the tools, then the kit.
  Safe to rerun. Runs on the Windows PowerShell 5.1 a new machine ships with.

  Usage:  powershell -ExecutionPolicy Bypass -File setup.ps1 [-Groups core,ai,docs]
#>
param([string[]]$Groups = @('core'))
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Have([string]$cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
              (Join-Path $env:USERPROFILE '.local\bin')
}

if (-not (Have 'winget')) {
  throw 'winget is missing. Install App Installer from the Microsoft Store, then run this again.'
}

Write-Host "`n[1/4] uv"
if (Have 'uv') { Write-Host '  ok     uv' } else {
  winget install --id astral-sh.uv --exact --silent --disable-interactivity `
    --accept-source-agreements --accept-package-agreements | Out-Null
  Refresh-Path
  if (-not (Have 'uv')) { throw 'uv installed but is not on PATH yet. Open a new terminal and rerun.' }
  Write-Host '  done   uv'
}

Write-Host "`n[2/4] edith"
# editable, so a git pull in this folder is all an update needs
uv tool install --editable $PSScriptRoot --reinstall --quiet
if ($LASTEXITCODE -ne 0) { throw 'uv could not install edith from this folder.' }
Refresh-Path
Write-Host ('  done   ' + (edith --version))

Write-Host "`n[3/4] tools"
edith install @Groups

Write-Host "`n[4/4] kit"
edith deploy
edith doctor --quiet
Write-Host "`nOpen a new terminal for the prompt, theme and PATH."
