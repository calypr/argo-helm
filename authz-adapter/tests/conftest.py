"""Test fixtures and configuration for authz-adapter tests."""

import json
import os
import pytest
import requests_mock
from unittest.mock import patch
from flask.testing import FlaskClient

# Import the app module
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import app


@pytest.fixture
def client() -> FlaskClient:
    """Create a test client for the Flask app."""
    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'FENCE_BASE': 'https://test-fence.example.com/user',
        'HTTP_TIMEOUT': '5.0',
        'FENCE_SERVICE_TOKEN': 'test-service-token'
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_user_doc():
    """Sample user document from Fence API."""
    return {
        "active": True,
        "email": "test@example.com",
        "name": "Test User",
        "username": "testuser",
        "authz": {
            "/services/workflow/gen3-workflow": [
                {"method": "create", "service": "gen3-workflow"}
            ]
        }
    }


@pytest.fixture
def inactive_user_doc():
    """Sample inactive user document."""
    return {
        "active": False,
        "email": "inactive@example.com",
        "authz": {}
    }


@pytest.fixture
def unauthorized_user_doc():
    """Sample user document without workflow permissions."""
    return {
        "active": True,
        "email": "unauthorized@example.com",
        "authz": {
            "/workspace": [
                {"method": "read", "service": "other"}
            ]
        }
    }


@pytest.fixture
def admin_user_doc():
    """Sample admin user document with wildcard permissions."""
    return {
        "active": True,
        "email": "admin@example.com",
        "authz": {
            "/services/workflow/gen3-workflow": [
                {"method": "*", "service": "gen3-workflow"}
            ]
        }
    }


@pytest.fixture
def mock_requests():
    """Mock requests for HTTP calls."""
    with requests_mock.Mocker() as m:
        yield m


@pytest.fixture
def valid_bearer_token():
    """Sample valid bearer token."""
    return "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"


@pytest.fixture
def invalid_bearer_token():
    """Sample invalid bearer token."""
    return "Bearer invalid.token.here"


class TestData:
    """Test data constants."""
    
    FENCE_USERINFO_URL = "https://test-fence.example.com/user/user"
    TIMEOUT = 5.0
    
    # Sample responses
    USER_INFO_SUCCESS = {
        "active": True,
        "email": "test@example.com",
        "authz": {
            "/services/workflow/gen3-workflow": [
                {"method": "create", "service": "gen3-workflow"}
            ]
        }
    }
    
    USER_INFO_UNAUTHORIZED = {
        "active": True,
        "email": "test@example.com",
        "authz": {
            "/workspace": [
                {"method": "read", "service": "other"}
            ]
        }
    }


@pytest.fixture
def test_data():
    """Provide test data constants."""
    return TestData
