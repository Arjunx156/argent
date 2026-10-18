---
name: genesis
description: Set up any new project (repo, app, library, CLI, scripts) with git, formatter, linter, types, tests, a justfile and CLAUDE.md, all passing before the first feature. Use when something new starts.
---

# Genesis

New work starts with its quality gates already in place: one command checks everything, and it passes before any feature lands.

## 1. Pick the stack

Infer it from the request. Ask only when two stacks are equally plausible and the choice is costly to reverse. Defaults:

| Kind | Stack |
|---|---|
| Python app, CLI, data or ML | `uv` + `ruff` + `basedpyright` + `pytest` |
| TypeScript library, CLI or server | `bun` + TypeScript strict + `biome` + `bun test` |
| Web app | Vite + React + TypeScript + Tailwind v4, or Next.js when it needs SSR or routes, with `bun` + `biome` |
| Documents | Markdown sources + folio (see that skill) |
| Rust | `cargo` + `clippy` + `rustfmt` (install the toolchain with `winget install Rustlang.Rustup` if missing) |

## 2. Scaffold with the official generator

Run the generator non-interactively. Check `--help` first, because flags drift between versions.

- Python: `uv init --package NAME` (a `src/` layout with a console entry point; `--lib` for libraries), then `uv add --dev ruff basedpyright pytest`.
- TypeScript: `bun init -y`, then `bun add -d @biomejs/biome typescript` and `bun x biome init`, then set `"indentStyle": "space"` in `biome.json` so it agrees with `.editorconfig`. Use `bun x`, not `bunx`, because the winget build of Bun ships no `bunx`.
- Vite web app: `bun create vite NAME --template react-ts`, then `bun add tailwindcss @tailwindcss/vite` and the biome step above.
- Next.js: `bun x create-next-app@latest NAME --ts --tailwind --app --use-bun --no-eslint` (confirm the flags with `--help`), then biome.

Then make sure the repository exists (`git init -b main` if the generator didn't do it).

## 3. Add the shared files

Copy these from `templates/` in this skill folder:

- `.editorconfig` and `.gitattributes` go into every project.
- `justfile.python` or `justfile.bun` goes in as `justfile`. Replace `NAME` in the `dev` recipe with the real entry point.
- Python projects also get the ruff and pyright settings from `pyproject.snippet.toml`, merged into `pyproject.toml`.

Make TypeScript strict: `"strict": true`, `"noUncheckedIndexedAccess": true`.

## 4. Write the project CLAUDE.md

Keep it under 40 lines and specific to this project:

```markdown
# NAME

One paragraph: what this is, who it is for, and what "good" means here.

## Commands
- `just dev`: run it
- `just check`: format check, lint, types and tests (must pass before any commit)
- `just fmt`: fix formatting and autofixable lint

## Layout
- `src/...`: what lives where, one line each

## Conventions
- Only rules that differ from, or sharpen, the global standing orders.
```

## 5. Write the README

Write a title, one paragraph on what it does, a quick start of three commands or fewer, and a short section on how it works. Skip badge walls, emoji and marketing.

## 6. Prove it

Write one smoke test first, because `pytest` and `bun test` both fail when they find no tests. Run `just fmt` once so the generator's output matches house style, then run `just check` and fix anything red. Then run `just dev` once (or the tests for a library) to see it work. Report the tree you created and the passing check output. Leave committing to the user unless they asked for it.
