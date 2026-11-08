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


def env_flag(name):
    """True if the environment variable is set to 1, true or yes."""
    return os.environ.get(name, '').strip().lower() in ('1', 'true', 'yes')


def default_upload_folder(database_path):
    """PTVAULT_UPLOAD_FOLDER, or 'uploads' beside the database (M-14)."""
    return os.environ.get('PTVAULT_UPLOAD_FOLDER') or \
        os.path.join(os.path.dirname(os.path.abspath(database_path)), 'uploads')


def encryption_required():
    """PTVAULT_ENCRYPTION_REQUIRED: on by default; 0, false or no turns it off."""
    return os.environ.get('PTVAULT_ENCRYPTION_REQUIRED', '').strip().lower() not in ('0', 'false', 'no')


class Config:
    """Application configuration."""

    # Flask configuration. SECRET_KEY and JWT_SECRET_KEY default to a random
    # value per import; app.py calls load_secrets() at startup to validate
    # environment values or load the persisted ones.
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
    # Exception details and tracebacks in API errors, and the Werkzeug debugger,
    # only when asked for: ENVIRONMENT defaults to development (L-2, L-10).
    DEBUG = env_flag('PTVAULT_DEBUG')

    # Encryption configuration. The key and salt are bound to one database,
    # so by default they live next to it: pointing DATABASE_PATH at another
    # location must never overwrite a different database's key.
    ENCRYPTION_KEY_FILE = os.environ.get('PTVAULT_ENCRYPTION_KEY_FILE',
        os.path.join(os.path.dirname(os.path.abspath(DATABASE_PATH)), 'encryption.key'))
    ENCRYPTION_SALT_FILE = os.environ.get('PTVAULT_ENCRYPTION_SALT_FILE',
        os.path.join(os.path.dirname(os.path.abspath(DATABASE_PATH)), 'encryption.salt'))
    # On unless set to 0/false/no: refuse to start without SQLCipher (M-8)
    ENCRYPTION_REQUIRED = encryption_required()
    # Keep writing the derived key to ENCRYPTION_KEY_FILE so restarts need no
    # passphrase. Weaker: anyone who can read that file can open the database.
    STORE_KEY_FILE = env_flag('PTVAULT_STORE_KEY_FILE')

    # File upload configuration. Evidence lives beside the database it belongs to
    # (M-14); PTVAULT_UPLOAD_FOLDER overrides. LEGACY_UPLOAD_FOLDER is where older
    # versions kept it, checked at startup in case files need moving.
    UPLOAD_FOLDER = default_upload_folder(DATABASE_PATH)
    LEGACY_UPLOAD_FOLDER = os.path.join(RUNTIME_DIR, 'data', 'uploads')
    MAX_FILE_SIZE = 250 * 1024 * 1024  # 250 MB limit
    ALLOWED_EXTENSIONS = {'.txt', '.xml', '.json', '.png', '.jpg', '.jpeg', '.pdf', '.html', '.log', '.pcap', '.nessus'}


# --------------------------------------------------------------- secrets

# Values shipped in .env.example and the docs, plus common stand-ins. A
# known value lets anyone forge session tokens, so PTVault refuses them.
PLACEHOLDER_SECRETS = frozenset({
    'your_secret_key_here',
    'your_jwt_secret_key_here',
    'your_random_64_char_hex_string',
    'your_random_base64_string',
    'changeme',
    'change_me',
    'secret',
    'secret123',
    'development',
})
MIN_SECRET_BYTES = 32

# Generated secrets live beside the database, like the encryption key.
def debugger_allowed(requested, interface, environment, frozen):
    """The Werkzeug debugger runs code typed into the browser: only when asked for
    (--debug or PTVAULT_DEBUG), on a loopback interface, outside production and
    frozen builds (L-10)."""
    return bool(requested and not frozen and environment != 'production'
                and interface in ('localhost', '127.0.0.1', '::1'))


SECRET_FILES = {
    'SECRET_KEY': 'flask_secret.key',
    'JWT_SECRET_KEY': 'jwt_secret.key',
}


class InsecureSecretError(RuntimeError):
    """A signing secret is a placeholder or too short to be safe."""


def check_secret(name, value):
    """Raise InsecureSecretError unless value is a usable signing secret."""
    stripped = (value or '').strip()
    if stripped.lower() in PLACEHOLDER_SECRETS:
        raise InsecureSecretError(
            f"{name} is a placeholder value. Remove it to have PTVault generate one, "
            f"or set a random value of at least {MIN_SECRET_BYTES} bytes "
            "(python3 -c \"import secrets; print(secrets.token_hex(32))\").")
    if len(stripped.encode('utf-8')) < MIN_SECRET_BYTES:
        raise InsecureSecretError(
            f"{name} is shorter than {MIN_SECRET_BYTES} bytes. Remove it to have PTVault "
            "generate one, or set a longer random value.")


def _load_or_create_secret_file(name, path):
    """Return the secret stored at path, creating it (mode 0600) on first use."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        # Write a private temp file, then link it into place: the link is
        # atomic and fails if another worker got there first, so no process
        # ever reads a half-written secret.
        value = secrets.token_hex(32)
        tmp_path = f"{path}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(value + '\n')
            os.link(tmp_path, path)
            return value
        except FileExistsError:
            pass  # another worker created it; use theirs
        finally:
            os.unlink(tmp_path)
    with open(path, 'r', encoding='utf-8') as f:
        value = f.read().strip()
    check_secret(f"{name} in {path}", value)
    return value


def load_secrets(config=Config):
    """Set SECRET_KEY and JWT_SECRET_KEY for the running app.

    An environment value must pass check_secret. Without one, a random value
    is generated once and stored beside the database, so restarts and
    multiple workers share it. Raises InsecureSecretError on a bad value.
    """
    data_dir = os.path.dirname(os.path.abspath(config.DATABASE_PATH))
    for name, filename in SECRET_FILES.items():
        value = os.environ.get(name)
        if value is not None and value.strip():
            check_secret(name, value)
            value = value.strip()
        elif value is not None:
            raise InsecureSecretError(f"{name} is set but empty. Remove it or set a random value.")
        else:
            value = _load_or_create_secret_file(name, os.path.join(data_dir, filename))
        setattr(config, name, value)
