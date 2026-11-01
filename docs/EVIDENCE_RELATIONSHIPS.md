# Evidence Relationship Mapping

This feature allows you to create and visualize relationships between evidence items, enabling you to document attack paths and show how different pieces of evidence connect during a penetration test.

## Overview

Evidence Relationship Mapping provides:

- **Visual Graph**: Interactive force-directed graph showing all evidence items and their connections
- **Relationship Types**: Predefined relationship types (leads_to, uses, discovers, exploits, escalates)
- **Path Finding**: Automatically find the shortest path between any two evidence items
- **Attack Paths**: Save and reuse common attack paths for reporting
- **Export**: Export graph visualizations as SVG files

## Use Cases

### Documenting Attack Chains

Link evidence items to show the progression of an attack:

1. **Reconnaissance** → Discovers vulnerable service
2. **Initial Access** → Uses discovered vulnerability to get shell
3. **Privilege Escalation** → Exploits misconfiguration for root
4. **Lateral Movement** → Uses credentials to access other systems

### Credential Reuse Tracking

Show where discovered credentials were used:

- Evidence #12 (database dump) → **uses** → Evidence #34 (SSH login)
- Evidence #34 (SSH access) → **discovers** → Evidence #45 (admin panel)

### Exploit Chain Documentation

Document multi-stage exploits:

- Evidence #1 (SQL injection) → **leads_to** → Evidence #2 (file upload)
- Evidence #2 (webshell) → **escalates** → Evidence #3 (root shell)

## Relationship Types

| Type | Description | Example Use |
|------|-------------|-------------|
| **leads_to** | Evidence naturally progresses to the next step | "Discovered open SMB port leads to null session" |
| **uses** | Evidence item is used as input for another action | "Used credentials from DB dump to login via SSH" |
| **discovers** | Evidence reveals new information or target | "Port scan discovers admin panel on port 8443" |
| **exploits** | Evidence is used to exploit a vulnerability | "SQL injection exploits authentication bypass" |
| **escalates** | Evidence enables privilege escalation | "SUID binary escalates from user to root" |
| **custom** | User-defined relationship with custom label | Any other relationship type |

## Using the Graph Visualization

### Initial Setup

1. Navigate to **Evidence** tab
2. Click **Relationships** sub-tab
3. The graph will load automatically with all evidence items as nodes

### Graph Controls

- **Pan**: Click and drag on empty space
- **Zoom**: Mouse wheel or pinch gesture
- **Move Node**: Click and drag any node
- **Select Node**: Click a node to view details

### Creating Relationships

#### Method 1: From Graph

1. Click the **Link Evidence** button
2. Select **Source Evidence** from dropdown
3. Choose **Relationship Type**
4. Select **Target Evidence** from dropdown
5. Optionally add a custom label and description
6. Click **Link**

#### Method 2: From Evidence Details

1. Select an evidence item from the list
2. Scroll to **Relationships** section
3. Click **Add Relationship**
4. Follow the same process as Method 1

### Finding Attack Paths

To find the path between two evidence items:

1. Click **Find Path** button
2. Click on the starting evidence node (highlighted in green)
3. Click on the target evidence node (highlighted in red)
4. Click **Calculate Path**
5. The shortest path will be highlighted on the graph
6. Path details appear in the right panel

### Saving Attack Paths

Once you've found a useful path:

1. After finding a path, click **Save Path**
2. Enter a name (e.g., "Initial Access to Domain Admin")
3. Add an optional description
4. Click **Save**
5. Access saved paths from the **Saved Paths** dropdown

### Exporting the Graph

Export the current graph view:

1. Click **Export Graph** button
2. Graph is saved as SVG file
3. Use in reports or presentations

## API Usage

### Create Relationship

```javascript
await API.relationships.create({
    source_id: 123,
    target_id: 456,
    type: 'uses',
    label: 'Used credentials from DB dump',
    description: 'Plaintext admin password found in users table'
});
```

### Find Path

```javascript
const result = await API.relationships.findPath(startId, endId);
console.log('Path length:', result.length);
console.log('Path steps:', result.path);
```

### Get Relationships for Evidence

```javascript
const data = await API.relationships.getForEvidence(evidenceId);
console.log('Incoming relationships:', data.incoming);
console.log('Outgoing relationships:', data.outgoing);
```

### Save Attack Path

```javascript
await API.relationships.savePath({
    name: 'Web to Root',
    description: 'Path from web app to root shell',
    start_id: 123,
    end_id: 789,
    path_data: pathArray
});
```

## Database Schema

### evidence_relationships

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| engagement_id | INTEGER | Engagement scope |
| source_evidence_id | INTEGER | Source evidence item |
| target_evidence_id | INTEGER | Target evidence item |
| relationship_type | TEXT | Type of relationship |
| label | TEXT | Optional custom label |
| description | TEXT | Optional explanation |
| created_at | TIMESTAMP | Creation timestamp |
| created_by | INTEGER | User who created it |

### attack_paths

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| engagement_id | INTEGER | Engagement scope |
| name | TEXT | Path name |
| description | TEXT | Optional description |
| start_evidence_id | INTEGER | Starting evidence |
| end_evidence_id | INTEGER | Target evidence |
| path_json | TEXT | Full path data as JSON |
| created_at | TIMESTAMP | Creation timestamp |
| created_by | INTEGER | User who saved it |

## Graph Algorithms

### Path Finding

The system uses **Breadth-First Search (BFS)** to find the shortest path between two evidence items:

1. Build an adjacency list from all relationships
2. Start from the source node
3. Explore neighbors level by level
4. Track visited nodes to avoid cycles
5. Return the first path found (guaranteed shortest)

Time Complexity: O(V + E) where V = nodes, E = edges

### Graph Traversal

The visualization uses **d3-force** simulation:

- **Force-link**: Pulls connected nodes together
- **Force-charge**: Pushes all nodes apart (avoids overlap)
- **Force-center**: Centers the graph in the viewport
- **Force-collision**: Prevents node overlap

## Tips and Best Practices

### Organization

1. **Create relationships as you go**: Don't wait until the end
2. **Use consistent labels**: Helps with pattern recognition
3. **Document key paths**: Save important attack chains
4. **Clean up dead ends**: Remove relationships that didn't lead anywhere

### Reporting

1. **Export key paths**: Include graphs in your reports
2. **Annotate screenshots**: Add relationship info to evidence
3. **Use path descriptions**: Explain the attack narrative
4. **Link to findings**: Connect paths to vulnerability writeups

### Performance

- Graphs with 100+ nodes may be slow to render
- Consider filtering by date range or tags for large engagements
- Saved paths load faster than recalculating

## Troubleshooting

### Graph Won't Load

- Check browser console for errors
- Verify d3.js is loaded (included in dashboard.html)
- Ensure engagement is selected
- Refresh the page

### Relationships Not Saving

- Verify both source and target exist
- Check that you have edit permissions
- Cannot create relationship from evidence to itself

### Path Finding Fails

- Ensure a path exists (nodes must be connected)
- Check that relationships point in the right direction
- Try intermediate nodes if direct path doesn't exist

### Graph Performance

- Too many nodes: Filter by host or date range
- Slow rendering: Disable force simulation after initial layout
- Browser lag: Export and view externally in Inkscape/Illustrator

## Future Enhancements

Planned features for future releases:

- **Bidirectional relationships**: Automatic reverse relationships
- **Relationship weights**: Prioritize certain paths over others
- **Timeline view**: Show evidence relationships over time
- **Subgraph extraction**: Focus on specific hosts or phases
- **Auto-relationship detection**: Suggest relationships based on content
- **Export to MITRE Navigator**: Map evidence to ATT&CK techniques

## Related Features

- **Host Management**: Evidence can be grouped by host
- **Tags**: Use tags to filter evidence before visualizing
- **Report Builder**: Include attack path diagrams in reports
- **Test Plans**: Link evidence to specific test plan items

---

For API documentation, see the inline JSDoc in:
- `/routes/relationships.py`
- `/static/js/api/relationships.js`
- `/static/js/relationship_graph.js`
