# Session Management

PTVault provides configurable session timeout controls to balance security and usability.

## Idle Timeout

The **idle timeout** automatically ends sessions that have been inactive for a set period of time. This protects against unauthorized access if you leave PTVault open unattended.

**Default**: 15 minutes of inactivity

**Configurable range**: 1 to 1440 minutes (1 minute to 24 hours)

### How It Works

1. Every time you interact with PTVault (clicking, typing, making API calls), the idle timer resets.
2. If no activity is detected for the configured timeout period, the server revokes your session.
3. Before the session expires, a **warning dialog** appears giving you the chance to continue your session by clicking "Stay Logged In."
4. If you do not respond to the warning, you are automatically logged out.

### Configuring Idle Timeout *(Admin only)*

1. Click the **Admin** tab
2. Click **Settings** in the sidebar
3. Find the **Session Management** section
4. Enter the desired timeout in minutes
5. Click **Save Settings**

The new timeout takes effect for all users immediately.

---

## Session Heartbeat

While PTVault is open in your browser, it periodically sends a heartbeat request to the server. This:
- Keeps your session alive during active use
- Retrieves the current idle timeout setting
- Confirms your session is still valid

If the heartbeat returns an authentication error (session expired, server restart), PTVault displays a login prompt.

---

## Revoking All Sessions *(Admin only)*

In a security incident or when rotating keys, an admin can immediately invalidate all active sessions across all users:

1. Go to **Admin > Settings**
2. Click **Revoke All Sessions**
3. Confirm the action

All users (including admins) will be required to log in again. This does not affect JWT token expiry — tokens are added to a blocklist server-side.

---

## Individual Session Tracking

Each login creates a record in the `user_sessions` table. Sessions store:
- A hashed token (never the raw token)
- Creation and expiry timestamps
- Last activity timestamp (updated with each heartbeat)
- IP address and User-Agent of the session

When a session expires or is revoked, its record is marked inactive.

---

## CSRF Protection

PTVault uses a **double-submit cookie** pattern to prevent Cross-Site Request Forgery attacks:

1. The frontend retrieves a CSRF token from `/api/auth/csrf-token`
2. This token is stored in a JavaScript-accessible cookie
3. All mutating requests (POST, PUT, DELETE) include the token in the `X-CSRF-Token` header
4. The server verifies the header token matches the cookie token

This means that even if an attacker tricks your browser into making a request to PTVault, they cannot forge the CSRF token and the request is rejected.
