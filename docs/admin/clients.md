# Client Management

The Clients tab in the Admin panel maintains a reusable database of client organizations. Client records exist independently of any engagement, so contact details and organizational information are available across projects without re-entering them.

**Access:** Admin only

---

## Accessing the Clients Tab

1. Click the **Admin** tab in the top navigation bar
2. Select **Clients** in the left sidebar

---

## Client Fields

| Field | Required | Description |
|-------|:--------:|-------------|
| **Name** | Yes | Organization name (e.g., "Acme Corporation") |
| **Admin Contact Name** | No | Name of the primary administrative contact |
| **Admin Contact Email** | No | Email address of the administrative contact |
| **Admin Contact Phone** | No | Phone number of the administrative contact |
| **Technical Contact Name** | No | Name of the technical point of contact |
| **Technical Contact Email** | No | Email address of the technical contact |
| **Technical Contact Phone** | No | Phone number of the technical contact |
| **Address** | No | Mailing or physical address |
| **Website** | No | Organization website URL |
| **Notes** | No | Free-form notes about the client |

---

## Creating a Client

1. Click **+ New Client**
2. Enter the client name (required) and any additional contact details
3. Click **Save**

---

## Editing a Client

1. Find the client in the list
2. Click the **Edit** icon
3. Modify the fields as needed
4. Click **Save**

---

## Deleting a Client

1. Find the client in the list
2. Click the **Delete** icon
3. Confirm the deletion

> **Note:** Deleting a client record does not delete any engagements linked to that client. Existing engagements retain their client name; the dropdown reference is simply cleared.

---

## Linking a Client to an Engagement

When creating or editing an engagement, a **Client** dropdown is available. Select a client from the dropdown to associate the engagement with that client record.

1. Go to **Engagements** and click **+ New Engagement**, or open an existing engagement for editing in **Admin > Engagements**
2. In the engagement form, find the **Client** dropdown
3. Select the appropriate client
4. Save the engagement

The selected client's name is stored with the engagement and displayed on engagement cards.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/clients` | List all clients |
| `POST` | `/api/clients` | Create a new client |
| `PUT` | `/api/clients/<id>` | Update a client |
| `DELETE` | `/api/clients/<id>` | Delete a client |
| `GET` | `/api/clients/options` | Lightweight list for dropdowns (id + name only) |

All endpoints require authentication. Admin role required for write operations.

```bash
# List all clients
curl -b cookies.txt http://localhost:5001/api/clients

# Create a client
curl -b cookies.txt -X POST http://localhost:5001/api/clients \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "admin_contact_name": "Jane Smith",
    "admin_contact_email": "jane.smith@acme.com",
    "website": "https://acme.com"
  }'
```
