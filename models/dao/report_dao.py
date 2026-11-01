"""Report Data Access Object.

Handles all database operations for reports and writeups.
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class ReportDAO(BaseDAO):
    """DAO for report and writeup management operations.

    Provides methods for managing vulnerability writeups and saved reports.
    """

    def __init__(self):
        """Initialize ReportDAO without engagement scoping (writeups are global)."""
        super().__init__('writeups', engagement_scoped=False)

    def find_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Find writeups by category.

        Args:
            category: Category name

        Returns:
            List of writeup dictionaries
        """
        return self.find_all({'category': category}, order_by='name')

    def find_by_criticality(self, criticality: str) -> List[Dict[str, Any]]:
        """Find writeups by criticality level.

        Args:
            criticality: One of 'critical', 'high', 'medium', 'low'

        Returns:
            List of writeup dictionaries
        """
        return self.find_all({'criticality': criticality}, order_by='cvss_score DESC')

    def search_writeups(self, query: str) -> List[Dict[str, Any]]:
        """Search writeups by name or content.

        Args:
            query: Search query

        Returns:
            List of writeup dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT * FROM writeups
            WHERE name LIKE ? OR description LIKE ? OR remediation LIKE ?
            ORDER BY name
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))

        return [self._row_to_dict(row) for row in cursor.fetchall()]
