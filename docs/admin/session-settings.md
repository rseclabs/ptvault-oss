# Session Settings

PTVault provides controls for managing session timeouts and revoking active sessions across all users.

## Accessing Session Settings

Click **Admin** → **Settings** → **Session Management** section.

---

## Idle Timeout

The idle timeout automatically ends sessions that have been inactive for a set period. This protects against unauthorized access if PTVault is left open on an unattended machine.

### Default Value

**15 minutes** of inactivity

### Configuring the Timeout

1. Go to **Admin > Settings**
2. Find the **Session Management** section
3. Enter the desired timeout in the **Idle Timeout (minutes)** field
4. Click **Save Settings**

### Allowed Range

| Minimum | Maximum |
|---------|---------|
| 1 minute | 1440 minutes (24 hours) |

### How the Timeout Works

1. Every user interaction (API calls, UI clicks) resets the idle timer
2. The frontend sends periodic **heartbeat requests** to keep the session alive during active use
3. If no activity is detected for the configured period, the server marks the session as expired
4. The next request from that browser triggers a logout and redirects to the login page
5. A **warning dialog** appears ~30 seconds before the session expires, giving the user a chance to continue

### Considerations

| Scenario | Recommended Timeout |
|----------|-------------------|
| Shared workstation | 5–10 minutes |
| Individual developer machine | 30–60 minutes |
| Background monitoring | 120–240 minutes |
| Air-gapped lab environment | 60–120 minutes |

---

## Revoking All Sessions

In a security incident, compromised admin credentials, or when rotating JWT keys, you can immediately invalidate all active sessions across all users.

### Steps

1. Go to **Admin > Settings**
2. Click **Revoke All Sessions**
3. A confirmation dialog appears explaining that all users (including yourself) will be logged out
4. Click **Confirm**

### What Happens

- All session records in the `user_sessions` table are marked as inactive
- All users receive a 401 Unauthorized response on their next request
- Everyone is redirected to the login page
- You (the admin) are also logged out and must log in again

### When to Use

- Suspected unauthorized access to a session token
- After changing the JWT secret key
- When a user account is compromised and you need to immediately cut off all access
- Security audit requiring fresh sessions for all users

---

## Per-User Session Tracking

Each login creates an individual session record. Sessions track:
- Creation and expiry timestamps
- Last activity timestamp (updated via heartbeat)
- IP address and browser User-Agent

Currently, PTVault does not expose a per-user session list in the UI — the Revoke All Sessions action affects everyone at once.
