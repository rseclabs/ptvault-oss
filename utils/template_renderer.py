"""Template Renderer.

Renders report templates with auto-populated content and placeholder replacement.
"""

import re
import json
import logging
from typing import Dict, Any, List
from utils.report_auto_populator import ReportAutoPopulator

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Render report templates with all sections and placeholders."""

    def __init__(self, db_connection, engagement_id: int):
        """Initialize renderer.

        Args:
            db_connection: Database connection
            engagement_id: Engagement ID for data population
        """
        self.db = db_connection
        self.engagement_id = engagement_id
        self.populator = ReportAutoPopulator(db_connection, engagement_id)

    def render_template(self, template_structure: str) -> List[Dict[str, Any]]:
        """Render complete template with all sections.

        Args:
            template_structure: JSON string of template structure

        Returns:
            List of rendered section dictionaries
        """
        try:
            sections = json.loads(template_structure)
        except (json.JSONDecodeError, TypeError):
            logger.error("Invalid template structure JSON")
            return []
        if not isinstance(sections, list):
            logger.error("Template structure is not a list of sections")
            return []

        rendered = []

        for section in (s for s in sections if isinstance(s, dict)):
            try:
                rendered_section = self._render_section(section)
                rendered.append(rendered_section)
            except Exception as e:
                logger.error(f"Error rendering section: {e}")
                rendered.append({
                    'title': section.get('title', 'Error'),
                    'content': f"Error rendering section: {str(e)}",
                    'type': 'error'
                })

        return rendered

    def _render_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Render a single section.

        Args:
            section: Section configuration dictionary

        Returns:
            Rendered section dictionary
        """
        section_type = section.get('type', 'custom')
        section_subtype = section.get('section_type')

        # Handle auto-populated sections
        if section_type == 'auto' or section_subtype:
            return self._render_auto_section(section)

        # Handle placeholder replacement in custom sections
        if section_type == 'custom' or section_type == 'placeholder':
            return self._render_custom_section(section)

        # Pass through other types
        return {
            'title': section.get('title'),
            'content': section.get('content', ''),
            'type': section_type,
            'config': section.get('config', {})
        }

    def _render_auto_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Render auto-populated section.

        Args:
            section: Section configuration

        Returns:
            Rendered section with auto-generated content
        """
        section_type = section.get('section_type') or section.get('type')
        config = section.get('config', {})

        content = ''

        if section_type == 'executive_summary' or section_type == 'auto_summary':
            content = self.populator.populate_executive_summary()

        elif section_type == 'findings_list' or section_type == 'auto_findings':
            severity = config.get('severity')
            limit = config.get('limit')
            content = self.populator.populate_findings_list(severity, limit)

        elif section_type == 'host_summary' or section_type == 'auto_hosts':
            content = self.populator.populate_host_summary()

        elif section_type == 'methodology' or section_type == 'auto_methodology':
            content = self.populator.populate_methodology()

        elif section_type == 'recommendations' or section_type == 'auto_recommendations':
            content = self.populator.populate_recommendations()

        else:
            content = f"Unknown auto-section type: {section_type}"
            logger.warning(content)

        return {
            'title': section.get('title') or self._get_default_title(section_type),
            'content': content,
            'type': 'auto',
            'section_type': section_type,
            'config': config
        }

    def _render_custom_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Render custom section with placeholder replacement.

        Args:
            section: Section configuration

        Returns:
            Rendered section with placeholders replaced
        """
        content = section.get('content', '')
        title = section.get('title', '')

        # Replace placeholders in both title and content
        if title:
            title = self._replace_placeholders(title)
        if content:
            content = self._replace_placeholders(content)

        return {
            'title': title,
            'content': content,
            'type': section.get('type', 'custom'),
            'config': section.get('config', {})
        }

    def _replace_placeholders(self, text: str) -> str:
        """Replace placeholders like {{ENGAGEMENT_NAME}} in text.

        Args:
            text: Text with placeholders

        Returns:
            Text with placeholders replaced
        """
        # Find all {{PLACEHOLDER}} patterns
        pattern = r'\{\{([A-Z_]+)\}\}'

        def replacer(match):
            placeholder = match.group(1)
            return self.populator.get_placeholder_value(placeholder)

        return re.sub(pattern, replacer, text)

    def _get_default_title(self, section_type: str) -> str:
        """Get default title for auto-section type.

        Args:
            section_type: Section type identifier

        Returns:
            Default section title
        """
        titles = {
            'executive_summary': 'Executive Summary',
            'auto_summary': 'Executive Summary',
            'findings_list': 'Findings',
            'auto_findings': 'Findings',
            'host_summary': 'Host Summary',
            'auto_hosts': 'Host Summary',
            'methodology': 'Testing Methodology',
            'auto_methodology': 'Testing Methodology',
            'recommendations': 'Recommendations',
            'auto_recommendations': 'Recommendations'
        }

        return titles.get(section_type, 'Section')

    def render_report_with_template(self, report_id: int, template_id: int) -> Dict[str, Any]:
        """Render an existing report using a template.

        Args:
            report_id: Report ID
            template_id: Template ID to apply

        Returns:
            Complete rendered report dictionary
        """
        cursor = self.db.cursor()

        # Get report
        cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        report_row = cursor.fetchone()
        if not report_row:
            raise ValueError('Report not found')

        columns = [desc[0] for desc in cursor.description]
        report = dict(zip(columns, report_row))

        # Get template
        cursor.execute('SELECT * FROM report_templates WHERE id = ?', (template_id,))
        template_row = cursor.fetchone()
        if not template_row:
            raise ValueError('Template not found')

        template_columns = [desc[0] for desc in cursor.description]
        template = dict(zip(template_columns, template_row))

        # Render sections
        rendered_sections = self.render_template(template['structure'])

        return {
            'report': report,
            'template': template,
            'sections': rendered_sections,
            'metadata': {
                'engagement_id': self.engagement_id,
                'template_id': template_id,
                'report_id': report_id
            }
        }
