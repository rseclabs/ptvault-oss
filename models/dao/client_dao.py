"""Client Data Access Object.

Handles CRUD for the clients table. Clients are global (not engagement-
scoped) so this DAO opts out of the BaseDAO engagement filter.
"""

import logging
from typing import Optional, Dict, Any

from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class ClientDAO(BaseDAO):
    """DAO for client management operations."""

    def __init__(self):
        super().__init__('clients', engagement_scoped=False)

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Case-insensitive lookup by client name.

        Args:
            name: Client name to look up.

        Returns:
            Client dict or None.
        """
        if not name:
            return None
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM clients WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (name.strip(),),
        )
        return self._row_to_dict(cursor.fetchone())

    def count_engagements(self, client_id: int) -> int:
        """Count engagements currently referencing this client.

        Used by the route layer to block deletes when a client still has
        engagements (returns the count so the UI can surface "client has
        N engagements; reassign first").

        Args:
            client_id: ID of the client to check.

        Returns:
            Number of engagements with this client_id.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM engagements WHERE client_id = ?",
            (client_id,),
        )
        return cursor.fetchone()[0]

    def list_options(self):
        """Lightweight listing for dropdowns: id + name only.

        Returns:
            List of dicts with just id and name, ordered by name.
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT id, name FROM clients ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
