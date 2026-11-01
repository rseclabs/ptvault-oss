"""Config path defaults.

The encryption key and salt are bound to one database. They must default to
the database's own directory so that pointing DATABASE_PATH somewhere else
(a second instance, a test run) can never overwrite another database's key.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_paths(env_overrides):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('PTVAULT_ENCRYPTION_') and k != 'DATABASE_PATH'}
    env.update(env_overrides)
    code = ("import json; from config import Config; "
            "print(json.dumps([Config.ENCRYPTION_KEY_FILE, Config.ENCRYPTION_SALT_FILE]))")
    out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_key_files_follow_database_path(tmp_path):
    db = tmp_path / 'other' / 'ptvault.db'
    key, salt = _config_paths({'DATABASE_PATH': str(db)})
    assert key == str(tmp_path / 'other' / 'encryption.key')
    assert salt == str(tmp_path / 'other' / 'encryption.salt')


def test_explicit_key_paths_win(tmp_path):
    key, salt = _config_paths({
        'DATABASE_PATH': str(tmp_path / 'ptvault.db'),
        'PTVAULT_ENCRYPTION_KEY_FILE': str(tmp_path / 'k' / 'custom.key'),
        'PTVAULT_ENCRYPTION_SALT_FILE': str(tmp_path / 's' / 'custom.salt'),
    })
    assert key == str(tmp_path / 'k' / 'custom.key')
    assert salt == str(tmp_path / 's' / 'custom.salt')
