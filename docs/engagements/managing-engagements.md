# Managing Engagements

## Viewing Engagements

The Engagements tab shows all engagements you have access to as cards. Each card displays:
- Engagement name and client
- Status badge (Active / Completed / Archived)
- Start and end dates
- Tags

Use the **search bar** to filter engagements by name in real time.

---

## Editing or Deleting an Engagement

Editing and deleting engagements is handled by admins in the **Admin > Engagements** tab, not from the engagement cards. See [Engagement Management (Admin)](../admin/engagements.md) for instructions.

---

## Changing Status

To mark an engagement as completed or archive it, an admin must edit the engagement from **Admin > Engagements**:

1. Go to **Admin > Engagements**
2. Click **Edit** on the engagement
3. Change the **Status** field to `Completed` or `Archived`
4. Click **Save**

Archived engagements can be shown by enabling the "Show Archived" toggle in the Engagements view.

---

## Switching Active Engagements

Click any engagement card to make it the active engagement. If you currently have an active engagement, a confirmation dialog asks if you want to switch. Confirm to proceed.

The active engagement name is shown in the navigation header throughout PTVault.

---

## Managing Members

Engagement members allow you to give specific PTVault users access to an engagement with defined roles.

### Adding a Member

1. Open an engagement (make it active or view its details)
2. Look for the **Members** section or the team icon
3. Click **+ Add Member**
4. Search for a user by name or email
5. Select an **engagement role**: `owner`, `editor`, or `viewer`
6. Click **Add**

### Changing a Member's Role

1. In the Members section, find the user
2. Click the role dropdown next to their name
3. Select the new role
4. The change takes effect immediately

### Removing a Member

1. In the Members section, click the **remove icon** next to a member
2. Confirm the removal

> **Note:** An engagement must always have at least one owner. You cannot remove the last owner or downgrade them to editor/viewer.

### Role Reference

| Role | Permissions |
|------|-------------|
| **owner** | Full control: edit content, manage members, delete engagement |
| **editor** | Add and modify evidence, hosts, ports, credentials, reports |
| **viewer** | Read-only access to all engagement content |

---

## Team-Based Access

Assigning a team to an engagement automatically grants access to all team members:

- Team **leads** receive **editor** access
- Team **members** receive **viewer** access

To assign a team, edit the engagement and select a team from the **Team** dropdown.

See [Team Management](../admin/team-management.md) for creating teams.

---

## Searching Across Engagements

The search bar at the top of the Engagements tab filters by engagement name. For searching within an engagement (evidence, hosts), use the search capabilities in the [Evidence](../evidence/searching-filtering.md) and [Hosts](../hosts/adding-hosts.md) sections.
