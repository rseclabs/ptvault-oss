## Advanced Report Builder

# Advanced Report Builder Documentation

The Advanced Report Builder provides template-based report generation with auto-population from engagement data and multi-engagement comparison capabilities.

## Table of Contents

- [Overview](#overview)
- [Report Templates](#report-templates)
- [Auto-Population](#auto-population)
- [Multi-Engagement Comparison](#multi-engagement-comparison)
- [API Reference](#api-reference)

---

## Overview

The Advanced Report Builder consists of three main components:

1. **Report Templates** - Reusable report structures
2. **Auto-Population** - Automatic content generation from engagement data
3. **Multi-Engagement Comparison** - Benchmarking across multiple assessments

### Key Features

- Pre-built templates for common report types
- Custom template creation
- Placeholder replacement (e.g., `{{CLIENT_NAME}}`)
- Auto-populated sections (summaries, findings, host tables)
- Multi-engagement comparison and trending
- Template duplication and customization

---

## Report Templates

### Default Templates

PTVault includes 4 pre-built templates:

| Template | Category | Description |
|----------|----------|-------------|
| **Executive Summary Report** | Executive | High-level overview with critical findings |
| **Technical Assessment Report** | Technical | Comprehensive technical report with evidence |
| **Compliance Assessment Report** | Compliance | Framework-mapped findings |
| **Quick Assessment Summary** | Executive | Single-page rapid assessment |

### Template Structure

Templates are JSON structures containing sections:

```json
{
  "name": "My Report Template",
  "description": "Custom pentest report",
  "category": "custom",
  "structure": [
    {
      "type": "custom",
      "title": "Introduction",
      "content": "Assessment for {{CLIENT_NAME}}"
    },
    {
      "type": "auto",
      "section_type": "executive_summary",
      "title": "Executive Summary",
      "config": {}
    },
    {
      "type": "auto",
      "section_type": "findings_list",
      "title": "Findings",
      "config": {
        "severity": "critical",
        "limit": 10
      }
    }
  ]
}
```

### Section Types

#### Custom Sections

Manual content with placeholder support:

```json
{
  "type": "custom",
  "title": "Report for {{CLIENT_NAME}}",
  "content": "Tested {{HOST_COUNT}} systems from {{START_DATE}} to {{END_DATE}}"
}
```

#### Auto-Populated Sections

Automatically generated from engagement data:

| Section Type | Description | Config Options |
|--------------|-------------|----------------|
| `executive_summary` | High-level summary with risk overview | None |
| `findings_list` | Detailed findings | `severity`, `limit` |
| `host_summary` | Host table with ports/creds | None |
| `methodology` | Testing methodology from test plans | None |
| `recommendations` | Prioritized remediation steps | None |

---

## Auto-Population

### Placeholders

Use `{{PLACEHOLDER}}` syntax in custom sections:

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{{ENGAGEMENT_NAME}}` | Engagement name | "ACME Corp Pentest" |
| `{{CLIENT_NAME}}` | Client organization | "ACME Corporation" |
| `{{DATE_RANGE}}` | Engagement date range | "2024-01-01 to 2024-01-15" |
| `{{START_DATE}}` | Start date | "2024-01-01" |
| `{{END_DATE}}` | End date | "2024-01-15" |
| `{{TESTER_NAME}}` | Lead tester | "John Doe" |
| `{{HOST_COUNT}}` | Number of hosts | "42" |
| `{{FINDING_COUNT}}` | Total findings | "15" |
| `{{EVIDENCE_COUNT}}` | Evidence items | "87" |
| `{{CRITICAL_COUNT}}` | Critical findings | "3" |
| `{{HIGH_COUNT}}` | High findings | "7" |
| `{{MEDIUM_COUNT}}` | Medium findings | "4" |
| `{{LOW_COUNT}}` | Low findings | "1" |

### Executive Summary

Auto-generates:
- Engagement overview
- Risk summary by severity
- Top 5 critical/high findings

**Example Output:**

```markdown
# Executive Summary

**Engagement:** ACME Corp External Pentest
**Client:** ACME Corporation
**Period:** 2024-01-01 to 2024-01-15

## Overview
This report summarizes the findings from the security assessment conducted for ACME Corporation.
The assessment included testing of 42 systems and resulted in 15 documented findings.

## Risk Summary
The assessment identified:
- **Critical Risk:** 3 finding(s)
- **High Risk:** 7 finding(s)
- **Medium Risk:** 4 finding(s)
- **Low Risk:** 1 finding(s)

## Key Findings
1. **SQL Injection in Admin Panel** - CRITICAL (CVSS 9.8)
2. **Remote Code Execution** - CRITICAL (CVSS 9.3)
...
```

### Findings List

Auto-generates detailed finding cards with:
- Title and severity
- CVSS score
- Description
- Remediation

**Config Options:**
- `severity`: Filter by severity level
- `limit`: Maximum number of findings

**Example:**

```json
{
  "type": "auto",
  "section_type": "findings_list",
  "config": {
    "severity": "critical",
    "limit": 5
  }
}
```

### Host Summary

Auto-generates host table:

| IP Address | Hostname | OS | Open Ports | Credentials | Status |
|------------|----------|----|-----------:|------------:|--------|
| 192.168.1.10 | web01 | Ubuntu 20.04 | 5 | 2 | Rooted |
| 192.168.1.11 | db01 | CentOS 7 | 3 | 0 | Shell |

### Methodology

Auto-generates methodology based on:
- Executed test plans
- MITRE ATT&CK techniques used
- Standard pentest phases

### Recommendations

Auto-generates prioritized remediation steps:
1. Critical priority items
2. High priority items
3. Medium priority items
4. Low priority items

---

## Multi-Engagement Comparison

Compare multiple engagements to identify trends and benchmarks.

### Comparison Metrics

| Metric | Description |
|--------|-------------|
| **Average Findings** | Average findings per engagement |
| **Average Hosts** | Average hosts per engagement |
| **Severity Distribution** | Breakdown by severity |
| **Common Findings** | Findings appearing in multiple engagements |
| **Tool Usage** | Distribution of tools used |

### Trend Analysis

| Trend | Description |
|-------|-------------|
| **Findings Over Time** | Finding count by engagement date |
| **Severity Trends** | Severity distribution over time |
| **Remediation Rate** | Percentage of findings remediated |

### Example Comparison

```json
{
  "engagement_ids": [1, 2, 3, 4]
}
```

**Response:**

```json
{
  "engagements": [
    {
      "id": 1,
      "name": "Q1 2024 Assessment",
      "client": "ACME Corp",
      "stats": {
        "host_count": 42,
        "findings_count": 15
      }
    }
  ],
  "metrics": {
    "avg_findings_per_engagement": 14.5,
    "avg_hosts_per_engagement": 38.2,
    "severity_distribution": {
      "critical": 8,
      "high": 22,
      "medium": 18,
      "low": 10
    },
    "common_findings": [
      {
        "title": "Weak Password Policy",
        "engagement_count": 3
      }
    ]
  },
  "trends": {
    "findings_over_time": [
      {
        "engagement_id": 1,
        "engagement_name": "Q1 2024 Assessment",
        "date": "2024-01-01",
        "finding_count": 15
      }
    ]
  }
}
```

---

## API Reference

### Template Endpoints

#### List Templates

```http
GET /api/reporting/templates
```

**Query Parameters:**
- `category` (optional) - Filter by category
- `public_only` (optional) - Return only public templates

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "Executive Summary Report",
      "category": "executive",
      "is_default": 1,
      "usage_count": 15
    }
  ]
}
```

#### Get Template

```http
GET /api/reporting/templates/{template_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "Executive Summary Report",
  "description": "High-level overview",
  "category": "executive",
  "structure": [...],
  "placeholders": {...}
}
```

#### Create Template

```http
POST /api/reporting/templates
```

**Body:**
```json
{
  "name": "My Custom Template",
  "description": "Custom report structure",
  "category": "custom",
  "structure": [
    {
      "type": "auto",
      "section_type": "executive_summary"
    }
  ],
  "placeholders": {
    "CLIENT_NAME": "Client organization name"
  },
  "is_public": true
}
```

#### Update Template

```http
PUT /api/reporting/templates/{template_id}
```

**Body:** (same as create, all fields optional)

#### Delete Template

```http
DELETE /api/reporting/templates/{template_id}
```

#### Duplicate Template

```http
POST /api/reporting/templates/{template_id}/duplicate
```

**Body:**
```json
{
  "name": "Copy of Original Template"
}
```

#### Apply Template

```http
POST /api/reporting/templates/{template_id}/apply
```

**Body:**
```json
{
  "engagement_id": 123,
  "report_name": "Q1 2024 Report"
}
```

**Response:**
```json
{
  "success": true,
  "report_id": 456,
  "engagement_id": 123
}
```

#### Preview Template

```http
GET /api/reporting/templates/{template_id}/preview?engagement_id=123
```

**Response:**
```json
{
  "template": {
    "id": 1,
    "name": "Executive Summary Report"
  },
  "sections": [
    {
      "title": "Executive Summary",
      "content": "...",
      "type": "auto"
    }
  ],
  "engagement_id": 123
}
```

### Comparison Endpoints

#### Compare Engagements

```http
POST /api/reporting/compare
```

**Body:**
```json
{
  "engagement_ids": [1, 2, 3]
}
```

**Response:** (see Multi-Engagement Comparison section)

---

## Usage Examples

### Creating a Custom Template

```python
import requests

template = {
    "name": "Custom Pentest Report",
    "description": "Standard pentest report format",
    "category": "custom",
    "structure": [
        {
            "type": "custom",
            "title": "Executive Summary for {{CLIENT_NAME}}",
            "content": "Assessment Period: {{DATE_RANGE}}"
        },
        {
            "type": "auto",
            "section_type": "findings_list",
            "config": {"severity": None, "limit": None}
        },
        {
            "type": "auto",
            "section_type": "recommendations"
        }
    ]
}

response = requests.post(
    'http://localhost:5001/api/reporting/templates',
    json=template,
    cookies={'session': session_cookie}
)

template_id = response.json()['id']
```

### Applying Template to Generate Report

```python
response = requests.post(
    f'http://localhost:5001/api/reporting/templates/{template_id}/apply',
    json={
        "engagement_id": 123,
        "report_name": "Q1 Security Assessment"
    },
    cookies={'session': session_cookie}
)

report_id = response.json()['report_id']
```

### Comparing Multiple Engagements

```python
response = requests.post(
    'http://localhost:5001/api/reporting/compare',
    json={
        "engagement_ids": [1, 2, 3, 4]
    },
    cookies={'session': session_cookie}
)

comparison = response.json()
print(f"Average findings: {comparison['metrics']['avg_findings_per_engagement']}")
```

---

## Best Practices

### Template Design

1. **Use Descriptive Names** - "Q1 2024 Executive Report" not "Report 1"
2. **Add Descriptions** - Help users understand template purpose
3. **Categorize Properly** - Use categories for organization
4. **Include Placeholders** - Document available placeholders
5. **Test with Real Data** - Preview before deploying

### Auto-Population

1. **Filter Findings** - Use severity filters for focused reports
2. **Limit Results** - Set limits for executive summaries
3. **Combine Sections** - Mix auto and custom sections
4. **Review Output** - Always review auto-generated content

### Comparison

1. **Similar Engagements** - Compare similar types (e.g., all external pentests)
2. **Consistent Timeframes** - Use similar date ranges
3. **Same Methodology** - Compare engagements with similar approaches
4. **Document Findings** - Use common finding titles for better matching

---

## Troubleshooting

### Template Not Rendering

**Problem:** Template preview shows errors

**Solutions:**
- Check JSON structure validity
- Verify `section_type` names
- Ensure engagement_id is valid
- Check database has sufficient data

### Placeholders Not Replaced

**Problem:** `{{PLACEHOLDER}}` appears in output

**Solutions:**
- Verify placeholder name is correct
- Check engagement has required data
- Ensure field is not NULL in database

### Comparison Returns Empty

**Problem:** Comparison shows no data

**Solutions:**
- Verify all engagement IDs exist
- Check engagements have findings
- Ensure proper engagement_id scoping

---

## Advanced Topics

### Custom Auto-Population

Extend `ReportAutoPopulator` for custom sections:

```python
def populate_custom_section(self) -> str:
    """Custom auto-populated section."""
    cursor = self.cursor

    cursor.execute('''
        SELECT custom_field FROM custom_table
        WHERE engagement_id = ?
    ''', (self.engagement_id,))

    results = cursor.fetchall()

    output = "# Custom Section\n\n"
    for row in results:
        output += f"- {row[0]}\n"

    return output
```

### Template Inheritance

Duplicate and customize default templates:

1. Find default template ID
2. Duplicate with new name
3. Modify structure as needed
4. Save as custom template

### Batch Report Generation

Generate reports for multiple engagements:

```python
for engagement_id in engagement_ids:
    response = requests.post(
        f'/api/reporting/templates/{template_id}/apply',
        json={
            "engagement_id": engagement_id,
            "report_name": f"Report-{engagement_id}"
        }
    )
    print(f"Created report {response.json()['report_id']}")
```

---

## Migration Guide

Existing reports are not affected by the template system. To use templates:

1. **Create Custom Template** - Based on your current report structure
2. **Test with Sample Data** - Preview with existing engagement
3. **Apply to New Engagements** - Use template for future reports
4. **Migrate Old Reports** - Optionally recreate using templates

---

## Further Reading

- [Report Generation](./REPORT_GENERATION.md) - Basic report builder
- [Evidence Management](./EVIDENCE.md) - Managing findings and evidence
- [API Documentation](./API.md) - Complete API reference
