# Admin Guide

The Admin section provides system management functions for PTVault administrators. Non-admin users see a limited subset of admin options.

## In This Section

- [User Management](./user-management.md) — Create, edit, and deactivate user accounts
- [Team Management](./team-management.md) — Organize users into teams with roles
- [Engagements](./engagements.md) — View, edit, and permanently delete engagements (admin only)
- [Clients](./clients.md) — Manage the reusable client organization database (admin only)
- [Database Encryption](./database-encryption.md) — Enable SQLCipher encryption at rest
- [Session Settings](./session-settings.md) — Configure idle timeout and revoke sessions

## Accessing the Admin Section

Click the **Admin** tab in the top navigation bar.

The left sidebar shows available admin pages:

| Page | Access |
|------|--------|
| **Settings** | Admin only |
| **Users** | Admin only |
| **Teams** | Admin only |
| **Engagements** | Admin only |
| **Clients** | Admin only |
| **Shell One-Liners** | Admin only |
| **License** | All users (view); Admin only (activate/remove) |

## Admin vs. Non-Admin

| Feature | Admin | Non-Admin |
|---------|:-----:|:---------:|
| View license status | ✓ | ✓ |
| Create/edit users | ✓ | — |
| Create/edit teams | ✓ | — |
| Edit/delete engagements | ✓ | — |
| Manage clients | ✓ | — |
| Configure idle timeout | ✓ | — |
| Enable/disable encryption | ✓ | — |
| Revoke all sessions | ✓ | — |
| Manage shell one-liners | ✓ | — |
| Update CyberChef | ✓ | — |
| Edit own profile | ✓ | ✓ |

## Shell One-Liners (Admin)

Manage the shell one-liner library used in **Tools > Command Hub > Shells**.

### Creating a One-Liner

1. Go to **Admin > Shell One-Liners**
2. Click **+ New One-Liner**
3. Fill in:
   - **Name**: Short descriptive name (e.g., `Python Reverse Shell`)
   - **Category**: `shells`, `reverse_shells`, or `shell_upgrades`
   - **Subcategory**: Language or technique group (e.g., `python`, `bash`, `netcat`)
   - **Command**: The actual one-liner (use `{{VARIABLE_NAME}}` for dynamic fields)
   - **Description**: When to use this one-liner
4. Click **Save**

### Variables

Commands can include named variables using the `{{VARIABLE}}` syntax. When a user views the one-liner in the Tools section, they can fill in these variables and the command updates dynamically.

Common variables: `{{LHOST}}`, `{{LPORT}}`, `{{CMD}}`

### Editing and Deleting

Click the edit or delete icon on any custom one-liner to modify or remove it.
