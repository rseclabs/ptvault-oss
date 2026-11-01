# Host Indicators & Colors

Host indicators let you tag systems with their current status at a glance. Indicators appear as small icon badges in the host list and can be used to filter hosts.

## Setting Indicators

1. Select a host from the host list
2. Click the **Indicators** tab in the host detail panel
3. Check or uncheck indicator checkboxes
4. Changes are saved automatically — no Save button needed

---

## Available Indicators

| Indicator | Icon | When to Use |
|-----------|------|-------------|
| **Rooted** | `#` | Full administrative/root access has been obtained on this system |
| **Shell** | Terminal | A user-level shell has been obtained (but not full root/admin) |
| **Interested** | Star | The host has interesting services, misconfigurations, or attack surface worth exploring |
| **Not Interested** | ✕ | The host has been reviewed and nothing valuable was found |
| **Out of Scope** | ⛔ | This host is outside the agreed test scope — do not test |
| **Flagged** | 🚩 | The host needs review, follow-up, or special attention |
| **Reviewed** | ✓ | Testing and documentation for this host are complete |

### Notes on Usage

- A host can have **multiple indicators** active simultaneously (e.g., "Shell" and "Interested")
- **Rooted** and **Shell** are mutually exclusive in concept but not enforced — use whichever reflects the current highest privilege
- **Out of Scope** is a safety marker — visually prominent to prevent accidental testing
- **Reviewed** helps track completion during long engagements

---

## Color Categories

Assign a color to visually group hosts by network segment, priority, or any other classification scheme.

**Available colors:** White, Yellow, Green, Blue, Red, Purple, Orange, Teal, Cyan, Brown

### Setting a Color

1. Select the host
2. Click the **Indicators** tab
3. Click one of the color buttons in the **Color Category** row
4. To remove a color, click **None** or click the active color again

The color appears as a **vertical bar on the left edge** of the host list entry.

### Suggested Color Conventions

| Color | Common Use |
|-------|-----------|
| Red | Critical / High priority hosts |
| Orange | Compromised hosts |
| Yellow | Medium priority / interesting services |
| Green | Completed / fully documented |
| Blue | Infrastructure (routers, switches, firewalls) |
| Purple | Domain controllers / critical servers |
| Teal | Database servers |
| Cyan | Web servers |
| Brown | Out of scope / excluded |
| White | Default / uncategorized |

> These are suggestions, not rules. Define your own convention and apply it consistently across your team.

---

## Filtering by Indicator

Use the **indicator filter** to focus on specific host categories:

1. Click the **funnel icon** above the host list
2. A filter panel appears with all indicators listed
3. Check one or more indicators
4. The host list updates to show only hosts matching **any** checked indicator
5. Click **Clear All** to reset the filter

**Example workflows:**
- Check **Rooted** and **Shell** to see all compromised hosts at a glance
- Check **Out of Scope** to verify you have not collected evidence on restricted hosts
- Check **Flagged** to review hosts that need follow-up before finalizing the report

---

## Indicators in Reports

Host indicators and colors are captured in JSON exports. When building reports, you can reference indicator data to generate host status summaries.
