# Contributing to pocket-watch

Thank you for your interest in contributing!

---

## Dev Environment Setup

pocket-watch uses Python stdlib only (no runtime deps). Dev tools are installed separately.

```
git clone https://github.com/MiguelDotL/pocket-watch.git
cd pocket-watch
python3 -m venv .venv
source .venv/bin/activate
pip install ruff mypy pytest bandit pre-commit
```

Install pre-commit hooks (optional but recommended):

```
pre-commit install
```

---

## Running Quality Gates

All gates run locally via `make`. There is no hosted CI — see the README for the rationale.

```
make lint          # ruff check
make typecheck     # mypy scripts/
make test          # pytest tests/
make privacy-check # grep audit for sensitive patterns
make security-check # bandit -r scripts/
make check-all     # all of the above
```

Tests must pass before opening a PR.

---

## Code Style

- Python 3.9+
- `ruff` for linting and formatting (`make lint`)
- `mypy` for type checking (`make typecheck`)
- Stdlib only for runtime code (no third-party imports in `scripts/` or `hooks/`)
- Dev tools (`ruff`, `mypy`, `pytest`, `bandit`) are fine in `Makefile` and dev setup docs

---

## Test Requirements

- New features require tests in `tests/`
- Bug fixes should include a regression test
- Use `tests/fixtures/gen_fixtures.py` for synthetic test data — do not add real data
- Tests must pass on Python 3.9+

Run tests: `make test`

---

## Opening a Pull Request

1. Fork the repo and create a branch: `feat/short-description` or `fix/short-description`
2. Run `make check-all` — all gates must be green
3. Add a CHANGELOG entry under `[Unreleased]`
4. Update docs if your change is user-facing
5. Open a PR using the template

PR template checklist:
- [ ] `make check-all` passes
- [ ] Tests added for new behavior
- [ ] CHANGELOG.md updated
- [ ] Docs updated (if user-facing)

---

## Platform Testing

macOS is the primary verified platform. Linux and Windows contributions are especially welcome — if you're testing on Linux/WSL/Windows, please use the `platform-report` issue template to report results.

---

## No Hosted CI

This project uses local `make check-all` for quality gates — no GitHub Actions, no third-party CI. If you want to add CI under your own billing profile for a fork, that's your call; PRs adding CI to this repo will not be merged. See CONTRIBUTING.md and the README for details.

---

## Reporting Issues

Please include `/pw-doctor` output in all bug reports. The issue templates pre-fill the required fields.

For security issues: see [SECURITY.md](SECURITY.md).
