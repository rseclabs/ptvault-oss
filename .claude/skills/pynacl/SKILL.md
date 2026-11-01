All three skill files have been created. Here's a summary:

**Created files:**

1. **`.claude/skills/pynacl/SKILL.md`** (~100 lines) - Overview of PyNaCl usage in PTVault, quick start for SecretBox encryption and password-derived key derivation, key concepts table, current integration status, and cross-references to related skills (argon2, jwt, flask, sqlite, python).

2. **`.claude/skills/pynacl/references/patterns.md`** (~145 lines) - SecretBox encryption patterns, key management (deriving from Argon2id, memory-only keys), base64 storage pattern for SQLite TEXT columns, and 4 anti-patterns with full problem/why/fix documentation:
   - Reusing keys across engagements
   - Storing raw key material in database
   - Silently catching CryptoError
   - Using SecretBox for password hashing

3. **`.claude/skills/pynacl/references/workflows.md`** (~140 lines) - Step-by-step workflow for adding field-level encryption (with checklist), key derivation flow diagram, file encryption pattern, testing patterns (unit + integration), and error handling guidance.

Key observations from the codebase analysis:
- PyNaCl is imported in `models/auth.py` (`nacl.secret`, `nacl.utils`) but no encryption functions are actively called yet
- The skill documents patterns ready for use when field-level encryption is implemented
- All examples use PTVault conventions (DAO layer, Flask routes, SQLite storage, Argon2id key derivation)
- 18 code blocks across all files