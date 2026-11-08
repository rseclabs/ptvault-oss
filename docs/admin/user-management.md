# User Management

PTVault supports multiple user accounts, each with a system-level role and optional team memberships. User management is accessible to admins only.

## Accessing User Management

Click **Admin** → **Users**.

## Viewing Users

The Users list shows all active (and optionally deactivated) user accounts:

| Column | Description |
|--------|-------------|
| Username | Unique login name |
| Full Name | Display name |
| Email | Login email address |
| Role | `admin`, `tester`, or `viewer` |
| Last Login | Most recent login timestamp |
| Status | Active or Deactivated |

---

## Creating a User

1. Click **+ New User**
2. Fill in:
   - **Full Name**: Display name
   - **Email**: Login email (must be unique)
   - **Username**: Unique username (alphanumeric)
   - **Password**: Must meet the strength requirements (see below)
   - **Role**: Select the system role

3. Click **Create**

### Password Requirements

| Requirement | Details |
|-------------|---------|
| Minimum length | 12 characters |
| Strength | Validated in real time with visual indicator |

Passwords are hashed with Argon2id immediately upon creation. PTVault never stores plaintext passwords.

### Role Assignment

| Role | When to Assign |
|------|---------------|
| **admin** | Full system administrators — trusted users who manage the platform |
| **tester** | Standard penetration testers — can create and manage engagements |
| **viewer** | Read-only users — clients, QA reviewers, or limited-access staff |

---

## Editing a User

1. Find the user in the list
2. Click the **edit icon** (pencil)
3. Modify:
   - Full Name
   - Email
   - Password (leave blank to keep the current password)
   - Role
4. Click **Save**

### Self-Edit

Any user can edit their own profile (name, email, password) without admin access. Go to **Admin > Users** and edit your own account, or use the profile icon in the navigation.

---

## Deactivating a User

Deactivation is a **soft delete** — the account is disabled but not removed from the database. Deactivated users cannot log in.

1. Find the user
2. Click the **deactivate icon** (or the deactivate option in the user menu)
3. Confirm the action

> **Note:** You cannot deactivate your own account.

All audit log entries and engagement memberships for the deactivated user are preserved.

---

## Activating a Deactivated User

1. Show deactivated users using the "Show Inactive" toggle
2. Find the deactivated user
3. Click **Activate**

The user can log in again immediately.

---

## Role Changes

To change a user's system role:

1. Edit the user
2. Select the new role from the **Role** dropdown
3. Save

Role changes take effect on the user's next API request (within seconds if they are currently logged in).

---

## Viewing Current Profile

Click **Admin > Users > Me** (or the profile link in the navigation) to view and edit your own account without admin access. You can change your display name, email, and password.

---

## Security Notes

- Passwords are hashed with **Argon2id** (time_cost=3, memory=64MiB, parallelism=4) — they cannot be recovered
- If a user forgets their password, an admin must set a new one via the edit form
- There is no self-service password reset — this is intentional for air-gapped security environments
- All login attempts and password changes are recorded in the audit log
