# Engagements

An **engagement** represents a single penetration testing project for a client. All data in PTVault — hosts, evidence, findings, and reports — belongs to an engagement. Data is strictly isolated between engagements.

## In This Section

- [Creating Engagements](./creating-engagements.md) — Set up a new project
- [Managing Engagements](./managing-engagements.md) — Edit, archive, search, and manage team access
- [Exporting & Importing](./exporting-importing.md) — Export engagement data and import from JSON

## Key Concepts

### Active Engagement

PTVault works on one engagement at a time — the **active engagement**. The active engagement name is displayed in the navigation header. All actions (adding hosts, collecting evidence, building reports) apply to the active engagement.

To switch engagements, click a different engagement card. If you have unsaved work, PTVault will prompt you to confirm the switch.

### Engagement Status

| Status | Description |
|--------|-------------|
| **Active** | Current in-progress project |
| **Completed** | Testing finished; data preserved for reference |
| **Archived** | Long-term storage; hidden from the default list |

### Data Isolation

Every database query for evidence, hosts, credentials, and reports is filtered by `engagement_id`. Users can only access engagements they own or are a member of. Admins can access all engagements.

## See Also

- [Roles & Permissions](../authentication/roles-permissions.md) — Who can access what
- [Engagement Members](./managing-engagements.md#managing-members) — Add team members to an engagement
