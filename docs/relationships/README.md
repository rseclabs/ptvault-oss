# Relationships

The Relationships feature lets you model directed connections between PTVault entities — evidence items, findings, notes, and credentials — to map attack chains and document how different findings relate to each other.

## What are Relationships?

A relationship connects two nodes with a directional edge and a type label:

```
Evidence A  --[leads_to]-->  Evidence B
Credential  --[enables]-->   Finding
Note        --[discovers]--> Evidence
```

This allows you to model complex attack narratives where one finding enables the next step.

## Node Types

The following entity types can be connected:

| Node Type | Example |
|-----------|---------|
| `evidence` | Tool output, screenshots, command output |
| `finding` | Documented vulnerability |
| `note` | Host note or engagement note |
| `credential` | Discovered username/password |

## Relationship Types

| Type | Meaning |
|------|---------|
| `leads_to` | This finding enables or leads to the next |
| `uses` | This technique uses the referenced resource |
| `discovers` | This finding discovered the referenced item |
| `exploits` | This action exploited the referenced vulnerability |
| `escalates` | This step escalated privileges via the referenced path |
| `custom` | User-defined relationship type |

## Creating a Relationship

1. Navigate to an evidence item, note, or finding
2. Look for the **Relationships** section or icon
3. Click **+ Add Relationship**
4. Select:
   - **Relationship type** (leads_to, uses, etc.)
   - **Target node type** (evidence, finding, note, credential)
   - **Target node** (search or select from the list)
5. Click **Create**

## Viewing Relationships

For any node, you can see:
- **Outgoing relationships**: Connections from this node to others
- **Incoming relationships**: Connections from other nodes to this one
- **Total count**: Summary of relationship activity

## Graph Visualization

The full relationship graph for the engagement can be viewed as an interactive diagram:
- **Nodes** represent entities (evidence, findings, credentials)
- **Edges** represent relationships with type labels
- Navigate the graph to trace attack paths visually

## Attack Path Analysis

Find the shortest path between two nodes using the path-finding feature:

1. Select a **start node** (e.g., initial access evidence)
2. Select an **end node** (e.g., domain admin credential)
3. Click **Find Path**
4. PTVault traverses the relationship graph and returns the shortest connection path

## Saving Attack Paths

Discovered attack paths can be saved as named records for reporting:

1. Run a path analysis
2. Click **Save Path**
3. Enter a name (e.g., `Initial Access to Domain Compromise`)
4. Click **Save**

Saved paths can be referenced in reports to document the full attack chain.

## Relationship Statistics

View a summary of relationship counts by type for the active engagement:

- Total relationships
- Count by type (leads_to, uses, exploits, etc.)
- Most connected nodes (central findings or pivot points)

## Use Cases

| Scenario | Example Relationship Chain |
|----------|--------------------------|
| Exploitation chain | SQLi finding → DB credentials → Server access |
| Privilege escalation | User shell → Misconfigured SUID → Root shell |
| Lateral movement | Compromised host → Pass-the-hash → Domain Controller |
| Credential reuse | Discovered password → Multiple service logins |
