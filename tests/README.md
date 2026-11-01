# Tests

`pytest tests/` runs the suite. CI enforces this on every push to `master`
and every PR (`.github/workflows/tests.yml`).

## Fixture contract

`conftest.py` provides three fixtures. Use them — don't hand-roll schemas
in your test file. Drift between hand-rolled fixtures and production
schema is exactly what this layout exists to prevent.

### `test_db`

In-memory SQLite connection with the production schema applied:
`models/schema.sql` is executed, then every migration in
`models/migrations/versions/` runs against it. Use directly when a test
works in raw SQL or needs to inspect rows independent of the DAO layer.

### `app_ctx`

Wraps `test_db` in a Flask app context with `g.db`, `g.user_id`,
`g.current_user`, and `g.active_engagement_id` set, plus a default user
seeded at id=1. **Required for any test that touches a `BaseDAO`
subclass** — DAO methods read `g.db` via property, so direct injection
(`dao.db = conn`) is silently dropped.

### `sample_engagement`

Depends on `app_ctx`. Inserts an engagement (id=1, "Test Engagement",
client_name="ACME Corp"), two hosts, two findings, and two evidence
rows. Returns the engagement id.

## Don't

- **Don't touch `data/ptvault.db`.** `test_db` is in-memory. Never call
  `get_db_connection()` in a test — it reads `Config.DATABASE_PATH` and
  will mutate the real dev database.
- **Don't hand-roll schemas.** If you need a column that doesn't exist
  in `test_db`, add it via a migration in `models/migrations/versions/`,
  not by tacking another `CREATE TABLE` onto your test fixture.
- **Don't inject `dao.db = test_db`.** Use `app_ctx`. The injection is
  silent when wrong, which makes failures confusing.
- **Don't ping `localhost:5000`.** Manual smoke scripts that hit a
  running server live in `scripts/manual_tests/` and are not collected
  by pytest. They're useful but separate.

## When tests surface a prod bug

If a test fails because production code is wrong (column name drift,
querying a dropped table, etc.), prefer fixing production. If the fix is
out of scope for the current change, mark the test `xfail` with a
`reason=` that names the bug, and open a follow-up — don't soften the
assertion.

## File map

| File | Scope |
|------|-------|
| `conftest.py` | Shared fixtures — single source of truth for test schema |
| `test_migrations.py` | Migration system itself: discovery, ordering, idempotency |
| `test_multi_user.py` | UserDAO + Argon2 password hashing |
| `test_relationships.py` | RelationshipDAO + AttackPathDAO |
| `test_report_templates.py` | TemplateDAO + ReportAutoPopulator + TemplateRenderer |
| `test_encryption.py` | SQLCipher encryption layer |
| `test_license.py` | License expiry checks |
| `test_nmap_parser.py`, `parsers/` | Tool parsers (Nmap, Nessus, Burp, ZAP, etc.) |
| `test_rbac.py`, `test_security.py` | RBAC, CSRF, security headers |
| `dao/`, `fixtures/` | DAO unit tests and parser fixture data |
