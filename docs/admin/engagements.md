# Engagement Management (Admin)

Admins can view, edit, and permanently delete any engagement from the Admin panel. This is the only place where engagements can be edited or deleted — the main Engagements tab is read-only except for switching the active engagement.

**Access:** Admin only

---

## Accessing the Engagements Tab

1. Click the **Admin** tab in the top navigation bar
2. Select **Engagements** in the left sidebar

The tab is only visible to users with the admin role.

---

## Viewing Engagements

The engagement list is displayed as a table with the following columns:

| Column | Description |
|--------|-------------|
| **Name** | Engagement name |
| **Client** | Associated client name |
| **Status** | Active, Completed, or Archived |
| **Start Date** | Scheduled or actual start date |
| **End Date** | Scheduled or actual end date |

---

## Editing an Engagement

1. Find the engagement in the table
2. Click the **Edit** button
3. Modify fields in the engagement form (same fields as when creating an engagement)
4. Click **Save**

Changes take effect immediately.

---

## Deleting an Engagement

> **Warning:** Deleting an engagement is permanent and cannot be undone. All associated data — hosts, open ports, credentials, evidence, notes, findings, reports, and test executions — is removed from the database.

1. Find the engagement in the table
2. Click the **Delete** button
3. A confirmation dialog appears — confirm that you want to delete the engagement
4. A second confirmation dialog appears — confirm again to proceed

The engagement and all its data are permanently removed after the second confirmation.

---

## Related

- [Creating Engagements](../engagements/creating-engagements.md) — How to create a new engagement
- [Managing Engagements](../engagements/managing-engagements.md) — Switching active engagement, managing members
- [Client Management](./clients.md) — Managing the client database
