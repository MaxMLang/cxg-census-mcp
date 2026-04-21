# Contributing

Thanks for your interest. This is an alpha, single-author project — issues
and small PRs are welcome, but please read the rest of this file first.

## Before opening a PR

For anything beyond a typo / docs fix, **open an issue first** describing the
change. That avoids you sinking time into something I'd rather see done a
different way (or not at all). Drive-by feature PRs without a prior issue
are likely to be closed.

## Set up

```bash
git clone https://github.com/MaxMLang/cxg-census-mcp
cd cxg-census-mcp
uv sync --extra dev                  # add `--extra census` for live Census tests
uv run pre-commit install            # optional but strongly recommended
```

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required.

## Local checks (must pass before pushing)

```bash
make lint                            # ruff check
make format                          # ruff format
make typecheck                       # mypy
make test                            # pytest -m "not live"  (mock mode)
make audit                           # pip-audit on prod deps
```

Or run the whole battery in one go: `make lint format typecheck test audit`.
CI runs the same things plus a Docker build, so green locally ≈ green on CI.

The `live` test marker hits real OLS + Census endpoints and is excluded by
default. Run it with `make test-live` only when you've changed something
that touches network behavior.

## Style

- **Code:** ruff + mypy must be happy. Don't disable rules without a
  comment explaining why.
- **Comments:** explain *why*, not *what*. Don't narrate code.
- **Commit messages:** lowercase, terse, imperative ("fix x", "add y", "drop
  z"). One concern per commit. No conventional-commits prefixes required.

## Tests

- New tool behavior → integration test under `tests/integration/`.
- New helper / pure function → unit test under `tests/unit/`.
- The `_isolated_env` fixture in `tests/conftest.py` already wires mock
  mode + a fresh cache dir, so most tests don't need any setup.

## What's in scope

- Better ontology resolution / hint coverage.
- New planner heuristics (with cost estimates).
- Bug fixes, doc improvements, performance work, test coverage.

## What's out of scope (for now)

- Anything that adds another non-trivial runtime dependency.
- New transports beyond stdio (HTTP, WebSocket, …).
- Authentication / multi-tenant support — this is a single-user local
  server.
- Anything that breaks the upstream attribution contract (every response
  must keep its `attribution` and `unaffiliated` fields).

## Security

Do **not** open public issues for security problems. See [`SECURITY.md`](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the
project's [MIT license](LICENSE).
