# Login & Logout

## Logging In

Navigate to `http://localhost:5001` (or `/login` directly). Enter your **email address** and **password**, then click **Sign In**.

On successful login:
- A secure JWT token is set in an httpOnly cookie
- You are redirected to the main dashboard
- Your last active engagement (if any) is restored automatically

### Legacy Login

If your PTVault instance was originally set up with a single master password (older versions), you can still log in using that password in the password field. The system accepts both formats.

### Failed Login

If your credentials are incorrect, you see a generic "Invalid credentials" error. PTVault does not distinguish between wrong email and wrong password to prevent user enumeration.

---

## Logging Out

Click your username or avatar in the top-right corner, then click **Logout**.

On logout:
- Your session token is revoked server-side
- The authentication cookie is cleared from your browser
- You are redirected to the login page

> **Tip:** Logging out from one browser session does not affect other active sessions (e.g., on another device). To revoke all sessions at once, use **Admin > Settings > Revoke All Sessions**.

---

## Automatic Session Expiry

Sessions expire automatically in two ways:

1. **Absolute expiry**: JWT tokens expire after 24 hours regardless of activity.
2. **Idle timeout**: If you have not interacted with PTVault for the configured idle period (default: 15 minutes), your session is automatically revoked.

When your session is about to expire due to inactivity, a **warning dialog** appears giving you the option to stay logged in. If you do not respond, you are logged out automatically.

See [Session Management](./session-management.md) for configuration details.

---

## Session Heartbeat

While you are actively using PTVault, the application sends periodic heartbeat requests to the server to keep the session alive. This happens automatically in the background — you do not need to do anything.

If the heartbeat fails (network interruption, server restart), you are prompted to log in again.
