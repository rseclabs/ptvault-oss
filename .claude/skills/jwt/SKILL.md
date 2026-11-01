All three JWT skill files have been written. Here's a summary of what was updated:

**SKILL.md** (98 lines) — Concise overview with:
- Accurate `create_session_token()` signature including `role` and `username` params
- All `g.*` context variables documented
- Decorator stack order with role hierarchy
- Links to references

**references/patterns.md** (221 lines) — Detailed patterns:
- Token creation with role claims (actual code from `models/auth.py:88-108`)
- Token validation with algorithm pinning explanation
- Cookie configuration table (dev vs production)
- All three middleware decorators (`@require_auth`, `@require_role`, `@require_engagement_access`) with actual code
- 4 anti-patterns with WARNING headers: secrets in payload, algorithm confusion, error leaking, localStorage storage
- Configuration reference with production requirements

**references/workflows.md** (235 lines) — End-to-end flows:
- Complete login flow with multi-user support (legacy + username/password)
- Logout flow with JWT invalidation caveat
- First-time setup with auto-login
- Frontend integration (AuthAPI module, global 401 redirect)
- Debugging table (5 common issues with fixes)
- "Adding a New Protected Endpoint" checklist with decorator order

Key improvements over the previous versions:
- Updated `create_session_token()` to include `role` and `username` parameters
- Added `g.current_user_role`, `g.current_username` to decorator documentation
- Added `@require_role` and `@require_engagement_access` patterns
- Reflected the `@handle_errors` decorator usage in routes
- Multi-user login support (username/password + legacy master_password)
- Cross-references to **argon2**, **flask**, **javascript**, and **python** skills