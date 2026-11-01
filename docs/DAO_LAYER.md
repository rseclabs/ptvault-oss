# PTVault Data Access Layer (DAO)

## Overview

The Data Access Object (DAO) layer consolidates all SQL queries from route files into a centralized, secure, and maintainable system. This eliminates the 277+ scattered SQL queries and provides:

- **Consistency**: All database operations follow the same patterns
- **Security**: Parameterized queries prevent SQL injection
- **Testability**: DAOs can be tested independently of routes
- **Maintainability**: Schema changes require updating only DAO files
- **Reusability**: Common operations are defined once and reused everywhere

## Architecture

```
Flask Routes (routes/*.py)
    ↓
DAO Layer (models/dao/*.py)
    ↓
SQLite Database
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `BaseDAO` | Common CRUD operations, engagement isolation |
| `EngagementDAO` | Engagement-specific operations and statistics |
| `EvidenceDAO` | Evidence management, search, filtering |
| `HostDAO` | Host, port, credential, note management |
| `ReportDAO` | Writeup and report operations |
| `TestPlanDAO` | Test plan and atomic test management |
| `UserDAO` | User authentication operations |

## Usage Examples

### Basic CRUD Operations

```python
from models.dao import EngagementDAO, EvidenceDAO

# Initialize DAO
engagement_dao = EngagementDAO()

# Create
engagement_id = engagement_dao.create({
    'name': 'ACME Corp Pentest',
    'client_name': 'ACME Corporation',
    'status': 'active'
})

# Read
engagement = engagement_dao.find_by_id(engagement_id)
all_engagements = engagement_dao.find_all()
active_engagements = engagement_dao.find_by_status('active')

# Update
engagement_dao.update(engagement_id, {
    'status': 'completed',
    'end_date': '2025-12-31'
})

# Delete
engagement_dao.delete(engagement_id)

# Count
total = engagement_dao.count()
active_count = engagement_dao.count({'status': 'active'})
```

### Engagement-Scoped Operations

Most DAOs automatically filter by `g.active_engagement_id`:

```python
from models.dao import EvidenceDAO, HostDAO

# These DAOs automatically filter by active engagement
evidence_dao = EvidenceDAO()
host_dao = HostDAO()

# All operations are scoped to current engagement
evidence = evidence_dao.find_all()  # Only current engagement's evidence
host = host_dao.find_by_ip('192.168.1.1')  # Only in current engagement
```

### Specialized Queries

#### Evidence Search

```python
from models.dao import EvidenceDAO

evidence_dao = EvidenceDAO()

# Full-text search
results = evidence_dao.search_fulltext('SQL injection', limit=50)

# Filter by tags
critical_items = evidence_dao.find_by_tags(['critical', 'urgent'], match_all=True)

# Filter by host
host_evidence = evidence_dao.find_by_host(host_id=123)

# Get evidence without hosts (General section)
general_evidence = evidence_dao.find_without_hosts()

# Advanced filtering
results = evidence_dao.filter_evidence(
    evidence_type='screenshot',
    date_from='2025-01-01',
    severity='high',
    tags=['critical'],
    limit=20
)
```

#### Host Management

```python
from models.dao import HostDAO

host_dao = HostDAO()

# Get host with full details
host = host_dao.get_full_details(host_id=123)
# Returns host with nested: evidence[], ports[], credentials[], notes[]

# Find by indicators
rooted_hosts = host_dao.find_by_indicator('rooted', True)
flagged_hosts = host_dao.find_by_indicator('flagged', True)

# Port management
port_id = host_dao.add_port(
    host_id=123,
    port=445,
    protocol='tcp',
    state='open',
    service='microsoft-ds',
    version='Windows Server 2019'
)

ports = host_dao.get_ports(host_id=123)

# Port grid data for visualization
grid_data = host_dao.get_port_grid_data()
# Returns: {'hosts': [...], 'ports': [...]}
```

#### Engagement Statistics

```python
from models.dao import EngagementDAO

engagement_dao = EngagementDAO()

# Get comprehensive statistics
stats = engagement_dao.get_statistics(engagement_id=1)
# Returns:
# {
#   'evidence_count': 150,
#   'evidence_by_type': {'note': 50, 'screenshot': 40, ...},
#   'evidence_by_tool': {'nmap': 10, 'burp': 20, ...},
#   'evidence_by_severity': {'critical': 5, 'high': 15, ...},
#   'host_count': 25,
#   'findings_count': 12,
#   'unique_tags': 30,
#   'files_count': 80
# }
```

## Migrating Routes to Use DAOs

### Before (Direct SQL)

```python
@engagements_bp.route('', methods=['GET'])
@require_auth
def list_engagements():
    status_filter = request.args.get('status')

    cursor = g.db.cursor()

    if status_filter:
        cursor.execute(
            "SELECT * FROM engagements WHERE status = ? ORDER BY created_at DESC",
            (status_filter,)
        )
    else:
        cursor.execute("SELECT * FROM engagements ORDER BY created_at DESC")

    rows = cursor.fetchall()
    engagements = []
    for row in rows:
        engagements.append({
            "id": row[0],
            "name": row[1],
            "client_name": row[2],
            # ... 10+ more fields
        })

    return jsonify(engagements), 200
```

### After (Using DAO)

```python
from models.dao import EngagementDAO

engagement_dao = EngagementDAO()

@engagements_bp.route('', methods=['GET'])
@require_auth
def list_engagements():
    status_filter = request.args.get('status')

    if status_filter:
        engagements = engagement_dao.find_by_status(status_filter)
    else:
        engagements = engagement_dao.find_all(order_by='created_at DESC')

    return jsonify(engagements), 200
```

**Benefits:**
- 20+ lines → 10 lines
- No manual row-to-dict conversion
- Type hints for better IDE support
- Testable independently
- Reusable across routes

## Creating a New DAO

### 1. Extend BaseDAO

```python
# models/dao/my_entity_dao.py

from models.dao.base import BaseDAO
from typing import List, Dict, Any

class MyEntityDAO(BaseDAO):
    """DAO for MyEntity operations."""

    def __init__(self):
        # Set engagement_scoped=True if entity is per-engagement
        super().__init__('my_entities', engagement_scoped=True)

    def find_by_custom_field(self, value: str) -> List[Dict[str, Any]]:
        """Find entities by custom field."""
        return self.find_all({'custom_field': value})

    def custom_query(self, param: int) -> List[Dict[str, Any]]:
        """Custom query not covered by BaseDAO."""
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT * FROM my_entities
            WHERE engagement_id = ? AND custom_condition
            ORDER BY created_at DESC
        ''', (self.engagement_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]
```

### 2. Register in __init__.py

```python
# models/dao/__init__.py

from models.dao.my_entity_dao import MyEntityDAO

__all__ = [
    # ... existing DAOs
    'MyEntityDAO',
]
```

### 3. Use in Routes

```python
from models.dao import MyEntityDAO

my_entity_dao = MyEntityDAO()

@my_blueprint.route('', methods=['GET'])
@require_auth
def list_my_entities():
    entities = my_entity_dao.find_all()
    return jsonify(entities), 200
```

## Testing DAOs

### Unit Tests

```python
# tests/dao/test_my_entity_dao.py

import pytest
from models.dao import MyEntityDAO

@pytest.fixture
def dao(app, db_connection):
    """Create DAO instance with test context."""
    with app.test_request_context():
        g.db = db_connection
        g.active_engagement_id = 1
        yield MyEntityDAO()

def test_find_by_custom_field(dao):
    """Test custom query method."""
    # Create test data
    dao.create({'name': 'Test', 'custom_field': 'value1'})
    dao.create({'name': 'Test2', 'custom_field': 'value2'})

    # Test query
    results = dao.find_by_custom_field('value1')

    assert len(results) == 1
    assert results[0]['custom_field'] == 'value1'

def test_engagement_isolation(dao):
    """Test data isolation between engagements."""
    # Create in engagement 1
    g.active_engagement_id = 1
    dao.create({'name': 'Eng1'})

    # Create in engagement 2
    g.active_engagement_id = 2
    dao.create({'name': 'Eng2'})

    # Verify isolation
    g.active_engagement_id = 1
    items = dao.find_all()
    assert len(items) == 1
    assert items[0]['name'] == 'Eng1'
```

### Integration Tests

```python
# tests/routes/test_my_entity_routes.py

def test_list_endpoint(client):
    """Test list endpoint uses DAO correctly."""
    # Setup test data via DAO
    dao = MyEntityDAO()
    dao.create({'name': 'Test Item'})

    # Test endpoint
    response = client.get('/api/my-entities')
    assert response.status_code == 200

    data = response.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'Test Item'
```

## Common Patterns

### Pattern 1: Find with Related Data

```python
def get_with_related(self, entity_id: int) -> Dict[str, Any]:
    """Get entity with related data from other tables."""
    entity = self.find_by_id(entity_id)
    if not entity:
        return None

    cursor = self.db.cursor()

    # Get related items
    cursor.execute('''
        SELECT * FROM related_table
        WHERE entity_id = ?
    ''', (entity_id,))

    entity['related_items'] = [self._row_to_dict(row)
                               for row in cursor.fetchall()]

    return entity
```

### Pattern 2: Bulk Operations

```python
def bulk_update_status(self, entity_ids: List[int], status: str) -> int:
    """Update status for multiple entities."""
    if not entity_ids:
        return 0

    cursor = self.db.cursor()

    placeholders = ','.join('?' * len(entity_ids))
    cursor.execute(f'''
        UPDATE my_entities
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders}) AND engagement_id = ?
    ''', (status, *entity_ids, self.engagement_id))

    self.db.commit()
    return cursor.rowcount
```

### Pattern 3: Aggregation Queries

```python
def get_summary(self) -> Dict[str, Any]:
    """Get summary statistics."""
    cursor = self.db.cursor()

    cursor.execute('''
        SELECT
            status,
            COUNT(*) as count,
            AVG(score) as avg_score
        FROM my_entities
        WHERE engagement_id = ?
        GROUP BY status
    ''', (self.engagement_id,))

    return {
        row['status']: {
            'count': row['count'],
            'avg_score': row['avg_score']
        }
        for row in cursor.fetchall()
    }
```

## Best Practices

### DO

- Use parameterized queries (`?` placeholders)
- Add type hints to all methods
- Document method parameters and return types
- Log significant operations (create, update, delete)
- Return consistent data types (dicts from `_row_to_dict`)
- Commit after write operations
- Test engagement isolation for scoped DAOs

### DON'T

- Use string interpolation for SQL (SQL injection risk)
- Return raw Row objects (use `_row_to_dict`)
- Forget to commit after write operations
- Mix engagement-scoped and unscoped logic
- Expose internal database errors to routes (handle gracefully)
- Create DAOs with side effects in `__init__`

## Performance Considerations

### Query Optimization

```python
# BAD: N+1 query problem
for entity in dao.find_all():
    related = related_dao.find_by_entity(entity['id'])  # Query per entity

# GOOD: Join query
entities = dao.find_all_with_related()  # Single query with JOIN
```

### Pagination

```python
# Always use limit/offset for large result sets
results = dao.find_all(limit=50, offset=0)
```

### Indexes

Ensure indexes exist for:
- Foreign keys
- Frequently filtered columns
- Sort columns

```sql
CREATE INDEX IF NOT EXISTS idx_evidence_engagement
    ON evidence(engagement_id);
CREATE INDEX IF NOT EXISTS idx_evidence_created
    ON evidence(created_at DESC);
```

## Migration Checklist

When converting a route to use DAOs:

- [ ] Identify all SQL queries in the route
- [ ] Check if DAO method exists or create new one
- [ ] Replace `cursor.execute()` with DAO method calls
- [ ] Remove manual row-to-dict conversion
- [ ] Verify engagement isolation is maintained
- [ ] Add unit tests for new DAO methods
- [ ] Update integration tests if needed
- [ ] Test in development environment
- [ ] Update API documentation if behavior changes

## Troubleshooting

### "Database connection not available"

**Cause**: DAO accessed outside Flask request context

**Solution**: Ensure `@require_auth` middleware is applied to route

### "No active engagement selected"

**Cause**: Engagement-scoped DAO used without setting `g.active_engagement_id`

**Solution**: Apply `@require_active_engagement` decorator or set manually

### "Record not found" with valid ID

**Cause**: Record exists but belongs to different engagement

**Solution**: Verify `g.active_engagement_id` is set correctly

### Slow queries

**Cause**: Missing indexes or N+1 query problem

**Solution**: Add indexes, use JOINs instead of multiple queries

## Further Reading

- `models/dao/base.py` - BaseDAO implementation
- `tests/dao/test_base_dao.py` - Comprehensive tests
- `routes/` - Example DAO usage in routes
- SQLite documentation - https://www.sqlite.org/docs.html
