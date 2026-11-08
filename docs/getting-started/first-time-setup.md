# First-Time Setup

PTVault ships with no user accounts. The first time you open it, the setup wizard asks you to create the initial administrator.

## Step 1: Create the Admin Account

1. Start PTVault (`python app.py`) and open `http://localhost:5001`
2. You are redirected to `/setup`
3. Enter a username, email, and password (minimum 12 characters) and confirm the password
4. Submit — the admin account is created and, when SQLCipher is available, database encryption is set up using a key derived from this password

> **Note:** The setup wizard is only available while no users exist. Once the first account is created, `/setup` returns 403.

## Step 2: Log In

Log in with the email and password you just created. Add more users from **Admin > Users**.

## Step 3: Back Up Your Encryption Files

Setup also encrypts the database. The key is derived from the password you choose here (the **database passphrase**) and is held in memory only. After every restart PTVault shows an unlock page until the passphrase is entered. Back up `encryption.salt` with the database (by default both are in `data/`) and keep the passphrase safe: without both, an encrypted database cannot be opened. Changing your account password later does not change the database passphrase.

## Step 4: Configure Optional Settings

After initial setup, you may want to:

- **Enable database encryption** (requires SQLCipher): Admin > Settings > Database Encryption
- **Set session timeout**: Admin > Settings > configure idle timeout
- **Add more users**: Admin > Users > Create User
- **Create teams**: Admin > Teams

## Step 5: Create Your First Engagement

1. Click the **Engagements** tab
2. Click **+ New Engagement**
3. Enter the client name and project details
4. Click **Create**

See [Creating Engagements](../engagements/creating-engagements.md) for full details.

---

## Legacy Single-User Setup

Older PTVault installations used a single "master password" instead of multi-user accounts. If you are migrating from a legacy install, the login page accepts both the legacy master password format and the new email+password format.

---

## Troubleshooting

**"Setup page not accessible"**
An admin account already exists. Use the login page at `/login` instead.

**"Password too short"**
Passwords must be at least 12 characters long.

**"Email already exists"**
That email address is registered to another account. Use a different email.
