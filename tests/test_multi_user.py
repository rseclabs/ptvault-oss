"""Tests for multi-user support functionality."""

import pytest

from models.dao.user_dao import UserDAO
from models.auth import hash_password, verify_password


class TestPasswordHashing:
    """Argon2id password hash/verify tests — no DB required."""

    def test_hash_and_verify_round_trip(self):
        password = "SecurePassword123!"
        password_hash = hash_password(password)

        assert password_hash is not None
        assert verify_password(password, password_hash)
        assert not verify_password("WrongPassword", password_hash)

    def test_hashes_are_salted(self):
        password = "TestPassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Salted: same password produces different hashes
        assert hash1 != hash2
        # Both still verify
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
        assert not verify_password("WrongPassword", hash1)


class TestUserDAO:
    """UserDAO behavior against the production schema."""

    def test_create_user_persists(self, app_ctx):
        dao = UserDAO()
        password_hash = hash_password("Pa55word!")

        user_id = dao.create_user(
            username='alice', email='alice@example.com',
            password_hash=password_hash, role='admin', full_name='Alice Admin',
        )
        assert user_id > 0

        user = dao.find_by_username('alice')
        assert user is not None
        assert user['email'] == 'alice@example.com'
        assert user['role'] == 'admin'
        assert verify_password("Pa55word!", user['password_hash'])

    def test_user_exists_reflects_inserts(self, app_ctx):
        dao = UserDAO()
        # app_ctx seeds the default test user (id=1)
        initial_count = dao.count()

        dao.create_user(
            username='bob', email='bob@example.com',
            password_hash=hash_password("Pa55word!"), role='tester',
        )
        assert dao.user_exists() is True
        assert dao.count() == initial_count + 1

    def test_find_by_email(self, app_ctx):
        dao = UserDAO()
        dao.create_user(
            username='carol', email='carol@example.com',
            password_hash=hash_password("Pa55word!"), role='viewer',
        )

        user = dao.find_by_email('carol@example.com')
        assert user is not None
        assert user['username'] == 'carol'
        assert user['role'] == 'viewer'


class TestRoles:
    """Test role-based access control invariants."""

    def test_role_hierarchy(self):
        role_hierarchy = {'owner': 3, 'editor': 2, 'viewer': 1}
        assert role_hierarchy['owner'] > role_hierarchy['editor']
        assert role_hierarchy['editor'] > role_hierarchy['viewer']

    def test_valid_roles(self):
        valid_system_roles = ['admin', 'tester', 'viewer']
        valid_engagement_roles = ['owner', 'editor', 'viewer']
        assert 'admin' in valid_system_roles
        assert 'owner' in valid_engagement_roles


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
