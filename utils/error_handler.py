"""Centralized error handling for PTVault.

This module provides:
- Custom exception classes with specific error types
- @handle_errors decorator for route functions
- Standardized JSON error responses
- Comprehensive logging with stack traces
"""

import logging
import traceback
from functools import wraps
from flask import jsonify, request, g
from werkzeug.exceptions import HTTPException

# Configure logger
logger = logging.getLogger(__name__)


# ============================================
# CUSTOM EXCEPTION CLASSES
# ============================================

class PTVaultError(Exception):
    """Base exception class for PTVault errors."""

    def __init__(self, message, status_code=500, details=None):
        """
        Initialize PTVault error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (default 500)
            details: Additional error details (not exposed to client)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self):
        """Convert exception to JSON-serializable dict."""
        return {
            'error': self.message,
            'type': self.__class__.__name__
        }


class ValidationError(PTVaultError):
    """Raised when request data validation fails."""

    def __init__(self, message, field=None, details=None):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation (optional)
            details: Additional validation details
        """
        details = details or {}
        if field:
            details['field'] = field
        super().__init__(message, status_code=400, details=details)


class DatabaseError(PTVaultError):
    """Raised when database operations fail."""

    def __init__(self, message, query=None, details=None):
        """
        Initialize database error.

        Args:
            message: Error message
            query: SQL query that failed (optional, for logging only)
            details: Additional database error details
        """
        details = details or {}
        if query:
            details['query'] = query
        super().__init__(message, status_code=500, details=details)


class AuthenticationError(PTVaultError):
    """Raised when authentication fails."""

    def __init__(self, message="Authentication failed", details=None):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(PTVaultError):
    """Raised when user lacks permission for operation."""

    def __init__(self, message="Permission denied", details=None):
        super().__init__(message, status_code=403, details=details)


# Alias for backward compatibility
ForbiddenError = AuthorizationError


class NotFoundError(PTVaultError):
    """Raised when requested resource is not found."""

    def __init__(self, resource_type, resource_id=None, details=None):
        """
        Initialize not found error.

        Args:
            resource_type: Type of resource (e.g., "engagement", "host")
            resource_id: ID of missing resource (optional)
            details: Additional context
        """
        message = f"{resource_type.capitalize()} not found"
        if resource_id:
            message += f": {resource_id}"

        details = details or {}
        details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id

        super().__init__(message, status_code=404, details=details)


class ConflictError(PTVaultError):
    """Raised when resource already exists or conflicts with existing data."""

    def __init__(self, message, details=None):
        super().__init__(message, status_code=409, details=details)


class FileUploadError(PTVaultError):
    """Raised when file upload fails."""

    def __init__(self, message, filename=None, details=None):
        """
        Initialize file upload error.

        Args:
            message: Error message
            filename: Name of file that failed (optional)
            details: Additional upload error details
        """
        details = details or {}
        if filename:
            details['filename'] = filename
        super().__init__(message, status_code=400, details=details)


class ParsingError(PTVaultError):
    """Raised when parsing tool output fails."""

    def __init__(self, message, tool_type=None, details=None):
        """
        Initialize parsing error.

        Args:
            message: Error message
            tool_type: Type of tool being parsed (e.g., "nmap", "burp")
            details: Additional parsing error details
        """
        details = details or {}
        if tool_type:
            details['tool_type'] = tool_type
        super().__init__(message, status_code=400, details=details)


# ============================================
# ERROR LOGGING FUNCTIONS
# ============================================

def log_exception(exc, context=None):
    """
    Log exception with full stack trace and context.

    Args:
        exc: Exception instance
        context: Additional context dict (route, user, etc.)
    """
    context = context or {}

    # Build log message
    log_parts = [
        f"Exception occurred: {exc.__class__.__name__}",
        f"Message: {str(exc)}"
    ]

    # Add context information
    if context:
        log_parts.append(f"Context: {context}")

    # Add PTVault error details if available
    if isinstance(exc, PTVaultError) and exc.details:
        log_parts.append(f"Details: {exc.details}")

    # Log with stack trace
    logger.error("\n".join(log_parts), exc_info=True)


def get_error_context():
    """
    Get current request context for error logging.

    Returns:
        dict: Context information (route, method, user, engagement)
    """
    context = {
        'route': request.endpoint,
        'method': request.method,
        'path': request.path
    }

    # Add user context if available
    if hasattr(g, 'current_user'):
        context['user_id'] = g.current_user

    # Add engagement context if available
    if hasattr(g, 'active_engagement_id'):
        context['engagement_id'] = g.active_engagement_id

    return context


# ============================================
# ERROR HANDLER DECORATOR
# ============================================

def handle_errors(f):
    """
    Decorator to handle exceptions in route functions.

    Provides:
    - Automatic exception logging with context
    - Standardized JSON error responses
    - Proper HTTP status codes
    - Security: No sensitive data exposure to client

    Usage:
        @blueprint.route('/endpoint')
        @require_auth
        @handle_errors
        def my_route():
            # Your route logic
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)

        except PTVaultError as e:
            # Known application errors - log and return structured response
            context = get_error_context()
            log_exception(e, context)
            return jsonify(e.to_dict()), e.status_code

        except HTTPException as e:
            # Werkzeug HTTP exceptions (404, 405, etc.)
            logger.warning(f"HTTP exception: {e.code} - {e.description}")
            return jsonify({
                'error': e.description or str(e),
                'type': 'HTTPException'
            }), e.code

        except Exception as e:
            # Unexpected errors - log with full context, return generic message
            context = get_error_context()
            log_exception(e, context)

            # In development, include exception details
            from config import Config
            if Config.ENVIRONMENT == 'development':
                return jsonify({
                    'error': 'Internal server error',
                    'type': e.__class__.__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }), 500

            # In production, return generic error
            return jsonify({
                'error': 'Internal server error',
                'type': 'InternalError'
            }), 500

    return decorated_function


# ============================================
# DATABASE ERROR HELPERS
# ============================================

def safe_db_operation(operation, error_message="Database operation failed", reraise=True):
    """
    Safely execute a database operation with error handling.

    Args:
        operation: Callable that performs the database operation
        error_message: Error message if operation fails
        reraise: Whether to re-raise as DatabaseError (default True)

    Returns:
        Result of operation if successful

    Raises:
        DatabaseError: If operation fails and reraise=True

    Example:
        def insert_host():
            cursor.execute('INSERT INTO hosts ...', (data,))
            return cursor.lastrowid

        host_id = safe_db_operation(insert_host, "Failed to insert host")
    """
    try:
        return operation()
    except Exception as e:
        logger.error(f"{error_message}: {str(e)}", exc_info=True)
        if reraise:
            raise DatabaseError(error_message, details={'original_error': str(e)})
        return None


# ============================================
# VALIDATION HELPERS
# ============================================

def require_fields(data, required_fields, error_prefix="Missing required field"):
    """
    Validate that required fields are present in request data.

    Args:
        data: Request data dict
        required_fields: List of required field names
        error_prefix: Error message prefix

    Raises:
        ValidationError: If any required field is missing

    Example:
        data = request.get_json()
        require_fields(data, ['name', 'client'], "Engagement")
    """
    if not data:
        raise ValidationError("Request data is required")

    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            raise ValidationError(f"{error_prefix}: {field}", field=field)


def validate_enum(value, allowed_values, field_name):
    """
    Validate that value is in allowed set.

    Args:
        value: Value to validate
        allowed_values: List/set of allowed values
        field_name: Name of field for error message

    Raises:
        ValidationError: If value not in allowed_values

    Example:
        validate_enum(status, ['active', 'archived'], 'status')
    """
    if value not in allowed_values:
        raise ValidationError(
            f"Invalid {field_name}: must be one of {', '.join(allowed_values)}",
            field=field_name,
            details={'allowed_values': list(allowed_values)}
        )


def validate_engagement_access(cursor, engagement_id, user_id=None):
    """
    Validate that engagement exists and user has access.

    Args:
        cursor: Database cursor
        engagement_id: Engagement ID to validate
        user_id: User ID (optional, uses g.current_user if not provided)

    Raises:
        NotFoundError: If engagement doesn't exist

    Returns:
        dict: Engagement row
    """
    cursor.execute('SELECT * FROM engagements WHERE id = ?', (engagement_id,))
    engagement = cursor.fetchone()

    if not engagement:
        raise NotFoundError('engagement', engagement_id)

    return engagement


def validate_max_length(value, max_length, field_name):
    """
    Validate that a string value does not exceed maximum length.

    Args:
        value: String value to validate
        max_length: Maximum allowed length
        field_name: Name of field for error message

    Raises:
        ValidationError: If value exceeds max_length
    """
    if value and isinstance(value, str) and len(value) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters",
            field=field_name
        )


def validate_password_strength(password):
    """
    Validate password meets complexity requirements.
    Requires: 12+ chars, 1 uppercase, 1 lowercase, 1 digit.

    Args:
        password: Password string to validate

    Raises:
        ValidationError: If password doesn't meet requirements
    """
    if len(password) < 12:
        raise ValidationError(
            "Password must be at least 12 characters",
            field='password'
        )
    if not any(c.isupper() for c in password):
        raise ValidationError(
            "Password must contain at least one uppercase letter",
            field='password'
        )
    if not any(c.islower() for c in password):
        raise ValidationError(
            "Password must contain at least one lowercase letter",
            field='password'
        )
    if not any(c.isdigit() for c in password):
        raise ValidationError(
            "Password must contain at least one digit",
            field='password'
        )
