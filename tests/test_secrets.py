"""H-8 / L-4: signing secrets are never placeholders and survive restarts.

A SECRET_KEY or JWT_SECRET_KEY from the environment must not be a known
placeholder or shorter than 32 bytes, or PTVault refuses to start. When one is
not set, a random value is generated once and kept beside the database, so a
restart (or a second worker) uses the same key.
"""

import os
import stat
import subprocess
import sys

import pytest

import config
from config import Config, InsecureSecretError, check_secret, load_secrets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRONG = 'a3f1' * 16  # 64 characters


@pytest.mark.parametrize('value', [
    'your_secret_key_here',
    'your_jwt_secret_key_here',
    '  YOUR_SECRET_KEY_HERE  ',
    'changeme',
    'x' * 31,
    '',
])
def test_weak_secrets_are_rejected(value):
    with pytest.raises(InsecureSecretError):
        check_secret('SECRET_KEY', value)


def test_strong_secret_is_accepted():
    check_secret('SECRET_KEY', STRONG)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'data' / 'ptvault.db'))
    monkeypatch.setattr(Config, 'SECRET_KEY', Config.SECRET_KEY)
    monkeypatch.setattr(Config, 'JWT_SECRET_KEY', Config.JWT_SECRET_KEY)
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.delenv('JWT_SECRET_KEY', raising=False)
    return tmp_path / 'data'


def test_unset_secrets_are_generated_once_and_reused(isolated_config):
    load_secrets()
    first = (Config.SECRET_KEY, Config.JWT_SECRET_KEY)
    assert first[0] != first[1]
    for value in first:
        check_secret('generated', value)

    Config.SECRET_KEY = Config.JWT_SECRET_KEY = None  # a fresh start
    load_secrets()
    assert (Config.SECRET_KEY, Config.JWT_SECRET_KEY) == first


def test_generated_secret_files_are_private(isolated_config):
    load_secrets()
    files = sorted(p.name for p in isolated_config.iterdir())
    assert files == sorted(config.SECRET_FILES.values())
    for path in isolated_config.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_environment_secret_wins_and_is_checked(isolated_config, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', STRONG)
    monkeypatch.setenv('JWT_SECRET_KEY', 'your_jwt_secret_key_here')
    with pytest.raises(InsecureSecretError):
        load_secrets()

    monkeypatch.setenv('JWT_SECRET_KEY', STRONG[::-1])
    load_secrets()
    assert Config.SECRET_KEY == STRONG
    assert Config.JWT_SECRET_KEY == STRONG[::-1]


def test_tampered_secret_file_is_rejected(isolated_config):
    load_secrets()
    jwt_file = isolated_config / config.SECRET_FILES['JWT_SECRET_KEY']
    jwt_file.write_text('short')
    with pytest.raises(InsecureSecretError):
        load_secrets()


def test_app_refuses_to_start_with_placeholder_secret(tmp_path):
    env = dict(os.environ)
    env.update({
        'SECRET_KEY': 'your_secret_key_here',
        'JWT_SECRET_KEY': STRONG,
        'DATABASE_PATH': str(tmp_path / 'ptvault.db'),
        'PTVAULT_ENCRYPTION_KEY_FILE': str(tmp_path / 'encryption.key'),
        'PTVAULT_ENCRYPTION_SALT_FILE': str(tmp_path / 'encryption.salt'),
    })
    result = subprocess.run([sys.executable, '-c', 'import app'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'SECRET_KEY' in result.stderr
    assert not (tmp_path / 'ptvault.db').exists()
