"""Audit logging utility for security and compliance tracking."""

from typing import Optional, Dict, Any
from flask import g, request
import json
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logger for tracking sensitive operations.

    Records:
    - User actions (create, update, delete, view, export)
    - Resource types (engagement, evidence, host, report, user, etc.)
    - IP address and user agent
    - Additional context in JSON details field
    """

    @staticmethod
    def log_action(
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        engagement_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log an audit event.

        Args:
            action: Action performed (create, update, delete, view, export)
            resource_type: Type of resource (engagement, evidence, host, etc.)
            resource_id: ID of the resource (if applicable)
            engagement_id: ID of the engagement (if applicable)
            details: Additional context as dictionary (will be JSON serialized)

        Example:
            AuditLogger.log_action(
                action='delete',
                resource_type='evidence',
                resource_id=123,
                engagement_id=5,
                details={'title': 'Nmap Scan', 'reason': 'duplicate'}
            )
        """
        try:
            # Get user info from Flask g context
            if not hasattr(g, 'current_user') or not hasattr(g, 'db'):
                logger.warning("Audit log skipped - no user context available")
                return

            user_id = g.current_user
            db = g.db

            # Get request context
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent') if request else None

            # Serialize details to JSON
            details_json = json.dumps(details) if details else None

            # Insert audit log
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO audit_log (
                    user_id, engagement_id, action, resource_type,
                    resource_id, details, ip_address, user_agent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                engagement_id,
                action,
                resource_type,
                resource_id,
                details_json,
                ip_address,
                user_agent
            ))
            db.commit()

            logger.debug(f"Audit log: user={user_id} action={action} resource={resource_type}/{resource_id}")

        except Exception as e:
            # Don't fail the main operation if audit logging fails
            logger.error(f"Failed to write audit log: {e}")

    @staticmethod
    def get_user_activity(
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """
        Get recent activity for a user.

        Args:
            user_id: User ID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of audit log dictionaries
        """
        if not hasattr(g, 'db'):
            return []

        cursor = g.db.cursor()
        cursor.execute('''
            SELECT
                id, action, resource_type, resource_id,
                engagement_id, details, timestamp
            FROM audit_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', (user_id, limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_engagement_activity(
        engagement_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Get recent activity for an engagement.

        Args:
            engagement_id: Engagement ID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of audit log dictionaries with username
        """
        if not hasattr(g, 'db'):
            return []

        cursor = g.db.cursor()
        cursor.execute('''
            SELECT
                al.id, al.user_id, u.username, al.action,
                al.resource_type, al.resource_id, al.details, al.timestamp
            FROM audit_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.engagement_id = ?
            ORDER BY al.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (engagement_id, limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_resource_history(
        resource_type: str,
        resource_id: int
    ) -> list:
        """
        Get all audit events for a specific resource.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            List of audit log dictionaries with username
        """
        if not hasattr(g, 'db'):
            return []

        cursor = g.db.cursor()
        cursor.execute('''
            SELECT
                al.id, al.user_id, u.username, al.action,
                al.engagement_id, al.details, al.timestamp
            FROM audit_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.resource_type = ? AND al.resource_id = ?
            ORDER BY al.timestamp DESC
        ''', (resource_type, resource_id))

        return [dict(row) for row in cursor.fetchall()]


# Convenience functions for common audit events

def audit_create(resource_type: str, resource_id: int, engagement_id: Optional[int] = None, **details):
    """Log resource creation."""
    AuditLogger.log_action('create', resource_type, resource_id, engagement_id, details or None)


def audit_update(resource_type: str, resource_id: int, engagement_id: Optional[int] = None, **details):
    """Log resource update."""
    AuditLogger.log_action('update', resource_type, resource_id, engagement_id, details or None)


def audit_delete(resource_type: str, resource_id: int, engagement_id: Optional[int] = None, **details):
    """Log resource deletion."""
    AuditLogger.log_action('delete', resource_type, resource_id, engagement_id, details or None)


def audit_view(resource_type: str, resource_id: int, engagement_id: Optional[int] = None, **details):
    """Log resource viewing (for sensitive data)."""
    AuditLogger.log_action('view', resource_type, resource_id, engagement_id, details or None)


def audit_export(resource_type: str, resource_id: int, engagement_id: Optional[int] = None, **details):
    """Log data export."""
    AuditLogger.log_action('export', resource_type, resource_id, engagement_id, details or None)
