<p align="center">
  <img src="assets/argent.svg" alt="ARGENT: Arjun's machine, rebuilt in one script and kept honest" width="760">
</p>

# argent

My whole engineering setup in one repo, plus a CLI that keeps it honest. One script turns a fresh Windows laptop into my machine. One command tells me, line by line, whether it still is.

## Activate

```powershell
gh repo clone Arjunx156/argent; cd argent
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It installs `uv`, then `argent` itself, then the core tools, then the kit, and finishes with a doctor's report. Safe to rerun. Want more on day one? `setup.ps1 -Groups core,ai,docs`.

## What it does

**Installs.** Sixty command-line tools and the seventeen Python and Node libraries the document skills import, in six groups (core, ai, docs, web, privacy, osint). They come from winget, `uv tool`, a GitHub release unpacked only after its sha256 matches the digest GitHub publishes, or a local Docker build. Python libraries go in through uv, never pip itself, and every install is checked by running detection again afterwards.

**Writes the standing orders.** Every Claude Code session on this machine starts from `~/.claude/CLAUDE.md`. Argent renders it from a template and `profile.toml`, and it only names a tool after detecting it. If Tectonic isn't installed, Claude is told so, along with the command that fixes it.

**Ships the skills.** Twenty of them. Sixteen come from Tadashi and its upstreams, credited in each `SOURCE`. Four are new and written for how I work: **hackathon** (demo path first, live link by hour two, the two-minute video), **genai** (Gemini, Bedrock and Ollama behind one interface, schemas, evals), **coursework** (Amrita reports with a real title page and real references) and **argent** (so Claude knows how to drive all this).

**Themes everything.** The Argent HUD scheme in Windows Terminal, a starship prompt in the same palette, a PowerShell profile with `proj` to jump to any project, editor fonts, and a Claude status line that runs, space in the home folder and all.

**Hardens privacy.** `argent harden` turns off the advertising ID, tailored ads, Bing in Start, silent app installs and the rest of Tadashi's list, one reason per line so you can see what you're agreeing to. `--machine` adds telemetry policy, the firewall and Defender from an elevated terminal, and `--dns` sends lookups to Quad9 over HTTPS, unless Cloudflare WARP is already handling them. Every old value is recorded first, so `argent restore` undoes it.

**Keeps a skill library.** `argent library sync` mirrors ten public skill repos, 320 skills at the last sync, into a folder Claude never loads, and `argent library find pdf` searches them. Cloning runs no hooks and follows no symlinks.

**Guards its work.** Argent hashes every file it writes. Edit one by hand and the next deploy calls it drift and leaves it alone. Every write sits behind a snapshot, and `argent restore` puts any snapshot back, including deleting files that weren't there before.

## Commands

| Command | Does |
|---|---|
| `argent doctor` | Checks tools, standing orders, status line, git identity, PATH, stray rules and skills, and every project |
| `argent deploy` | Renders the kit into place behind a snapshot (`--dry-run` to look first) |
| `argent diff` | The exact lines a deploy would change |
| `argent restore` | Lists snapshots, or puts one back |
| `argent ship -m "msg"` | Message rules, gitleaks, `just check`, commit, push |
| `argent projects` | Every project under my roots: dirty, unpushed, no remote, no git |
| `argent tools` | The manifest, and what this machine has of it |
| `argent install <group or tool>` | Installs what is missing, then checks it's really there |
| `argent harden` | Privacy settings, recorded first (`--machine`, `--dns`, `--dry-run`) |
| `argent library` | `sync` mirrors public skill repos; `find <words>` searches them |
| `argent shelve <path>` | Parks Claude config argent doesn't manage, without deleting it |

## Why not just Tadashi

Argent grew out of [Tadashi](https://github.com/riteshroshann/tadashi), Ritesh Roshan's environment, and it kept the best of it: the standing orders, the skills, folio and the tool picks. Running it on my laptop turned up three problems:

- The status line never ran. My home folder has a space in it, the path wasn't quoted, and Python tried to execute a stray log file called `C:\Users\ARJUN`.
- The standing orders told Claude that Tectonic, LibreOffice and Bitwarden were installed. None of them were.
- Deploys copied files one way. Running it again would have quietly put Ritesh's name back into my standing orders.

Argent fixes each one by construction: `doctor` runs the status line for real, claims render only for detected tools, and hand edits are drift, never casualties.

## How it works

```text
profile.toml       who I am and where my projects live
kit/tools.toml     the tool manifest: source, group, and the line Claude may read
kit/claude/        standing orders template, status line, skills
kit/config/        terminal scheme, prompt, PowerShell block, editor settings
src/argent/         the CLI: stdlib only at runtime, Python 3.12+
tests/             pytest, every test against a fake machine in a temp folder
```

A deploy builds one target per file. Whole files belong to argent. Shared files, like `settings.json` for Claude, Windows Terminal and VS Code, or the PowerShell profile, get merged: argent touches only its own keys or its own marked block. The plan compares each target with the disk and with the hash argent recorded last time, so it can tell new, update, adopt and drift apart before anything is written.

## Keeping it sharp

```powershell
git pull; argent install core ai; argent deploy; argent doctor
winget upgrade --all; uv tool upgrade --all
```

Change the kit here, never in `~/.claude`. Then `just check` and `argent deploy`.

<p align="center"><sub>Engineered by Arjun Krishnan.</sub></p>
