"""Template Data Access Object.

Handles all database operations for report templates.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class TemplateDAO(BaseDAO):
    """DAO for report template operations.

    Provides methods for creating, reading, updating, and deleting report templates,
    as well as applying templates to engagements.
    """

    def __init__(self):
        """Initialize TemplateDAO.

        Note: Templates are NOT engagement-scoped (they are reusable across engagements).
        """
        super().__init__('report_templates', engagement_scoped=False)

    def find_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Find all templates in a category.

        Args:
            category: Category name ('executive', 'technical', 'compliance', 'custom')

        Returns:
            List of template dictionaries
        """
        return self.find_all({'category': category}, order_by='name ASC')

    def find_default_templates(self) -> List[Dict[str, Any]]:
        """Find all default (pre-built) templates.

        Returns:
            List of template dictionaries with is_default=1
        """
        return self.find_all({'is_default': 1}, order_by='category, name')

    def find_public_templates(self) -> List[Dict[str, Any]]:
        """Find all public templates.

        Returns:
            List of template dictionaries with is_public=1
        """
        return self.find_all({'is_public': 1}, order_by='category, name')

    def apply_to_engagement(self, template_id: int, engagement_id: int,
                           report_name: Optional[str] = None) -> int:
        """Apply a template to create a new report.

        Renders auto-populated template sections and converts them into
        format_tool workspace items that the report builder understands.

        Args:
            template_id: Template ID
            engagement_id: Target engagement ID
            report_name: Optional custom report name (defaults to template name)

        Returns:
            int: Created report ID

        Raises:
            ValueError: If template not found
        """
        template = self.find_by_id(template_id)
        if not template:
            raise ValueError('Template not found')

        cursor = self.db.cursor()

        # Use template name if no custom name provided
        if not report_name:
            report_name = template['name']

        # Parse template structure
        try:
            structure = json.loads(template['structure'])
        except (json.JSONDecodeError, TypeError):
            structure = []

        # Render template sections and convert to report workspace items
        from utils.template_renderer import TemplateRenderer
        from utils.report_auto_populator import ReportAutoPopulator

        renderer = TemplateRenderer(self.db, engagement_id)
        populator = ReportAutoPopulator(self.db, engagement_id)

        workspace_items = []
        for section in structure:
            items = self._convert_section_to_workspace_items(
                section, renderer, populator, len(workspace_items)
            )
            workspace_items.extend(items)

        # Create report with rendered workspace items. template_id ties
        # the report back to its source template so get_with_usage_count
        # can report accurate usage statistics.
        cursor.execute('''
            INSERT INTO reports (engagement_id, name, structure, template_id)
            VALUES (?, ?, ?, ?)
        ''', (engagement_id, report_name, json.dumps(workspace_items), template_id))
        report_id = cursor.lastrowid

        self.db.commit()

        logger.info(f"Applied template {template_id} to engagement {engagement_id}, created report {report_id}")
        return report_id

    def _convert_section_to_workspace_items(self, section, renderer, populator,
                                             start_position) -> List[Dict]:
        """Convert a template section into workspace-compatible report items.

        Auto sections are rendered into section header + text block pairs.
        Custom sections with placeholders are resolved and stored as text blocks.

        Args:
            section: Template section definition
            renderer: TemplateRenderer instance
            populator: ReportAutoPopulator instance
            start_position: Starting position index

        Returns:
            List of workspace item dicts
        """
        import uuid
        items = []
        pos = start_position
        section_type = section.get('type', 'custom')
        title = section.get('title', '')

        if section_type == 'auto':
            # Render the auto section to get markdown content
            rendered = renderer._render_auto_section(section)
            content = rendered.get('content', '')

            # Add a section header if title is present
            if title:
                items.append({
                    'id': str(uuid.uuid4()),
                    'type': 'format_tool',
                    'source_id': 'sectionheader',
                    'position': pos,
                    'customizations': {},
                    'writeup_type': 'format_tool',
                    'format_tool_id': 'sectionheader',
                    'title': 'Section Header',
                    'toolData': {'text': title, 'level': 2, 'numbered': False, 'number': ''}
                })
                pos += 1

            # Add the rendered content as a text block
            if content:
                items.append({
                    'id': str(uuid.uuid4()),
                    'type': 'format_tool',
                    'source_id': 'textblock',
                    'position': pos,
                    'customizations': {},
                    'writeup_type': 'format_tool',
                    'format_tool_id': 'textblock',
                    'title': 'Text Block',
                    'toolData': {'content': content}
                })
                pos += 1

        elif section_type == 'custom' or section_type == 'placeholder':
            # Render placeholders in custom sections
            rendered = renderer._render_custom_section(section)
            rendered_title = rendered.get('title', title)
            rendered_content = rendered.get('content', '')

            # Add section header if title is present
            if rendered_title:
                items.append({
                    'id': str(uuid.uuid4()),
                    'type': 'format_tool',
                    'source_id': 'sectionheader',
                    'position': pos,
                    'customizations': {},
                    'writeup_type': 'format_tool',
                    'format_tool_id': 'sectionheader',
                    'title': 'Section Header',
                    'toolData': {'text': rendered_title, 'level': 2, 'numbered': False, 'number': ''}
                })
                pos += 1

            # Add content as text block
            if rendered_content:
                items.append({
                    'id': str(uuid.uuid4()),
                    'type': 'format_tool',
                    'source_id': 'textblock',
                    'position': pos,
                    'customizations': {},
                    'writeup_type': 'format_tool',
                    'format_tool_id': 'textblock',
                    'title': 'Text Block',
                    'toolData': {'content': rendered_content}
                })
                pos += 1

        return items

    def get_with_usage_count(self) -> List[Dict[str, Any]]:
        """Get all templates with usage count.

        Returns:
            List of template dictionaries with 'usage_count' field added
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT
                t.*,
                COUNT(r.id) as usage_count
            FROM report_templates t
            LEFT JOIN reports r ON r.template_id = t.id
            GROUP BY t.id
            ORDER BY t.category, t.name
        ''')

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def duplicate_template(self, template_id: int, new_name: str) -> int:
        """Duplicate an existing template.

        Args:
            template_id: Source template ID
            new_name: Name for the duplicated template

        Returns:
            int: New template ID

        Raises:
            ValueError: If template not found
        """
        template = self.find_by_id(template_id)
        if not template:
            raise ValueError('Template not found')

        cursor = self.db.cursor()

        # Create duplicate
        cursor.execute('''
            INSERT INTO report_templates
            (name, description, category, structure, placeholders, is_default, is_public, created_by)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        ''', (
            new_name,
            template['description'],
            template['category'],
            template['structure'],
            template['placeholders'],
            template['is_public'],
            template['created_by']
        ))

        new_id = cursor.lastrowid
        self.db.commit()

        logger.info(f"Duplicated template {template_id} as {new_id}")
        return new_id
