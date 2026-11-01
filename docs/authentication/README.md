# Authentication & Access

PTVault uses a multi-user authentication system with role-based access control (RBAC). All sessions are secured with JWT tokens stored in httpOnly cookies and protected against CSRF attacks.

## In This Section

- [Login & Logout](./login-logout.md) — How to authenticate and end sessions
- [Session Management](./session-management.md) — Idle timeouts, heartbeats, and session revocation
- [Roles & Permissions](./roles-permissions.md) — System roles and engagement-level roles

## How Authentication Works

1. You log in with your **email** and **password**
2. PTVault verifies your credentials using **Argon2id** hashing
3. A **JWT token** (HS256) is issued and stored in an httpOnly cookie
4. Every API request includes this cookie automatically
5. The server validates the token on each request
6. Sessions expire after **24 hours** or after the configured **idle timeout**

## Security Highlights

- Passwords are hashed with Argon2id (memory-hard, side-channel resistant)
- Tokens are stored in httpOnly cookies — JavaScript cannot access them
- CSRF protection uses a double-submit cookie pattern
- Idle sessions are automatically revoked server-side
- All security-sensitive actions are recorded in the audit log

## See Also

- [Security Architecture](../security/README.md)
- [Admin: Session Settings](../admin/session-settings.md)
- [Admin: User Management](../admin/user-management.md)
