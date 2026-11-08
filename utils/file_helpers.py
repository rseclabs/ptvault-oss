"""File management helper functions for evidence uploads."""

import os
import re
from datetime import datetime
from typing import Optional


def resolve_evidence_file(file_path: Optional[str], engagement_id: int, upload_folder: str) -> Optional[str]:
    """Return the real path of an engagement's evidence file, or None.

    Stored paths are relative ("<engagement_id>/<file>"). The path is
    resolved (following any symlink) and accepted only if it lies inside that
    engagement's own upload folder, so an absolute path, a '..' path or a
    path into another engagement's folder is never read, served or deleted.
    """
    if not file_path or engagement_id is None:
        return None
    engagement_root = os.path.realpath(os.path.join(upload_folder, str(int(engagement_id))))
    full_path = os.path.realpath(os.path.join(upload_folder, file_path))
    if not full_path.startswith(engagement_root + os.sep):
        return None
    return full_path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and ensure filesystem safety.

    - Removes path components (os.path.basename)
    - Replaces spaces with underscores
    - Removes special characters except: . - _
    - Limits length to 255 characters

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized filename safe for filesystem storage
    """
    if not filename:
        return "untitled"

    # Get basename to remove any path components (prevent ../ attacks)
    filename = os.path.basename(filename)

    # Replace spaces with underscores
    filename = filename.replace(' ', '_')

    # Remove special characters except: . - _
    # Keep alphanumeric, dots, hyphens, underscores
    filename = re.sub(r'[^\w\.\-]', '', filename)

    # Limit length to 255 characters (filesystem limit)
    if len(filename) > 255:
        # Preserve file extension if possible
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext

    # Ensure we have a valid filename
    if not filename or filename == '.':
        return "untitled"

    return filename


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """
    Check if a file has an allowed extension.

    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions (e.g., {'.txt', '.xml'})

    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename:
        return False

    # Get file extension (lowercase)
    ext = os.path.splitext(filename)[1].lower()

    return ext in allowed_extensions


def get_file_size_human(bytes_size: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        bytes_size: File size in bytes

    Returns:
        Human-readable string (e.g., "1.5 MB", "500 KB")
    """
    if bytes_size is None:
        return "0 B"

    # Define size units
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0

    return f"{bytes_size:.1f} PB"


def create_safe_filepath(engagement_id: int, evidence_id: int, filename: str) -> tuple:
    """
    Generate a safe file path for storing uploaded evidence.

    Organizes files by engagement_id with unique timestamp and evidence_id
    to prevent conflicts and enable easy cleanup.

    Args:
        engagement_id: ID of the engagement
        evidence_id: ID of the evidence record
        filename: Original filename

    Returns:
        Tuple of (full_path, relative_path)
        - full_path: Absolute path for file storage
        - relative_path: Relative path for database storage
    """
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Sanitize filename
    safe_filename = sanitize_filename(filename)

    # Build path: engagement_id/evidence_id_timestamp_filename
    relative_path = f"{engagement_id}/{evidence_id}_{timestamp}_{safe_filename}"

    # Note: full_path will be constructed by prepending UPLOAD_FOLDER
    # We return relative_path for database storage
    return relative_path, relative_path
