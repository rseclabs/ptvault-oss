# Sample engagement

A fictional internal penetration test of **ACME Corporation** that fills every part of
PTVault with realistic data, so new users can learn the app by clicking around.

Everything is invented: private `10.0.5.0/24` addresses, the `acme.local` and `acme.example`
domains, and made-up accounts, passwords and hashes.

## Load it

PTVault must be running and unlocked, and you need an admin or tester account.

```bash
python3 sample_data/load_sample.py --email admin@example.com
# another address:   --url http://localhost:5000
# password:          prompted, or set PTVAULT_PASSWORD
```

The loader uses only the Python standard library and PTVault's normal REST API. It logs in
as you, so it works with an encrypted database and never touches the `data/` folder. If a
sample engagement already exists, it stops; `--replace` deletes the old one first (see
*Known issues*).

## What it creates

| Where in PTVault | Sample content |
|---|---|
| **Engagements** | *ACME Corp Internal Pentest (Sample)*, linked to the client *ACME Corporation (Sample)* |
| **Dashboard** | totals, findings by severity, scanner results, ports and host status |
| **Hosts** | 22 hosts: 20 from the Nmap import, `intranet.acme.local` from the Burp import, and one added by hand. Indicators (rooted, shell, out of scope...), colours, host notes with embedded screenshots, ports, manual and Nessus findings, credentials |
| **Hosts → Saved Searches** | five searches: compromised hosts, critical scanner results, a CIDR range, a colour, a keyword |
| **Port Grid** | open and filtered ports across the subnet |
| **General** | a notes tree (start with *Start here*), engagement credentials, three terminal dumps, eight curated findings |
| **Tools → Attack Maps** | the path from a standard user to Domain Admin, with host, finding and evidence nodes |
| **Tools → Command** | three sample commands with `{variables}` |
| **Test Plans** | an ATT&CK Navigator layer (12 techniques) and a detection test plan run against DC01, with outcomes recorded (prevented, alerted, logged, not detected, skipped) |
| **Reporting** | four writeups tagged `sample`, and a finished report that uses findings, writeups and every format tool, including the attack map. Export it as HTML, Markdown, PDF or Word |

It also creates relationships between evidence, findings, notes and credentials, and a
saved attack path. The API has these, but the current UI does not show them.

The client, writeups, commands and ATT&CK layer are shared across engagements. Deleting the
engagement leaves them in place; remove them by hand (the writeups are tagged `sample`).

## The story

The tester starts as a standard domain user (assumed breach) and reaches Domain Admin two ways:

1. **Active Directory:** Kerberoast `svc_sql` → sysadmin on SQL-PROD01 → LSASS dump →
   `adm_jsmith`'s hash → pass-the-hash and DCSync on DC01.
2. **Web:** SQL injection in the intranet portal leaks the `portal_app` database password,
   which is reused on the HR database.

Along the way: the vsftpd 2.3.4 backdoor on FTP-LEGACY (root), Tomcat Manager default
credentials on ERP-APP01, SMB signing and SNMP findings. VPN-GW is out of scope.

## Files

| File | Purpose |
|---|---|
| `load_sample.py` | the loader |
| `content.py` | all the sample's text and structure; edit this to change the story |
| `files/` | tool output, screenshots and the ATT&CK layer that the loader uploads |
| `generate_scans.py` | regenerates the Nmap and Nessus files (deterministic) |
| `build_assets.py` | regenerates the Burp file, the layer and the screenshots (needs Playwright's Chromium) |

`tests/test_sample_data.py` checks that `content.py` stays consistent: every host IP is
created by a scan, every key resolves, every value is one the API accepts, and the tool files
parse. Run it after editing the sample.

## Known issues

- **Deleting an engagement is incomplete (M-13 in the 2026-11-07 retest).** Delete leaves the
  engagement's members, attack maps, test plans, reports, saved searches and relationships
  behind. The next engagement can reuse the deleted ID and inherit them. If the deleted
  engagement was the newest one, creating the next one fails with a 500 error. `--replace`
  removes what it can through the API first, but it cannot remove the owner's membership row,
  so it fails while the sample is the newest engagement. Until M-13 is fixed, load the sample
  into a fresh instance rather than replacing it.
- Only the Nmap, Nessus and Burp importers are wired into uploads, so the sample uses those three.
