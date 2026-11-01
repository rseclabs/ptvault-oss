"""
Atomic Red Team Downloader for PTVault.
Downloads and extracts the Atomic Red Team repository from GitHub.
"""

import os
import zipfile
import shutil
import requests
from datetime import datetime
from config import Config

# GitHub URL for Atomic Red Team master branch ZIP
ATOMICS_ZIP_URL = "https://github.com/redcanaryco/atomic-red-team/archive/refs/heads/master.zip"
ATOMICS_DIR = os.path.join(Config.DATA_DIR if hasattr(Config, 'DATA_DIR') else './data', 'atomics')


def download_atomics_zip(progress_callback=None):
    """
    Download the Atomic Red Team ZIP file from GitHub.

    Args:
        progress_callback: Optional callback function(downloaded_bytes, total_bytes)

    Returns:
        str: Path to the downloaded ZIP file
    """
    zip_path = os.path.join(ATOMICS_DIR, 'atomic-red-team.zip')

    # Create atomics directory if it doesn't exist
    os.makedirs(ATOMICS_DIR, exist_ok=True)

    # Download with streaming to handle large file
    response = requests.get(ATOMICS_ZIP_URL, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)

    return zip_path


def extract_atomics_zip(zip_path):
    """
    Extract the Atomic Red Team ZIP file.
    Only extracts the atomics/ folder content.

    Args:
        zip_path: Path to the ZIP file

    Returns:
        str: Path to the extracted atomics folder
    """
    # Extract to temporary location
    temp_extract_dir = os.path.join(ATOMICS_DIR, '_temp_extract')

    # Clean up any previous temp extraction
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)

    # Find the atomics folder inside the extracted content
    # The ZIP extracts to atomic-red-team-master/atomics/
    extracted_root = os.path.join(temp_extract_dir, 'atomic-red-team-master')
    atomics_source = os.path.join(extracted_root, 'atomics')

    if not os.path.exists(atomics_source):
        raise FileNotFoundError(f"Could not find atomics folder in extracted ZIP")

    # Move atomics content to final location
    atomics_dest = os.path.join(ATOMICS_DIR, 'techniques')

    # Remove old techniques folder if it exists
    if os.path.exists(atomics_dest):
        shutil.rmtree(atomics_dest)

    # Move the atomics folder
    shutil.move(atomics_source, atomics_dest)

    # Clean up
    shutil.rmtree(temp_extract_dir)
    os.remove(zip_path)

    return atomics_dest


def download_and_parse_atomics(db_conn):
    """
    Main function to download, extract, and parse Atomic Red Team tests.

    Args:
        db_conn: SQLite database connection

    Returns:
        dict: Result with status and statistics
    """
    from utils.atomics_parser import parse_all_atomics, update_atomics_metadata

    try:
        # Step 1: Download
        print("Downloading Atomic Red Team repository...")
        zip_path = download_atomics_zip()

        # Step 2: Extract
        print("Extracting atomics...")
        atomics_path = extract_atomics_zip(zip_path)

        # Step 3: Parse and populate database
        print("Parsing atomic tests...")
        stats = parse_all_atomics(atomics_path, db_conn)

        # Step 4: Update metadata
        update_atomics_metadata(db_conn, atomics_path, stats)

        return {
            "success": True,
            "message": f"Successfully downloaded and parsed {stats['total_tests']} tests from {stats['total_techniques']} techniques",
            "total_techniques": stats['total_techniques'],
            "total_tests": stats['total_tests'],
            "download_path": atomics_path
        }

    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to download: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to process atomics: {str(e)}"
        }


def download_and_parse_atomics_with_progress(db_conn):
    """
    Download, extract, and parse Atomic Red Team tests with progress updates.
    Yields progress dictionaries for SSE streaming.

    Args:
        db_conn: SQLite database connection

    Yields:
        dict: Progress updates with stage, percent, message
    """
    from utils.atomics_parser import parse_all_atomics_with_progress, update_atomics_metadata

    try:
        # Stage 1: Download (0-50%)
        yield {'stage': 'download', 'percent': 0, 'message': 'Connecting to GitHub...'}

        zip_path = os.path.join(ATOMICS_DIR, 'atomic-red-team.zip')
        os.makedirs(ATOMICS_DIR, exist_ok=True)

        response = requests.get(ATOMICS_ZIP_URL, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        # Estimate ~500MB if no content-length
        if total_size == 0:
            total_size = 500 * 1024 * 1024

        downloaded = 0
        last_yield = 0
        yield_interval = 512 * 1024  # Yield every 512KB

        yield {'stage': 'download', 'percent': 1, 'message': 'Starting download...'}

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):  # Larger chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Only yield every yield_interval bytes to reduce overhead
                    if downloaded - last_yield >= yield_interval:
                        last_yield = downloaded
                        download_percent = min(49, int((downloaded / total_size) * 50))
                        downloaded_mb = downloaded // (1024 * 1024)
                        total_mb = total_size // (1024 * 1024)
                        yield {
                            'stage': 'download',
                            'percent': download_percent,
                            'message': f'Downloading... {downloaded_mb}MB / ~{total_mb}MB'
                        }

        yield {'stage': 'download', 'percent': 50, 'message': 'Download complete'}

        # Stage 2: Extract (50-60%)
        yield {'stage': 'extract', 'percent': 52, 'message': 'Extracting files...'}
        atomics_path = extract_atomics_zip(zip_path)
        yield {'stage': 'extract', 'percent': 60, 'message': 'Extraction complete'}

        # Stage 3: Parse (60-95%)
        yield {'stage': 'parse', 'percent': 62, 'message': 'Parsing atomic tests...'}

        stats = None
        for progress in parse_all_atomics_with_progress(atomics_path, db_conn):
            # Scale parsing progress from 60-95%
            scaled_percent = 60 + int(progress['percent'] * 0.35)
            yield {
                'stage': 'parse',
                'percent': scaled_percent,
                'message': progress['message']
            }
            if 'stats' in progress:
                stats = progress['stats']

        # Stage 4: Finalize (95-100%)
        yield {'stage': 'finalize', 'percent': 96, 'message': 'Updating metadata...'}
        if stats:
            update_atomics_metadata(db_conn, atomics_path, stats)

        yield {
            'stage': 'complete',
            'percent': 100,
            'message': f'Complete! {stats["total_tests"]} tests from {stats["total_techniques"]} techniques',
            'success': True,
            'total_techniques': stats['total_techniques'],
            'total_tests': stats['total_tests']
        }

    except requests.RequestException as e:
        yield {'stage': 'error', 'percent': 0, 'error': f'Download failed: {str(e)}'}
    except Exception as e:
        yield {'stage': 'error', 'percent': 0, 'error': f'Failed: {str(e)}'}


def get_atomics_path():
    """Get the path to the atomics techniques folder."""
    return os.path.join(ATOMICS_DIR, 'techniques')


def is_atomics_installed():
    """Check if atomics are installed."""
    atomics_path = get_atomics_path()
    return os.path.exists(atomics_path) and os.path.isdir(atomics_path)
