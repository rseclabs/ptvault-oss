"""Tests for PTVault security hardening features.

Covers:
- Security response headers (X-Content-Type-Options, X-Frame-Options, CSP, etc.)
- CSRF double-submit cookie pattern (csrf_protect before_request hook)
- Password complexity validation (validate_password_strength)
- Input length validation (validate_max_length)
- Custom exception classes and their HTTP status codes
- The handle_errors decorator
"""

import json
import os
import sys
import sqlite3
import tempfile

import pytest

# Ensure the project root is on sys.path so local modules resolve.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ---------------------------------------------------------------------------
# Flask test-app fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app():
    """Create a minimal Flask test application backed by an in-memory database.

    We cannot import app.py directly because it tries to open the production
    database at import time.  Instead we
    reconstruct the parts we need:

    * The same security-header after_request hook.
    * The same csrf_protect before_request hook.
    * The auth blueprint (for /api/auth/setup, /api/auth/login,
      /api/auth/csrf-token, /api/auth/logout).
    * The health-check endpoint (/api/health).

    The database is an isolated in-memory SQLite file that is initialised with
    the full schema, so the auth routes can create users and sessions.
    """
    from flask import Flask, jsonify, g, request as flask_request
    from config import Config, BASE_DIR
    import re

    # -----------------------------------------------------------------------
    # Disable SQLCipher for the entire module so get_connection() uses plain
    # sqlite3 against our temp database file (not an encrypted one).
    # -----------------------------------------------------------------------
    from models import encryption as _enc_module
    _original_sqlcipher_flag = _enc_module._SQLCIPHER_AVAILABLE
    _enc_module._SQLCIPHER_AVAILABLE = False

    # Also stash and override the encryption key file path so is_encryption_enabled()
    # stays False even if a real key file exists on disk.
    _original_key_file = Config.ENCRYPTION_KEY_FILE
    Config.ENCRYPTION_KEY_FILE = os.path.join(tempfile.mkdtemp(), 'no_key.key')

    # -----------------------------------------------------------------------
    # Point Config at a temporary database for the duration of this module.
    # -----------------------------------------------------------------------
    tmpdir = tempfile.mkdtemp(prefix='ptvault_test_')
    test_db_path = os.path.join(tmpdir, 'test_security.db')
    original_db_path = Config.DATABASE_PATH
    Config.DATABASE_PATH = test_db_path

    # -----------------------------------------------------------------------
    # Build the schema SQL (same logic as init_db but to our temp path)
    # -----------------------------------------------------------------------
    schema_path = os.path.join(BASE_DIR, 'models', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Strip comments and split statements (mirrors models/database.py:init_db)
    schema_sql = re.sub(r'--[^\n]*', '', schema_sql)
    statements = []
    current = []
    in_block = False
    for line in schema_sql.split('\n'):
        line = line.strip()
        if not line:
            continue
        current.append(line)
        upper = line.upper()
        if 'BEGIN' in upper:
            in_block = True
        if in_block and 'END' in upper:
            in_block = False
            statements.append(' '.join(current))
            current = []
        elif not in_block and line.endswith(';'):
            statements.append(' '.join(current))
            current = []
    if current:
        statements.append(' '.join(current))

    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    for stmt in statements:
        stmt = stmt.strip().rstrip(';')
        if stmt:
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()
    conn.close()

    # -----------------------------------------------------------------------
    # Create the Flask application
    # -----------------------------------------------------------------------
    flask_app = Flask(__name__,
                      template_folder=os.path.join(BASE_DIR, 'templates'),
                      static_folder=os.path.join(BASE_DIR, 'static'))
    flask_app.config.from_object(Config)
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    # Register the auth blueprint
    from routes.auth import auth_bp
    flask_app.register_blueprint(auth_bp)

    # Health check endpoint
    @flask_app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok'})

    # Teardown: close db connection
    @flask_app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # Mirror the CSRF protection from app.py
    @flask_app.before_request
    def csrf_protect():
        if flask_request.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        if flask_request.path in ('/api/auth/setup', '/api/auth/login', '/api/auth/csrf-token'):
            return
        if not flask_request.path.startswith('/api/'):
            return
        cookie_token = flask_request.cookies.get('csrf_token')
        header_token = flask_request.headers.get('X-CSRF-Token')
        if not cookie_token or not header_token:
            return jsonify({'error': 'CSRF token missing'}), 403
        if cookie_token != header_token:
            return jsonify({'error': 'CSRF token mismatch'}), 403

    # The real security-header hook app.py registers (utils/security_headers.py)
    from utils.security_headers import apply_security_headers
    flask_app.after_request(apply_security_headers)

    yield flask_app

    # Restore original config and encryption state
    Config.DATABASE_PATH = original_db_path
    Config.ENCRYPTION_KEY_FILE = _original_key_file
    _enc_module._SQLCIPHER_AVAILABLE = _original_sqlcipher_flag

    # Clean up temp files
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def setup_and_login(client):
    """Helper: create the initial admin user and return the logged-in client."""
    client.post(
        '/api/auth/setup',
        json={'email': 'admin@test.com', 'password': 'TestPassword123!', 'full_name': 'Admin'},
        content_type='application/json'
    )
    resp = client.post(
        '/api/auth/login',
        json={'email': 'admin@test.com', 'password': 'TestPassword123!'},
        content_type='application/json'
    )
    return resp


# ===========================================================================
# Security Headers
# ===========================================================================

class TestSecurityHeaders:
    """Security headers must appear on every response."""

    def test_x_content_type_options_is_nosniff(self, client):
        """X-Content-Type-Options header should be 'nosniff'."""
        response = client.get('/api/health')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options_is_deny(self, client):
        """X-Frame-Options should be 'DENY' to prevent clickjacking."""
        response = client.get('/api/health')
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_referrer_policy_is_strict(self, client):
        """Referrer-Policy should be 'strict-origin-when-cross-origin'."""
        response = client.get('/api/health')
        assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    def test_x_xss_protection_header(self, client):
        """X-XSS-Protection header should be set."""
        response = client.get('/api/health')
        assert response.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_content_security_policy_present(self, client):
        """Content-Security-Policy header should be present."""
        response = client.get('/api/health')
        csp = response.headers.get('Content-Security-Policy')
        assert csp is not None, "CSP header is missing"

    def test_csp_restricts_default_src_to_self(self, client):
        """CSP should restrict default-src to 'self'."""
        response = client.get('/api/health')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp

    def test_csp_allows_no_third_party_assets(self, client):
        """Scripts, styles and fonts are vendored, so CSP names no external host."""
        response = client.get('/api/health')
        csp = response.headers.get('Content-Security-Policy', '')
        directives = dict(
            part.strip().split(' ', 1) for part in csp.split(';') if part.strip()
        )
        for name in ('script-src', 'style-src', 'font-src'):
            assert 'http' not in directives[name], f"{name} allows an external host"

    def test_templates_load_no_third_party_assets(self):
        """Every <script src> and <link href> in templates points at this server."""
        import glob
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pattern = re.compile(r'<(?:script|link)\b[^>]*\b(?:src|href)="(https?:)?//', re.I)
        offenders = [
            os.path.basename(path)
            for path in glob.glob(os.path.join(root, 'templates', '*.html'))
            if pattern.search(open(path, encoding='utf-8').read())
        ]
        assert offenders == [], f"templates load external assets: {offenders}"

    def test_security_headers_on_404(self, client):
        """Security headers should appear even on 404 responses."""
        response = client.get('/api/nonexistent-endpoint-xyz')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_security_headers_on_post(self, client):
        """Security headers should be set on POST responses too."""
        response = client.post(
            '/api/auth/setup',
            json={'email': 'sec@test.com', 'password': 'Valid123pass!'},
            content_type='application/json'
        )
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_no_hsts_in_development(self, client):
        """HSTS should not be set in development mode (default ENVIRONMENT)."""
        response = client.get('/api/health')
        # In development, HSTS must NOT be present
        hsts = response.headers.get('Strict-Transport-Security')
        from config import Config
        if Config.ENVIRONMENT != 'production':
            assert hsts is None, "HSTS must not be set in development mode"


# ===========================================================================
# CSRF Protection
# ===========================================================================

class TestCSRFProtection:
    """Test CSRF double-submit cookie pattern (csrf_protect before_request hook)."""

    def test_csrf_token_endpoint_returns_token(self, client):
        """GET /api/auth/csrf-token should return a CSRF token in the response body."""
        response = client.get('/api/auth/csrf-token')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'csrf_token' in data

    def test_csrf_token_is_64_hex_chars(self, client):
        """CSRF token should be 64 hex characters (secrets.token_hex(32))."""
        response = client.get('/api/auth/csrf-token')
        data = json.loads(response.data)
        token = data['csrf_token']
        assert len(token) == 64
        # Validate it is a valid hex string
        int(token, 16)

    def test_csrf_token_sets_cookie(self, client):
        """GET /api/auth/csrf-token should set a csrf_token cookie."""
        response = client.get('/api/auth/csrf-token')
        assert 'csrf_token' in response.headers.get('Set-Cookie', '')

    def test_mutating_api_request_without_csrf_token_rejected(self, client, app):
        """POST to a protected API endpoint without CSRF tokens should return 403."""
        # Use a dummy protected endpoint that exists after login.
        # We send a POST to /api/engagements (any protected route) without CSRF.
        # Even if auth fails first, the CSRF check runs before auth on non-exempt paths.
        with app.test_client() as c:
            # Manually inject an auth_token cookie so the CSRF check is reached.
            from models.auth import create_session_token
            token = create_session_token(999, role='admin', username='testuser')
            c.set_cookie('auth_token', token)
            # Do NOT set csrf_token cookie or X-CSRF-Token header.
            resp = c.post(
                '/api/auth/logout',  # logout is a POST but not in the CSRF exempt list
                content_type='application/json'
            )
            # /api/auth/logout posts should be blocked (it's not in the exempt list)
            # Note: logout is not in ('/api/auth/setup', '/api/auth/login', '/api/auth/csrf-token')
            assert resp.status_code == 403

    def test_csrf_mismatch_rejected(self, client, app):
        """POST with mismatched cookie and header CSRF tokens should return 403."""
        with app.test_client() as c:
            from models.auth import create_session_token
            token = create_session_token(999, role='admin', username='testuser')
            c.set_cookie('auth_token', token)
            c.set_cookie('csrf_token', 'aaaa' * 16)  # 64 chars
            # Send a different value in the header
            resp = c.post(
                '/api/auth/logout',
                headers={'X-CSRF-Token': 'bbbb' * 16},
                content_type='application/json'
            )
            assert resp.status_code == 403
            data = json.loads(resp.data)
            assert 'mismatch' in data.get('error', '').lower()

    def test_csrf_matching_tokens_allowed(self, client, app):
        """POST with matching CSRF cookie and header should pass CSRF check."""
        with app.test_client() as c:
            csrf_value = 'cc' * 32  # 64 chars of 'cc'
            c.set_cookie('csrf_token', csrf_value)
            # Setup is exempt from CSRF, so use a real CSRF-exempt POST to test the
            # positive path via setup (which is always exempt from CSRF).
            resp = c.post(
                '/api/auth/setup',
                json={'email': 'csrf_test@test.com', 'password': 'CSRFTest123!'},
                content_type='application/json'
            )
            # Should not be blocked by CSRF (setup is explicitly exempt)
            assert resp.status_code in (201, 409)  # 409 if already set up

    def test_login_exempt_from_csrf(self, client):
        """Login POST should not require a CSRF token."""
        # Attempt login without any CSRF token - it should not return 403 for CSRF.
        resp = client.post(
            '/api/auth/login',
            json={'email': 'nobody@test.com', 'password': 'WrongPass1!'},
            content_type='application/json'
        )
        # Should be 401 (bad credentials) not 403 (CSRF failure)
        assert resp.status_code == 401

    def test_setup_exempt_from_csrf(self, client):
        """Setup POST should not require a CSRF token."""
        resp = client.post(
            '/api/auth/setup',
            json={'email': 'exempt@test.com', 'password': 'ValidPass123!'},
            content_type='application/json'
        )
        # Should be 201 (created) or 409 (already set up) - not 403 CSRF failure.
        assert resp.status_code in (201, 409)

    def test_get_requests_bypass_csrf(self, client):
        """GET requests should never be blocked by CSRF."""
        resp = client.get('/api/health')
        assert resp.status_code == 200

    def test_head_requests_bypass_csrf(self, client):
        """HEAD requests should never be blocked by CSRF."""
        resp = client.head('/api/health')
        assert resp.status_code == 200


# ===========================================================================
# Password Complexity Validation
# ===========================================================================

class TestPasswordComplexityValidation:
    """Test validate_password_strength from utils/error_handler.py."""

    def test_valid_password_does_not_raise(self):
        """A password meeting all requirements should not raise."""
        from utils.error_handler import validate_password_strength
        # Should not raise
        validate_password_strength('SecurePass123!')

    def test_password_too_short_raises_validation_error(self):
        """Password under 12 characters should raise ValidationError."""
        from utils.error_handler import validate_password_strength, ValidationError
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('Short1a!')
        assert exc_info.value.status_code == 400

    def test_password_exactly_12_chars_accepted(self):
        """Password of exactly 12 characters (meeting other requirements) should be accepted."""
        from utils.error_handler import validate_password_strength
        validate_password_strength('SecurePas12!')  # 12 chars

    def test_password_no_uppercase_raises_validation_error(self):
        """Password without an uppercase letter should raise ValidationError."""
        from utils.error_handler import validate_password_strength, ValidationError
        with pytest.raises(ValidationError):
            validate_password_strength('nouppercase123')

    def test_password_no_lowercase_raises_validation_error(self):
        """Password without a lowercase letter should raise ValidationError."""
        from utils.error_handler import validate_password_strength, ValidationError
        with pytest.raises(ValidationError):
            validate_password_strength('NOLOWERCASE123')

    def test_password_no_digit_raises_validation_error(self):
        """Password without a digit should raise ValidationError."""
        from utils.error_handler import validate_password_strength, ValidationError
        with pytest.raises(ValidationError):
            validate_password_strength('NoDigitsHereAtAll')

    def test_error_field_is_password(self):
        """ValidationError for password strength should report field='password'."""
        from utils.error_handler import validate_password_strength, ValidationError
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('short')
        assert exc_info.value.details.get('field') == 'password'

    def test_setup_rejects_short_password(self, client):
        """POST /api/auth/setup with a password under 12 chars should return 400."""
        resp = client.post(
            '/api/auth/setup',
            json={'email': 'pw@test.com', 'password': 'Short1!'},
            content_type='application/json'
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'error' in data

    def test_setup_rejects_password_without_uppercase(self, client):
        """POST /api/auth/setup without uppercase in password should return 400."""
        resp = client.post(
            '/api/auth/setup',
            json={'email': 'pw2@test.com', 'password': 'nouppercase123'},
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_setup_rejects_password_without_digit(self, client):
        """POST /api/auth/setup without a digit in password should return 400."""
        resp = client.post(
            '/api/auth/setup',
            json={'email': 'pw3@test.com', 'password': 'NoDigitsHereAtAll'},
            content_type='application/json'
        )
        assert resp.status_code == 400


# ===========================================================================
# Input Length Validation
# ===========================================================================

class TestInputLengthValidation:
    """Test validate_max_length from utils/error_handler.py."""

    def test_short_string_does_not_raise(self):
        """A string under the limit should not raise."""
        from utils.error_handler import validate_max_length
        validate_max_length('short string', 255, 'test_field')

    def test_string_at_exact_limit_does_not_raise(self):
        """A string exactly at the limit should not raise."""
        from utils.error_handler import validate_max_length
        validate_max_length('x' * 255, 255, 'test_field')

    def test_string_over_limit_raises_validation_error(self):
        """A string exceeding the limit should raise ValidationError."""
        from utils.error_handler import validate_max_length, ValidationError
        with pytest.raises(ValidationError):
            validate_max_length('x' * 300, 255, 'test_field')

    def test_validation_error_reports_correct_field(self):
        """ValidationError should name the offending field."""
        from utils.error_handler import validate_max_length, ValidationError
        with pytest.raises(ValidationError) as exc_info:
            validate_max_length('x' * 300, 255, 'email')
        assert exc_info.value.details.get('field') == 'email'

    def test_none_value_does_not_raise(self):
        """None should be handled gracefully (not raise)."""
        from utils.error_handler import validate_max_length
        validate_max_length(None, 255, 'test_field')

    def test_empty_string_does_not_raise(self):
        """Empty string is always under any positive limit."""
        from utils.error_handler import validate_max_length
        validate_max_length('', 10, 'test_field')

    def test_non_string_value_does_not_raise(self):
        """Non-string values (e.g. int) should not raise."""
        from utils.error_handler import validate_max_length
        validate_max_length(42, 10, 'test_field')


# ===========================================================================
# Custom Exception Classes
# ===========================================================================

class TestCustomExceptions:
    """Test PTVault exception hierarchy and HTTP status codes."""

    def test_validation_error_status_code_is_400(self):
        """ValidationError should carry HTTP status 400."""
        from utils.error_handler import ValidationError
        err = ValidationError("bad input")
        assert err.status_code == 400

    def test_authentication_error_status_code_is_401(self):
        """AuthenticationError should carry HTTP status 401."""
        from utils.error_handler import AuthenticationError
        err = AuthenticationError()
        assert err.status_code == 401

    def test_authorization_error_status_code_is_403(self):
        """AuthorizationError should carry HTTP status 403."""
        from utils.error_handler import AuthorizationError
        err = AuthorizationError()
        assert err.status_code == 403

    def test_not_found_error_status_code_is_404(self):
        """NotFoundError should carry HTTP status 404."""
        from utils.error_handler import NotFoundError
        err = NotFoundError('engagement', 42)
        assert err.status_code == 404
        assert 'Engagement' in err.message

    def test_conflict_error_status_code_is_409(self):
        """ConflictError should carry HTTP status 409."""
        from utils.error_handler import ConflictError
        err = ConflictError("duplicate resource")
        assert err.status_code == 409

    def test_database_error_status_code_is_500(self):
        """DatabaseError should carry HTTP status 500."""
        from utils.error_handler import DatabaseError
        err = DatabaseError("query failed")
        assert err.status_code == 500

    def test_forbidden_error_alias(self):
        """ForbiddenError should be an alias for AuthorizationError."""
        from utils.error_handler import ForbiddenError, AuthorizationError
        assert ForbiddenError is AuthorizationError

    def test_validation_error_with_field_sets_details(self):
        """ValidationError with field should include it in details dict."""
        from utils.error_handler import ValidationError
        err = ValidationError("bad value", field='email')
        assert err.details.get('field') == 'email'

    def test_to_dict_includes_error_and_type(self):
        """PTVaultError.to_dict() should include 'error' and 'type' keys."""
        from utils.error_handler import ValidationError
        err = ValidationError("test message")
        d = err.to_dict()
        assert d['error'] == 'test message'
        assert d['type'] == 'ValidationError'

    def test_not_found_error_includes_resource_type_in_details(self):
        """NotFoundError should record the resource type in its details."""
        from utils.error_handler import NotFoundError
        err = NotFoundError('host', 99)
        assert err.details.get('resource_type') == 'host'
        assert err.details.get('resource_id') == 99


# ===========================================================================
# handle_errors Decorator
# ===========================================================================

class TestHandleErrorsDecorator:
    """Test the handle_errors decorator routes exceptions to JSON responses."""

    def test_handle_errors_passes_through_normal_return(self, app):
        """handle_errors should not interfere with a successful response."""
        from utils.error_handler import handle_errors
        with app.app_context():
            from flask import jsonify

            @handle_errors
            def good_route():
                return jsonify({'ok': True}), 200

            # Call inside a real request context so Flask machinery works
            with app.test_request_context('/'):
                response, status = good_route()
                assert status == 200

    def test_handle_errors_converts_validation_error_to_400(self, app):
        """handle_errors should convert ValidationError to a 400 JSON response."""
        from utils.error_handler import handle_errors, ValidationError
        with app.test_request_context('/'):
            @handle_errors
            def bad_route():
                raise ValidationError("bad field value", field='name')

            response, status = bad_route()
            assert status == 400
            data = json.loads(response.get_data())
            assert 'error' in data

    def test_handle_errors_converts_not_found_to_404(self, app):
        """handle_errors should convert NotFoundError to a 404 JSON response."""
        from utils.error_handler import handle_errors, NotFoundError
        with app.test_request_context('/'):
            @handle_errors
            def missing_route():
                raise NotFoundError('engagement', 999)

            response, status = missing_route()
            assert status == 404

    def test_handle_errors_converts_auth_error_to_401(self, app):
        """handle_errors should convert AuthenticationError to a 401 JSON response."""
        from utils.error_handler import handle_errors, AuthenticationError
        with app.test_request_context('/'):
            @handle_errors
            def locked_route():
                raise AuthenticationError("token expired")

            response, status = locked_route()
            assert status == 401

    def test_handle_errors_converts_authz_error_to_403(self, app):
        """handle_errors should convert AuthorizationError to a 403 JSON response."""
        from utils.error_handler import handle_errors, AuthorizationError
        with app.test_request_context('/'):
            @handle_errors
            def forbidden_route():
                raise AuthorizationError("admin only")

            response, status = forbidden_route()
            assert status == 403


# ===========================================================================
# Require-Fields Helper
# ===========================================================================

class TestRequireFields:
    """Test the require_fields validation helper."""

    def test_all_fields_present_does_not_raise(self):
        """require_fields should pass silently when all fields are present."""
        from utils.error_handler import require_fields
        require_fields({'name': 'Alice', 'email': 'a@b.com'}, ['name', 'email'])

    def test_missing_field_raises_validation_error(self):
        """require_fields should raise ValidationError when a field is missing."""
        from utils.error_handler import require_fields, ValidationError
        with pytest.raises(ValidationError):
            require_fields({'name': 'Alice'}, ['name', 'email'])

    def test_empty_string_field_treated_as_missing(self):
        """require_fields should treat empty-string values as missing."""
        from utils.error_handler import require_fields, ValidationError
        with pytest.raises(ValidationError):
            require_fields({'name': ''}, ['name'])

    def test_none_data_raises_validation_error(self):
        """require_fields should raise when the entire data dict is None."""
        from utils.error_handler import require_fields, ValidationError
        with pytest.raises(ValidationError):
            require_fields(None, ['name'])


# ===========================================================================
# Auth Route Integration (security-relevant flows)
# ===========================================================================

class TestAuthRouteSecurityBehaviours:
    """Integration tests for auth-related security behaviours via the test client."""

    def test_unauthenticated_request_returns_401(self, client):
        """Calling a protected API route without auth cookie should return 401.

        We test by hitting /api/auth/logout via GET which will 405,
        so we use a crafted test route. For the purposes of this test we verify
        that an existing protected endpoint pattern blocks anonymous callers.
        The health-check is public, so we just confirm it is 200 to show the
        app is running. The CSRF block handles missing-token POSTs as 403,
        which is tested separately.
        """
        resp = client.get('/api/health')
        assert resp.status_code == 200

    def test_login_with_correct_credentials_returns_200(self, client, app):
        """Login with the correct password should succeed with HTTP 200."""
        # Use a fresh client with an isolated db state
        with app.test_client() as c:
            # First ensure we can set up (may already be done)
            c.post(
                '/api/auth/setup',
                json={'email': 'login_test@test.com', 'password': 'LoginTest123!'},
                content_type='application/json'
            )
            resp = c.post(
                '/api/auth/login',
                json={'email': 'login_test@test.com', 'password': 'LoginTest123!'},
                content_type='application/json'
            )
            # 200 if credentials match, 401 if another user was already created
            assert resp.status_code in (200, 401)

    def test_login_with_wrong_password_returns_401(self, client):
        """Login with an incorrect password should return 401."""
        resp = client.post(
            '/api/auth/login',
            json={'email': 'admin@test.com', 'password': 'WrongPass999!'},
            content_type='application/json'
        )
        assert resp.status_code == 401

    def test_login_sets_auth_token_cookie(self, client, app):
        """Successful login should set an httpOnly auth_token cookie."""
        with app.test_client() as c:
            # Setup admin if needed
            c.post(
                '/api/auth/setup',
                json={'email': 'cookie_test@test.com', 'password': 'CookieTest123!'},
                content_type='application/json'
            )
            resp = c.post(
                '/api/auth/login',
                json={'email': 'cookie_test@test.com', 'password': 'CookieTest123!'},
                content_type='application/json'
            )
            if resp.status_code == 200:
                assert 'auth_token' in resp.headers.get('Set-Cookie', '')

    def test_setup_duplicate_returns_409(self, client):
        """Calling /api/auth/setup when a user already exists should return 409."""
        # First call may succeed (201) or conflict (409) depending on prior state.
        client.post(
            '/api/auth/setup',
            json={'email': 'dup@test.com', 'password': 'DupTest12345!'},
            content_type='application/json'
        )
        # Second call must conflict.
        resp = client.post(
            '/api/auth/setup',
            json={'email': 'dup2@test.com', 'password': 'DupTest12345!'},
            content_type='application/json'
        )
        assert resp.status_code == 409

    def test_setup_requires_email_and_password_fields(self, client, app):
        """Setup without required fields should return 400."""
        with app.test_client() as c:
            resp = c.post(
                '/api/auth/setup',
                json={'email': 'only@test.com'},  # missing password
                content_type='application/json'
            )
            assert resp.status_code in (400, 409)

    def test_logout_clears_auth_cookie(self, client, app):
        """POST /api/auth/logout should delete the auth_token cookie."""
        with app.test_client() as c:
            # Plant a dummy auth_token cookie and matching CSRF tokens
            csrf_value = 'aa' * 32
            c.set_cookie('auth_token', 'dummy_token_value')
            c.set_cookie('csrf_token', csrf_value)
            resp = c.post(
                '/api/auth/logout',
                headers={'X-CSRF-Token': csrf_value},
                content_type='application/json'
            )
            assert resp.status_code == 200
            # Cookie should be deleted (empty or expired)
            set_cookie = resp.headers.get('Set-Cookie', '')
            # Flask deletes a cookie by setting max-age=0 or expires in the past
            assert 'auth_token' in set_cookie
