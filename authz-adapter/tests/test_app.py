import pytest
import requests_mock
from unittest.mock import patch
import json
import importlib
import sys
import os

class TestAppBasic:
    """Basic Flask application tests."""
    
    @pytest.mark.unit
    def test_app_created(self):
        """Test that the Flask app is created successfully."""
        import app
        assert app.app is not None
        assert app.app.name == "app"

    @pytest.mark.unit
    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        import app
        client = app.app.test_client()
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.get_data(as_text=True) == "ok"

    @pytest.mark.unit
    def test_missing_authorization_header(self):
        """Test request without Authorization header."""
        import app
        client = app.app.test_client()
        response = client.get('/check')
        assert response.status_code == 401
        assert "authz fetch failed" in response.get_data(as_text=True)

class TestFetchUserDoc:
    """Test the fetch_user_doc function."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_fetch_user_doc_with_bearer_token(self):
        """Test fetch_user_doc with valid Bearer token."""
        with requests_mock.Mocker() as m:
            # Set environment variables BEFORE importing app
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                # Import app after setting environment variables
                import app
                
                # Mock the URL that the app constructs
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, json={"email": "test@example.com", "active": True})
                
                doc, err = app.fetch_user_doc("Bearer test-token")
                assert err is None
                assert doc["email"] == "test@example.com"
                assert doc["active"] is True

    @pytest.mark.unit
    def test_fetch_user_doc_with_service_token(self):
        """Test fetch_user_doc with service token when no Bearer token."""
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'FENCE_SERVICE_TOKEN': 'service-token-123'
            }
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, json={"email": "service@example.com", "active": True})
                
                doc, err = app.fetch_user_doc(None)
                assert err is None
                assert doc["email"] == "service@example.com"

    @pytest.mark.unit
    def test_fetch_user_doc_non_200_response(self):
        """Test fetch_user_doc with non-200 response."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, status_code=404)
                
                doc, err = app.fetch_user_doc("Bearer test-token")
                assert doc is None
                assert "userinfo status 404" in err

    @pytest.mark.unit
    def test_fetch_user_doc_timeout(self):
        """Test fetch_user_doc with timeout."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                import requests
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, exc=requests.exceptions.Timeout)
                
                # Should return error message instead of raising exception
                doc, err = app.fetch_user_doc("Bearer test-token")
                assert doc is None
                assert err == "timeout"

    @pytest.mark.unit
    def test_fetch_user_doc_connection_error(self):
        """Test fetch_user_doc with connection error."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                import requests
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, exc=requests.exceptions.ConnectionError)
                
                # Should return error message instead of raising exception
                doc, err = app.fetch_user_doc("Bearer test-token")
                assert doc is None
                assert err == "connection error"

    @pytest.mark.unit
    def test_fetch_user_doc_invalid_json(self):
        """Test fetch_user_doc with invalid JSON response."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, text="invalid json")
                
                # Should return error message for invalid JSON
                doc, err = app.fetch_user_doc("Bearer test-token")
                assert doc is None
                assert "request error: Expecting value" in err

    @pytest.mark.unit
    def test_fetch_user_doc_case_insensitive_bearer(self):
        """Test fetch_user_doc with case-insensitive Bearer token."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, json={"email": "test@example.com", "active": True})
                
                doc, err = app.fetch_user_doc("bearer test-token")
                assert err is None
                assert doc["email"] == "test@example.com"

    @pytest.mark.unit
    def test_fetch_user_doc_malformed_bearer(self):
        """Test fetch_user_doc with malformed Bearer token."""
        env_vars = {'FENCE_SERVICE_TOKEN': ''}
        with patch.dict('os.environ', env_vars):
            import app
            
            doc, err = app.fetch_user_doc("malformed-token")
            assert doc is None
            assert err == "no token"

class TestCheckEndpoint:
    """Test the /check endpoint."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_check_with_valid_user(self):
        """Test /check endpoint with valid user having permissions."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": True,
                    "email": "authorized@example.com",
                    "authz": {
                        "/services/workflow/gen3-workflow": [
                            {"method": "create", "service": "gen3-workflow"}
                        ]
                    }
                }
                m.get(mock_url, json=user_doc)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 200

    @pytest.mark.unit
    def test_check_with_invalid_user(self):
        """Test /check endpoint with user without special permissions (gets viewer access)."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": True,
                    "email": "viewer@example.com",
                    "authz": {}  # No special permissions, but still gets viewer access
                }
                m.get(mock_url, json=user_doc)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                # Active users with empty authz still get argo-viewer access
                assert response.status_code == 200
                assert 'X-Auth-Request-Groups' in response.headers
                assert 'argo-viewer' in response.headers['X-Auth-Request-Groups']
                assert 'argo-runner' not in response.headers['X-Auth-Request-Groups']

    @pytest.mark.unit
    def test_check_with_inactive_user(self):
        """Test /check endpoint with inactive user."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": False,
                    "email": "inactive@example.com",
                    "authz": {
                        "/services/workflow/gen3-workflow": [
                            {"method": "create", "service": "gen3-workflow"}
                        ]
                    }
                }
                m.get(mock_url, json=user_doc)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 403

class TestResponseHeaders:
    """Test response headers and content."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_response_headers_on_success(self):
        """Test response headers on successful authorization."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                
                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": True,
                    "email": "test@example.com",
                    "authz": {
                        "/services/workflow/gen3-workflow": [
                            {"method": "create", "service": "gen3-workflow"}
                        ]
                    }
                }
                m.get(mock_url, json=user_doc)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 200
                
                # Check for user info headers (nginx auth_request format)
                assert 'X-Auth-Request-User' in response.headers
                assert 'X-Auth-Request-Email' in response.headers
                assert 'X-Auth-Request-Groups' in response.headers
                assert 'X-Allowed' in response.headers
                
                # Verify header values
                assert response.headers['X-Auth-Request-User'] == 'test@example.com'
                assert response.headers['X-Auth-Request-Email'] == 'test@example.com'
                assert 'argo-runner' in response.headers['X-Auth-Request-Groups']
                assert 'argo-viewer' in response.headers['X-Auth-Request-Groups']
                assert response.headers['X-Allowed'] == 'true'

class TestErrorHandling:
    """Test error handling scenarios."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                import requests
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, exc=requests.exceptions.Timeout)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 401

    @pytest.mark.unit
    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars):
                import app
                import requests
                
                mock_url = "https://test-fence.example.com/user/user"
                m.get(mock_url, exc=requests.exceptions.ConnectionError)
                
                client = app.app.test_client()
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 401

    @pytest.mark.unit
    def test_malformed_authorization_header(self):
        """Test handling of malformed authorization headers."""
        import app
        client = app.app.test_client()
        
        # Test various malformed headers
        malformed_headers = [
            "Basic user:pass",  # Wrong type
            "Bearer",          # Missing token
            "bearer ",         # Empty token
            "",               # Empty header
            "InvalidFormat token"  # Invalid format
        ]
        
        for header in malformed_headers:
            response = client.get('/check', headers={'Authorization': header})
            assert response.status_code == 401


class TestGetDebuggingVars:
    """Test the get_debugging_vars function."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_get_debugging_vars_returns_none_when_no_debug_email(self):
        """Test that get_debugging_vars returns (None, None) when DEBUG_EMAIL is not set."""
        env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check'):
                email, groups = app.get_debugging_vars()
                assert email is None
                assert groups is None

    @pytest.mark.unit
    def test_get_debugging_vars_with_debug_email_env_only(self):
        """Test get_debugging_vars with DEBUG_EMAIL env var set."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check'):
                email, groups = app.get_debugging_vars()
                assert email == 'debug@example.com'
                assert groups is None

    @pytest.mark.unit
    def test_get_debugging_vars_with_debug_email_and_groups_env(self):
        """Test get_debugging_vars with DEBUG_EMAIL and DEBUG_GROUPS env vars set."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com',
            'DEBUG_GROUPS': 'argo-runner,argo-viewer'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check'):
                email, groups = app.get_debugging_vars()
                assert email == 'debug@example.com'
                assert groups == ['argo-runner', 'argo-viewer']

    @pytest.mark.unit
    def test_get_debugging_vars_query_params_override_env(self):
        """Test that query params override env vars when DEBUG_EMAIL is set."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'env@example.com',
            'DEBUG_GROUPS': 'env-group'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context(
                '/check?debug_email=query@example.com&debug_groups=query-group1,query-group2'
            ):
                email, groups = app.get_debugging_vars()
                assert email == 'query@example.com'
                assert groups == ['query-group1', 'query-group2']

    @pytest.mark.unit
    def test_get_debugging_vars_query_email_only(self):
        """Test get_debugging_vars with debug_email query param only (requires DEBUG_EMAIL env)."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'env@example.com'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check?debug_email=query@example.com'):
                email, groups = app.get_debugging_vars()
                assert email == 'query@example.com'
                assert groups is None

    @pytest.mark.unit
    def test_get_debugging_vars_query_groups_with_env_email(self):
        """Test get_debugging_vars with debug_groups query param and DEBUG_EMAIL env var."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'env@example.com'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check?debug_groups=group1,group2'):
                email, groups = app.get_debugging_vars()
                assert email == 'env@example.com'
                assert groups == ['group1', 'group2']

    @pytest.mark.unit
    def test_get_debugging_vars_single_group(self):
        """Test get_debugging_vars with a single group in DEBUG_GROUPS."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com',
            'DEBUG_GROUPS': 'single-group'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context('/check'):
                email, groups = app.get_debugging_vars()
                assert email == 'debug@example.com'
                assert groups == ['single-group']

    @pytest.mark.unit
    def test_get_debugging_vars_query_params_ignored_without_debug_email_env(self):
        """Test that query params are ignored when DEBUG_EMAIL env is not set."""
        env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            with app.app.test_request_context(
                '/check?debug_email=query@example.com&debug_groups=group1'
            ):
                email, groups = app.get_debugging_vars()
                # Without DEBUG_EMAIL env var, query params should be ignored
                assert email is None
                assert groups is None


class TestCheckWithDebuggingVars:
    """Test /check endpoint behavior with debugging variables."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_check_bypasses_auth_with_debug_email_and_groups(self):
        """Test that /check bypasses auth when DEBUG_EMAIL and DEBUG_GROUPS are set."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com',
            'DEBUG_GROUPS': 'argo-runner,argo-viewer'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            client = app.app.test_client()
            # No Authorization header needed when debugging vars are set
            response = client.get('/check')
            assert response.status_code == 200
            assert response.headers['X-Auth-Request-User'] == 'debug@example.com'
            assert response.headers['X-Auth-Request-Email'] == 'debug@example.com'
            assert response.headers['X-Auth-Request-Groups'] == 'argo-runner,argo-viewer'
            assert response.headers['X-Allowed'] == 'true'

    @pytest.mark.unit
    def test_check_falls_back_to_auth_when_only_debug_email_set(self):
        """Test that /check falls back to auth when only DEBUG_EMAIL is set (no groups)."""
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'DEBUG_EMAIL': 'debug@example.com'
                # No DEBUG_GROUPS set
            }
            with patch.dict('os.environ', env_vars, clear=True):
                import app

                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": True,
                    "email": "auth@example.com",
                    "authz": {
                        "/services/workflow/gen3-workflow": [
                            {"method": "create", "service": "gen3-workflow"}
                        ]
                    }
                }
                m.get(mock_url, json=user_doc)

                client = app.app.test_client()
                # Without groups, it should fall back to real auth
                response = client.get('/check', headers={'Authorization': 'Bearer valid-token'})
                assert response.status_code == 200
                # Should use the email from auth, not debug email
                assert response.headers['X-Auth-Request-Email'] == 'auth@example.com'

    @pytest.mark.unit
    def test_check_with_debug_query_params(self):
        """Test /check with debug_email and debug_groups query parameters."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'env@example.com',
            'DEBUG_GROUPS': 'env-group'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            client = app.app.test_client()
            response = client.get(
                '/check?debug_email=query@example.com&debug_groups=query-runner,query-viewer'
            )
            assert response.status_code == 200
            assert response.headers['X-Auth-Request-User'] == 'query@example.com'
            assert response.headers['X-Auth-Request-Email'] == 'query@example.com'
            assert response.headers['X-Auth-Request-Groups'] == 'query-runner,query-viewer'

    @pytest.mark.unit
    def test_check_with_debug_groups_override_in_query(self):
        """Test /check with debug_groups query param overriding env var."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com',
            'DEBUG_GROUPS': 'env-group'
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            client = app.app.test_client()
            response = client.get('/check?debug_groups=query-admin,query-viewer')
            assert response.status_code == 200
            assert response.headers['X-Auth-Request-Email'] == 'debug@example.com'
            assert response.headers['X-Auth-Request-Groups'] == 'query-admin,query-viewer'

    @pytest.mark.unit
    def test_check_query_params_ignored_without_debug_email_env(self):
        """Test that query params are ignored when DEBUG_EMAIL env is not set."""
        with requests_mock.Mocker() as m:
            env_vars = {'FENCE_BASE': 'https://test-fence.example.com/user'}
            with patch.dict('os.environ', env_vars, clear=True):
                import app

                mock_url = "https://test-fence.example.com/user/user"
                user_doc = {
                    "active": True,
                    "email": "auth@example.com",
                    "authz": {
                        "/services/workflow/gen3-workflow": [
                            {"method": "create", "service": "gen3-workflow"}
                        ]
                    }
                }
                m.get(mock_url, json=user_doc)

                client = app.app.test_client()
                # Query params should be ignored without DEBUG_EMAIL env
                response = client.get(
                    '/check?debug_email=query@example.com&debug_groups=query-group',
                    headers={'Authorization': 'Bearer valid-token'}
                )
                assert response.status_code == 200
                # Should use auth email, not query param email
                assert response.headers['X-Auth-Request-Email'] == 'auth@example.com'

    @pytest.mark.unit
    def test_check_without_auth_fails_when_debug_incomplete(self):
        """Test /check returns 401 when debug vars are incomplete and no auth provided."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com'
            # No DEBUG_GROUPS - incomplete debug config
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            client = app.app.test_client()
            # No Authorization header, and debug vars incomplete
            response = client.get('/check')
            assert response.status_code == 401

    @pytest.mark.unit
    def test_check_with_empty_debug_groups(self):
        """Test /check behavior with empty DEBUG_GROUPS."""
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'DEBUG_EMAIL': 'debug@example.com',
            'DEBUG_GROUPS': ''  # Empty groups
        }
        with patch.dict('os.environ', env_vars, clear=True):
            import app
            client = app.app.test_client()
            # Empty groups should result in fallback to real auth
            response = client.get('/check')
            # Without valid auth, should fail
            assert response.status_code == 401
