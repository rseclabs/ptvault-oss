# Host Visual Indicators Feature

This document describes the Host Visual Indicators feature added to PTVault.

## Overview

The Host Visual Indicators feature allows you to mark and categorize hosts with visual indicators during penetration testing engagements. This makes it easier to track the status and significance of different hosts at a glance.

## Indicators

The following indicators are available:

| Indicator | Icon | Description |
|-----------|------|-------------|
| **Rooted** | `#` (hash) | Host has been compromised with root/administrator privileges |
| **Shell** | Terminal icon | A shell has been obtained on this host |
| **Interested** | Star icon | Host has interesting ports or services worth investigating |
| **Not Interested** | X-circle icon | Nothing interesting found on this host |
| **Out of Scope** | Ban icon | This host is out of scope - do not touch |
| **Flagged** | Flag icon | Host flagged for further review |
| **Reviewed** | Check-circle icon | Host has been fully reviewed |
| **Color Category** | Colored bar | Assign a color category (white, yellow, green, blue, red, purple, orange, teal, cyan, brown) |

## Usage

### Setting Indicators

1. Navigate to the Evidence tab and select a host from the host list
2. In the host details panel, you'll see a "Host Indicators" section at the top
3. Check the boxes for applicable indicators
4. Select a color category by clicking one of the color buttons
5. Changes are saved automatically

### Viewing Indicators

- **Host List**: Indicator badges appear below the hostname in the host list
- **Color Badge**: A colored vertical bar appears on the left edge of host items with a color category

### Filtering Hosts

1. Click the filter icon (funnel) above the host list
2. Check the indicators you want to filter by
3. The host list will show only hosts matching ANY of the selected indicators
4. Click "Clear All" to remove all filters

## Technical Details

### Database Schema

The following columns have been added to the `hosts` table:

```sql
rooted INTEGER DEFAULT 0
shell INTEGER DEFAULT 0
interested INTEGER DEFAULT 0
not_interested INTEGER DEFAULT 0
out_of_scope INTEGER DEFAULT 0
flagged INTEGER DEFAULT 0
reviewed INTEGER DEFAULT 0
color_category TEXT DEFAULT NULL
```

### Migration

For existing databases, run the migration script:

```bash
python3 migrate_indicators.py
```

Or run migrations through the application:

```python
from models.database import run_migrations
run_migrations()
```

### API Endpoints

The existing host update endpoint has been extended to support indicator fields:

```http
PUT /api/hosts/<host_id>
Content-Type: application/json

{
  "rooted": true,
  "shell": false,
  "interested": true,
  "color_category": "red"
}
```

### Frontend Components

**Files Modified:**
- `templates/dashboard.html` - Added indicators section and filter panel
- `static/css/main.css` - Added indicator styling with dark mode support
- `static/js/hosts.js` - Added indicator management functions
- Integrated Lucide Icons for modern, consistent iconography

**Key Functions:**
- `HostManager.updateIndicator(indicator, value)` - Update a single indicator
- `HostManager.updateColorCategory(color)` - Update host color category
- `HostManager.applyFilters()` - Filter hosts by indicators
- `HostManager.renderIndicatorBadges(host)` - Render indicator badges in host list

## UI Features

### Dark Mode Support

All indicator colors and UI elements support both light and dark themes automatically.

### Responsive Design

The indicators section adapts to different screen sizes with a responsive grid layout.

### Icon Library

Uses Lucide Icons (https://lucide.dev) for crisp, modern iconography that scales well at any size.

## Best Practices

1. **Out of Scope**: Always mark out-of-scope hosts immediately to avoid accidental testing
2. **Color Categories**: Use consistent colors across your team (e.g., red = critical, yellow = medium priority)
3. **Reviewed**: Mark hosts as reviewed only after thorough testing to track progress
4. **Rooted vs Shell**: Rooted indicates full admin access, Shell indicates user-level access
5. **Filtering**: Use filters to quickly focus on specific host categories during different phases of testing

## Examples

### Typical Workflow

1. Initial reconnaissance: Mark interesting hosts with "Interested"
2. Exploitation: Mark compromised hosts with "Shell" or "Rooted"
3. Post-exploitation: Add color categories for different network segments
4. Final review: Mark each host as "Reviewed" after documentation
5. Use filters to ensure all critical hosts (rooted, flagged) are documented

### Color Category Suggestions

- **Red**: Critical/High priority hosts
- **Orange**: Compromised hosts
- **Yellow**: Medium priority / interesting services
- **Green**: Completed/documented
- **Blue**: Infrastructure / routers / switches
- **Purple**: Domain controllers / critical servers
- **Teal**: Database servers
- **Cyan**: Web servers
- **Brown**: Out of scope / excluded

## Troubleshooting

### Icons not appearing

Ensure Lucide Icons is loaded:
```javascript
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}
```

### Indicators not saving

Check browser console for API errors. Verify the host belongs to the active engagement.

### Filters not working

Clear all filters and reapply. Check that hosts have the indicators set correctly.

## Future Enhancements

Potential future improvements:
- Custom indicator definitions
- Bulk indicator operations
- Indicator-based reporting
- Indicator history/audit log
- AND logic filter mode (in addition to OR)
