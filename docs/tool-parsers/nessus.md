# Nessus Parser

The Nessus parser imports `.nessus` export files from Tenable Nessus, extracting vulnerability findings, CVSS scores, and CVE data for all scanned hosts.

## Exporting from Nessus

1. Open Nessus and navigate to your scan
2. Click **Export** (or the download icon)
3. Select **Nessus** format (`.nessus` extension)
4. Download the file

> The `.nessus` format is XML-based. PTVault accepts files with either the `.nessus` or `.xml` extension.

## Importing into PTVault

1. Click **+ Add Evidence** and select **Tool Output**
2. Enter a title (e.g., `Nessus Scan - ACME Corp Internal`)
3. Select your `.nessus` file
4. Click **Save**

## What Gets Extracted

| Data | Where It Goes |
|------|--------------|
| Host IP addresses | New host records in the host list |
| Host FQDNs | Set as hostname for each host |
| Open ports | Added to each host's Open Ports tab |
| Plugin name | Evidence title |
| Plugin family | Stored in metadata |
| Severity (0–4) | Mapped to severity level in metadata |
| CVSS v2 score | Stored in `cvss` metadata field |
| CVSS v3 score | Stored in `cvss3` metadata field |
| CVE references | Stored in `cve` metadata field |
| Plugin description | Evidence content |
| Solution | Stored in metadata `remediation` field |
| Plugin output | Appended to evidence content |

## Severity Mapping

| Nessus Risk Rating | PTVault Severity Level |
|-------------------|----------------------|
| Critical (4) | `critical` |
| High (3) | `high` |
| Medium (2) | `medium` |
| Low (1) | `low` |
| None / Informational (0) | `info` |

## Automatic Tags

Evidence items from Nessus imports are automatically tagged with:
- `nessus`
- `vulnerability-scan`
- Severity level: `critical`, `high`, `medium`, `low`

Imports with critical-severity findings also get the tag `critical-findings`.

## Host Search Integration

After importing Nessus results, the host-level **search bar** indexes the Nessus vulnerability metadata. You can search for:
- CVE IDs: `CVE-2021-44228` (Log4Shell)
- Plugin names: `Apache Log4j`
- CVSS scores: `cvss:9.8`
- Vulnerability descriptions

## Large Scan Files

Nessus scans can produce very large `.nessus` files (hundreds of MB for enterprise scans). PTVault handles large files, but parsing may take 30–60 seconds for very large scans. The upload limit is 250 MB.

## Troubleshooting

**"File format not recognized"**
Ensure the file is a valid Nessus export (`.nessus` format), not a policy file or report export in another format. The XML should have a `<NessusClientData_v2>` root element.

**"Parsing is slow"**
Large Nessus files with many findings take longer. The parsing happens server-side. Wait for the upload to complete before navigating away.
