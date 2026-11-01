# Roles & Permissions

PTVault uses a two-level role system: **system-level roles** that apply across the entire application, and **engagement-level roles** that control access within a specific engagement.

---

## System Roles

Every PTVault user is assigned one of three system roles:

| Role | Description |
|------|-------------|
| **admin** | Full system access. Can manage all users, teams, and engagements. Has implicit owner access to every engagement. |
| **tester** | Standard user. Can create engagements and work on engagements they are members of. |
| **viewer** | Read-only user. Can view engagements they are members of but cannot modify data. |

### What Admins Can Do

- Create, edit, and deactivate user accounts
- Assign and change user roles
- Create and manage teams
- Access and modify all engagements (implicit owner)
- Configure application settings (idle timeout, encryption)
- Revoke all active sessions

### What Testers Can Do

- Create new engagements (becomes owner automatically)
- Access engagements they own or are a member of
- Add and manage evidence, hosts, findings, and reports within their engagements

### What Viewers Can Do

- View engagements they are members of (read-only)
- Cannot create or modify any engagement data

---

## Engagement-Level Roles

Each engagement has its own member list with individual roles. This allows fine-grained control over who can read vs. edit a specific engagement.

| Role | Permissions within an Engagement |
|------|----------------------------------|
| **owner** | Full control: edit content, delete the engagement, manage members, change member roles |
| **editor** | Can add and modify evidence, hosts, ports, credentials, and reports |
| **viewer** | Read-only: can view all engagement content but cannot modify anything |

### Role Assignment

- When a user creates an engagement, they are automatically assigned the **owner** role.
- Owners can invite other users to an engagement and assign them a role.
- An engagement must always have at least one owner — the last owner cannot downgrade or remove themselves.

### Team-Based Access

Engagements can be assigned to a **team**. When a team is assigned:
- Team **leads** receive **editor** access to the engagement
- Team **members** receive **viewer** access to the engagement

This provides a quick way to grant an entire team access to an engagement without adding members individually.

See [Team Management](../admin/team-management.md) for details on creating and managing teams.

---

## Permission Reference Table

| Action | admin | tester (owner) | tester (editor) | tester (viewer) | viewer |
|--------|:-----:|:--------------:|:---------------:|:---------------:|:------:|
| View engagement list | ✓ | ✓ (own) | ✓ (member) | ✓ (member) | ✓ (member) |
| Create engagement | ✓ | ✓ | — | — | — |
| Edit engagement details | ✓ | ✓ | — | — | — |
| Delete engagement | ✓ | ✓ | — | — | — |
| Manage engagement members | ✓ | ✓ | — | — | — |
| Add/edit hosts | ✓ | ✓ | ✓ | — | — |
| Add/edit evidence | ✓ | ✓ | ✓ | — | — |
| Add/edit credentials | ✓ | ✓ | ✓ | — | — |
| View evidence | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create/edit reports | ✓ | ✓ | ✓ | — | — |
| View reports | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage users | ✓ | — | — | — | — |
| Manage teams | ✓ | — | — | — | — |
| Configure settings | ✓ | — | — | — | — |

---

## Changing a User's Role

Only admins can change system roles:

1. Go to **Admin > Users**
2. Find the user and click **Edit**
3. Select the new role from the dropdown
4. Click **Save**

To change an engagement-level role, see [Engagement Members](../engagements/managing-engagements.md#managing-members).
