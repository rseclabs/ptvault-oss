"""User Data Access Object.

Handles all database operations for user management.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class UserDAO(BaseDAO):
    """DAO for user management operations.

    Supports multi-user PTVault with role-based access control.
    """

    def __init__(self):
        """Initialize UserDAO without engagement scoping."""
        super().__init__('users', engagement_scoped=False)

    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find user by username.

        Args:
            username: Username

        Returns:
            User dictionary or None if not found
        """
        return self.find_one({'username': username})

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find user by email.

        Args:
            email: Email address

        Returns:
            User dictionary or None if not found
        """
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?) LIMIT 1', ((email or '').strip(),))
        return self._row_to_dict(cursor.fetchone())

    def get_primary_user(self) -> Optional[Dict[str, Any]]:
        """Get the primary (first) user.

        Returns:
            User dictionary or None if no users exist
        """
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM users LIMIT 1')
        row = cursor.fetchone()
        return self._row_to_dict(row)

    def user_exists(self) -> bool:
        """Check if any user exists (for setup check).

        Returns:
            bool: True if at least one user exists
        """
        return self.count() > 0

    def create_user(self, username: str, email: str, password_hash: str,
                   role: str = 'tester', full_name: str = None,
                   created_by: int = None) -> int:
        """Create new user.

        Args:
            username: Unique username
            email: Unique email address
            password_hash: Argon2id password hash
            role: User role (admin, tester, viewer)
            full_name: Optional full name
            created_by: User ID who created this user

        Returns:
            int: New user ID

        Raises:
            sqlite3.IntegrityError: If username or email already exists
        """
        data = {
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'full_name': full_name,
            'created_by': created_by
        }
        return self.create(data)

    def get_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users.

        Returns:
            List of user dictionaries (without password_hash)
        """
        users = self.find_all({'is_active': 1}, order_by='username')
        # Remove password hashes for security
        for user in users:
            user.pop('password_hash', None)
        return users

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user account (soft delete).

        Args:
            user_id: User ID to deactivate

        Returns:
            bool: True if deactivated
        """
        return self.update(user_id, {'is_active': 0})

    def delete_user(self, user_id: int) -> bool:
        """Permanently delete a user and clean up dependent rows.

        Removes the user's sessions and engagement memberships, then deletes
        the user row. Foreign keys are not enforced by SQLite by default in
        this codebase, so dependent rows are removed explicitly. Audit log
        entries are preserved for compliance — their user_id will reference a
        removed user, which is acceptable since the audit trail outlives the
        account.

        Args:
            user_id: User ID to delete

        Returns:
            bool: True if the user row was removed
        """
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM engagement_members WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        deleted = cursor.rowcount > 0
        self.db.commit()
        if deleted:
            logger.info(f"Deleted user id={user_id}")
        else:
            logger.warning(f"No user found to delete: id={user_id}")
        return deleted

    def activate_user(self, user_id: int) -> bool:
        """Activate user account.

        Args:
            user_id: User ID to activate

        Returns:
            bool: True if activated
        """
        return self.update(user_id, {'is_active': 1})

    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update user password hash.

        Args:
            user_id: User ID
            password_hash: New password hash (Argon2id)

        Returns:
            bool: True if updated
        """
        return self.update(user_id, {'password_hash': password_hash})

    def update_last_login(self, user_id: int) -> bool:
        """Update last login timestamp.

        Args:
            user_id: User ID

        Returns:
            bool: True if updated
        """
        return self.update(user_id, {'last_login': datetime.utcnow().isoformat()})

    def get_user_engagements(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all engagements a user has access to.

        Args:
            user_id: User ID

        Returns:
            List of engagement dictionaries with member role
        """
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT e.*, em.role as member_role
            FROM engagements e
            JOIN engagement_members em ON e.id = em.engagement_id
            WHERE em.user_id = ?
            ORDER BY e.updated_at DESC
        ''', (user_id,))

        return [dict(row) for row in cursor.fetchall()]
