# PTVault DAO Quick Reference Card

## Import DAOs

```python
from models.dao import (
    EngagementDAO,
    EvidenceDAO,
    HostDAO,
    ReportDAO,
    TestPlanDAO,
    UserDAO
)
```

## Common Operations

### Create
```python
dao = EngagementDAO()
record_id = dao.create({
    'name': 'Test',
    'status': 'active'
})
```

### Read
```python
# By ID
record = dao.find_by_id(123)

# All records
records = dao.find_all()

# With filters
active_records = dao.find_all({'status': 'active'})

# With pagination
page = dao.find_all(limit=20, offset=0)

# First match
record = dao.find_one({'name': 'Test'})
```

### Update
```python
dao.update(123, {
    'status': 'completed',
    'updated_field': 'value'
})
```

### Delete
```python
dao.delete(123)
```

### Count & Exists
```python
total = dao.count()
active_count = dao.count({'status': 'active'})
exists = dao.exists({'name': 'Test'})
```

## EngagementDAO

```python
engagement_dao = EngagementDAO()

# Find by status
active = engagement_dao.find_by_status('active')
active = engagement_dao.find_active_engagements()

# Statistics
stats = engagement_dao.get_statistics(engagement_id)
# Returns: evidence_count, host_count, findings_count, etc.

# Export data
export_data = engagement_dao.get_export_data(engagement_id)

# Delete with cascade
engagement_dao.delete_with_cascade(engagement_id)
```

## EvidenceDAO

```python
evidence_dao = EvidenceDAO()

# By type
notes = evidence_dao.find_by_type('note')

# By host
host_evidence = evidence_dao.find_by_host(host_id)

# Without hosts (General section)
general = evidence_dao.find_without_hosts()
count = evidence_dao.count_without_hosts()

# By tags
critical = evidence_dao.find_by_tags(['critical', 'urgent'], match_all=True)
any_tag = evidence_dao.find_by_tags(['critical', 'high'], match_all=False)

# Full-text search
results = evidence_dao.search_fulltext('SQL injection', limit=50)

# Advanced filtering
results = evidence_dao.filter_evidence(
    evidence_type='screenshot',
    date_from='2025-01-01',
    severity='high',
    tags=['critical'],
    limit=20
)

# Link to host
evidence_dao.link_to_host(evidence_id, host_id, source='manual')
evidence_dao.unlink_from_host(evidence_id, host_id)
evidence_dao.unlink_all_hosts(evidence_id)

# Get linked hosts
hosts = evidence_dao.get_linked_hosts(evidence_id)

# Bulk operations
evidence_dao.bulk_tag([1, 2, 3], 'reviewed,critical')
evidence_dao.bulk_delete([1, 2, 3])
```

## HostDAO

```python
host_dao = HostDAO()

# By IP
host = host_dao.find_by_ip('192.168.1.1')

# By indicator
rooted = host_dao.find_by_indicator('rooted', True)
flagged = host_dao.find_by_indicator('flagged', True)

# By color
red_hosts = host_dao.find_by_color('red')

# With evidence count
hosts = host_dao.get_with_evidence_count()

# Full details
host = host_dao.get_full_details(host_id)
# Returns: host with evidence[], ports[], credentials[], notes[]

# Port management
port_id = host_dao.add_port(
    host_id=123,
    port=445,
    protocol='tcp',
    state='open',
    service='microsoft-ds',
    version='Windows Server 2019'
)
host_dao.update_port(port_id, {'state': 'closed'})
host_dao.delete_port(port_id)
ports = host_dao.get_ports(host_id)

# Port grid
grid = host_dao.get_port_grid_data()
# Returns: {'hosts': [...], 'ports': [...]}

# Credential management
cred_id = host_dao.add_credential(
    host_id=123,
    username='admin',
    password='password123',
    password_type='cleartext',
    service='ssh'
)
host_dao.update_credential(cred_id, {'password': 'newpass'})
host_dao.delete_credential(cred_id)
creds = host_dao.get_credentials(host_id)

# Note management
note_id = host_dao.add_note(host_id, 'Important note')
host_dao.update_note(note_id, 'Updated note')
host_dao.delete_note(note_id)
notes = host_dao.get_notes(host_id)
```

## ReportDAO

```python
report_dao = ReportDAO()

# By category
writeups = report_dao.find_by_category('Web Application')

# By criticality
critical = report_dao.find_by_criticality('critical')

# Search
results = report_dao.search_writeups('SQL injection')
```

## TestPlanDAO

```python
test_plan_dao = TestPlanDAO()

# With item count
plans = test_plan_dao.find_with_item_count()

# Plan items
items = test_plan_dao.get_plan_items(test_plan_id)

# Add test item
item_id = test_plan_dao.add_test_item(
    test_plan_id=1,
    technique_id='T1003',
    status='pending'
)

# Update status
test_plan_dao.update_test_item_status(
    item_id,
    status='completed',
    output='Test output'
)
```

## UserDAO

```python
user_dao = UserDAO()

# Find by username
user = user_dao.find_by_username('admin')

# Get primary user
user = user_dao.get_primary_user()

# Check if user exists
exists = user_dao.user_exists()

# Update password
user_dao.update_password(user_id, new_hash)
```

## Route Example

```python
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_active_engagement
from models.dao import EvidenceDAO

evidence_bp = Blueprint('evidence', __name__, url_prefix='/api/evidence')
evidence_dao = EvidenceDAO()

@evidence_bp.route('', methods=['GET'])
@require_auth
@require_active_engagement
def list_evidence():
    # Get query parameters
    evidence_type = request.args.get('type')
    tags = request.args.getlist('tags')

    # Use DAO
    if evidence_type:
        evidence = evidence_dao.find_by_type(evidence_type)
    elif tags:
        evidence = evidence_dao.find_by_tags(tags)
    else:
        evidence = evidence_dao.find_all()

    return jsonify(evidence), 200

@evidence_bp.route('/<int:evidence_id>', methods=['GET'])
@require_auth
@require_active_engagement
def get_evidence(evidence_id):
    evidence = evidence_dao.find_by_id(evidence_id)

    if not evidence:
        return jsonify({'error': 'Not found'}), 404

    return jsonify(evidence), 200

@evidence_bp.route('', methods=['POST'])
@require_auth
@require_active_engagement
def create_evidence():
    data = request.get_json()

    if not data.get('title'):
        return jsonify({'error': 'Title required'}), 400

    evidence_id = evidence_dao.create(data)
    evidence = evidence_dao.find_by_id(evidence_id)

    return jsonify(evidence), 201

@evidence_bp.route('/<int:evidence_id>', methods=['PUT'])
@require_auth
@require_active_engagement
def update_evidence(evidence_id):
    data = request.get_json()

    if not evidence_dao.exists({'id': evidence_id}):
        return jsonify({'error': 'Not found'}), 404

    evidence_dao.update(evidence_id, data)
    evidence = evidence_dao.find_by_id(evidence_id)

    return jsonify(evidence), 200

@evidence_bp.route('/<int:evidence_id>', methods=['DELETE'])
@require_auth
@require_active_engagement
def delete_evidence(evidence_id):
    if not evidence_dao.delete(evidence_id):
        return jsonify({'error': 'Not found'}), 404

    return '', 204

@evidence_bp.route('/search', methods=['GET'])
@require_auth
@require_active_engagement
def search_evidence():
    query = request.args.get('q', '')

    results = evidence_dao.search_fulltext(query, limit=50)

    return jsonify(results), 200
```

## Best Practices

### DO
- ✓ Use parameterized queries (DAOs handle this)
- ✓ Let DAOs handle engagement scoping
- ✓ Use type hints for parameters
- ✓ Check if record exists before operations
- ✓ Use specialized methods over generic ones
- ✓ Test DAOs independently of routes

### DON'T
- ✗ Use string interpolation for SQL
- ✗ Bypass DAO layer for database access
- ✗ Modify `g.active_engagement_id` in DAOs
- ✗ Return raw Row objects (use _row_to_dict)
- ✗ Forget to commit after write operations
- ✗ Mix engagement-scoped and unscoped logic

## Common Patterns

### Pattern 1: Find or Create
```python
host = host_dao.find_by_ip(ip)
if not host:
    host_id = host_dao.create({'ip': ip})
    host = host_dao.find_by_id(host_id)
```

### Pattern 2: Update or Create
```python
entity = dao.find_one({'name': name})
if entity:
    dao.update(entity['id'], data)
else:
    dao.create({**data, 'name': name})
```

### Pattern 3: Conditional Delete
```python
if dao.exists({'id': record_id}):
    dao.delete(record_id)
```

### Pattern 4: Bulk Operations
```python
# Filter records
records = dao.find_all({'status': 'pending'})
record_ids = [r['id'] for r in records]

# Bulk update
for record_id in record_ids:
    dao.update(record_id, {'status': 'processed'})
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Database connection not available" | Apply `@require_auth` to route |
| "No active engagement selected" | Apply `@require_active_engagement` |
| "Record not found" with valid ID | Verify `g.active_engagement_id` |
| Slow queries | Add database indexes |
| N+1 queries | Use specialized methods with JOINs |

## Performance Tips

```python
# BAD: N+1 queries
for host in hosts:
    ports = host_dao.get_ports(host['id'])

# GOOD: Get all data at once
hosts = host_dao.get_with_evidence_count()
grid_data = host_dao.get_port_grid_data()

# Use pagination for large result sets
page1 = dao.find_all(limit=50, offset=0)
page2 = dao.find_all(limit=50, offset=50)

# Use filters to reduce result set
recent = dao.find_all(
    filters={'status': 'active'},
    order_by='created_at DESC',
    limit=20
)
```

## Documentation

- **Full Guide**: `docs/DAO_LAYER.md`
- **Implementation Summary**: `docs/DAO_IMPLEMENTATION_SUMMARY.md`
- **Tests**: `tests/dao/test_base_dao.py`
- **Verification**: `verify_dao.py`

---

**Quick Start**: Import DAO → Call methods → Let DAOs handle SQL and engagement scoping
