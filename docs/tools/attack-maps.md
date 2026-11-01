# Attack Maps

Attack Maps let you create visual diagrams showing how a network was compromised — mapping the attack path from initial access through lateral movement to the final objective.

## Accessing Attack Maps

Click **Tools** → **Attack Maps**.

Attack maps are scoped to the active engagement. Each engagement can have multiple named maps.

## Creating a Map

1. Click **+ New Attack Map**
2. Enter a name (e.g., `External to Domain Admin`, `Web Application Compromise`)
3. Click **Create**
4. The map editor opens with an empty canvas

## Building a Map

### Adding Nodes

Nodes represent entities in your attack path: hosts, services, users, actions, or objectives.

1. Click **+ Add Node** or double-click the canvas
2. Select the node type
3. Enter a label (e.g., `192.168.1.10`, `Domain Controller`, `Initial Access`)
4. Click **Add**

The node appears on the canvas. Drag it to position it.

### Node Types

PTVault has seven node types, each with a distinct color and purpose:

| Type | Color | Shape | Use |
|------|-------|-------|-----|
| **Recon** | Purple | Rectangle | Pre-attack reconnaissance (OSINT, scanning, enumeration) |
| **Tactic** | Blue | Rectangle | ATT&CK-aligned tactics (Initial Access, Lateral Movement, etc.) |
| **Exploit** | Red | Rectangle | Specific exploits or attack techniques used |
| **Connector** | Green | Diamond | Logic gates — model AND/OR branching in an attack path |
| **Evidence** | Teal | Rectangle | Links to an evidence item stored in the current engagement |
| **Finding** | Purple (light) | Rectangle | Links to a writeup/finding stored in the current engagement |
| **Host** | Dark blue | Rectangle | Links to a host tracked in the current engagement |

#### Reference Node Types (Evidence, Finding, Host)

When you add an **Evidence**, **Finding**, or **Host** node, PTVault opens a picker to select the actual item from your engagement data. The node displays the item's title and key metadata. This creates a live connection between your attack map and the rest of your engagement data.

For **Host** reference nodes, you can mark the host as **Compromised** (checkbox in the node editor). Compromised hosts render with a skull badge and a red header to make them visually distinct in the map.

#### Connector Nodes

Connector nodes render as diamonds and are used to represent decision points or branching logic in the attack path. Use them to show:
- **AND** — all preceding conditions must be true before the next step
- **Parallel paths** — multiple routes that converge at a single outcome

Label the connector with `AND`, `OR`, or a descriptive condition.

### Adding Edges (Connections)

Edges are directed arrows connecting nodes to show the attack flow.

1. Click a **source node** to select it
2. Click **+ Connect** or drag from the node's edge to a target node
3. Optionally enter an **edge label** (e.g., `SMB exploit`, `Pass-the-hash`, `Kerberoast`)
4. Click **Create Edge**

### Repositioning Nodes

Drag nodes to rearrange the layout. Positions are saved when you save the map. Use **Batch Update** to save all position changes at once.

### Editing Nodes and Edges

- Click a node to select it, then click **Edit** to change its label, type, or properties
- Click an edge to select it, then click **Delete** to remove it

---

## Duplicating a Map

Create a variant of an existing map:

1. Open the map
2. Click **Duplicate**
3. Enter a new name
4. The duplicate is created with all nodes and edges

---

## Exporting as SVG

Export the attack map as a scalable SVG image:

1. Open the map
2. Click **Export SVG**
3. The SVG file downloads

SVG exports can be embedded directly in reports. In the [Report Builder](../reporting/report-builder.md), use the **Attack Map** format tool to embed a saved map directly in your report.

---

## Embedding in Reports

Attack maps can be embedded in reports using the **Attack Map** format tool in the Report Builder:

1. Open the Report Builder
2. In the Format Tools section on the left, find **Attack Map**
3. Drag it into the workspace
4. In the editor, select the map to embed from the dropdown
5. The map SVG is embedded in the report preview

---

## Use Cases

| Scenario | Example Map |
|----------|------------|
| External pentest | Internet → Web App (SQLi) → Internal Network → Domain Controller |
| Internal pentest | Workstation → SMB Relay → File Server → Domain Admin |
| Phishing engagement | Phishing Email → Initial Access (VBA macro) → C2 Beacon → Lateral Movement |
| Web application | External → SSRF → Internal Services → RCE → Data Exfiltration |
