"""Team Data Access Object.

Handles all database operations for teams and team membership.
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class TeamDAO(BaseDAO):
    """DAO for team management operations."""

    def __init__(self):
        super().__init__('teams', engagement_scoped=False)

    def find_all_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Find all teams a user belongs to."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT t.*, tm.role as member_role
            FROM teams t
            JOIN team_members tm ON t.id = tm.team_id
            WHERE tm.user_id = ?
            ORDER BY t.name
        ''', (user_id,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_members(self, team_id: int) -> List[Dict[str, Any]]:
        """Get all members of a team with user details."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT tm.id, tm.team_id, tm.user_id, tm.role, tm.added_at, tm.added_by,
                   u.username, u.email
            FROM team_members tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.team_id = ?
            ORDER BY tm.role DESC, u.username
        ''', (team_id,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def add_member(self, team_id: int, user_id: int, role: str = 'member',
                   added_by: Optional[int] = None) -> int:
        """Add a member to a team. Returns the membership ID."""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO team_members (team_id, user_id, role, added_by)
            VALUES (?, ?, ?, ?)
        ''', (team_id, user_id, role, added_by))
        self.db.commit()
        return cursor.lastrowid

    def update_member_role(self, member_id: int, role: str) -> bool:
        """Update a team member's role."""
        cursor = self.db.cursor()
        cursor.execute('''
            UPDATE team_members SET role = ? WHERE id = ?
        ''', (role, member_id))
        self.db.commit()
        return cursor.rowcount > 0

    def remove_member(self, member_id: int) -> bool:
        """Remove a member from a team."""
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM team_members WHERE id = ?', (member_id,))
        self.db.commit()
        return cursor.rowcount > 0

    def is_member(self, team_id: int, user_id: int) -> bool:
        """Check if a user is a member of a team."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?
        ''', (team_id, user_id))
        return cursor.fetchone() is not None

    def get_user_team_ids(self, user_id: int) -> List[int]:
        """Get all team IDs a user belongs to."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT team_id FROM team_members WHERE user_id = ?
        ''', (user_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_user_role_in_team(self, team_id: int, user_id: int) -> Optional[str]:
        """Get a user's role in a specific team."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT role FROM team_members WHERE team_id = ? AND user_id = ?
        ''', (team_id, user_id))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_accessible_engagement_ids(self, user_id: int) -> List[int]:
        """Get engagement IDs accessible to a user through team membership."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT e.id
            FROM engagements e
            JOIN team_members tm ON e.team_id = tm.team_id
            WHERE tm.user_id = ?
        ''', (user_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_team_for_engagement(self, engagement_id: int) -> Optional[Dict[str, Any]]:
        """Get the team assigned to an engagement."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT t.*
            FROM teams t
            JOIN engagements e ON e.team_id = t.id
            WHERE e.id = ?
        ''', (engagement_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row)

    def get_member_by_id(self, member_id: int) -> Optional[Dict[str, Any]]:
        """Get a team member record by ID."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT id, team_id, user_id, role, added_at, added_by
            FROM team_members WHERE id = ?
        ''', (member_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row)
