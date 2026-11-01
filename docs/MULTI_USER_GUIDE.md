# PTVault Multi-User Guide

PTVault now supports multiple users with role-based access control (RBAC), enabling teams to collaborate on penetration testing engagements securely.

## Table of Contents

- [Overview](#overview)
- [User Roles](#user-roles)
- [Getting Started](#getting-started)
- [User Management](#user-management)
- [Engagement Team Management](#engagement-team-management)
- [Permissions](#permissions)
- [Audit Logging](#audit-logging)
- [API Reference](#api-reference)

---

## Overview

### Key Features

- **Multi-User Support**: Multiple users can work on different engagements simultaneously
- **Role-Based Access Control**: System-level and engagement-level roles
- **Team Collaboration**: Add team members to specific engagements
- **Audit Logging**: Track all user actions for security and compliance
- **Session Management**: JWT-based authentication with secure httpOnly cookies

### Architecture

```
System Level (PTVault Instance)
├── Admin Users (full system access)
├── Tester Users (can create engagements, access assigned engagements)
└── Viewer Users (read-only access to assigned engagements)

Engagement Level (Per Project)
├── Owners (full engagement control)
├── Editors (can modify evidence, hosts, reports)
└── Viewers (read-only access)
```

---

## User Roles

### System-Level Roles

| Role | Permissions |
|------|-------------|
| **Admin** | - Full system access<br>- Create/manage users<br>- Access all engagements<br>- System configuration |
| **Tester** | - Create new engagements<br>- Access assigned engagements<br>- Normal user operations |
| **Viewer** | - Read-only access to assigned engagements<br>- Cannot create or modify data |

### Engagement-Level Roles

| Role | Permissions |
|------|-------------|
| **Owner** | - Full engagement control<br>- Add/remove team members<br>- Delete engagement<br>- All editor permissions |
| **Editor** | - Create/modify evidence<br>- Create/modify hosts<br>- Create/modify reports<br>- View all engagement data |
| **Viewer** | - View evidence<br>- View hosts<br>- View reports<br>- Cannot modify anything |

---

## Getting Started

### Initial Setup

1. **First-Time Setup**: Create the admin account

```bash
curl -X POST http://localhost:5001/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "master_password": "YourSecurePassword123!",
    "username": "admin",
    "email": "admin@company.com",
    "full_name": "System Administrator"
  }'
```

2. **Login**

```bash
# With username/password
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "YourSecurePassword123!"
  }'

# Legacy mode (backward compatibility)
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "master_password": "YourSecurePassword123!"
  }'
```

---

## User Management

### List All Users (Admin Only)

```bash
curl -X GET http://localhost:5001/api/users \
  -H "Cookie: auth_token=YOUR_TOKEN"
```

Response:
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@company.com",
      "full_name": "System Administrator",
      "role": "admin",
      "is_active": 1,
      "created_at": "2026-02-09T12:00:00"
    }
  ]
}
```

### Create New User (Admin Only)

```bash
curl -X POST http://localhost:5001/api/users \
  -H "Cookie: auth_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jdoe",
    "email": "jdoe@company.com",
    "password": "SecurePass123!",
    "role": "tester",
    "full_name": "John Doe"
  }'
```

### Update User

```bash
# Users can update their own profile
curl -X PUT http://localhost:5001/api/users/2 \
  -H "Cookie: auth_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith",
    "email": "jsmith@company.com"
  }'

# Admins can change roles
curl -X PUT http://localhost:5001/api/users/2 \
  -H "Cookie: auth_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin"
  }'
```

### Deactivate User (Admin Only)

```bash
curl -X DELETE http://localhost:5001/api/users/2 \
  -H "Cookie: auth_token=YOUR_TOKEN"
```

### Get Current User Profile

```bash
curl -X GET http://localhost:5001/api/users/me \
  -H "Cookie: auth_token=YOUR_TOKEN"
```

---

## Engagement Team Management

### List Engagement Members

```bash
curl -X GET http://localhost:5001/api/engagements/1/members \
  -H "Cookie: auth_token=YOUR_TOKEN"
```

Response:
```json
{
  "members": [
    {
      "id": 1,
      "user_id": 1,
      "username": "admin",
      "email": "admin@company.com",
      "full_name": "System Administrator",
      "system_role": "admin",
      "engagement_role": "owner",
      "added_at": "2026-02-09T12:00:00",
      "added_by_username": "admin"
    }
  ]
}
```

### Add Team Member (Owner Only)

```bash
curl -X POST http://localhost:5001/api/engagements/1/members \
  -H "Cookie: auth_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 2,
    "role": "editor"
  }'
```

### Update Member Role (Owner Only)

```bash
curl -X PUT http://localhost:5001/api/engagements/1/members/2 \
  -H "Cookie: auth_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "viewer"
  }'
```

### Remove Team Member (Owner Only)

```bash
curl -X DELETE http://localhost:5001/api/engagements/1/members/2 \
  -H "Cookie: auth_token=YOUR_TOKEN"
```

---

## Permissions

### System-Level Permissions

| Action | Admin | Tester | Viewer |
|--------|-------|--------|--------|
| Create users | ✓ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ |
| Create engagement | ✓ | ✓ | ✗ |
| View all engagements | ✓ | Own only | Own only |

### Engagement-Level Permissions

| Action | Owner | Editor | Viewer |
|--------|-------|--------|--------|
| Add members | ✓ | ✗ | ✗ |
| Remove members | ✓ | ✗ | ✗ |
| Delete engagement | ✓ | ✗ | ✗ |
| Create evidence | ✓ | ✓ | ✗ |
| Edit evidence | ✓ | ✓ | ✗ |
| Delete evidence | ✓ | ✓ | ✗ |
| View evidence | ✓ | ✓ | ✓ |
| Create hosts | ✓ | ✓ | ✗ |
| Edit hosts | ✓ | ✓ | ✗ |
| Delete hosts | ✓ | ✓ | ✗ |
| View hosts | ✓ | ✓ | ✓ |
| Generate reports | ✓ | ✓ | ✓ |
| Export data | ✓ | ✓ | ✓ |

### Special Rules

- **Admins**: Automatically have owner-level access to all engagements
- **Last Owner**: Cannot remove/downgrade the last owner of an engagement
- **Self-Management**: Users cannot deactivate themselves

---

## Audit Logging

All user actions are logged for security and compliance.

### Tracked Actions

- **create**: Resource creation
- **update**: Resource modification
- **delete**: Resource deletion
- **view**: Viewing sensitive resources
- **export**: Data export operations

### Tracked Resources

- `user` - User accounts
- `engagement` - Engagement projects
- `evidence` - Evidence items
- `host` - Target hosts
- `report` - Generated reports
- `member` - Engagement member assignments

### Audit Log Structure

```json
{
  "id": 123,
  "user_id": 1,
  "username": "admin",
  "engagement_id": 5,
  "action": "create",
  "resource_type": "evidence",
  "resource_id": 456,
  "details": {
    "title": "Nmap Scan Results",
    "type": "tool_output"
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "timestamp": "2026-02-09T14:30:00"
}
```

### Using Audit Logger

```python
from utils.audit_logger import audit_create, audit_update, audit_delete

# Log evidence creation
audit_create('evidence', evidence_id, engagement_id=g.active_engagement_id,
            title='Nmap Scan', type='tool_output')

# Log engagement update
audit_update('engagement', engagement_id, name='Updated Name')

# Log evidence deletion
audit_delete('evidence', evidence_id, engagement_id=g.active_engagement_id,
            reason='duplicate')
```

---

## API Reference

### Authentication Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/setup` | None | Initial admin setup |
| POST | `/api/auth/login` | None | User login |
| POST | `/api/auth/logout` | None | User logout |

### User Management Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users` | Admin | List all users |
| POST | `/api/users` | Admin | Create user |
| GET | `/api/users/:id` | Self/Admin | Get user details |
| PUT | `/api/users/:id` | Self/Admin | Update user |
| DELETE | `/api/users/:id` | Admin | Deactivate user |
| POST | `/api/users/:id/activate` | Admin | Activate user |
| GET | `/api/users/me` | Auth | Get current user |
| GET | `/api/users/me/engagements` | Auth | Get user's engagements |

### Engagement Members Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/engagements/:id/members` | Viewer+ | List members |
| POST | `/api/engagements/:id/members` | Owner | Add member |
| PUT | `/api/engagements/:id/members/:mid` | Owner | Update member role |
| DELETE | `/api/engagements/:id/members/:mid` | Owner | Remove member |

---

## Migration from Single-User

Existing PTVault installations are automatically migrated:

1. **Backup**: Always backup your database before upgrading
2. **Migration**: Run migrations on startup
   ```bash
   python -c "from models.database import run_migrations; run_migrations()"
   ```
3. **Existing User**: Becomes the admin user with username `admin`
4. **Existing Engagements**: Admin is automatically added as owner

### Compatibility

- **Legacy Login**: The old `master_password` login still works
- **Single-User Mode**: If only one user exists, behavior is unchanged
- **API Compatibility**: All existing API endpoints remain functional

---

## Security Best Practices

1. **Strong Passwords**: Enforce 8+ character passwords
2. **Role Assignment**: Use principle of least privilege
3. **Regular Audits**: Review audit logs periodically
4. **User Deactivation**: Deactivate users immediately upon departure
5. **HTTPS**: Always use HTTPS in production
6. **Session Timeout**: JWT tokens expire after 24 hours (configurable)

---

## Troubleshooting

### Migration Issues

```bash
# Check migration status
python -c "from models.migrations import get_migration_status; \
           from models.database import get_db_connection; \
           print(get_migration_status(get_db_connection()))"

# Force migration re-run
python -c "from models.database import run_migrations; run_migrations()"
```

### User Can't Access Engagement

1. Check user is a member: `GET /api/engagements/:id/members`
2. Check user is active: `GET /api/users/:id`
3. Check engagement exists: `GET /api/engagements/:id`

### Permission Denied Errors

1. Verify user role: `GET /api/users/me`
2. Verify engagement role: `GET /api/engagements/:id/members`
3. Check required permission level in API docs

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/rseclabs/ptvault-oss/issues
- Documentation: See README.md and DEPLOYMENT.md
