"""Uploaded evidence files, encrypted at rest with the database key (M-14).

SQLCipher protects only the database. While it is encrypted, every evidence
file is stored as a PyNaCl SecretBox (XSalsa20-Poly1305) under a key derived
from the in-memory database key, so after a restart the files are as locked as
the database: nothing can read them until /unlock is given the passphrase.

Each file gets its own key, derived with keyed BLAKE2b from the database key and
the file's path relative to the upload folder ("<engagement_id>/<name>"). A file
copied or renamed to another record's path therefore does not decrypt.

Format of an encrypted file: MAGIC, then the SecretBox output (24-byte nonce,
ciphertext, 16-byte tag). Files without MAGIC are plaintext: written before this
change or while encryption is off. encrypt_existing() converts them on the first
unlock; decrypt_existing() reverses it before encryption is disabled.

Files are created 0600 in 0700 directories, and every write goes to a temporary
file in the same directory first, then os.replace, so a crash never leaves a
half-written evidence file.
"""

import logging
import os
import stat

import nacl.exceptions
import nacl.hash
import nacl.secret
from nacl.encoding import RawEncoder

from config import Config
from models import encryption

logger = logging.getLogger(__name__)

MAGIC = b'PTVAULT-ENC1\n'
_PERSON = b'ptvault-upload1'           # BLAKE2b personalisation (max 16 bytes)
_TMP_SUFFIX = '.ptvault-tmp'
FILE_MODE = 0o600
DIR_MODE = 0o700


class UploadDecryptError(Exception):
    """An encrypted evidence file does not open with this database's key."""


def _normalise(relative_path):
    return relative_path.replace(os.sep, '/').lstrip('/')


def _database_key():
    """The database key (hex), or None while the database is not encrypted.

    Raises encryption.DatabaseLocked when the database is encrypted but locked.
    """
    if not encryption.is_encryption_enabled():
        return None
    return encryption.get_encryption_key()


def _file_key(relative_path):
    """The file's own key, or None while the database is not encrypted."""
    db_key = _database_key()
    if db_key is None:
        return None
    return nacl.hash.blake2b(_normalise(relative_path).encode('utf-8'), key=bytes.fromhex(db_key),
                             person=_PERSON, digest_size=nacl.secret.SecretBox.KEY_SIZE, encoder=RawEncoder)


def ensure_dir(path):
    """Create a directory 0700, and any missing parents 0700 too.

    os.makedirs applies its mode only to the last directory (and the umask
    reduces it), so each missing level is created and chmod-ed in turn.
    """
    path = os.path.abspath(path)
    missing = []
    current = path
    while not os.path.isdir(current):
        missing.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    for directory in reversed(missing):
        os.makedirs(directory, mode=DIR_MODE, exist_ok=True)
        os.chmod(directory, DIR_MODE)
    os.chmod(path, DIR_MODE)


def _atomic_write(full_path, data):
    ensure_dir(os.path.dirname(full_path))
    tmp = full_path + _TMP_SUFFIX
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, FILE_MODE)
        os.replace(tmp, full_path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _seal(relative_path, data):
    key = _file_key(relative_path)
    if key is None:
        return data
    return MAGIC + nacl.secret.SecretBox(key).encrypt(data)


def _open(relative_path, stored):
    if not stored.startswith(MAGIC):
        return stored
    key = _file_key(relative_path)
    if key is None:
        raise UploadDecryptError(f'{relative_path} is encrypted but the database is not')
    try:
        return nacl.secret.SecretBox(key).decrypt(stored[len(MAGIC):])
    except nacl.exceptions.CryptoError:
        raise UploadDecryptError(f'{relative_path} does not open with this database key')


def write_file(full_path, relative_path, data):
    """Store an evidence file: encrypted while the database is, always 0600."""
    _atomic_write(full_path, _seal(relative_path, data))


def read_file(full_path, relative_path):
    """Return an evidence file's contents.

    Raises encryption.DatabaseLocked while locked, UploadDecryptError if the
    file does not open with this key, OSError if it cannot be read.
    """
    with open(full_path, 'rb') as f:
        return _open(relative_path, f.read())


def is_sealed(full_path):
    with open(full_path, 'rb') as f:
        return f.read(len(MAGIC)) == MAGIC


def _evidence_files(upload_folder):
    """(full_path, relative_path) for each regular file under the upload folder."""
    for root, dirs, names in os.walk(upload_folder):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in names:
            full_path = os.path.join(root, name)
            if name.endswith(_TMP_SUFFIX) or not stat.S_ISREG(os.lstat(full_path).st_mode):
                continue
            yield full_path, _normalise(os.path.relpath(full_path, upload_folder))


def harden_permissions(upload_folder=None):
    """Make the upload folder 0700 throughout and its files 0600."""
    upload_folder = upload_folder or Config.UPLOAD_FOLDER
    if not os.path.isdir(upload_folder):
        return
    for root, dirs, _ in os.walk(upload_folder):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        os.chmod(root, DIR_MODE)
    for full_path, _ in _evidence_files(upload_folder):
        os.chmod(full_path, FILE_MODE)


def encrypt_existing(upload_folder=None):
    """Encrypt plaintext evidence files in place; return how many were converted.

    Run after the database key becomes available (unlock, setup, enabling
    encryption, an unattended start). Does nothing while the database is not
    encrypted. Safe to repeat: sealed files are skipped.
    """
    upload_folder = upload_folder or Config.UPLOAD_FOLDER
    if not os.path.isdir(upload_folder) or _database_key() is None:
        return 0
    converted = 0
    for full_path, relative_path in _evidence_files(upload_folder):
        if is_sealed(full_path):
            continue
        with open(full_path, 'rb') as f:
            data = f.read()
        write_file(full_path, relative_path, data)
        converted += 1
    harden_permissions(upload_folder)
    if converted:
        logger.info('Encrypted %d existing evidence file(s)', converted)
    return converted


def decrypt_existing(upload_folder=None):
    """Decrypt every sealed evidence file in place; return how many.

    Run before encryption is disabled, while the key is still available.
    """
    upload_folder = upload_folder or Config.UPLOAD_FOLDER
    if not os.path.isdir(upload_folder):
        return 0
    converted = 0
    for full_path, relative_path in _evidence_files(upload_folder):
        if not is_sealed(full_path):
            continue
        data = read_file(full_path, relative_path)
        _atomic_write(full_path, data)
        converted += 1
    if converted:
        logger.info('Decrypted %d evidence file(s)', converted)
    return converted


def legacy_upload_folder_warning():
    """Explain a move if the old upload folder holds files and the new one none.

    UPLOAD_FOLDER used to be fixed to <app>/data/uploads; it now follows
    DATABASE_PATH. An install with DATABASE_PATH elsewhere must move its files.
    """
    legacy = getattr(Config, 'LEGACY_UPLOAD_FOLDER', None)
    if not legacy or os.path.realpath(legacy) == os.path.realpath(Config.UPLOAD_FOLDER):
        return None
    if not (os.path.isdir(legacy) and any(True for _ in _evidence_files(legacy))):
        return None
    if os.path.isdir(Config.UPLOAD_FOLDER) and any(True for _ in _evidence_files(Config.UPLOAD_FOLDER)):
        return None
    return (f'Evidence files are in {legacy}, but uploads are now kept beside the database in '
            f'{Config.UPLOAD_FOLDER}. Move the folder there (or set PTVAULT_UPLOAD_FOLDER) and restart.')
