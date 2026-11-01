"""Seed default report templates.

Provides 4 pre-built templates for common report types.
"""

import json
import logging

logger = logging.getLogger(__name__)


def seed_default_templates(conn):
    """Seed default report templates if they don't exist.

    Args:
        conn: Database connection
    """
    cursor = conn.cursor()

    # Check if defaults already exist
    cursor.execute('SELECT COUNT(*) FROM report_templates WHERE is_default = 1')
    if cursor.fetchone()[0] > 0:
        logger.info("Default templates already exist, skipping seed")
        return

    templates = [
        _executive_summary_template(),
        _technical_report_template(),
        _compliance_report_template(),
        _quick_assessment_template()
    ]

    for template in templates:
        cursor.execute('''
            INSERT INTO report_templates
            (name, description, category, structure, placeholders, is_default, is_public)
            VALUES (?, ?, ?, ?, ?, 1, 1)
        ''', (
            template['name'],
            template['description'],
            template['category'],
            json.dumps(template['structure']),
            json.dumps(template['placeholders'])
        ))

    conn.commit()
    logger.info(f"Seeded {len(templates)} default report templates")


def _executive_summary_template() -> dict:
    """Executive Summary template - High-level overview for executives."""
    return {
        'name': 'Executive Summary Report',
        'description': 'High-level overview with critical findings and risk summary for executive audiences',
        'category': 'executive',
        'placeholders': {
            'ENGAGEMENT_NAME': 'Name of the engagement',
            'CLIENT_NAME': 'Client organization name',
            'DATE_RANGE': 'Engagement date range',
            'CRITICAL_COUNT': 'Number of critical findings',
            'HIGH_COUNT': 'Number of high findings'
        },
        'structure': [
            {
                'type': 'auto',
                'section_type': 'executive_summary',
                'title': 'Executive Summary',
                'config': {}
            },
            {
                'type': 'auto',
                'section_type': 'findings_list',
                'title': 'Critical and High Risk Findings',
                'config': {
                    'severity': None,  # All findings
                    'limit': 10  # Top 10 only
                }
            },
            {
                'type': 'auto',
                'section_type': 'recommendations',
                'title': 'Prioritized Recommendations',
                'config': {}
            },
            {
                'type': 'custom',
                'title': 'Conclusion',
                'content': '''The security assessment of {{CLIENT_NAME}} identified {{CRITICAL_COUNT}} critical and {{HIGH_COUNT}} high-severity findings that require immediate attention.

We recommend prioritizing the remediation steps outlined in this report to improve the overall security posture of the organization.

Our team is available to assist with remediation efforts and answer any questions regarding these findings.'''
            }
        ]
    }


def _technical_report_template() -> dict:
    """Technical Report template - Detailed findings with evidence."""
    return {
        'name': 'Technical Assessment Report',
        'description': 'Comprehensive technical report with detailed findings, evidence, and remediation steps',
        'category': 'technical',
        'placeholders': {
            'ENGAGEMENT_NAME': 'Name of the engagement',
            'CLIENT_NAME': 'Client organization name',
            'DATE_RANGE': 'Engagement date range',
            'TESTER_NAME': 'Lead tester name'
        },
        'structure': [
            {
                'type': 'custom',
                'title': 'Introduction',
                'content': '''# {{ENGAGEMENT_NAME}}

**Client:** {{CLIENT_NAME}}
**Assessment Period:** {{DATE_RANGE}}
**Conducted By:** {{TESTER_NAME}}

This report documents the technical findings from the security assessment performed for {{CLIENT_NAME}}.'''
            },
            {
                'type': 'auto',
                'section_type': 'executive_summary',
                'title': 'Executive Summary',
                'config': {}
            },
            {
                'type': 'auto',
                'section_type': 'methodology',
                'title': 'Testing Methodology',
                'config': {}
            },
            {
                'type': 'auto',
                'section_type': 'host_summary',
                'title': 'Scope and Host Summary',
                'config': {}
            },
            {
                'type': 'auto',
                'section_type': 'findings_list',
                'title': 'Detailed Findings',
                'config': {
                    'severity': None,
                    'limit': None
                }
            },
            {
                'type': 'auto',
                'section_type': 'recommendations',
                'title': 'Remediation Recommendations',
                'config': {}
            }
        ]
    }


def _compliance_report_template() -> dict:
    """Compliance Report template - Findings mapped to frameworks."""
    return {
        'name': 'Compliance Assessment Report',
        'description': 'Report structured for compliance requirements with framework mappings',
        'category': 'compliance',
        'placeholders': {
            'ENGAGEMENT_NAME': 'Name of the engagement',
            'CLIENT_NAME': 'Client organization name',
            'DATE_RANGE': 'Engagement date range'
        },
        'structure': [
            {
                'type': 'custom',
                'title': 'Compliance Assessment',
                'content': '''# Compliance Security Assessment

**Organization:** {{CLIENT_NAME}}
**Assessment Period:** {{DATE_RANGE}}

This report documents the security compliance assessment findings and recommendations.'''
            },
            {
                'type': 'auto',
                'section_type': 'executive_summary',
                'title': 'Executive Summary',
                'config': {}
            },
            {
                'type': 'custom',
                'title': 'Compliance Framework',
                'content': '''## Applicable Standards

This assessment was conducted with reference to the following security frameworks and standards:

- NIST Cybersecurity Framework
- CIS Critical Security Controls
- OWASP Top 10
- Industry-specific compliance requirements'''
            },
            {
                'type': 'auto',
                'section_type': 'findings_list',
                'title': 'Findings by Severity',
                'config': {
                    'severity': None,
                    'limit': None
                }
            },
            {
                'type': 'auto',
                'section_type': 'recommendations',
                'title': 'Compliance Recommendations',
                'config': {}
            },
            {
                'type': 'custom',
                'title': 'Attestation',
                'content': '''## Assessment Attestation

This security assessment was conducted in accordance with industry-standard penetration testing methodologies. All testing was performed with appropriate authorization from {{CLIENT_NAME}}.

The findings documented in this report represent the state of security at the time of testing ({{DATE_RANGE}}) and should be remediated according to the prioritization outlined herein.'''
            }
        ]
    }


def _quick_assessment_template() -> dict:
    """Quick Assessment template - Single-page summary."""
    return {
        'name': 'Quick Assessment Summary',
        'description': 'Simplified single-page summary for rapid assessments',
        'category': 'executive',
        'placeholders': {
            'ENGAGEMENT_NAME': 'Name of the engagement',
            'CLIENT_NAME': 'Client organization name',
            'DATE_RANGE': 'Engagement date range',
            'HOST_COUNT': 'Number of hosts tested',
            'FINDING_COUNT': 'Total findings'
        },
        'structure': [
            {
                'type': 'custom',
                'title': 'Quick Assessment Summary',
                'content': '''# {{ENGAGEMENT_NAME}} - Quick Summary

**Client:** {{CLIENT_NAME}}
**Date:** {{DATE_RANGE}}
**Hosts Tested:** {{HOST_COUNT}}
**Findings:** {{FINDING_COUNT}}'''
            },
            {
                'type': 'auto',
                'section_type': 'executive_summary',
                'title': None,  # No title, inline content
                'config': {}
            },
            {
                'type': 'auto',
                'section_type': 'findings_list',
                'title': 'Key Findings',
                'config': {
                    'severity': None,
                    'limit': 5  # Top 5 only
                }
            },
            {
                'type': 'auto',
                'section_type': 'recommendations',
                'title': 'Immediate Actions',
                'config': {}
            }
        ]
    }
