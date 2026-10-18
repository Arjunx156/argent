<p align="center">
  <img src="assets/edith.svg" alt="EDITH: Arjun's machine, rebuilt in one script and kept honest" width="760">
</p>

# edith

My whole engineering setup in one repo, plus a CLI that keeps it honest. One script turns a fresh Windows laptop into my machine. One command tells me, line by line, whether it still is.

## Activate

```powershell
gh repo clone Arjunx156/edith; cd edith
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It installs `uv`, then `edith` itself, then the core tools, then the kit, and finishes with a doctor's report. Safe to rerun. Want more on day one? `setup.ps1 -Groups core,ai,docs`.

## What it does

**Installs.** Fifty tools in six groups (core, ai, docs, web, privacy, osint), from winget, `uv tool`, or a GitHub release that gets unpacked only after its sha256 matches the digest GitHub publishes. Nothing goes through pip.

**Writes the standing orders.** Every Claude Code session on this machine starts from `~/.claude/CLAUDE.md`. Edith renders it from a template and `profile.toml`, and it only names a tool after detecting it. If Tectonic isn't installed, Claude is told so, along with the command that fixes it.

**Ships the skills.** Nineteen of them. Fifteen come from Tadashi and its upstreams, credited in each `SOURCE`. Four are new and written for how I work: **hackathon** (demo path first, live link by hour two, the two-minute video), **genai** (Gemini, Bedrock and Ollama behind one interface, schemas, evals), **coursework** (Amrita reports with a real title page and real references) and **edith** (so Claude knows how to drive all this).

**Themes everything.** The Edith HUD scheme in Windows Terminal, a starship prompt in the same palette, a PowerShell profile with `proj` to jump to any project, editor fonts, and a Claude status line that runs, space in the home folder and all.

**Guards its work.** Edith hashes every file it writes. Edit one by hand and the next deploy calls it drift and leaves it alone. Every write sits behind a snapshot, and `edith restore` puts any snapshot back, including deleting files that weren't there before.

## Commands

| Command | Does |
|---|---|
| `edith doctor` | Checks tools, standing orders, status line, git identity, PATH, stray rules and skills, and every project |
| `edith deploy` | Renders the kit into place behind a snapshot (`--dry-run` to look first) |
| `edith diff` | The exact lines a deploy would change |
| `edith restore` | Lists snapshots, or puts one back |
| `edith ship -m "msg"` | Message rules, gitleaks, `just check`, commit, push |
| `edith projects` | Every project under my roots: dirty, unpushed, no remote, no git |
| `edith tools` | The manifest, and what this machine has of it |
| `edith install <group>` | Installs what a group is missing |
| `edith shelve <path>` | Parks Claude config edith doesn't manage, without deleting it |

## Why not just Tadashi

Edith grew out of [Tadashi](https://github.com/riteshroshann/tadashi), Ritesh Roshan's environment, and it kept the best of it: the standing orders, the skills, folio and the tool picks. Running it on my laptop turned up three problems:

- The status line never ran. My home folder has a space in it, the path wasn't quoted, and Python tried to execute a stray log file called `C:\Users\ARJUN`.
- The standing orders told Claude that Tectonic, LibreOffice and Bitwarden were installed. None of them were.
- Deploys copied files one way. Running it again would have quietly put Ritesh's name back into my standing orders.

Edith fixes each one by construction: `doctor` runs the status line for real, claims render only for detected tools, and hand edits are drift, never casualties.

## How it works

```text
profile.toml       who I am and where my projects live
kit/tools.toml     the tool manifest: source, group, and the line Claude may read
kit/claude/        standing orders template, status line, skills
kit/config/        terminal scheme, prompt, PowerShell block, editor settings
src/edith/         the CLI: stdlib only at runtime, Python 3.12+
tests/             110 tests, every one against a fake machine in a temp folder
```

A deploy builds one target per file. Whole files belong to edith. Shared files, like `settings.json` for Claude, Windows Terminal and VS Code, or the PowerShell profile, get merged: edith touches only its own keys or its own marked block. The plan compares each target with the disk and with the hash edith recorded last time, so it can tell new, update, adopt and drift apart before anything is written.

## Keeping it sharp

```powershell
git pull; edith install core ai; edith deploy; edith doctor
winget upgrade --all; uv tool upgrade --all
```

Change the kit here, never in `~/.claude`. Then `just check` and `edith deploy`.

<p align="center"><sub>Engineered by Arjun Krishnan.</sub></p>
