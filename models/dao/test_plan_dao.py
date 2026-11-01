"""Test Plan Data Access Object.

Handles all database operations for test plans and atomic tests.
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class TestPlanDAO(BaseDAO):
    """DAO for test plan management operations.

    Provides methods for managing test plans and linking atomic tests.
    """

    def __init__(self):
        """Initialize TestPlanDAO with engagement-based scoping."""
        super().__init__('test_plans', engagement_scoped=True)

    def find_with_item_count(self) -> List[Dict[str, Any]]:
        """Get all test plans with count of test items.

        Returns:
            List of test plan dictionaries with 'item_count' field added
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT
                tp.*,
                COUNT(tpi.id) as item_count
            FROM test_plans tp
            LEFT JOIN test_plan_items tpi ON tp.id = tpi.test_plan_id
            WHERE tp.engagement_id = ?
            GROUP BY tp.id
            ORDER BY tp.created_at DESC
        ''', (self.engagement_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_plan_items(self, test_plan_id: int) -> List[Dict[str, Any]]:
        """Get all test items for a test plan.

        Args:
            test_plan_id: Test plan ID

        Returns:
            List of test item dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT * FROM test_plan_items
            WHERE test_plan_id = ?
            ORDER BY created_at
        ''', (test_plan_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def add_test_item(self, test_plan_id: int, technique_id: str,
                     status: str = 'pending', output: Optional[str] = None) -> int:
        """Add test item to a test plan.

        Args:
            test_plan_id: Test plan ID
            technique_id: MITRE ATT&CK technique ID
            status: Test status ('pending', 'completed', 'failed')
            output: Test output/notes

        Returns:
            int: Test item record ID
        """
        cursor = self.db.cursor()

        cursor.execute('''
            INSERT INTO test_plan_items
            (test_plan_id, technique_id, status, output)
            VALUES (?, ?, ?, ?)
        ''', (test_plan_id, technique_id, status, output))
        self.db.commit()

        logger.info(f"Added test item to plan {test_plan_id}")
        return cursor.lastrowid

    def update_test_item_status(self, item_id: int, status: str, output: Optional[str] = None) -> bool:
        """Update test item status and output.

        Args:
            item_id: Test item ID
            status: New status
            output: Optional output text

        Returns:
            bool: True if updated
        """
        cursor = self.db.cursor()

        if output is not None:
            cursor.execute('''
                UPDATE test_plan_items
                SET status = ?, output = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, output, item_id))
        else:
            cursor.execute('''
                UPDATE test_plan_items
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, item_id))

        self.db.commit()

        logger.info(f"Updated test item {item_id} status to {status}")
        return cursor.rowcount > 0
