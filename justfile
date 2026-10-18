set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default: check

# Run edith from the source tree
dev *args:
    uv run edith {{args}}

# Format check, lint, types, tests
check:
    uv run ruff format --check .
    uv run ruff check .
    uv run basedpyright
    uv run pytest -q

# Fix formatting and autofixable lint
fmt:
    uv run ruff format .
    uv run ruff check --fix .

test *args:
    uv run pytest -q {{args}}
