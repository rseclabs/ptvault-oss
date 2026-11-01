# Ports & Credentials

## Open Ports

The **Open Ports** tab displays all discovered ports for a selected host. Ports are automatically populated when importing tool output (Nmap, Nessus) and can also be added manually.

### Viewing Ports

1. Select a host from the host list
2. Click the **Open Ports** tab
3. The ports table shows: Port, Protocol, State, Service, Version

| Column | Description |
|--------|-------------|
| **Port** | Port number (e.g., `80`, `443`, `3389`) |
| **Protocol** | `tcp` or `udp` |
| **State** | `open`, `filtered`, or `closed` |
| **Service** | Service name (e.g., `http`, `ssh`, `rdp`) |
| **Version** | Service banner/version string (e.g., `Apache httpd 2.4.51`) |

### Adding a Port Manually

1. Click **+ Add Port** in the Open Ports tab
2. Enter:
   - Port number (required)
   - Protocol (tcp/udp)
   - State (open/filtered)
   - Service name
   - Version string
3. Click **Save**

### Editing a Port

Click the **edit icon** next to a port entry to modify its service name, version, or state.

### Deleting a Port

Click the **delete icon** next to a port entry to remove it.

### Automatic Population from Tool Imports

When you import an Nmap XML file, all discovered open and filtered ports are automatically created for each host. The service name and version are extracted from the Nmap service detection output.

See [Nmap Parser](../tool-parsers/nmap.md) for details.

---

## Credentials

The **Credentials** tab stores discovered credentials for a selected host. This includes passwords, password hashes, API keys, and other authentication data.

### Viewing Credentials

1. Select a host from the host list
2. Click the **Credentials** tab
3. The table shows all stored credentials

### Credential Fields

| Field | Description |
|-------|-------------|
| **Username** | The account name (e.g., `administrator`, `root`, `sqlsvc`) |
| **Password** | The plaintext password (if recovered) |
| **Password Type** | `cleartext` or `hash` |
| **Hash Type** | Hash algorithm if type is hash (e.g., `NTLM`, `MD5`, `SHA-256`, `bcrypt`) |
| **Service** | The service this credential applies to (e.g., `SMB`, `SSH`, `MSSQL`, `VPN`) |
| **Notes** | Any additional context (source, where found, crack status) |

### Adding a Credential

1. Click **+ Add Credential** in the Credentials tab
2. Fill in the relevant fields
3. Click **Save**

### Editing a Credential

Click the **edit icon** next to a credential to modify it.

### Deleting a Credential

Click the **delete icon** next to a credential to remove it.

---

## General Section Credentials

The **General** pseudo-host has its own Credentials tab for credentials not tied to a specific host — for example:
- Domain credentials from a phishing attack
- Credentials found in configuration files before host attribution
- Credentials used for initial access from an external starting point

Access the General section by clicking **General** at the top of the host list.

---

## Security Note

Credentials are stored in the PTVault database. If database encryption is enabled (Admin > Settings > Database Encryption), credentials are encrypted at rest using SQLCipher. We strongly recommend enabling encryption when storing sensitive credentials.

See [Database Encryption](../admin/database-encryption.md).
