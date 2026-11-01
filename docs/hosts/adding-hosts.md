# Adding & Managing Hosts

## Adding a Host Manually

1. Click the **Hosts** tab to ensure you are in the Hosts section
2. Click **+ Add Host** above the host list
3. Enter the **IP address** (required)
4. Optionally enter a **hostname** (e.g., `webserver.acme.local`) and **OS** (e.g., `Windows Server 2019`)
5. Click **Add**

The new host appears in the host list. Click it to open the detail panel on the right.

---

## Importing Hosts from Tool Output

The fastest way to populate hosts is by importing scan results:

- **Nmap XML**: Automatically creates hosts with all open ports and service data → [Nmap Parser](../tool-parsers/nmap.md)
- **Nessus**: Creates hosts with vulnerability findings → [Nessus Parser](../tool-parsers/nessus.md)
- **Other tools**: See [Tool Parsers](../tool-parsers/README.md)

---

## Editing a Host

1. Click the host in the host list to select it
2. In the detail panel header, click the **edit icon**
3. Update the IP address, hostname, or OS
4. Click **Save**

---

## Deleting a Host

1. Select the host in the list
2. Click the **delete icon** in the detail panel header
3. Confirm the deletion

> **Note:** Deleting a host unlinks its associated evidence but does not delete the evidence itself. Evidence moves to the "General" (unlinked) section.

---

## Searching Hosts

The **search bar** above the host list performs real-time search as you type. It searches across:

| Searched Fields | Examples |
|-----------------|---------|
| IP address | `192.168.1` matches all hosts in that subnet |
| Hostname | `dc01`, `webserver` |
| Host notes content | Any text in notes |
| Evidence titles | Evidence items linked to the host |
| Evidence content | Text within evidence notes |
| Port numbers | `3389` shows hosts with RDP |
| Service names | `ssh`, `http`, `smb` |
| Credential usernames | `administrator`, `root` |
| Scan metadata | Nessus plugin names, CVE IDs |

---

## Filtering Hosts by Indicator

Click the **funnel icon** above the host list to open the indicator filter panel.

Select one or more indicators to show only hosts that match **any** of the selected indicators (OR logic):

- Rooted
- Shell
- Interested
- Not Interested
- Out of Scope
- Flagged
- Reviewed

Click **Clear All** to remove all filters and show all hosts.

See [Host Indicators](./host-indicators.md) for indicator descriptions.

---

## Host List Display

Each host in the list shows:
- **Color bar**: Left edge colored bar if a color category is assigned
- **IP address**: Primary identifier
- **Hostname**: Secondary label (if set)
- **Indicator badges**: Small icons for each active indicator

Click any host to load its details in the right panel.
