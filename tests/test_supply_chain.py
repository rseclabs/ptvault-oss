"""L-5, L-6, L-7: container, dependency and CI pinning.

These are static checks: Docker and GitHub Actions do not run in the test
suite, so the files themselves are checked for the properties that matter.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHA256 = re.compile(r'@sha256:[0-9a-f]{64}\b')


def _read(name):
    return (ROOT / name).read_text()


# ------------------------------------------------------------------ L-5: container

def test_base_image_is_pinned_by_digest():
    froms = [line for line in _read('Dockerfile').splitlines() if line.startswith('FROM ')]
    assert froms and all(SHA256.search(line) for line in froms), froms


def test_container_runs_as_a_non_root_user():
    users = [line.split()[1] for line in _read('Dockerfile').splitlines() if line.startswith('USER ')]
    assert users and users[-1] not in ('root', '0', '0:0')


def test_container_installs_hashed_dependencies():
    dockerfile = _read('Dockerfile')
    assert 'requirements.lock' in dockerfile and '--require-hashes' in dockerfile


def test_compose_publishes_on_loopback_only():
    compose = _read('docker-compose.yml')
    ports = re.findall(r'^\s*-\s*"([^"]+)"\s*$', compose.split('ports:', 1)[1].split('volumes:', 1)[0], re.M)
    assert ports and all(p.startswith('127.0.0.1:') for p in ports), ports


# ------------------------------------------------------------------ L-6: dependencies

def _lock_entries():
    entries, current = {}, None
    for line in _read('requirements.lock').splitlines():
        m = re.match(r'^([A-Za-z0-9_.\-]+)==([^\s;\\]+)', line)
        if m:
            current = m.group(1).lower().replace('_', '-')
            entries[current] = {'version': m.group(2), 'hashes': 0}
        elif current and '--hash=sha256:' in line:
            entries[current]['hashes'] += 1
    return entries


def test_every_locked_package_has_a_hash():
    entries = _lock_entries()
    assert len(entries) > 20
    assert all(e['hashes'] for e in entries.values()), [n for n, e in entries.items() if not e['hashes']]


def test_every_requirement_is_in_the_lock():
    entries = _lock_entries()
    for line in _read('requirements.txt').splitlines():
        name = re.split(r'[\[<>=!~ ;]', line.strip(), maxsplit=1)[0].lower().replace('_', '-')
        if name and not name.startswith('#'):
            assert name in entries, name


def test_python_jose_excludes_the_vulnerable_releases():
    assert 'python-jose[cryptography]>=3.4.0' in _read('requirements.txt')
    major, minor = (int(x) for x in _lock_entries()['python-jose']['version'].split('.')[:2])
    assert (major, minor) >= (3, 4)


# ------------------------------------------------------------------ L-7: CI

def _workflows():
    return list((ROOT / '.github' / 'workflows').glob('*.yml'))


def test_actions_are_pinned_to_commit_shas():
    uses = [u for wf in _workflows() for u in re.findall(r'uses:\s*([^\s#]+)', wf.read_text())]
    assert uses and all(re.search(r'@[0-9a-f]{40}$', u) for u in uses), uses


def test_workflows_declare_read_only_permissions():
    for wf in _workflows():
        text = wf.read_text()
        assert re.search(r'^permissions:\s*\n\s+contents:\s*read\s*$', text, re.M), wf.name


def test_ci_installs_the_hashed_lock():
    for wf in _workflows():
        text = wf.read_text()
        if 'pip install' in text:
            assert '--require-hashes -r requirements.lock' in text, wf.name
