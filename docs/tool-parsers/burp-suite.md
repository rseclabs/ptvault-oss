# Burp Suite Parser

The Burp Suite parser imports XML exports from Burp Suite's issue scanner, extracting web application vulnerability findings.

## Exporting from Burp Suite

1. In Burp Suite, go to **Target > Site map** or **Dashboard > Issues**
2. Right-click on the target or select all issues
3. Choose **Report issues**
4. Select **XML** as the output format
5. Save the file (typically with a `.xml` extension)

Alternatively, from the Scanner:
1. Go to **Scanner > Scan queue** or **Issue activity**
2. Select all issues
3. Right-click → **Export selected items** → **XML**

## Importing into PTVault

1. Click **+ Add Evidence** and select **Tool Output**
2. Enter a title (e.g., `Burp Suite Scan - ACME Corp App`)
3. Select your Burp XML file
4. Click **Save**

## What Gets Extracted

| Data | Where It Goes |
|------|--------------|
| Issue name | Evidence title |
| Severity (High/Medium/Low/Info) | Metadata `severity_level` field |
| Confidence | Stored in metadata |
| Affected URL | Stored in evidence content and metadata |
| Issue detail | Evidence content body |
| Issue background | Appended to evidence content |
| Remediation | Stored in metadata |
| Request samples | Stored in metadata |
| Response samples | Stored in metadata |

## Automatic Tags

Evidence items from Burp imports are automatically tagged with:
- `burp`
- `web`
- `vulnerability`
- Severity level: `critical`, `high`, `medium`, `low`, or `info`

## Issue Severity Mapping

| Burp Severity | PTVault Severity Level |
|--------------|----------------------|
| High | `high` |
| Medium | `medium` |
| Low | `low` |
| Information | `info` |

Note: Burp does not have a "Critical" category — critical findings in Burp are mapped to `high` in PTVault.

## Troubleshooting

**"File format not recognized"**
Ensure the file is a Burp Suite XML export (not a project file or state file). The XML should have an `<issues>` root element.

**"No findings imported"**
The scan may not have identified any issues, or the target had no vulnerabilities detected. Check the Burp project directly.
