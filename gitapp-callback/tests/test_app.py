#!/usr/bin/env python3
"""
Tests for GitHub App Callback Service
"""

import pytest
import sys
import os
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set testing flag before importing app
os.environ['TESTING'] = '1'

from app import app, init_db


@pytest.fixture
def client():
    """Create test client with temporary database."""
    # Create temporary database for each test
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite')
    temp_db.close()
    
    app.config['TESTING'] = True
    
    # Set temp DB path
    import app as app_module
    app_module.DB_PATH = temp_db.name
    os.environ['DB_PATH'] = temp_db.name
    
    # Initialize database
    init_db()
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except:
        pass


def test_healthz(client):
    """Test health check endpoint."""
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.data == b'ok'


def test_registrations_form_missing_installation_id(client):
    """Test registration form without installation_id."""
    response = client.get('/registrations')
    assert response.status_code == 400
    assert b'Missing installation_id' in response.data


def test_registrations_form_with_installation_id(client):
    """Test registration form with valid installation_id."""
    response = client.get('/registrations?installation_id=12345678')
    assert response.status_code == 200
    assert b'12345678' in response.data
    assert b'Complete Repository Registration' in response.data


def test_registrations_form_with_update_action(client):
    """Test registration form with update action and existing data."""
    from app import save_registration
    
    # Create existing registration first
    existing_data = {
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'adminUsers': ['admin@example.com'],
        'readUsers': [],
        'dataBucket': None,
        'artifactBucket': None
    }
    save_registration('12345678', existing_data)
    
    # Now access update form
    response = client.get('/registrations?installation_id=12345678&setup_action=update')
    assert response.status_code == 200
    assert b'12345678' in response.data
    assert b'updating an existing installation' in response.data.lower()
    assert b'updating an existing installation' in response.data


def test_registrations_submit_missing_installation_id(client):
    """Test form submission without installation_id."""
    response = client.post('/registrations', data={
        'defaultBranch': 'main',
        'adminUsers': 'admin@example.com'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'installation_id' in json_data['error']


def test_registrations_submit_missing_admin_users(client):
    """Test form submission without admin users."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'admin user' in json_data['error'].lower()


def test_registrations_submit_invalid_email(client):
    """Test form submission with invalid email."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'adminUsers': 'not-an-email'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'Invalid email' in json_data['error']


def test_registrations_submit_valid_minimal(client):
    """Test successful form submission with minimal data."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'adminUsers': 'admin@example.com'
    })
    assert response.status_code == 200
    assert b'Registration Complete' in response.data


def test_registrations_submit_valid_full(client):
    """Test successful form submission with AWS bucket configuration."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'develop',
        'dataBucket_bucket': 'my-data-bucket',
        'dataBucket_accessKey': 'AKIAIOSFODNN7EXAMPLE',
        'dataBucket_secretKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        'dataBucket_is_aws': 'on',
        'artifactBucket_bucket': 'my-artifact-bucket',
        'artifactBucket_accessKey': 'AKIAIOSFODNN7EXAMPLE2',
        'artifactBucket_secretKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY2',
        'artifactBucket_is_aws': 'on',
        'adminUsers': 'admin1@example.com, admin2@example.com',
        'readUsers': 'reader1@example.com, reader2@example.com'
    })
    assert response.status_code == 200
    assert b'Registration Complete' in response.data
    assert b'develop' in response.data
    assert b'my-data-bucket' in response.data
    assert b'my-artifact-bucket' in response.data


def test_registrations_submit_valid_json_response(client):
    """Test successful form submission with JSON Accept header."""
    response = client.post('/registrations', 
        data={
            'installation_id': '12345678',
            'defaultBranch': 'main',
            'adminUsers': 'admin@example.com'
        },
        headers={'Accept': 'application/json'}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['config']['installation_id'] == '12345678'
    assert json_data['config']['defaultBranch'] == 'main'
    assert 'admin@example.com' in json_data['config']['adminUsers']


def test_registrations_submit_multiple_emails(client):
    """Test form submission with multiple comma-separated emails."""
    response = client.post('/registrations',
        data={
            'installation_id': '12345678',
            'defaultBranch': 'main',
            'adminUsers': 'admin1@example.com, admin2@example.com, admin3@example.com',
            'readUsers': 'reader1@example.com, reader2@example.com'
        },
        headers={'Accept': 'application/json'}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['config']['adminUsers']) == 3
    assert len(json_data['config']['readUsers']) == 2


def test_registrations_bucket_missing_credentials(client):
    """Test that bucket name without credentials fails."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'dataBucket_bucket': 'my-bucket',
        'adminUsers': 'admin@example.com'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'access key and secret key' in json_data['error'].lower()


def test_registrations_bucket_aws_config(client):
    """Test AWS bucket configuration with JSON response."""
    response = client.post('/registrations', 
        data={
            'installation_id': '12345678',
            'defaultBranch': 'main',
            'dataBucket_bucket': 'my-data-bucket',
            'dataBucket_accessKey': 'AKIAIOSFODNN7EXAMPLE',
            'dataBucket_secretKey': 'secret123',
            'dataBucket_is_aws': 'on',
            'adminUsers': 'admin@example.com'
        },
        headers={'Accept': 'application/json'}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['config']['dataBucket']['bucket'] == 'my-data-bucket'
    assert json_data['config']['dataBucket']['accessKey'] == 'AKIAIOSFODNN7EXAMPLE'
    assert json_data['config']['dataBucket']['secretKey'] == 'secret123'
    assert json_data['config']['dataBucket']['is_aws'] is True
    assert 'hostname' not in json_data['config']['dataBucket']


def test_registrations_bucket_non_aws_config(client):
    """Test non-AWS bucket configuration with all required fields."""
    response = client.post('/registrations', 
        data={
            'installation_id': '12345678',
            'defaultBranch': 'main',
            'artifactBucket_bucket': 'my-artifacts',
            'artifactBucket_accessKey': 'minioadmin',
            'artifactBucket_secretKey': 'minioadmin',
            'artifactBucket_hostname': 'https://minio.example.org:9000',
            'artifactBucket_region': 'us-east-1',
            'artifactBucket_pathStyle': 'on',
            'adminUsers': 'admin@example.com'
        },
        headers={'Accept': 'application/json'}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['config']['artifactBucket']['bucket'] == 'my-artifacts'
    assert json_data['config']['artifactBucket']['is_aws'] is False
    assert json_data['config']['artifactBucket']['hostname'] == 'https://minio.example.org:9000'
    assert json_data['config']['artifactBucket']['region'] == 'us-east-1'
    assert json_data['config']['artifactBucket']['pathStyle'] is True


def test_registrations_bucket_non_aws_missing_hostname(client):
    """Test that non-AWS bucket without hostname fails."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'dataBucket_bucket': 'my-bucket',
        'dataBucket_accessKey': 'key',
        'dataBucket_secretKey': 'secret',
        'dataBucket_region': 'us-east-1',
        'adminUsers': 'admin@example.com'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'hostname and region' in json_data['error'].lower()


def test_registrations_bucket_non_aws_invalid_hostname(client):
    """Test that non-AWS bucket with non-https hostname fails."""
    response = client.post('/registrations', data={
        'installation_id': '12345678',
        'defaultBranch': 'main',
        'dataBucket_bucket': 'my-bucket',
        'dataBucket_accessKey': 'key',
        'dataBucket_secretKey': 'secret',
        'dataBucket_hostname': 'http://minio.example.org',
        'dataBucket_region': 'us-east-1',
        'adminUsers': 'admin@example.com'
    })
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'must start with https://' in json_data['error'].lower()


def test_database_persistence_install(client):
    """Test that install action saves to database."""
    from app import get_registration
    
    # Submit registration
    response = client.post('/registrations', data={
        'installation_id': 'test-install-123',
        'defaultBranch': 'develop',
        'adminUsers': 'admin@example.com'
    }, headers={'Accept': 'application/json'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    
    # Verify it was saved to database
    saved_data = get_registration('test-install-123')
    assert saved_data is not None
    assert saved_data['installation_id'] == 'test-install-123'
    assert saved_data['defaultBranch'] == 'develop'
    assert 'admin@example.com' in saved_data['adminUsers']


def test_database_persistence_update(client):
    """Test that update action modifies existing registration."""
    from app import save_registration, get_registration
    
    # Create initial registration
    initial_data = {
        'installation_id': 'test-update-456',
        'defaultBranch': 'main',
        'adminUsers': ['admin@example.com'],
        'readUsers': [],
        'dataBucket': None,
        'artifactBucket': None
    }
    save_registration('test-update-456', initial_data)
    
    # Update the registration
    response = client.post('/registrations', data={
        'installation_id': 'test-update-456',
        'defaultBranch': 'production',
        'adminUsers': 'admin@example.com,lead@example.com'
    }, headers={'Accept': 'application/json'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    
    # Verify the update
    updated_data = get_registration('test-update-456')
    assert updated_data is not None
    assert updated_data['defaultBranch'] == 'production'
    assert len(updated_data['adminUsers']) == 2


def test_install_with_existing_registration_redirects(client):
    """Test that install action with existing registration warns and redirects."""
    from app import save_registration
    
    # Create existing registration
    existing_data = {
        'installation_id': '78900001',
        'defaultBranch': 'main',
        'adminUsers': ['admin@example.com'],
        'readUsers': [],
        'dataBucket': None,
        'artifactBucket': None
    }
    save_registration('78900001', existing_data)
    
    # Try to access install form (should get error/redirect)
    response = client.get('/registrations?installation_id=78900001&setup_action=install')
    
    assert response.status_code == 200
    assert b'already registered' in response.data
    assert b'setup_action=update' in response.data


def test_update_without_existing_registration_fails(client):
    """Test that update action without existing registration returns error."""
    # Try to access update form without existing data
    response = client.get('/registrations?installation_id=99900001&setup_action=update')
    
    assert response.status_code == 404
    assert b'not found' in response.data


def test_update_form_prepopulates_data(client):
    """Test that update form pre-populates with existing data."""
    from app import save_registration
    
    # Create existing registration with bucket data
    existing_data = {
        'installation_id': '11100001',
        'defaultBranch': 'staging',
        'dataBucket': {
            'bucket': 'my-data',
            'accessKey': 'AKIATEST',
            'secretKey': 'secretTest123',
            'is_aws': True
        },
        'artifactBucket': None,
        'adminUsers': ['user1@example.com', 'user2@example.com'],
        'readUsers': ['viewer@example.com']
    }
    save_registration('11100001', existing_data)
    
    # Access update form
    response = client.get('/registrations?installation_id=11100001&setup_action=update')
    
    assert response.status_code == 200
    assert b'staging' in response.data
    assert b'my-data' in response.data
    assert b'user1@example.com' in response.data
    assert b'user2@example.com' in response.data
    assert b'viewer@example.com' in response.data


def test_invalid_installation_id_non_integer(client):
    """Test that non-integer installation_id returns error."""
    response = client.get('/registrations?installation_id=abc123')
    
    assert response.status_code == 400
    assert b'Invalid installation_id' in response.data
    assert b'Must be an integer' in response.data


def test_invalid_setup_action(client):
    """Test that invalid setup_action returns error."""
    response = client.get('/registrations?installation_id=12345678&setup_action=invalid')
    
    assert response.status_code == 400
    assert b'Invalid setup_action' in response.data
    assert b'install' in response.data and b'update' in response.data


def test_missing_setup_action_defaults_to_install(client):
    """Test that missing setup_action defaults to install."""
    response = client.get('/registrations?installation_id=12345678')
    
    assert response.status_code == 200
    assert b'Complete Repository Registration' in response.data
