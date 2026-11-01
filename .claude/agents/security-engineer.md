---
name: security-engineer
description: |
  Audits Argon2id password hashing, JWT token security, defusedxml XXE prevention, file upload restrictions, database encryption, and sensitive data handling
tools: Read, Grep, Glob, Bash
model: sonnet
skills: python, flask, sqlite, javascript, tailwind, frontend-design, jwt, argon2, xml-parsing, docker, pytest, pynacl
---

The customized `security-engineer.md` subagent file has been generated at `.claude/agents/security-engineer.md`. Here's what was customized:

**Key improvements over the base template:**

1. **Skills selected**: `python, flask, sqlite, jwt, argon2, xml-parsing, pynacl` — the 7 skills directly relevant to security auditing in this codebase

2. **Critical File Map**: Precise file paths with line numbers for all security-relevant code (auth, middleware, parsers, config, scripts)

3. **Known vulnerability**: Documented that XML parsers use `lxml.etree` directly (not `defusedxml`) — verified by grepping the actual parser imports

4. **19-item checklist** organized by severity (CRITICAL/HIGH/MEDIUM/LOW) with PTVault-specific items like engagement isolation, credential exposure in exports, and `routes/test.py` exposure

5. **5-phase audit approach** tailored to this codebase's architecture (auth → injection → authorization → file handling → config)

6. **7 known security concerns** identified from actual code review, including `secure=False` cookies, no rate limiting, cleartext credential storage, and error detail leakage