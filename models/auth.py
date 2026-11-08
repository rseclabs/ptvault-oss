"""Authentication module for master password and session management."""

import hashlib
import secrets
from typing import Optional
from argon2 import PasswordHasher
from argon2.low_level import Type
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import Config


# Argon2 configuration for password hashing
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    type=Type.ID  # Argon2id
)


def hash_master_password(password: str) -> str:
    """
    Hash a master password using Argon2id.

    Args:
        password: The master password to hash

    Returns:
        str: Argon2id hash string (includes salt and parameters)
    """
    return ph.hash(password)


def hash_password(password: str) -> str:
    """
    Hash a user password using Argon2id.
    Alias for hash_master_password for multi-user support.

    Args:
        password: The password to hash

    Returns:
        str: Argon2id hash string (includes salt and parameters)
    """
    return ph.hash(password)


def verify_master_password(password: str, hash: str) -> bool:
    """
    Verify a master password against an Argon2id hash.
    Uses constant-time comparison (handled by argon2-cffi).

    Args:
        password: The password to verify
        hash: The stored Argon2id hash

    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        ph.verify(hash, password)
        return True
    except Exception:
        return False


def verify_password(password: str, hash: str) -> bool:
    """
    Verify a user password against an Argon2id hash.
    Alias for verify_master_password for multi-user support.

    Args:
        password: The password to verify
        hash: The stored Argon2id hash

    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        ph.verify(hash, password)
        return True
    except Exception:
        return False


def create_session_token(user_id: int, role: str = 'tester', username: str = None) -> str:
    """
    Create a JWT session token for a user.

    Args:
        user_id: The user's ID
        role: The user's role (admin, tester, viewer)
        username: The user's username (optional, for logging)

    Returns:
        str: JWT token string
    """
    expiry = datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRY_HOURS)
    payload = {
        'user_id': user_id,
        'role': role,
        'username': username,
        'exp': expiry,
        # Unique per login, so two sessions never share a token (or its
        # session row) and each can be revoked on its own.
        'jti': secrets.token_hex(16),
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    return token


def verify_session_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT session token.

    Args:
        token: The JWT token to verify

    Returns:
        dict: Token payload if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except JWTError:
        return None


def create_session_record(conn, user_id, token):
    """Store the session token hash; a token is only accepted while this row is active."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_sessions (user_id, token_hash, expires_at, created_at, last_active, is_active)
        VALUES (?, ?, datetime('now', ?), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
    ''', (user_id, token_hash, f'+{int(Config.JWT_EXPIRY_HOURS)} hours'))
    conn.commit()
    return cursor.lastrowid


SESSION_OK = 'ok'
SESSION_REVOKED = 'revoked'
SESSION_IDLE = 'idle'


def check_session(conn, token, idle_timeout_minutes):
    """Check the token's session row and record activity.

    Returns SESSION_OK, SESSION_REVOKED (no active row, or past expiry) or
    SESSION_IDLE (inactive longer than the timeout; the row is deactivated).
    Database errors propagate so the caller can refuse the request.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id,
               expires_at IS NOT NULL AND expires_at <= datetime('now') AS expired,
               last_active IS NOT NULL AND last_active < datetime('now', ?) AS idle
        FROM user_sessions
        WHERE token_hash = ? AND is_active = 1
    ''', (f'-{int(idle_timeout_minutes)} minutes', token_hash))
    row = cursor.fetchone()
    if not row:
        return SESSION_REVOKED

    session_id, expired, idle = row[0], row[1], row[2]
    if expired or idle:
        cursor.execute('UPDATE user_sessions SET is_active = 0 WHERE id = ?', (session_id,))
        conn.commit()
        return SESSION_REVOKED if expired else SESSION_IDLE

    cursor.execute('UPDATE user_sessions SET last_active = CURRENT_TIMESTAMP WHERE id = ?', (session_id,))
    conn.commit()
    return SESSION_OK


def revoke_session(conn, token):
    """Revoke a session by marking it inactive."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE user_sessions SET is_active = 0 WHERE token_hash = ?
    ''', (token_hash,))
    conn.commit()


def revoke_all_sessions(conn, user_id):
    """Revoke all sessions for a user."""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE user_sessions SET is_active = 0 WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
