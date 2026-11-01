# Port Grid

The **Port Grid** provides a bird's-eye view of all open and filtered ports across every host in the active engagement.

## Accessing the Port Grid

Click the **Port Grid** tab in the top navigation bar. The grid loads all port data for the current engagement in a single API call.

## Reading the Grid

| Element | Description |
|---------|-------------|
| **Rows** | Individual hosts (IP addresses) |
| **Columns** | Unique port/protocol combinations discovered across all hosts |
| **Green cell** | Port is **open** on that host |
| **Orange cell** | Port is **filtered** on that host |
| **Empty cell** | Port was not discovered on that host (closed or not scanned) |

Port columns are sorted numerically and only include ports that appear on at least one host.

## Use Cases

### Identify Common Services

Quickly see which hosts share the same services:
- All hosts with port 22 (SSH) open
- All hosts with port 3389 (RDP) open
- All hosts with port 445 (SMB) open

### Spot Unusual Open Ports

Columns with only one or two green cells may indicate unusual services worth investigating.

### Plan Lateral Movement

Identify hosts that are accessible from already-compromised systems by looking at which ports are open on multiple machines.

### Track Scan Coverage

Empty rows (no ports) indicate hosts that have been added but not yet scanned. Dense rows indicate thoroughly enumerated hosts.

## Data Source

The Port Grid displays port data from the `host_ports` table — the same data shown in each host's **Open Ports** tab. Any ports added manually or imported from tool output appear here.

## Tips

- Import an Nmap XML file first to populate the grid with comprehensive port data
- Use the grid alongside the [Hosts](../hosts/README.md) section: click a host in the grid context to jump to its detail
- The grid is a read-only view — use the host's Open Ports tab to add or edit individual ports
