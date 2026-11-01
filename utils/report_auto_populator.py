"""Report Auto-Population Engine.

Automatically populates report sections from engagement data.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportAutoPopulator:
    """Automatically populate report sections from engagement data.

    Provides methods to generate executive summaries, findings lists,
    host summaries, methodologies, and recommendations from engagement data.
    """

    def __init__(self, db_connection, engagement_id: int):
        """Initialize auto-populator.

        Args:
            db_connection: Database connection
            engagement_id: Engagement ID to pull data from
        """
        self.db = db_connection
        self.engagement_id = engagement_id
        self.cursor = db_connection.cursor()
        self._engagement_cache = None
        self._stats_cache = None

    def _get_engagement(self) -> Dict[str, Any]:
        """Get engagement details (cached)."""
        if self._engagement_cache is None:
            self.cursor.execute(
                'SELECT * FROM engagements WHERE id = ?',
                (self.engagement_id,)
            )
            row = self.cursor.fetchone()
            if row:
                columns = [desc[0] for desc in self.cursor.description]
                self._engagement_cache = dict(zip(columns, row))
            else:
                self._engagement_cache = {}
        return self._engagement_cache

    def _get_statistics(self) -> Dict[str, Any]:
        """Get engagement statistics (cached)."""
        if self._stats_cache is None:
            from models.dao.engagement_dao import EngagementDAO
            dao = EngagementDAO()
            self._stats_cache = dao.get_statistics(self.engagement_id)
        return self._stats_cache

    def populate_executive_summary(self) -> str:
        """Generate executive summary from engagement data.

        Returns:
            Markdown-formatted executive summary
        """
        engagement = self._get_engagement()
        stats = self._get_statistics()

        # Get critical/high findings
        self.cursor.execute('''
            SELECT title, criticality, cvss_score
            FROM engagement_findings
            WHERE engagement_id = ? AND criticality IN ('critical', 'high')
            ORDER BY
                CASE criticality
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                END,
                cvss_score DESC
            LIMIT 5
        ''', (self.engagement_id,))
        critical_findings = self.cursor.fetchall()

        # Build summary
        summary = f"# Executive Summary\n\n"
        summary += f"**Engagement:** {engagement.get('name', 'Unknown')}\n\n"
        summary += f"**Client:** {engagement.get('client_name', 'Unknown')}\n\n"

        if engagement.get('start_date') and engagement.get('end_date'):
            summary += f"**Period:** {engagement['start_date']} to {engagement['end_date']}\n\n"

        summary += f"## Overview\n\n"
        summary += f"This report summarizes the findings from the security assessment conducted for "
        summary += f"{engagement.get('client_name', 'the client')}. "
        summary += f"The assessment included testing of {stats.get('host_count', 0)} systems "
        summary += f"and resulted in {stats.get('findings_count', 0)} documented findings.\n\n"

        # Risk summary
        severity_dist = stats.get('evidence_by_severity', {})
        critical_count = severity_dist.get('critical', 0)
        high_count = severity_dist.get('high', 0)
        medium_count = severity_dist.get('medium', 0)
        low_count = severity_dist.get('low', 0)

        summary += f"## Risk Summary\n\n"
        summary += f"The assessment identified:\n\n"
        summary += f"- **Critical Risk:** {critical_count} finding(s)\n"
        summary += f"- **High Risk:** {high_count} finding(s)\n"
        summary += f"- **Medium Risk:** {medium_count} finding(s)\n"
        summary += f"- **Low Risk:** {low_count} finding(s)\n\n"

        # Key findings
        if critical_findings:
            summary += f"## Key Findings\n\n"
            summary += "The following critical and high-severity issues require immediate attention:\n\n"
            for idx, (title, criticality, cvss) in enumerate(critical_findings, 1):
                cvss_str = f" (CVSS {cvss})" if cvss else ""
                summary += f"{idx}. **{title}** - {criticality.upper()}{cvss_str}\n"
            summary += "\n"

        return summary

    def populate_findings_list(self, severity: Optional[str] = None,
                              limit: Optional[int] = None) -> str:
        """Generate findings list with optional filtering.

        Args:
            severity: Filter by severity ('critical', 'high', 'medium', 'low')
            limit: Maximum number of findings to include

        Returns:
            Markdown-formatted findings list
        """
        query = '''
            SELECT title, criticality, cvss_score, finding_content, remediation_content
            FROM engagement_findings
            WHERE engagement_id = ?
        '''
        params = [self.engagement_id]

        if severity:
            query += ' AND criticality = ?'
            params.append(severity)

        query += '''
            ORDER BY
                CASE criticality
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                cvss_score DESC
        '''

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        self.cursor.execute(query, params)
        findings = self.cursor.fetchall()

        if not findings:
            return "No findings match the specified criteria.\n"

        output = "# Findings\n\n"
        for idx, (title, criticality, cvss, content, remediation) in enumerate(findings, 1):
            output += f"## {idx}. {title}\n\n"
            output += f"**Severity:** {criticality.upper()}"
            if cvss:
                output += f" (CVSS {cvss})"
            output += "\n\n"

            if content:
                output += f"### Description\n\n{content}\n\n"

            if remediation:
                output += f"### Remediation\n\n{remediation}\n\n"

            output += "---\n\n"

        return output

    def populate_host_summary(self) -> str:
        """Generate host summary table.

        Returns:
            Markdown-formatted host table
        """
        self.cursor.execute('''
            SELECT
                h.ip,
                h.hostname,
                h.os,
                COUNT(DISTINCT hp.id) as port_count,
                COUNT(DISTINCT hc.id) as cred_count,
                h.rooted,
                h.shell
            FROM hosts h
            LEFT JOIN host_ports hp ON h.id = hp.host_id
            LEFT JOIN host_credentials hc ON h.id = hc.host_id
            WHERE h.engagement_id = ?
            GROUP BY h.id
            ORDER BY h.ip
        ''', (self.engagement_id,))

        hosts = self.cursor.fetchall()

        if not hosts:
            return "No hosts identified during this engagement.\n"

        output = "# Host Summary\n\n"
        output += "| IP Address | Hostname | OS | Open Ports | Credentials | Status |\n"
        output += "|------------|----------|----|-----------:|------------:|--------|\n"

        for ip, hostname, os, ports, creds, rooted, shell in hosts:
            hostname_str = hostname or '-'
            os_str = os or 'Unknown'
            status_parts = []
            if rooted:
                status_parts.append('Rooted')
            if shell:
                status_parts.append('Shell')
            status = ', '.join(status_parts) if status_parts else '-'

            output += f"| {ip} | {hostname_str} | {os_str} | {ports} | {creds} | {status} |\n"

        output += "\n"
        return output

    def populate_methodology(self) -> str:
        """Generate methodology section from test plans.

        Returns:
            Markdown-formatted methodology
        """
        # Get executed test plans
        self.cursor.execute('''
            SELECT
                tp.name,
                tp.description,
                COUNT(DISTINCT tpi.id) as item_count,
                SUM(CASE WHEN tpi.enabled = 1 THEN 1 ELSE 0 END) as enabled_count
            FROM test_plans tp
            LEFT JOIN test_plan_items tpi ON tp.id = tpi.test_plan_id
            WHERE tp.engagement_id = ?
            GROUP BY tp.id
            ORDER BY tp.created_at
        ''', (self.engagement_id,))

        test_plans = self.cursor.fetchall()

        output = "# Testing Methodology\n\n"
        output += "The following testing methodology was employed during this engagement:\n\n"

        if test_plans:
            output += "## Test Plans Executed\n\n"
            for name, description, items, enabled in test_plans:
                output += f"### {name}\n\n"
                if description:
                    output += f"{description}\n\n"
                output += f"- Total techniques: {items}\n"
                output += f"- Enabled: {enabled}\n\n"
        else:
            output += "## Standard Methodology\n\n"
            output += "Testing followed industry-standard penetration testing practices including:\n\n"
            output += "1. **Reconnaissance** - Information gathering and target enumeration\n"
            output += "2. **Scanning** - Port and vulnerability scanning\n"
            output += "3. **Exploitation** - Attempting to exploit identified vulnerabilities\n"
            output += "4. **Post-Exploitation** - Privilege escalation and lateral movement\n"
            output += "5. **Documentation** - Recording findings and generating reports\n\n"

        return output

    def populate_recommendations(self) -> str:
        """Generate prioritized recommendations from findings.

        Returns:
            Markdown-formatted recommendations
        """
        # Get unique remediation steps grouped by severity
        self.cursor.execute('''
            SELECT criticality, remediation_content
            FROM engagement_findings
            WHERE engagement_id = ? AND remediation_content IS NOT NULL AND remediation_content != ''
            ORDER BY
                CASE criticality
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END
        ''', (self.engagement_id,))

        findings = self.cursor.fetchall()

        if not findings:
            return "No specific recommendations available.\n"

        output = "# Recommendations\n\n"
        output += "Based on the findings identified during this assessment, we recommend the following remediation steps:\n\n"

        # Group by severity
        by_severity = {'critical': [], 'high': [], 'medium': [], 'low': []}
        for criticality, remediation in findings:
            if criticality in by_severity:
                by_severity[criticality].append(remediation)

        priority = 1
        for severity in ['critical', 'high', 'medium', 'low']:
            items = by_severity[severity]
            if items:
                output += f"## {severity.title()} Priority\n\n"
                for remediation in items:
                    output += f"{priority}. {remediation}\n\n"
                    priority += 1

        return output

    def get_placeholder_value(self, placeholder: str) -> str:
        """Get value for a placeholder.

        Args:
            placeholder: Placeholder name (without {{ }})

        Returns:
            str: Replacement value
        """
        engagement = self._get_engagement()
        stats = self._get_statistics()

        placeholders = {
            'ENGAGEMENT_NAME': lambda: engagement.get('name', 'Unknown Engagement'),
            'CLIENT_NAME': lambda: engagement.get('client_name', 'Unknown Client'),
            'DATE_RANGE': lambda: f"{engagement.get('start_date', 'N/A')} to {engagement.get('end_date', 'N/A')}",
            'START_DATE': lambda: engagement.get('start_date', 'N/A'),
            'END_DATE': lambda: engagement.get('end_date', 'N/A'),
            'TESTER_NAME': lambda: engagement.get('contact_name', 'Security Team'),
            'HOST_COUNT': lambda: str(stats.get('host_count', 0)),
            'FINDING_COUNT': lambda: str(stats.get('findings_count', 0)),
            'EVIDENCE_COUNT': lambda: str(stats.get('evidence_count', 0)),
            'CRITICAL_COUNT': lambda: str(stats.get('evidence_by_severity', {}).get('critical', 0)),
            'HIGH_COUNT': lambda: str(stats.get('evidence_by_severity', {}).get('high', 0)),
            'MEDIUM_COUNT': lambda: str(stats.get('evidence_by_severity', {}).get('medium', 0)),
            'LOW_COUNT': lambda: str(stats.get('evidence_by_severity', {}).get('low', 0)),
        }

        if placeholder in placeholders:
            try:
                return placeholders[placeholder]()
            except Exception as e:
                logger.error(f"Error getting placeholder {placeholder}: {e}")
                return f"{{{{ERROR: {placeholder}}}}}"

        return f"{{{{{placeholder}}}}}"  # Return unchanged if unknown
