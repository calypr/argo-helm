#!/usr/bin/env python3
"""
Tests for GitHub App Callback Service
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


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
    """Test registration form with update action."""
    response = client.get('/registrations?installation_id=12345678&setup_action=update')
    assert response.status_code == 200
    assert b'12345678' in response.data
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
