"""
Atomic Red Team Downloader for PTVault.

Downloads one pinned commit of the Atomic Red Team repository, verifies it,
and imports its atomics/ folder (M-6):

- the archive is fetched with a timeout and a size cap,
- zip entries cannot escape the work folder and the extracted size is capped,
- a SHA-256 over the extracted atomics/ tree (every file's path and content)
  must match ATOMICS_TREE_SHA256 - GitHub generates archive zips on demand, so
  the tree, not the zip bytes, is what is pinned,
- only then is the library replaced, beside the database (not in the working
  directory), and only one download runs at a time.

To move to a newer commit: pick one that has been on master for at least two
weeks, download its archive, compute atomics_tree_sha256() over its atomics/
folder, and update ATOMICS_COMMIT and ATOMICS_TREE_SHA256 together.
"""

import hashlib
import os
import shutil
import tempfile
import threading
import zipfile

import requests

from config import Config

ATOMICS_COMMIT = '1edbe50b8f49560110e6cf85161c1ef75a5732b7'   # master, 2026-10-21
ATOMICS_ZIP_URL = f'https://github.com/redcanaryco/atomic-red-team/archive/{ATOMICS_COMMIT}.zip'
ATOMICS_ARCHIVE_ROOT = f'atomic-red-team-{ATOMICS_COMMIT}'
ATOMICS_TREE_SHA256 = '4a879134139745885e35528e8e8021f4abee4ebd8d42caec8471acc6640a454d'  # 1325 files under atomics/
ATOMICS_MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024     # the pinned archive is ~169 MB
ATOMICS_MAX_EXTRACTED_BYTES = 600 * 1024 * 1024    # ~291 MB uncompressed
ATOMICS_DOWNLOAD_TIMEOUT = (15, 120)               # connect, read (seconds)

_download_lock = threading.Lock()


class AtomicsDownloadError(Exception):
    """The pinned archive could not be fetched, verified or unpacked."""


def atomics_dir():
    """The Atomics folder: beside the database, like the key and salt files."""
    return os.path.join(os.path.dirname(os.path.abspath(Config.DATABASE_PATH)), 'atomics')


def get_atomics_path():
    """Get the path to the atomics techniques folder."""
    return os.path.join(atomics_dir(), 'techniques')


def is_atomics_installed():
    """Check if atomics are installed."""
    return os.path.isdir(get_atomics_path())


def atomics_tree_sha256(root):
    """SHA-256 over every file under root: sorted relative paths and their contents."""
    entries = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            digest = hashlib.sha256()
            with open(path, 'rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    digest.update(block)
            entries.append((os.path.relpath(path, root).replace(os.sep, '/'), digest.hexdigest()))
    tree = hashlib.sha256()
    for rel, file_hash in sorted(entries):
        tree.update(f'{rel}\0{file_hash}\n'.encode('utf-8'))
    return tree.hexdigest()


def _download(zip_path):
    """Yield (downloaded, total) while fetching the pinned archive to zip_path."""
    response = requests.get(ATOMICS_ZIP_URL, stream=True, timeout=ATOMICS_DOWNLOAD_TIMEOUT)
    response.raise_for_status()
    total = int(response.headers.get('content-length') or 0) or 170 * 1024 * 1024
    downloaded = 0
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            downloaded += len(chunk)
            if downloaded > ATOMICS_MAX_DOWNLOAD_BYTES:
                raise AtomicsDownloadError('download is larger than expected')
            f.write(chunk)
            yield downloaded, total


def _extract_atomics(zip_path, work):
    """Extract only <root>/atomics/ into work, refusing unsafe entries; return its path."""
    dest = os.path.realpath(os.path.join(work, 'extract'))
    prefix = f'{ATOMICS_ARCHIVE_ROOT}/atomics/'
    with zipfile.ZipFile(zip_path) as archive:
        members, total = [], 0
        for info in archive.infolist():
            name = info.filename
            target = os.path.realpath(os.path.join(dest, name))
            is_symlink = (info.external_attr >> 16) & 0o170000 == 0o120000
            if os.path.isabs(name) or name.startswith(('/', '\\')) or is_symlink \
                    or not target.startswith(dest + os.sep):
                raise AtomicsDownloadError(f'unsafe path in archive: {name!r}')
            if name.startswith(prefix):
                members.append(info)
                total += info.file_size
        if total > ATOMICS_MAX_EXTRACTED_BYTES:
            raise AtomicsDownloadError('archive contents are larger than expected')
        if not members:
            raise AtomicsDownloadError('archive does not contain the atomics folder')
        archive.extractall(dest, members=members)
    return os.path.join(dest, ATOMICS_ARCHIVE_ROOT, 'atomics')


def _install(staged_atomics, work):
    """Replace the installed library with the verified copy."""
    os.makedirs(atomics_dir(), exist_ok=True)
    final = get_atomics_path()
    previous = os.path.join(work, 'previous')
    if os.path.exists(final):
        os.rename(final, previous)
    shutil.move(staged_atomics, final)
    return final


def download_and_parse_atomics_with_progress(db_conn):
    """
    Download, verify, install and parse the pinned Atomic Red Team commit.
    Yields progress dictionaries for streaming (stage, percent, message).
    """
    from utils.atomics_parser import parse_all_atomics_with_progress, update_atomics_metadata

    if not _download_lock.acquire(blocking=False):
        yield {'stage': 'error', 'percent': 0, 'error': 'An Atomics download is already running'}
        return
    work = None
    try:
        os.makedirs(atomics_dir(), exist_ok=True)
        work = tempfile.mkdtemp(prefix='download-', dir=atomics_dir())
        zip_path = os.path.join(work, 'atomic-red-team.zip')

        # Stage 1: Download (0-50%)
        yield {'stage': 'download', 'percent': 0, 'message': f'Downloading commit {ATOMICS_COMMIT[:12]}...'}
        last = 0
        for downloaded, total in _download(zip_path):
            if downloaded - last >= 512 * 1024:
                last = downloaded
                yield {'stage': 'download', 'percent': min(49, int(downloaded / total * 50)),
                       'message': f'Downloading... {downloaded // (1024 * 1024)}MB / ~{total // (1024 * 1024)}MB'}
        yield {'stage': 'download', 'percent': 50, 'message': 'Download complete'}

        # Stage 2: Extract and verify (50-60%); nothing installed has changed yet
        yield {'stage': 'extract', 'percent': 52, 'message': 'Extracting and verifying...'}
        staged = _extract_atomics(zip_path, work)
        if atomics_tree_sha256(staged) != ATOMICS_TREE_SHA256:
            raise AtomicsDownloadError('the Atomics library does not match the pinned SHA-256')
        atomics_path = _install(staged, work)
        yield {'stage': 'extract', 'percent': 60, 'message': 'Verified and installed'}

        # Stage 3: Parse (60-95%)
        yield {'stage': 'parse', 'percent': 62, 'message': 'Parsing atomic tests...'}
        stats = None
        for progress in parse_all_atomics_with_progress(atomics_path, db_conn):
            yield {'stage': 'parse', 'percent': 60 + int(progress['percent'] * 0.35),
                   'message': progress['message']}
            if 'stats' in progress:
                stats = progress['stats']

        # Stage 4: Finalize (95-100%)
        yield {'stage': 'finalize', 'percent': 96, 'message': 'Updating metadata...'}
        if stats:
            update_atomics_metadata(db_conn, atomics_path, stats, version=ATOMICS_COMMIT)

        flagged = (stats or {}).get('plan_items_flagged', 0)
        message = f'Complete! {stats["total_tests"]} tests from {stats["total_techniques"]} techniques'
        if flagged:
            message += f'; {flagged} test plan item(s) changed and need review'
        yield {
            'stage': 'complete',
            'percent': 100,
            'message': message,
            'success': True,
            'total_techniques': stats['total_techniques'],
            'total_tests': stats['total_tests'],
            'plan_items_flagged': flagged,
        }

    except requests.RequestException as e:
        yield {'stage': 'error', 'percent': 0, 'error': f'Download failed: {e}'}
    except (AtomicsDownloadError, zipfile.BadZipFile) as e:
        yield {'stage': 'error', 'percent': 0, 'error': f'Download rejected: {e}'}
    except Exception as e:
        yield {'stage': 'error', 'percent': 0, 'error': f'Failed: {e}'}
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
        _download_lock.release()


def download_and_parse_atomics(db_conn):
    """Non-streaming wrapper: run the download and return the final result."""
    last = None
    for last in download_and_parse_atomics_with_progress(db_conn):
        pass
    if last and last.get('stage') == 'complete':
        return {'success': True, 'message': last['message'], 'total_techniques': last['total_techniques'],
                'total_tests': last['total_tests'], 'download_path': get_atomics_path()}
    return {'success': False, 'error': (last or {}).get('error', 'unknown error')}
