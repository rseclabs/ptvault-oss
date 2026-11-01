# Team Management

Teams let you group users together and grant them collective access to engagements. When an engagement is assigned to a team, all team members automatically receive access.

## Accessing Team Management

Click **Admin** → **Teams**.

## Creating a Team

1. Click **+ New Team**
2. Enter:
   - **Team Name**: Descriptive name (e.g., `Red Team`, `Web Assessment Team`, `Client Auditors`)
   - **Description**: Optional description of the team's purpose
3. Click **Create**

## Adding Team Members

1. Click on a team to open its details
2. Click **+ Add Member**
3. Search for a user by name or email
4. Select a **team role**:
   - **Lead**: The team member gets **editor** access to assigned engagements
   - **Member**: The team member gets **viewer** access to assigned engagements
5. Click **Add**

## Team Roles

| Team Role | Engagement Access | When to Use |
|-----------|------------------|-------------|
| **Lead** | Editor | Senior testers who can modify evidence and reports |
| **Member** | Viewer | Junior testers, clients, or QA reviewers who need read-only access |

Note: These team roles map to engagement-level roles (`editor` and `viewer`). Team members who are also system `admin`s always have full engagement access regardless of team role.

## Changing a Member's Role

1. Find the member in the team's member list
2. Click the role dropdown or edit icon
3. Select the new role
4. The change takes effect immediately for all team engagements

## Removing a Team Member

1. Find the member in the team list
2. Click the **remove icon** (X)
3. Confirm the removal

The user loses access to all engagements assigned to this team (unless they have direct membership or admin access).

## Editing a Team

1. Click the **edit icon** on the team card or at the top of the team detail view
2. Modify the team name or description
3. Click **Save**

## Deleting a Team

1. Click the **delete icon** on the team
2. Confirm the deletion

Deleting a team:
- Removes all team member assignments
- Sets the `team_id` field to null on all engagements that were assigned to this team (engagement data is preserved)

## Assigning a Team to an Engagement

Teams are assigned when creating or editing an engagement:

1. Open an engagement (edit mode)
2. Select a team from the **Team** dropdown
3. Save the engagement

All team members now have access to the engagement with their respective roles (lead → editor, member → viewer).

## Viewing Team Access

From the team detail view, you can see:
- All team members and their roles
- All engagements assigned to this team

## Example Team Structure

```
Red Team Assessment 2026
├── Lead: alice@example.com (tester) → editor access
├── Lead: bob@example.com (tester)   → editor access
└── Member: carol@example.com (viewer) → viewer access

Assigned Engagements:
├── ACME Corp External Pentest
└── ACME Corp Internal Pentest
```

In this example, Alice and Bob can modify evidence, while Carol can only view.
