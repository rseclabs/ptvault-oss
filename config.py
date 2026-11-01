import os
import sys
import secrets
import base64


def get_base_dir():
    """Get the application base directory, handling PyInstaller frozen bundles."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle — bundled data is in sys._MEIPASS
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_runtime_dir():
    """Get the runtime directory for writable data (database, uploads, keys).

    When frozen, this is the directory containing the executable.
    When running from source, this is the project root.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# Resolve once at import time
BASE_DIR = get_base_dir()
RUNTIME_DIR = get_runtime_dir()


class Config:
    """Application configuration."""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SESSION_TYPE = 'filesystem'  # Store sessions on filesystem
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # Database configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(RUNTIME_DIR, 'data', 'ptvault.db'))

    # JWT configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', 24))

    # Environment
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

    # Encryption configuration. The key and salt are bound to one database,
    # so by default they live next to it: pointing DATABASE_PATH at another
    # location must never overwrite a different database's key.
    ENCRYPTION_KEY_FILE = os.environ.get('PTVAULT_ENCRYPTION_KEY_FILE',
        os.path.join(os.path.dirname(os.path.abspath(DATABASE_PATH)), 'encryption.key'))
    ENCRYPTION_SALT_FILE = os.environ.get('PTVAULT_ENCRYPTION_SALT_FILE',
        os.path.join(os.path.dirname(os.path.abspath(DATABASE_PATH)), 'encryption.salt'))
    ENCRYPTION_REQUIRED = os.environ.get('PTVAULT_ENCRYPTION_REQUIRED', '').lower() == 'true'

    # File upload configuration
    UPLOAD_FOLDER = os.path.join(RUNTIME_DIR, 'data', 'uploads')
    MAX_FILE_SIZE = 250 * 1024 * 1024  # 250 MB limit
    ALLOWED_EXTENSIONS = {'.txt', '.xml', '.json', '.png', '.jpg', '.jpeg', '.pdf', '.html', '.log', '.pcap', '.nessus'}
