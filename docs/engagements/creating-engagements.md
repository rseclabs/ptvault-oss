# Creating Engagements

## Steps

1. Click the **Engagements** tab in the top navigation bar
2. Click **+ New Engagement**
3. Fill in the engagement details (see fields below)
4. Click **Create**

The new engagement appears in the engagement list. Click it to make it your active engagement.

---

## Engagement Fields

| Field | Required | Description |
|-------|:--------:|-------------|
| **Name** | Yes | Full project name (e.g., `ACME Corp External Pentest 2026`) |
| **Client Name** | No | Client organization name |
| **Short Name** | No | Abbreviated identifier used in exports (e.g., `ACME-EXT`) |
| **Description** | No | Project scope, rules of engagement, and notes |
| **Tags** | No | Comma-separated labels for organization (e.g., `external,web,2026`) |
| **Start Date** | No | Engagement start date |
| **End Date** | No | Engagement end date |
| **Status** | Yes | `Active`, `Completed`, or `Archived` |
| **Contact Name** | No | Client point-of-contact name |
| **Contact Email** | No | Client POC email address |
| **Contact Phone** | No | Client POC phone number |
| **Team** | No | Assign a team for shared access |

---

## Tips

- Use **Short Name** consistently with your file naming conventions — it appears in export filenames.
- **Tags** help filter engagements when you have many projects. Consider tagging by engagement type (`external`, `internal`, `web`, `phishing`) and year.
- Set **Status** to `Active` while work is in progress, then change to `Completed` when you deliver the report.
- Assign a **Team** if multiple testers will work on the engagement — all team members get appropriate access automatically.

---

## After Creating an Engagement

Once created, click the engagement card to make it active. You are ready to:

1. [Import hosts from a scan](../tool-parsers/nmap.md) or [add hosts manually](../hosts/adding-hosts.md)
2. [Collect evidence](../evidence/collecting-evidence.md)
3. [Build a report](../reporting/report-builder.md)
