# Argent

Arjun Krishnan's engineering environment. The `argent` CLI installs the tools, renders the standing orders and skills into `~/.claude`, themes the terminal, prompt and editors, and keeps all of it honest: it detects drift, refuses to clobber hand edits, snapshots before every write and can restore any snapshot. Good means a fresh Windows laptop becomes Arjun's machine with one script, and `argent doctor` tells the truth about it.

## Commands
- `just dev <args>`: run argent from source (`just dev doctor`)
- `just check`: format check, lint, types and tests (must pass before any commit)
- `just fmt`: fix formatting and autofixable lint

## Layout
- `src/argent/`: the CLI. Stdlib only at runtime, Python 3.12+
- `kit/`: everything deployed. `tools.toml` is the tool manifest, `claude/` holds the standing orders template, status line and skills, `config/` holds terminal, prompt, shell and editor settings
- `profile.toml`: who Arjun is and where his projects live. Templates read it; nothing else hardcodes his name
- `tests/`: pytest; every test runs against a fake home in `tmp_path`, never the real machine

## Conventions
- Commit and push after every verified step, with `just check` green first.
- No runtime dependencies. If the stdlib can do it, it does.
- All filesystem access goes through `argent.paths.Env`, so tests can point it at a temp dir.
- Anything that writes outside the repo snapshots first and supports `--dry-run`.
- The standing orders may only claim tools that `argent` detected on the machine.
