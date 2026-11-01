# Contributing to PTVault

Thanks for your interest in improving PTVault! Bug reports, parser additions,
documentation fixes, and features are all welcome.

## Getting Started

```bash
git clone <your fork>
cd ptvault
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py              # http://localhost:5001
```

Run the test suite before opening a pull request:

```bash
python -m pytest tests/ -v --ignore=tests/e2e
```

The Playwright tests in `tests/e2e/` need a running instance and are skipped
unless `PT_USERNAME` / `PT_PASSWORD` are set.

## Project Layout

- `routes/` — Flask blueprints (registered in `features.py`)
- `models/` — database access, DAOs, and versioned migrations (`models/migrations/versions/NNN_*.py`)
- `middleware/` — `@require_auth`, `@require_role`, `@require_engagement_access`
- `utils/parsers/` — tool output parsers (Nmap, Nessus, Burp, …)
- `static/js/` and `templates/` — vanilla JS single-page app (no build step)
- `docs/` — user documentation

`CLAUDE.md` has a fuller architecture overview and code-style notes.

## Guidelines

- **Keep it local-first.** No telemetry, no cloud calls without the user opting in.
- **Scope data by engagement.** Every query touching engagement data must filter
  by `engagement_id` and respect `@require_engagement_access`.
- **Parse XML safely.** Use `defusedxml`, never `xml.etree` directly.
- **Schema changes go in a new migration**, never by editing an old one.
- **Python:** PEP 8, `snake_case`, imports ordered stdlib / third-party / local.
- **JavaScript:** vanilla ES6+, `camelCase`; no frameworks or build tooling.
- **Add tests** for new routes, parsers, and bug fixes.
- **Never commit** `.env`, `data/`, `keys/`, real scan output, or client data.
  Use synthetic fixtures under `tests/fixtures/`.

## Pull Requests

1. Fork and create a branch from `main`.
2. Keep each PR focused on one change; describe what and why.
3. Make sure tests pass and update docs in `docs/` when behavior changes.
4. Use [Conventional Commits](https://www.conventionalcommits.org/) style
   messages where practical (`feat:`, `fix:`, `docs:` …).

## Reporting Bugs and Requesting Features

Use the GitHub issue templates. For security issues, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
