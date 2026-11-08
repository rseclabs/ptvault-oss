# Security Architecture

PTVault is designed from the ground up for security-conscious environments. This document describes the security mechanisms in place to protect your engagement data.

## Authentication

| Mechanism | Implementation | Details |
|-----------|---------------|---------|
| Password hashing | Argon2id | time_cost=3, memory=64MiB, parallelism=4, hash_len=32 |
| Session tokens | JWT (HS256) | Stored in httpOnly cookies; 24-hour expiry |
| CSRF protection | Double-submit cookie | `X-CSRF-Token` header required on mutating requests |
| Session revocation | Server-side blocklist | Individual session invalidation on logout |

### Why Argon2id?

Argon2id is the winner of the Password Hashing Competition (PHC) and is recommended by NIST. It is deliberately memory-intensive (64 MiB per hash), making GPU-based brute-force attacks significantly more expensive than with algorithms like bcrypt or PBKDF2.

### Why httpOnly Cookies for JWT?

Storing tokens in httpOnly cookies (rather than localStorage or sessionStorage) prevents JavaScript-based attacks — including XSS — from stealing the token. The httpOnly flag means the cookie is never accessible to `document.cookie` or any JavaScript code.

---

## Data Encryption

| Layer | Status | Details |
|-------|--------|---------|
| In transit | Application responsibility | Run PTVault behind HTTPS in production |
| At rest (database) | Optional | SQLCipher with AES-256, key derived via Argon2id |
| In memory | Plaintext during operation | Credentials visible to process memory |

### Database Encryption

When SQLCipher encryption is enabled, the database file is encrypted with AES-256. The encryption key is derived from the database passphrase (the password chosen at setup) using Argon2id and is held in memory only: it is never written to disk, so after a restart PTVault stays locked until the passphrase is entered on the unlock page. See [Database Encryption](../admin/database-encryption.md).

---

## Input Security

| Threat | Mitigation |
|--------|-----------|
| XXE (XML External Entity) | All XML parsing uses `defusedxml` library |
| SQL Injection | Parameterized queries throughout the codebase |
| XSS | Content Security Policy headers; Jinja2 auto-escaping in templates |
| CSRF | Double-submit cookie pattern on all mutating requests |
| File upload abuse | Extension allowlist; 250MB size limit; content-type validation |

### defusedxml

PTVault uses the `defusedxml` library for all XML parsing (Nmap, Burp Suite, Nessus, etc.). This prevents XXE attacks where malicious XML files attempt to access local files or initiate server-side requests.

### File Upload Security

Uploaded files are validated against a strict allowlist:

```
.txt  .xml  .json  .png  .jpg  .jpeg  .pdf  .html  .log  .pcap  .nessus
```

Files with extensions not on this list are rejected before upload processing.

---

## Data Isolation

Every database query for engagement data (evidence, hosts, credentials, ports) is filtered by the authenticated user's accessible engagement IDs. Users cannot access data from engagements they are not members of, even by guessing IDs.

### Engagement Access Checks

1. `@require_auth` — Verifies JWT token is valid
2. `@require_engagement_access` — Verifies the user has the required role on the engagement
3. Query-level filtering — All SQL queries include `WHERE engagement_id = ?`

---

## Audit Logging

PTVault logs security-sensitive actions to the `audit_log` database table:

| Action | Logged |
|--------|--------|
| Login (success and failure) | ✓ |
| Logout | ✓ |
| Password change | ✓ |
| User creation and deactivation | ✓ |
| Role changes | ✓ |
| Engagement creation and deletion | ✓ |
| Database encryption changes | ✓ |
| Session revocation | ✓ |

Each log entry includes: user ID, action type, target (what was affected), IP address, User-Agent, and timestamp.

---

## Network Security

PTVault is designed for **local use only**. It listens on `localhost` by default. For production:

- Run behind an HTTPS reverse proxy (nginx, Caddy)
- Use a firewall to restrict access to the PTVault port
- Never expose PTVault directly to the internet without HTTPS and authentication hardening
- Consider running on a dedicated VLAN for sensitive engagements

See [DEPLOYMENT.md](../../DEPLOYMENT.md) for production deployment guidance.

---

## Sensitive Data Best Practices

1. **Enable database encryption** for all installations handling real client data
2. **Use full-disk encryption** on the machine running PTVault
3. **Export and delete** old engagement data after delivery and sign-off
4. **Back up securely** — keep database and key files in separate, encrypted locations
5. **Use strong passwords** — PTVault's Argon2id hashing is strong, but a weak password is still a vulnerability
6. **Keep PTVault updated** — new versions include security improvements

---

## Environment Variables for Security

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session cookie signing — must be secret and random in production |
| `JWT_SECRET_KEY` | JWT token signing — must be secret and random in production |
| `ENVIRONMENT=production` | Enables `Secure` flag on cookies (requires HTTPS) |
| `PTVAULT_ENCRYPTION_REQUIRED` | On by default: PTVault refuses to start without SQLCipher or with an unencrypted database that has an account, setup always encrypts, and encryption cannot be disabled. `0`, `false` or `no` turns it off |

Generate strong keys for production:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
