All 5 files have been created. Here's a summary of what was generated:

## Pytest Skill - Files Created

**`.claude/skills/pytest/SKILL.md`** (107 lines)
- Quick start with run commands
- Minimal test + DAO test examples
- Key concepts table (in-memory DB, Flask g mock, tmp_path, parametrize, engagement isolation)
- Common patterns: parser tests, isolation tests
- New test checklist and validation loop
- Cross-references to python, flask, sqlite, xml-parsing, argon2, jwt skills

**`references/unit.md`** (148 lines)
- DAO unit test patterns with Flask app context fixture
- CRUD testing with engagement isolation verification
- Parser unit test patterns with fixture files and invalid input
- Utility function tests (pure functions, no Flask deps)
- WARNING: testing against production schema drift
- WARNING: skipping error case tests
- Parametrized test examples from actual codebase

**`references/integration.md`** (142 lines)
- Flask test client pattern (auth_client fixture)
- Protected route testing
- Migration test patterns (idempotency, status checking, module loading)
- RBAC logic tests
- Parser auto-detection tests
- WARNING: missing Flask test client fixture in conftest.py
- WARNING: no pytest-cov configured

**`references/mocking.md`** (143 lines)
- MockG class pattern for monkeypatching `flask.g`
- Decision table: monkeypatch vs app context vs direct injection
- tmp_path vs tempfile patterns
- DAO injection pattern
- Migration module dynamic loading
- WARNING: tempfile cleanup leaks
- WARNING: mixing injection with Flask context
- WARNING: not resetting state between tests

**`references/fixtures.md`** (145 lines)
- Full conftest.py fixture examples from the actual codebase
- Database fixture layers (minimal vs full schema vs on-disk)
- File fixtures and dynamic fixture data
- Fixture scope guidance (function vs session)
- WARNING: mutable default data
- WARNING: heavy fixture setup without reuse
- Fixture composition checklist