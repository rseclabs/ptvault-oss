"""Generate realistic Nmap and Nessus XML scan files for the demo engagement.

Writes:
    sample_data/files/acme_internal_nmap.xml   (importable as nmap tool output)
    sample_data/files/acme_internal.nessus     (importable as nessus tool output)

Both files cover the same fictional /24 network. The Nmap file lists 20 hosts
with realistic service banners. The Nessus file covers a subset of those hosts
with a mix of Critical/High/Medium/Low/Info findings, real-looking CVE numbers,
and CVSS vectors.

Everything here is fictional: private 10.0.5.0/24 addresses and the acme.local
domain. Output is deterministic (fixed scan date), so regenerating gives the
same files.

Usage from the repo root:
    ./venv/bin/python sample_data/generate_scans.py

load_sample.py imports both files; they can also be imported by hand with
Evidence -> Import.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.dom import minidom

SCRIPT_DIR = Path(__file__).resolve().parent
SCANS_DIR = SCRIPT_DIR / "files"

# ---------------------------------------------------------------------------
# Host inventory shared by both files
# ---------------------------------------------------------------------------
# (ip, hostname, os, mac, [(port, proto, service, product, version, extrainfo), ...])
HOSTS = [
    ("10.0.5.10", "DC01.acme.local",
     "Microsoft Windows Server 2019 Standard 17763",
     "00:50:56:AA:BB:0A",
     [
         (53, "tcp", "domain", "Microsoft DNS", "6.1.7601", None),
         (88, "tcp", "kerberos-sec", "Microsoft Windows Kerberos", None, None),
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (139, "tcp", "netbios-ssn", "Microsoft Windows netbios-ssn", None, None),
         (389, "tcp", "ldap", "Microsoft Windows Active Directory LDAP",
          None, "Domain: acme.local"),
         (445, "tcp", "microsoft-ds", "Microsoft Windows Server 2019 - 2022 SMB",
          None, None),
         (464, "tcp", "kpasswd5", None, None, None),
         (636, "tcp", "tcpwrapped", None, None, None),
         (3268, "tcp", "ldap", "Microsoft Windows AD LDAP",
          None, "Domain: acme.local"),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services",
          None, None),
         (5985, "tcp", "wsman", "Microsoft HTTPAPI httpd 2.0", None,
          "SSDP/UPnP"),
     ]),
    ("10.0.5.11", "DC02.acme.local",
     "Microsoft Windows Server 2019 Standard 17763",
     "00:50:56:AA:BB:0B",
     [
         (53, "tcp", "domain", "Microsoft DNS", "6.1.7601", None),
         (88, "tcp", "kerberos-sec", "Microsoft Windows Kerberos", None, None),
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (139, "tcp", "netbios-ssn", "Microsoft Windows netbios-ssn", None, None),
         (389, "tcp", "ldap", "Microsoft Windows AD LDAP",
          None, "Domain: acme.local"),
         (445, "tcp", "microsoft-ds", "Microsoft Windows Server 2019 - 2022 SMB",
          None, None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services",
          None, None),
     ]),
    ("10.0.5.12", "EXCHANGE01.acme.local",
     "Microsoft Windows Server 2016 Standard",
     "00:50:56:AA:BB:0C",
     [
         (25, "tcp", "smtp", "Microsoft Exchange smtpd", "15.1", None),
         (80, "tcp", "http", "Microsoft IIS httpd", "10.0", None),
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (143, "tcp", "imap", "Microsoft Exchange imapd", None, None),
         (443, "tcp", "ssl/http", "Microsoft IIS httpd", "10.0", None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows Server 2016 SMB", None, None),
         (587, "tcp", "smtp", "Microsoft Exchange smtpd", "15.1", None),
         (993, "tcp", "ssl/imap", "Microsoft Exchange imapd", None, None),
         (995, "tcp", "ssl/pop3", "Microsoft Exchange pop3d", None, None),
     ]),
    ("10.0.5.13", "SQL-PROD01.acme.local",
     "Microsoft Windows Server 2019 Standard",
     "00:50:56:AA:BB:0D",
     [
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (139, "tcp", "netbios-ssn", "Microsoft Windows netbios-ssn", None, None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (1433, "tcp", "ms-sql-s", "Microsoft SQL Server", "2019 15.00.2000", None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.14", "SQL-PROD02.acme.local",
     "Microsoft Windows Server 2019 Standard",
     "00:50:56:AA:BB:0E",
     [
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (1433, "tcp", "ms-sql-s", "Microsoft SQL Server", "2019 15.00.2000", None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.15", "FILE01.acme.local",
     "Microsoft Windows Server 2019 Standard",
     "00:50:56:AA:BB:0F",
     [
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (139, "tcp", "netbios-ssn", "Microsoft Windows netbios-ssn", None, None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.17", "JUMP01.acme.local",
     "Linux 5.15 (Ubuntu 22.04)",
     "00:50:56:AA:BB:11",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.9p1 Ubuntu 3ubuntu0.1",
          "Ubuntu Linux; protocol 2.0"),
     ]),
    ("10.0.5.19", "WEB-INT01.acme.local",
     "Linux 5.15 (Ubuntu 22.04)",
     "00:50:56:AA:BB:13",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.5",
          "Ubuntu Linux; protocol 2.0"),
         (80, "tcp", "http", "nginx", "1.18.0", "Ubuntu"),
         (443, "tcp", "ssl/http", "nginx", "1.18.0", "Ubuntu"),
     ]),
    ("10.0.5.22", "DEV-BUILD.acme.local",
     "Linux 5.4 (Ubuntu 20.04)",
     "00:50:56:AA:BB:16",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.5", None),
         (80, "tcp", "http", "Apache httpd", "2.4.41", "(Ubuntu)"),
         (443, "tcp", "ssl/http", "Apache httpd", "2.4.41", "(Ubuntu)"),
         (8080, "tcp", "http-proxy", "Jenkins", "2.387.3", None),
     ]),
    ("10.0.5.26", "FTP-LEGACY.acme.local",
     "Linux 2.6.32 (CentOS 6)",
     "00:50:56:AA:BB:1A",
     [
         (21, "tcp", "ftp", "vsftpd", "2.3.4", None),
         (22, "tcp", "ssh", "OpenSSH", "5.3", "protocol 2.0"),
         (80, "tcp", "http", "Apache httpd", "2.2.15", "(CentOS)"),
     ]),
    ("10.0.5.28", "ERP-APP01.acme.local",
     "Linux 4.18 (RHEL 8.7)",
     "00:50:56:AA:BB:1C",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.0", "protocol 2.0"),
         (80, "tcp", "http", "Apache httpd", "2.4.37", "(Red Hat Enterprise Linux)"),
         (443, "tcp", "ssl/http", "Apache httpd", "2.4.37", "(Red Hat Enterprise Linux)"),
         (8080, "tcp", "http-proxy", "Apache Tomcat", "9.0.27", None),
         (8443, "tcp", "ssl/http", "Apache Tomcat", "9.0.27", None),
     ]),
    ("10.0.5.29", "HR-DB.acme.local",
     "Linux 5.15 (Ubuntu 22.04)",
     "00:50:56:AA:BB:1D",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.9p1", None),
         (5432, "tcp", "postgresql", "PostgreSQL DB", "14.5", None),
     ]),
    ("10.0.5.30", "FINANCE-APP.acme.local",
     "Microsoft Windows Server 2022 Datacenter",
     "00:50:56:AA:BB:1E",
     [
         (80, "tcp", "http", "Microsoft IIS httpd", "10.0", None),
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (443, "tcp", "ssl/http", "Microsoft IIS httpd", "10.0", None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.1", "CORE-RTR01.acme.local",
     "Cisco IOS 15.6",
     "00:50:56:AA:BB:01",
     [
         (22, "tcp", "ssh", "Cisco SSH", "1.25", None),
         (23, "tcp", "telnet", "Cisco router telnetd", None, None),
         (80, "tcp", "http", "Cisco IOS http config", None, None),
         (443, "tcp", "ssl/https", "Cisco IOS http config", None, None),
     ]),
    ("10.0.5.18", "VPN-GW.acme.local",
     "Pulse Secure 9.1R12",
     "00:50:56:AA:BB:12",
     [
         (443, "tcp", "ssl/https", "Pulse Secure VPN", "9.1R12", None),
     ]),
    ("10.0.5.27", "SHAREPOINT01.acme.local",
     "Microsoft Windows Server 2019 Standard",
     "00:50:56:AA:BB:1B",
     [
         (80, "tcp", "http", "Microsoft IIS httpd", "10.0", None),
         (443, "tcp", "ssl/http", "Microsoft IIS httpd", "10.0", None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.23", "CITRIX01.acme.local",
     "Microsoft Windows Server 2019 Standard",
     "00:50:56:AA:BB:17",
     [
         (80, "tcp", "http", "Microsoft IIS httpd", "10.0", None),
         (135, "tcp", "msrpc", "Microsoft Windows RPC", None, None),
         (443, "tcp", "ssl/http", "Microsoft IIS httpd", "10.0", None),
         (445, "tcp", "microsoft-ds", "Microsoft Windows SMB", None, None),
         (3389, "tcp", "ms-wbt-server", "Microsoft Terminal Services", None, None),
     ]),
    ("10.0.5.21", "MAIL-RELAY.acme.local",
     "Linux 5.10 (Debian 11)",
     "00:50:56:AA:BB:15",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.4p1 Debian 5+deb11u1", None),
         (25, "tcp", "smtp", "Postfix smtpd", None, None),
         (587, "tcp", "smtp", "Postfix smtpd", None, None),
     ]),
    ("10.0.5.31", "IDP01.acme.local",
     "Linux 5.15 (Ubuntu 22.04)",
     "00:50:56:AA:BB:1F",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.9p1", None),
         (443, "tcp", "ssl/http", "nginx", "1.22.1", None),
     ]),
    ("10.0.5.33", "MONITORING.acme.local",
     "Linux 5.4 (Ubuntu 20.04)",
     "00:50:56:AA:BB:21",
     [
         (22, "tcp", "ssh", "OpenSSH", "8.2p1", None),
         (3000, "tcp", "http", "Grafana", "9.5.2", None),
         (9090, "tcp", "http", "Prometheus", "2.45.0", None),
     ]),
]


# ---------------------------------------------------------------------------
# Nessus vulnerability catalog: keyed by (ip, plugin_id)
# Severity 0=Info, 1=Low, 2=Medium, 3=High, 4=Critical
# ---------------------------------------------------------------------------
def make_vuln(plugin_id, plugin_name, plugin_family, port, proto, service,
              severity, risk, synopsis, description, solution, cves,
              cvss, vector, output=None, exploit="false"):
    return {
        "plugin_id": plugin_id, "plugin_name": plugin_name,
        "plugin_family": plugin_family, "port": port, "protocol": proto,
        "svc_name": service, "severity": severity, "risk_factor": risk,
        "synopsis": synopsis, "description": description,
        "solution": solution, "cves": cves, "cvss_base_score": cvss,
        "cvss_vector": vector, "plugin_output": output,
        "exploit_available": exploit,
    }


VULNS_BY_HOST = {
    "10.0.5.10": [  # DC01
        make_vuln(
            "100485", "MS Netlogon: Elevation of Privilege Vulnerability (Zerologon)",
            "Windows", "445", "tcp", "cifs", 4, "Critical",
            "An elevation of privilege vulnerability exists in the Netlogon protocol.",
            "An unauthenticated attacker with network access to the DC can establish "
            "a vulnerable Netlogon secure channel and impersonate the DC, leading to "
            "full domain compromise (CVE-2020-1472).",
            "Apply the August 2020 Microsoft security updates and enable enforcement "
            "mode (FullSecureChannelProtection=1).",
            ["CVE-2020-1472"], "10.0",
            "AV:N/AC:L/Au:N/C:C/I:C/A:C",
            "Nessus was able to perform a partial Zerologon authentication.",
            "true",
        ),
        make_vuln(
            "57608", "SMB Signing not required",
            "Misc.", "445", "tcp", "cifs", 2, "Medium",
            "Signing is not required on the remote SMB server.",
            "Signing is not required on the remote SMB server. An unauthenticated, "
            "remote attacker can exploit this to conduct man-in-the-middle attacks "
            "against the SMB server.",
            "Enforce message signing in the host's configuration. On Windows, this "
            "is found in the policy setting 'Microsoft network server: Digitally "
            "sign communications (always)'.",
            [], "5.0", "AV:N/AC:L/Au:N/C:N/I:P/A:N", None,
        ),
    ],
    "10.0.5.11": [  # DC02
        make_vuln(
            "57608", "SMB Signing not required",
            "Misc.", "445", "tcp", "cifs", 2, "Medium",
            "Signing is not required on the remote SMB server.",
            "Signing is not required on the remote SMB server. An unauthenticated, "
            "remote attacker can exploit this to conduct man-in-the-middle attacks.",
            "Enforce message signing in the host's configuration.",
            [], "5.0", "AV:N/AC:L/Au:N/C:N/I:P/A:N", None,
        ),
    ],
    "10.0.5.12": [  # EXCHANGE01
        make_vuln(
            "157404", "Microsoft Exchange Server CVE-2022-41040, CVE-2022-41082 (ProxyNotShell)",
            "Windows", "443", "tcp", "www", 4, "Critical",
            "The remote Exchange server is missing security updates.",
            "The Microsoft Exchange Server installation is missing the September 2022 "
            "Security Update. It is therefore vulnerable to ProxyNotShell, a chain of "
            "an SSRF (CVE-2022-41040) and an RCE (CVE-2022-41082).",
            "Apply the September 2022 Microsoft Exchange Server security update.",
            ["CVE-2022-41040", "CVE-2022-41082"], "8.8",
            "AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
            "Build : 15.01.2375.024 (vulnerable, requires SU09-2022 or later).",
            "true",
        ),
        make_vuln(
            "104743", "TLS Version 1.0 Protocol Detection",
            "Service detection", "443", "tcp", "www", 1, "Low",
            "The remote service encrypts traffic using a deprecated protocol.",
            "The remote service accepts connections encrypted using TLS 1.0. TLS 1.0 "
            "has known cryptographic flaws.",
            "Enable support for TLS 1.2 and/or 1.3, and disable support for TLS 1.0.",
            [], "3.7", "AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N", None,
        ),
    ],
    "10.0.5.13": [  # SQL-PROD01
        make_vuln(
            "10398", "Microsoft Windows SMB Service Detection",
            "Windows", "445", "tcp", "cifs", 0, "None",
            "It was possible to obtain information about the remote operating system.",
            "Nessus was able to obtain the remote operating system through SMB.",
            "n/a", [], None, None, None,
        ),
        make_vuln(
            "85582", "Microsoft SQL Server Unsupported Version Detection",
            "Databases", "1433", "tcp", "mssql", 3, "High",
            "The remote database server is no longer supported.",
            "According to its self-reported version, the Microsoft SQL Server "
            "instance is running an unsupported version. Lack of support implies "
            "no new security patches will be released.",
            "Upgrade to a version that is currently supported.",
            [], "7.5", "AV:N/AC:L/Au:N/C:P/I:P/A:P",
            "Detected version: Microsoft SQL Server 2019 RTM (without CU).", "false",
        ),
    ],
    "10.0.5.15": [  # FILE01
        make_vuln(
            "26920", "Microsoft Windows SMB NULL Session Authentication",
            "Windows", "445", "tcp", "cifs", 3, "High",
            "It is possible to log into the remote host with a NULL session.",
            "The remote host is running Microsoft Windows. It is possible to log "
            "into it using a NULL session (i.e., with no login or password). "
            "Depending on the configuration, an attacker may be able to enumerate "
            "users and shares.",
            "Apply the suggested fix in the referenced Microsoft KB articles.",
            [], "5.0", "AV:N/AC:L/Au:N/C:P/I:N/A:N",
            "Anonymous bind permitted. Listed shares: Public, NETLOGON, SYSVOL, IPC$",
            "false",
        ),
    ],
    "10.0.5.26": [  # FTP-LEGACY
        make_vuln(
            "55523", "vsftpd Smiley Face Backdoor",
            "FTP", "21", "tcp", "ftp", 4, "Critical",
            "The remote FTP server contains a backdoor.",
            "The version of vsftpd running on the remote host has been compiled "
            "with a backdoor. Attempting to log in with a username containing :) "
            "(a smiley face) triggers the backdoor, which results in a shell "
            "listening on TCP port 6200.",
            "Validate and recompile a clean version of the vsftpd 2.3.4 source "
            "code, or upgrade to the latest version.",
            ["CVE-2011-2523"], "10.0",
            "AV:N/AC:L/Au:N/C:C/I:C/A:C",
            "vsftpd 2.3.4 backdoor confirmed via 'USER user:)' on port 21.",
            "true",
        ),
        make_vuln(
            "33850", "Unix Operating System Unsupported Version Detection",
            "General", "0", "tcp", "general", 4, "Critical",
            "The remote host is running an unsupported version of a Unix-like operating system.",
            "The remote host is running CentOS 6, which reached end-of-life on "
            "2020-11-30. As a result, it should not be used since it lacks security patches.",
            "Upgrade to a supported version.",
            [], "10.0", "AV:N/AC:L/Au:N/C:C/I:C/A:C", None,
        ),
        make_vuln(
            "70658", "SSH Server CBC Mode Ciphers Enabled",
            "Misc.", "22", "tcp", "ssh", 1, "Low",
            "The SSH server is configured to use Cipher Block Chaining.",
            "The SSH server is configured to support CBC mode ciphers, which may "
            "allow an attacker to recover plaintext from ciphertext.",
            "Disable CBC mode cipher encryption, and enable CTR or GCM cipher mode.",
            ["CVE-2008-5161"], "2.6", "AV:N/AC:H/Au:N/C:P/I:N/A:N", None,
        ),
    ],
    "10.0.5.28": [  # ERP-APP01
        make_vuln(
            "34970", "Apache Tomcat Default Files",
            "CGI abuses", "8443", "tcp", "https", 2, "Medium",
            "The default error page, default index page, example JSPs and/or "
            "example servlets are installed on the remote Apache Tomcat server.",
            "These files should be removed as they may help an attacker uncover "
            "information about the remote Tomcat install or its host.",
            "Delete the default index page and remove the example JSP and servlets.",
            [], "5.0", "AV:N/AC:L/Au:N/C:P/I:N/A:N", None,
        ),
        make_vuln(
            "97134", "Apache Tomcat Default Credentials",
            "CGI abuses", "8443", "tcp", "https", 4, "Critical",
            "The remote Apache Tomcat server uses a default username and password.",
            "Nessus successfully authenticated to the Apache Tomcat Manager "
            "interface using the default credentials 'tomcat:tomcat'. An attacker "
            "with these credentials can deploy arbitrary WAR files, leading to "
            "remote code execution as the Tomcat user.",
            "Edit conf/tomcat-users.xml to remove or change the default account.",
            [], "9.8", "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "Logged in as 'tomcat' on /manager/html.", "true",
        ),
        make_vuln(
            "84574", "Missing HSTS Header",
            "Web Servers", "443", "tcp", "https", 1, "Low",
            "The remote web server does not enforce HSTS.",
            "The remote HTTPS server does not transmit a Strict-Transport-Security "
            "header to enforce HTTPS-only connections.",
            "Configure the web server to send the Strict-Transport-Security header.",
            [], "2.6", "AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N", None,
        ),
    ],
    "10.0.5.30": [  # FINANCE-APP
        make_vuln(
            "11213", "HTTP TRACE / TRACK Methods Allowed",
            "Web Servers", "443", "tcp", "www", 1, "Low",
            "Debugging functions are enabled on the remote web server.",
            "The remote web server supports the TRACE and/or TRACK methods, which "
            "are used to debug web server connections.",
            "Disable these HTTP methods.",
            ["CVE-2003-1567", "CVE-2004-2320"], "5.0",
            "AV:N/AC:L/Au:N/C:P/I:N/A:N", None,
        ),
        make_vuln(
            "10107", "HTTP Server Type and Version",
            "Web Servers", "443", "tcp", "www", 0, "None",
            "A web server is running on the remote host.",
            "This plugin attempts to determine the type and the version of the "
            "remote web server.",
            "n/a", [], None, None,
            "Microsoft-IIS/10.0", "false",
        ),
    ],
    "10.0.5.1": [  # CORE-RTR01
        make_vuln(
            "10264", "SNMP Agent Default Community Names",
            "SNMP", "161", "udp", "snmp", 2, "Medium",
            "The community names of the remote SNMP server can be guessed.",
            "It is possible to obtain the default community names of the remote "
            "SNMP server. An attacker may use this information to gain more "
            "knowledge about the remote host or change the configuration.",
            "Disable the SNMP service or filter incoming UDP packets to port 161.",
            ["CVE-1999-0517", "CVE-1999-0516"], "7.5",
            "AV:N/AC:L/Au:N/C:P/I:P/A:P",
            "The community 'public' was found.", "false",
        ),
        make_vuln(
            "42263", "Telnet Service Enabled",
            "Service detection", "23", "tcp", "telnet", 2, "Medium",
            "The remote service supports cleartext authentication.",
            "The remote host is running a Telnet server. Using Telnet over an "
            "unencrypted channel is not recommended.",
            "Disable the Telnet service and use SSH instead.",
            [], "4.8", "AV:N/AC:H/Au:N/C:P/I:P/A:N", None,
        ),
    ],
    "10.0.5.22": [  # DEV-BUILD
        make_vuln(
            "73334", "Jenkins Multiple Vulnerabilities",
            "CGI abuses", "8080", "tcp", "http-proxy", 3, "High",
            "The Jenkins server is affected by multiple vulnerabilities.",
            "The Jenkins instance is anonymously accessible. The build console "
            "logs contain references to AWS access keys committed to a build "
            "artifact, which an attacker could harvest.",
            "Disable anonymous read access in Jenkins global security settings. "
            "Rotate any credentials that may have been exposed in build logs.",
            [], "7.5", "AV:N/AC:L/Au:N/C:P/I:P/A:P",
            "/jobs/staging-deploy/12/console contains 'AKIAEXAMPLEKEY1234XX'.",
            "true",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Nmap XML builder
# ---------------------------------------------------------------------------
def build_nmap_xml(start_ts):
    runtime_str = datetime.fromtimestamp(start_ts, timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    nmaprun = ET.Element("nmaprun", {
        "scanner": "nmap",
        "args": "nmap -sV -O -p- --min-rate 1000 -oX scan.xml 10.0.5.0/24",
        "start": str(start_ts),
        "startstr": runtime_str,
        "version": "7.94",
        "xmloutputversion": "1.05",
    })
    ET.SubElement(nmaprun, "scaninfo", {
        "type": "syn", "protocol": "tcp",
        "numservices": "65535", "services": "1-65535",
    })
    ET.SubElement(nmaprun, "verbose", {"level": "0"})
    ET.SubElement(nmaprun, "debugging", {"level": "0"})

    host_ts = start_ts + 60
    for ip, hostname, os_str, mac, ports in HOSTS:
        host_start = host_ts
        host_end = host_ts + 30
        host_ts = host_end + 5

        host_el = ET.SubElement(nmaprun, "host", {
            "starttime": str(host_start),
            "endtime": str(host_end),
        })
        ET.SubElement(host_el, "status", {
            "state": "up", "reason": "syn-ack", "reason_ttl": "64",
        })
        ET.SubElement(host_el, "address", {"addr": ip, "addrtype": "ipv4"})
        if mac:
            ET.SubElement(host_el, "address", {
                "addr": mac, "addrtype": "mac", "vendor": "VMware, Inc.",
            })
        if hostname:
            hostnames_el = ET.SubElement(host_el, "hostnames")
            ET.SubElement(hostnames_el, "hostname", {
                "name": hostname, "type": "PTR",
            })
        else:
            ET.SubElement(host_el, "hostnames")

        ports_el = ET.SubElement(host_el, "ports")
        for port_num, proto, svc, product, version, extrainfo in ports:
            port_el = ET.SubElement(ports_el, "port", {
                "protocol": proto, "portid": str(port_num),
            })
            ET.SubElement(port_el, "state", {
                "state": "open", "reason": "syn-ack", "reason_ttl": "64",
            })
            svc_attrs = {"name": svc or "unknown",
                         "method": "probed", "conf": "10"}
            if product:
                svc_attrs["product"] = product
            if version:
                svc_attrs["version"] = version
            if extrainfo:
                svc_attrs["extrainfo"] = extrainfo
            ET.SubElement(port_el, "service", svc_attrs)

        # OS detection block
        os_el = ET.SubElement(host_el, "os")
        ET.SubElement(os_el, "portused", {
            "state": "open", "proto": "tcp",
            "portid": str(ports[0][0]) if ports else "22",
        })
        osmatch = ET.SubElement(os_el, "osmatch", {
            "name": os_str, "accuracy": "97", "line": "10000",
        })
        if "Windows" in os_str:
            ET.SubElement(osmatch, "osclass", {
                "type": "general purpose", "vendor": "Microsoft",
                "osfamily": "Windows", "osgen": "Server",
                "accuracy": "97",
            })
        elif "Cisco" in os_str:
            ET.SubElement(osmatch, "osclass", {
                "type": "router", "vendor": "Cisco",
                "osfamily": "IOS", "osgen": "15.X",
                "accuracy": "97",
            })
        elif "Pulse" in os_str:
            ET.SubElement(osmatch, "osclass", {
                "type": "specialized", "vendor": "Pulse Secure",
                "osfamily": "Pulse Connect Secure", "osgen": "9.X",
                "accuracy": "95",
            })
        else:
            ET.SubElement(osmatch, "osclass", {
                "type": "general purpose", "vendor": "Linux",
                "osfamily": "Linux", "osgen": "5.X",
                "accuracy": "97",
            })
        ET.SubElement(host_el, "times", {
            "srtt": "200", "rttvar": "50", "to": "100000",
        })

    end_ts = host_ts + 30
    runstats = ET.SubElement(nmaprun, "runstats")
    ET.SubElement(runstats, "finished", {
        "time": str(end_ts),
        "timestr": datetime.fromtimestamp(end_ts, timezone.utc).strftime("%a %b %d %H:%M:%S %Y"),
        "summary": f"Nmap done at {runtime_str}; {len(HOSTS)} IP addresses "
                   f"({len(HOSTS)} hosts up) scanned in {end_ts - start_ts:.2f} seconds",
        "elapsed": f"{end_ts - start_ts:.2f}",
        "exit": "success",
    })
    ET.SubElement(runstats, "hosts", {
        "up": str(len(HOSTS)), "down": "0", "total": str(len(HOSTS)),
    })
    return nmaprun


# ---------------------------------------------------------------------------
# Nessus XML builder
# ---------------------------------------------------------------------------
def build_nessus_xml():
    root = ET.Element("NessusClientData_v2")

    policy = ET.SubElement(root, "Policy")
    ET.SubElement(policy, "policyName").text = "Internal Network Scan — Authenticated"
    ET.SubElement(policy, "policyComments").text = (
        "Authenticated internal scan policy used during ACME engagement."
    )
    prefs = ET.SubElement(policy, "Preferences")
    server_prefs = ET.SubElement(prefs, "ServerPreferences")
    for k, v in [
        ("max_hosts", "30"), ("max_checks", "5"),
        ("plugin_set", "all"), ("optimize_test", "yes"),
    ]:
        pref = ET.SubElement(server_prefs, "preference")
        ET.SubElement(pref, "name").text = k
        ET.SubElement(pref, "value").text = v

    report = ET.SubElement(root, "Report", {
        "name": "ACME Internal — Authenticated Scan",
        "xmlns:cm": "http://www.nessus.org/cm",
    })

    for ip, hostname, os_str, mac, ports in HOSTS:
        vulns = VULNS_BY_HOST.get(ip)
        if not vulns:
            continue

        rh = ET.SubElement(report, "ReportHost", {"name": ip})
        hp = ET.SubElement(rh, "HostProperties")
        for tag_name, tag_value in [
            ("HOST_END", "Sun May  4 14:32:11 2026"),
            ("operating-system", os_str),
            ("system-type", "general-purpose"),
            ("host-fqdn", hostname or ""),
            ("host-ip", ip),
            ("mac-address", mac or ""),
            ("HOST_START", "Sun May  4 13:11:00 2026"),
        ]:
            if tag_value:
                tag_el = ET.SubElement(hp, "tag", {"name": tag_name})
                tag_el.text = tag_value

        for v in vulns:
            ri_attrs = {
                "port": v["port"],
                "svc_name": v["svc_name"],
                "protocol": v["protocol"],
                "severity": str(v["severity"]),
                "pluginID": v["plugin_id"],
                "pluginName": v["plugin_name"],
                "pluginFamily": v["plugin_family"],
            }
            ri = ET.SubElement(rh, "ReportItem", ri_attrs)
            for child_tag, child_text in [
                ("synopsis", v["synopsis"]),
                ("description", v["description"]),
                ("solution", v["solution"]),
                ("risk_factor", v["risk_factor"]),
                ("plugin_output", v.get("plugin_output")),
                ("cvss_base_score", v.get("cvss_base_score")),
                ("cvss_vector", v.get("cvss_vector")),
                ("exploit_available", v.get("exploit_available")),
            ]:
                if child_text:
                    el = ET.SubElement(ri, child_tag)
                    el.text = child_text
            for cve in v.get("cves") or []:
                cve_el = ET.SubElement(ri, "cve")
                cve_el.text = cve

    return root


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_pretty(root, out_path):
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    out_path.write_bytes(pretty)


def main():
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = int(datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc).timestamp())

    nmap_path = SCANS_DIR / "acme_internal_nmap.xml"
    write_pretty(build_nmap_xml(start_ts), nmap_path)
    print(f"[OK] Wrote {nmap_path.relative_to(SCRIPT_DIR.parent)} "
          f"({nmap_path.stat().st_size:,} bytes, {len(HOSTS)} hosts)")

    nessus_path = SCANS_DIR / "acme_internal.nessus"
    write_pretty(build_nessus_xml(), nessus_path)
    vuln_count = sum(len(v) for v in VULNS_BY_HOST.values())
    crit_count = sum(1 for v in (vv for vs in VULNS_BY_HOST.values() for vv in vs)
                     if v["severity"] == 4)
    print(f"[OK] Wrote {nessus_path.relative_to(SCRIPT_DIR.parent)} "
          f"({nessus_path.stat().st_size:,} bytes, "
          f"{len(VULNS_BY_HOST)} hosts, {vuln_count} vulns, {crit_count} critical)")


if __name__ == "__main__":
    main()
