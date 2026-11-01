"""Markdown report generation for PTVault."""


def generate_markdown_report(engagement_data):
    """
    Generate a well-formatted Markdown report from engagement data.

    Args:
        engagement_data: Dictionary with engagement, evidence, statistics, and export_metadata

    Returns:
        str: Formatted Markdown report
    """
    eng = engagement_data['engagement']
    evidence = engagement_data['evidence']
    stats = engagement_data['statistics']
    export_meta = engagement_data['export_metadata']

    # Group evidence by severity
    critical = [e for e in evidence if e.get('severity_level') == 'critical']
    high = [e for e in evidence if e.get('severity_level') == 'high']
    medium = [e for e in evidence if e.get('severity_level') == 'medium']
    low = [e for e in evidence if e.get('severity_level') == 'low']
    unclassified = [e for e in evidence if not e.get('severity_level')]

    # Start building markdown
    md = []

    # Header
    md.append(f"# Penetration Test Report: {eng['name']}")
    md.append("")
    md.append(f"**Client:** {eng.get('client_name') or 'N/A'}")
    md.append(f"**Engagement Period:** {eng.get('start_date') or 'N/A'} to {eng.get('end_date') or 'N/A'}")
    md.append(f"**Status:** {eng.get('status') or 'N/A'}")
    md.append("")
    md.append("---")
    md.append("")

    # Table of Contents
    md.append("## Table of Contents")
    md.append("- [Executive Summary](#executive-summary)")
    md.append("- [Scope](#scope)")
    md.append("- [Findings Summary](#findings-summary)")
    md.append("- [Detailed Evidence](#detailed-evidence)")
    if critical:
        md.append("  - [Critical Findings](#critical-findings)")
    if high:
        md.append("  - [High Findings](#high-findings)")
    if medium:
        md.append("  - [Medium Findings](#medium-findings)")
    if low:
        md.append("  - [Low Findings](#low-findings)")
    md.append("- [Tools Used](#tools-used)")
    md.append("- [Appendices](#appendices)")
    md.append("")
    md.append("---")
    md.append("")

    # Executive Summary
    md.append("## Executive Summary")
    md.append("")
    md.append(eng.get('description') or "*To be completed*")
    md.append("")
    md.append("---")
    md.append("")

    # Scope
    md.append("## Scope")
    md.append("")
    if eng.get('tags'):
        md.append(f"**Tags:** {eng.get('tags')}")
        md.append("")
    if eng.get('contact_name') or eng.get('contact_email'):
        md.append("**Contact Information:**")
        if eng.get('contact_name'):
            md.append(f"- Name: {eng.get('contact_name')}")
        if eng.get('contact_email'):
            md.append(f"- Email: {eng.get('contact_email')}")
        if eng.get('contact_phone'):
            md.append(f"- Phone: {eng.get('contact_phone')}")
        md.append("")
    md.append("*Detailed scope to be added by pentester*")
    md.append("")
    md.append("---")
    md.append("")

    # Findings Summary
    md.append("## Findings Summary")
    md.append("")
    md.append(f"**Total Evidence Items:** {stats['total_evidence']}")
    md.append("")

    if stats['evidence_by_severity']:
        md.append("**By Severity:**")
        for severity in ['critical', 'high', 'medium', 'low']:
            count = stats['evidence_by_severity'].get(severity, 0)
            md.append(f"- {severity.capitalize()}: {count}")
        md.append("")

    if stats['evidence_by_type']:
        md.append("**By Type:**")
        for etype, count in stats['evidence_by_type'].items():
            md.append(f"- {etype.replace('_', ' ').title()}: {count}")
        md.append("")

    md.append("---")
    md.append("")

    # Detailed Evidence
    md.append("## Detailed Evidence")
    md.append("")

    # Critical Findings
    if critical:
        md.append("### Critical Findings")
        md.append("")
        for i, ev in enumerate(critical, 1):
            md.extend(_format_evidence_item(ev, i))
        md.append("---")
        md.append("")

    # High Findings
    if high:
        md.append("### High Findings")
        md.append("")
        for i, ev in enumerate(high, 1):
            md.extend(_format_evidence_item(ev, i))
        md.append("---")
        md.append("")

    # Medium Findings
    if medium:
        md.append("### Medium Findings")
        md.append("")
        for i, ev in enumerate(medium, 1):
            md.extend(_format_evidence_item(ev, i))
        md.append("---")
        md.append("")

    # Low Findings
    if low:
        md.append("### Low Findings")
        md.append("")
        for i, ev in enumerate(low, 1):
            md.extend(_format_evidence_item(ev, i))
        md.append("---")
        md.append("")

    # Unclassified Evidence (not from security tools)
    if unclassified:
        md.append("### Additional Evidence")
        md.append("")
        md.append("*Evidence without severity classification (notes, screenshots, etc.)*")
        md.append("")
        for i, ev in enumerate(unclassified, 1):
            md.extend(_format_evidence_item(ev, i))
        md.append("---")
        md.append("")

    # Tools Used
    md.append("## Tools Used")
    md.append("")
    if stats['evidence_by_tool']:
        for tool, count in stats['evidence_by_tool'].items():
            md.append(f"- **{tool}**: {count} scan(s)")
    else:
        md.append("*No tool outputs recorded*")
    md.append("")
    md.append("---")
    md.append("")

    # Appendices
    md.append("## Appendices")
    md.append("")

    # All unique tags
    all_tags = set()
    for ev in evidence:
        if ev.get('tags'):
            all_tags.update(ev['tags'])

    if all_tags:
        md.append("### All Tags")
        md.append(", ".join(sorted(all_tags)))
        md.append("")

    # Statistics
    md.append("### Statistics")
    md.append(f"- Total evidence items: {stats['total_evidence']}")
    md.append(f"- Unique tags: {stats['total_tags']}")
    md.append(f"- Files attached: {stats['total_files']}")
    md.append("")

    md.append("---")
    md.append("")
    md.append(f"*Report generated by PTVault on {export_meta['exported_at']}*")

    return "\n".join(md)


def _format_evidence_item(evidence, index):
    """Format a single evidence item as Markdown lines."""
    lines = []

    lines.append(f"#### {index}. {evidence['title']}")
    lines.append("")

    # Metadata header
    lines.append(f"**Type:** {evidence['evidence_type'].replace('_', ' ').title()}")
    if evidence.get('tags'):
        lines.append(f"**Tags:** {', '.join(evidence['tags'])}")
    if evidence.get('tool_name'):
        lines.append(f"**Tool:** {evidence['tool_name']}")
    if evidence.get('severity_level'):
        lines.append(f"**Severity:** {evidence['severity_level'].upper()}")
    lines.append(f"**Date:** {evidence['created_at']}")
    lines.append("")

    # Content
    if evidence.get('content'):
        lines.append(evidence['content'])
        lines.append("")

    # File attachment
    if evidence.get('file_path'):
        lines.append(f"**Attachment:** `{evidence['file_path']}`")
        if evidence.get('file_name'):
            lines.append(f"**Filename:** `{evidence['file_name']}`")
        lines.append("")

    # Tool metadata (formatted nicely)
    if evidence.get('metadata'):
        metadata = evidence['metadata']

        # nmap-specific metadata
        if evidence.get('tool_name') == 'nmap':
            if metadata.get('summary'):
                summary = metadata['summary']
                lines.append("**Scan Summary:**")
                if summary.get('hosts_up'):
                    lines.append(f"- Hosts found: {summary['hosts_up']}")
                if summary.get('total_hosts'):
                    lines.append(f"- Total hosts scanned: {summary['total_hosts']}")
                lines.append("")
            if metadata.get('tool_version'):
                lines.append(f"*Tool: nmap {metadata['tool_version']}*")
                lines.append("")

        # Burp Suite-specific metadata
        elif evidence.get('tool_name') == 'burp_suite':
            if metadata.get('summary'):
                summary = metadata['summary']
                lines.append("**Burp Suite Findings:**")
                if summary.get('total_issues'):
                    lines.append(f"- Total issues: {summary['total_issues']}")
                if summary.get('by_severity'):
                    for sev, count in summary['by_severity'].items():
                        if count > 0:
                            lines.append(f"- {sev}: {count}")
                lines.append("")

        # Nessus-specific metadata
        elif evidence.get('tool_name') == 'nessus':
            if metadata.get('summary'):
                summary = metadata['summary']
                lines.append("**Nessus Scan Results:**")
                if summary.get('total_vulnerabilities'):
                    lines.append(f"- Total vulnerabilities: {summary['total_vulnerabilities']}")
                if summary.get('hosts_scanned'):
                    lines.append(f"- Hosts scanned: {summary['hosts_scanned']}")
                if summary.get('by_severity'):
                    for sev, count in summary['by_severity'].items():
                        if count > 0:
                            lines.append(f"- {sev}: {count}")
                lines.append("")

    lines.append("")
    return lines
