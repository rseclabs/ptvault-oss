"""Base Data Access Object with common CRUD operations.

This module provides the foundational DAO class that all specific DAOs inherit from.
It handles common database operations, engagement-based data isolation, and
provides utilities for building dynamic queries safely.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from flask import g

logger = logging.getLogger(__name__)


class BaseDAO:
    """Base class for all DAOs with common database operations.

    This class provides:
    - Automatic engagement-based data isolation
    - Common CRUD operations (find_all, find_by_id, create, update, delete)
    - Safe parameterized query building
    - Database connection management via Flask's g context

    Attributes:
        table_name: The database table this DAO operates on
        engagement_scoped: If True, automatically filters queries by engagement_id
    """

    ALLOWED_ORDER_COLUMNS = {
        'id', 'name', 'title', 'created_at', 'updated_at',
        'status', 'severity', 'criticality', 'ip_address',
        'hostname', 'port', 'email', 'username', 'role',
        'id DESC', 'name DESC', 'title DESC',
        'created_at DESC', 'updated_at DESC',
        'status DESC', 'severity DESC', 'criticality DESC',
    }

    def __init__(self, table_name: str, engagement_scoped: bool = True):
        """Initialize DAO.

        Args:
            table_name: Database table name
            engagement_scoped: If True, automatically filter by engagement_id
        """
        self.table_name = table_name
        self.engagement_scoped = engagement_scoped
        logger.debug(f"Initialized {self.__class__.__name__} for table '{table_name}' "
                    f"(engagement_scoped={engagement_scoped})")

    @property
    def db(self):
        """Get database connection from Flask g context.

        Returns:
            sqlite3.Connection: Database connection

        Raises:
            RuntimeError: If called outside Flask request context
        """
        if not hasattr(g, 'db'):
            raise RuntimeError("Database connection not available. "
                             "Ensure @require_auth middleware is applied.")
        return g.db

    @property
    def engagement_id(self) -> Optional[int]:
        """Get active engagement ID from Flask g context.

        Returns:
            Optional[int]: Active engagement ID, or None if not set
        """
        return getattr(g, 'active_engagement_id', None)

    def _build_where_clause(self, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Build WHERE clause from filters dictionary.

        Automatically adds engagement_id filter if engagement_scoped is True.

        Args:
            filters: Dictionary of column:value pairs to filter by

        Returns:
            Tuple of (where_clause_string, parameter_values)

        Example:
            >>> dao._build_where_clause({'status': 'active', 'name': 'Test'})
            ("status = ? AND name = ? AND engagement_id = ?", ['active', 'Test', 1])
        """
        # Scoped tables always filter by engagement. With no active
        # engagement the filter is "engagement_id = NULL", which matches no
        # rows: fail closed rather than return every engagement's data.
        if self.engagement_scoped:
            filters = {**filters, 'engagement_id': self.engagement_id}

        where_parts = []
        values = []

        for key, value in filters.items():
            where_parts.append(f"{key} = ?")
            values.append(value)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        return where_clause, values

    def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
        """Convert SQLite Row object to dictionary.

        Args:
            row: sqlite3.Row object

        Returns:
            Dictionary with column names as keys, or None if row is None
        """
        if row is None:
            return None
        return dict(row)

    def find_all(self, filters: Optional[Dict[str, Any]] = None,
                 order_by: str = "id",
                 limit: Optional[int] = None,
                 offset: int = 0) -> List[Dict[str, Any]]:
        """Find all records matching filters.

        Args:
            filters: Optional dictionary of column:value pairs to filter by
            order_by: Column to order by (default: 'id')
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of dictionaries, one per matching record

        Example:
            >>> dao.find_all({'status': 'active'}, order_by='created_at DESC', limit=10)
        """
        filters = filters or {}
        where_clause, values = self._build_where_clause(filters)

        # Validate order_by to prevent SQL injection
        if order_by not in self.ALLOWED_ORDER_COLUMNS:
            logger.warning(f"Invalid order_by '{order_by}' for {self.table_name}, defaulting to 'id'")
            order_by = 'id'

        query = f"SELECT * FROM {self.table_name} WHERE {where_clause} ORDER BY {order_by}"

        if limit:
            query += " LIMIT ?"
            values.append(limit)
            if offset:
                query += " OFFSET ?"
                values.append(offset)

        cursor = self.db.cursor()
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def find_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Find record by ID.

        Automatically applies engagement filtering if engagement_scoped is True.

        Args:
            record_id: Primary key value

        Returns:
            Dictionary with record data, or None if not found

        Example:
            >>> dao.find_by_id(123)
            {'id': 123, 'name': 'Test', ...}
        """
        filters = {'id': record_id}
        where_clause, values = self._build_where_clause(filters)

        cursor = self.db.cursor()
        query = f"SELECT * FROM {self.table_name} WHERE {where_clause}"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)

        row = cursor.fetchone()
        return self._row_to_dict(row)

    def find_one(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find single record matching filters.

        Args:
            filters: Dictionary of column:value pairs

        Returns:
            Dictionary with record data, or None if not found

        Example:
            >>> dao.find_one({'email': 'user@example.com'})
        """
        where_clause, values = self._build_where_clause(filters)

        cursor = self.db.cursor()
        query = f"SELECT * FROM {self.table_name} WHERE {where_clause} LIMIT 1"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)

        row = cursor.fetchone()
        return self._row_to_dict(row)

    def create(self, data: Dict[str, Any]) -> int:
        """Create new record.

        Automatically adds engagement_id if engagement_scoped is True.

        Args:
            data: Dictionary of column:value pairs

        Returns:
            int: ID of newly created record

        Raises:
            sqlite3.IntegrityError: If constraints are violated

        Example:
            >>> dao.create({'name': 'Test', 'status': 'active'})
            123
        """
        # Scoped records always belong to the active engagement.
        if self.engagement_scoped:
            if not self.engagement_id:
                raise ValueError(f"no active engagement for {self.table_name} record")
            data = {**data, 'engagement_id': self.engagement_id}

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = list(data.values())

        cursor = self.db.cursor()
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)
        self.db.commit()

        logger.info(f"Created {self.table_name} record with id={cursor.lastrowid}")
        return cursor.lastrowid

    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """Update record by ID.

        Automatically applies engagement filtering if engagement_scoped is True.

        Args:
            record_id: Primary key value
            data: Dictionary of column:value pairs to update

        Returns:
            bool: True if record was updated, False if not found

        Example:
            >>> dao.update(123, {'status': 'completed'})
            True
        """
        if not data:
            logger.warning(f"Update called with empty data for {self.table_name} id={record_id}")
            return False

        # Build SET clause
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = list(data.values())

        # Build WHERE clause
        filters = {'id': record_id}
        where_clause, where_values = self._build_where_clause(filters)
        values.extend(where_values)

        cursor = self.db.cursor()
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)
        self.db.commit()

        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Updated {self.table_name} record id={record_id}")
        else:
            logger.warning(f"No record found to update: {self.table_name} id={record_id}")

        return updated

    def delete(self, record_id: int) -> bool:
        """Delete record by ID.

        Automatically applies engagement filtering if engagement_scoped is True.

        Args:
            record_id: Primary key value

        Returns:
            bool: True if record was deleted, False if not found

        Example:
            >>> dao.delete(123)
            True
        """
        filters = {'id': record_id}
        where_clause, values = self._build_where_clause(filters)

        cursor = self.db.cursor()
        query = f"DELETE FROM {self.table_name} WHERE {where_clause}"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)
        self.db.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted {self.table_name} record id={record_id}")
        else:
            logger.warning(f"No record found to delete: {self.table_name} id={record_id}")

        return deleted

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching filters.

        Args:
            filters: Optional dictionary of column:value pairs

        Returns:
            int: Number of matching records

        Example:
            >>> dao.count({'status': 'active'})
            42
        """
        filters = filters or {}
        where_clause, values = self._build_where_clause(filters)

        cursor = self.db.cursor()
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE {where_clause}"
        logger.debug("Executing: %s", query)          # never the values (L-18)
        cursor.execute(query, values)

        return cursor.fetchone()[0]

    def exists(self, filters: Dict[str, Any]) -> bool:
        """Check if record exists matching filters.

        Args:
            filters: Dictionary of column:value pairs

        Returns:
            bool: True if at least one matching record exists

        Example:
            >>> dao.exists({'email': 'user@example.com'})
            True
        """
        return self.count(filters) > 0
