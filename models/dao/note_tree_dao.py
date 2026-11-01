"""Hierarchical-notes Data Access Object.

A single tree implementation parameterized by table + scope-FK column,
so `engagement_notes` and `host_notes` can share all the tree logic.

Storage: adjacency list (parent_id self-reference) plus per-sibling
sort_order for stable ordering. Roots have parent_id = NULL.

The route layer is responsible for:
- Returning 409 when delete would orphan children (use count_children).
- Trimming/validating content before passing it in.

This module is responsible for:
- Atomic create / move / delete operations.
- Cycle prevention on move (refuses to move a note into its own subtree).
- Default sort_order = max(sort_order)+1 within parent when caller
  doesn't supply one.
"""

import logging
from typing import Any, Dict, List, Optional

from flask import g

logger = logging.getLogger(__name__)

# Length cap for the preview snippet returned in list responses. Keeps
# the response payload small for engagements with many large notes.
PREVIEW_CHARS = 500


class NoteTreeDAO:
    """Tree DAO for a notes-style table with a single scope FK."""

    def __init__(self, table: str, scope_column: str):
        """
        Args:
            table: e.g. 'engagement_notes' or 'host_notes'.
            scope_column: e.g. 'engagement_id' or 'host_id'.
        """
        self.table = table
        self.scope_column = scope_column

    @property
    def db(self):
        return g.db

    def list_for(self, scope_id: int) -> List[Dict[str, Any]]:
        """Return the flat note list for a scope, ordered for tree-build.

        Each row includes parent_id, sort_order, title, and a preview of the
        first PREVIEW_CHARS of content plus a has_more flag so the
        frontend can lazy-load full content on click.
        """
        cursor = self.db.cursor()
        cursor.execute(
            f"""
            SELECT id, parent_id, sort_order, title,
                   SUBSTR(content, 1, ?) AS content_preview,
                   LENGTH(content) AS content_length,
                   created_at, updated_at
              FROM {self.table}
             WHERE {self.scope_column} = ?
             ORDER BY (parent_id IS NOT NULL), parent_id, sort_order, id
            """,
            (PREVIEW_CHARS, scope_id),
        )
        notes = []
        for row in cursor.fetchall():
            d = dict(row)
            d['has_more'] = (d['content_length'] or 0) > PREVIEW_CHARS
            notes.append(d)
        return notes

    def get_full(self, note_id: int, scope_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a note's full content (used by the lazy-load endpoint)."""
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT * FROM {self.table} "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (note_id, scope_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create(
        self,
        scope_id: int,
        content: str,
        title: str = '',
        parent_id: Optional[int] = None,
        sort_order: Optional[int] = None,
    ) -> int:
        """Create a note. Returns new note id.

        If parent_id is provided, it must belong to the same scope —
        callers should validate that and either reject or fall back to
        None.

        If sort_order is None, the new note gets max+1 within its parent
        bucket (siblings of the same parent_id, including roots when
        parent_id is None).
        """
        cursor = self.db.cursor()

        if sort_order is None:
            sort_order = self._next_sort_order(scope_id, parent_id)

        cursor.execute(
            f"INSERT INTO {self.table} "
            f"({self.scope_column}, content, title, parent_id, sort_order) "
            "VALUES (?, ?, ?, ?, ?)",
            (scope_id, content, title, parent_id, sort_order),
        )
        self.db.commit()
        return cursor.lastrowid

    def update(self, note_id: int, scope_id: int, content: str, title: str = '') -> bool:
        """Update a note's content and title. Returns True if a row was updated."""
        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE {self.table} "
            "SET content = ?, title = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (content, title, note_id, scope_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def update_content(self, note_id: int, scope_id: int, content: str) -> bool:
        """Update a note's content only. Returns True if a row was updated."""
        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE {self.table} "
            "SET content = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (content, note_id, scope_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def delete(self, note_id: int, scope_id: int) -> bool:
        """Delete a note. Caller must check count_children first."""
        cursor = self.db.cursor()
        cursor.execute(
            f"DELETE FROM {self.table} "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (note_id, scope_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def count_children(self, note_id: int, scope_id: int) -> int:
        """Count direct children of a note in the same scope."""
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {self.table} "
            f"WHERE parent_id = ? AND {self.scope_column} = ?",
            (note_id, scope_id),
        )
        return cursor.fetchone()[0]

    def parent_belongs_to_scope(
        self, parent_id: Optional[int], scope_id: int
    ) -> bool:
        """Verify a candidate parent_id actually exists in this scope.

        None is always valid (root). Callers should reject create/move
        requests where parent_id refers to a note in another scope.
        """
        if parent_id is None:
            return True
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT 1 FROM {self.table} "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (parent_id, scope_id),
        )
        return cursor.fetchone() is not None

    def move(
        self,
        note_id: int,
        scope_id: int,
        new_parent_id: Optional[int],
        new_sort_order: Optional[int],
    ) -> bool:
        """Move a note to a new parent / sort_order within the same scope.

        Refuses cycles: if new_parent_id is the note itself or any of
        its descendants, raises ValueError.

        Returns True on success.
        """
        if new_parent_id is not None:
            if new_parent_id == note_id:
                raise ValueError("Cannot make a note its own parent")
            if not self.parent_belongs_to_scope(new_parent_id, scope_id):
                raise ValueError("Parent note not found in this scope")
            if self._is_descendant(new_parent_id, note_id, scope_id):
                raise ValueError("Cannot move a note into its own subtree")

        if new_sort_order is None:
            new_sort_order = self._next_sort_order(scope_id, new_parent_id)

        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE {self.table} "
            "SET parent_id = ?, sort_order = ?, "
            "    updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = ? AND {self.scope_column} = ?",
            (new_parent_id, new_sort_order, note_id, scope_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _next_sort_order(
        self, scope_id: int, parent_id: Optional[int]
    ) -> int:
        cursor = self.db.cursor()
        if parent_id is None:
            cursor.execute(
                f"SELECT COALESCE(MAX(sort_order), 0) FROM {self.table} "
                f"WHERE {self.scope_column} = ? AND parent_id IS NULL",
                (scope_id,),
            )
        else:
            cursor.execute(
                f"SELECT COALESCE(MAX(sort_order), 0) FROM {self.table} "
                f"WHERE {self.scope_column} = ? AND parent_id = ?",
                (scope_id, parent_id),
            )
        return cursor.fetchone()[0] + 1

    def _is_descendant(
        self, candidate_id: int, ancestor_id: int, scope_id: int
    ) -> bool:
        """True if candidate_id is in the subtree rooted at ancestor_id.

        Walks the parent chain upward from candidate_id to a root or
        until we encounter ancestor_id. Bounded by tree depth, so trees
        of any reasonable depth resolve in microseconds.
        """
        cursor = self.db.cursor()
        current = candidate_id
        seen = set()
        while current is not None:
            if current in seen:
                # Defensive: stop on accidental cycles in legacy data.
                return False
            seen.add(current)
            if current == ancestor_id:
                return True
            cursor.execute(
                f"SELECT parent_id FROM {self.table} "
                f"WHERE id = ? AND {self.scope_column} = ?",
                (current, scope_id),
            )
            row = cursor.fetchone()
            current = row[0] if row else None
        return False
