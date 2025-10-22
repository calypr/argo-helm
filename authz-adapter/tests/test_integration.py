"""Integration tests for the authz-adapter service."""

import json
import os
import pytest
import requests
import time
import threading
from unittest.mock import patch
import subprocess
import signal

# Import the app module
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import app


class TestEndToEndFlow:
    """End-to-end integration tests."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_authorization_flow_with_mock_fence(self):
        """Test complete authorization flow with mocked Fence service."""
        import requests_mock
        
        # Setup mock Fence response
        user_doc = {
            "active": True,
            "email": "integration@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        with requests_mock.Mocker() as m:
            # Setup environment
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '5.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                m.get(fence_url, json=user_doc, status_code=200)
                
                # Create test client
                app.app.config['TESTING'] = True
                client = app.app.test_client()
                
                # Test health check
                health_response = client.get('/healthz')
                assert health_response.status_code == 200
                assert health_response.data == b'ok'
                
                # Test authorization check
                auth_response = client.get('/check', headers={
                    'Authorization': 'Bearer test-integration-token'
                })
                
                assert auth_response.status_code == 200
                assert auth_response.headers['X-Auth-Request-User'] == 'integration@example.com'
                assert 'argo-runner' in auth_response.headers['X-Auth-Request-Groups']
                assert 'argo-viewer' in auth_response.headers['X-Auth-Request-Groups']

    @pytest.mark.integration
    def test_nginx_auth_request_simulation(self):
        """Simulate NGINX auth_request module behavior."""
        import requests_mock
        
        # Setup mock responses for different scenarios
        authorized_user = {
            "active": True,
            "email": "authorized@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        unauthorized_user = {
            "active": True,
            "email": "unauthorized@example.com",
            "authz": {}
        }
        
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '3.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                client = app.app.test_client()
                
                # Test authorized user
                m.get(fence_url, json=authorized_user, status_code=200)
                
                response = client.get('/check', headers={
                    'Authorization': 'Bearer authorized-token',
                    'X-Original-URI': '/argo/workflows',
                    'X-Original-Method': 'GET'
                })
                
                assert response.status_code == 200
                assert response.headers['X-Auth-Request-User'] == 'authorized@example.com'
                assert response.headers['X-Auth-Request-Email'] == 'authorized@example.com'
                groups = response.headers['X-Auth-Request-Groups']
                assert 'argo-runner' in groups
                assert 'argo-viewer' in groups
                assert response.headers['X-Allowed'] == 'true'
                
                # Test unauthorized user
                m.get(fence_url, json=unauthorized_user, status_code=200)
                
                response = client.get('/check', headers={
                    'Authorization': 'Bearer unauthorized-token',
                    'X-Original-URI': '/argo/workflows',
                    'X-Original-Method': 'POST'
                })
                
                assert response.status_code == 200  # Still returns 200 but with limited groups
                assert response.headers['X-Auth-Request-User'] == 'unauthorized@example.com'
                groups = response.headers['X-Auth-Request-Groups']
                assert 'argo-runner' not in groups
                assert 'argo-viewer' in groups

    @pytest.mark.integration
    def test_concurrent_requests(self):
        """Test handling multiple concurrent authorization requests."""
        import concurrent.futures
        import requests_mock
        
        # Setup mock response
        user_doc = {
            "active": True,
            "email": "concurrent@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        # Set up mocking and environment once for all concurrent requests
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '5.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                m.get(fence_url, json=user_doc, status_code=200)
                
                def make_auth_request():
                    """Make a single authorization request."""
                    client = app.app.test_client()
                    response = client.get('/check', headers={
                        'Authorization': 'Bearer concurrent-token'
                    })
                    return response.status_code, response.headers.get('X-Auth-Request-User')
                
                # Execute multiple requests concurrently
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(make_auth_request) for _ in range(20)]
                    results = [future.result() for future in concurrent.futures.as_completed(futures)]
                
                # Verify all requests succeeded
                for status_code, user in results:
                    assert status_code == 200
                    assert user == 'concurrent@example.com'

    @pytest.mark.integration
    def test_error_scenarios(self):
        """Test various error scenarios."""
        import requests_mock
        
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '2.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                client = app.app.test_client()
                fence_url = "https://test-fence.example.com/user/user"
                
                # Test Fence service unavailable
                m.get(fence_url, status_code=503)
                response = client.get('/check', headers={
                    'Authorization': 'Bearer test-token'
                })
                assert response.status_code == 401
                
                # Test Fence service timeout
                m.get(fence_url, exc=requests.exceptions.Timeout)
                response = client.get('/check', headers={
                    'Authorization': 'Bearer test-token'
                })
                # With enhanced error handling, timeout should return 401, not raise exception
                assert response.status_code == 401
                
                # Test invalid JSON response
                m.get(fence_url, text="invalid json", status_code=200)
                response = client.get('/check', headers={
                    'Authorization': 'Bearer test-token'
                })
                # With enhanced error handling, JSON errors should return 401, not raise exception
                assert response.status_code == 401

    @pytest.mark.integration
    def test_performance_baseline(self):
        """Test performance baseline for authorization checks."""
        import requests_mock
        
        # Setup fast mock response
        user_doc = {
            "active": True,
            "email": "perf@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '1.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                m.get(fence_url, json=user_doc, status_code=200)
                
                client = app.app.test_client()
                
                # Measure response time for multiple requests
                response_times = []
                for i in range(10):
                    start_time = time.time()
                    response = client.get('/check', headers={
                        'Authorization': f'Bearer perf-token-{i}'
                    })
                    end_time = time.time()
                    
                    assert response.status_code == 200
                    response_times.append(end_time - start_time)
                
                # Verify performance is reasonable (under 100ms without network)
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                
                assert avg_response_time < 0.1, f"Average response time {avg_response_time:.3f}s exceeds 100ms"
                assert max_response_time < 0.2, f"Max response time {max_response_time:.3f}s exceeds 200ms"


class TestKubernetesIntegration:
    """Tests for Kubernetes-specific scenarios."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.integration
    @pytest.mark.slow
    def test_health_check_for_kubernetes(self):
        """Test health check endpoint for Kubernetes probes."""
        client = app.app.test_client()
        
        # Test liveness probe
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.data == b'ok'
        assert response.headers.get('Content-Type') == 'text/html; charset=utf-8'
        
        # Test readiness probe (same endpoint for now)
        response = client.get('/healthz')
        assert response.status_code == 200

    @pytest.mark.integration
    def test_service_token_fallback(self):
        """Test service token fallback for pod-to-pod communication."""
        import requests_mock
        
        user_doc = {
            "active": True,
            "email": "service@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'FENCE_SERVICE_TOKEN': 'service-account-token',
                'HTTP_TIMEOUT': '5.0'
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                m.get(fence_url, json=user_doc, status_code=200)
                
                client = app.app.test_client()
                
                # Request without Authorization header should use service token
                response = client.get('/check')
                
                assert response.status_code == 200
                assert response.headers['X-Auth-Request-User'] == 'service@example.com'
                
                # Verify the service token was used
                assert len(m.request_history) == 1
                request = m.request_history[0]
                assert request.headers['Authorization'] == 'Bearer service-account-token'

    @pytest.mark.integration
    def test_resource_limits_simulation(self):
        """Test behavior under resource constraints."""
        import requests_mock
        
        # Simulate slow Fence response
        user_doc = {
            "active": True,
            "email": "slow@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        with requests_mock.Mocker() as m:
            env_vars = {
                'FENCE_BASE': 'https://test-fence.example.com/user',
                'HTTP_TIMEOUT': '1.0',  # Reasonable timeout for test environment
            }
            
            with patch.dict(os.environ, env_vars):
                import app
                
                fence_url = "https://test-fence.example.com/user/user"
                
                # Add delay to simulate slow network (but still within timeout)
                def slow_response(request, context):
                    time.sleep(0.1)  # 100ms delay
                    return user_doc
                
                m.get(fence_url, json=slow_response, status_code=200)
                
                client = app.app.test_client()
                
                # Request should still succeed within timeout
                response = client.get('/check', headers={
                    'Authorization': 'Bearer slow-token'
                })
                
                assert response.status_code == 200
                assert response.headers['X-Auth-Request-User'] == 'slow@example.com'


@pytest.mark.integration
@pytest.mark.slow
class TestDockerIntegration:
    """Integration tests using Docker container."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.fixture(scope="class")
    def docker_container(self):
        """Start a Docker container for integration testing."""
        try:
            # Build the Docker image
            subprocess.run([
                "docker", "build", "-t", "authz-adapter:test", 
                str(pathlib.Path(__file__).parent.parent)
            ], check=True, capture_output=True)
            
            # Start the container
            container = subprocess.Popen([
                "docker", "run", "--rm", "-p", "8081:8080",
                "-e", "FENCE_BASE=https://test-fence.example.com/user",
                "authz-adapter:test"
            ])
            
            # Wait for container to start
            time.sleep(2)
            
            yield "http://localhost:8081"
            
        finally:
            # Clean up
            if 'container' in locals():
                container.terminate()
                container.wait()

    def test_docker_health_check(self, docker_container):
        """Test health check against running Docker container."""
        response = requests.get(f"{docker_container}/healthz", timeout=5)
        assert response.status_code == 200
        assert response.text == "ok"

    def test_docker_auth_endpoint(self, docker_container):
        """Test auth endpoint against running Docker container."""
        # This would require a real Fence service or additional mocking
        response = requests.get(
            f"{docker_container}/check",
            headers={"Authorization": "Bearer test-token"},
            timeout=5
        )
        # Without real Fence service, this will likely return 401
        assert response.status_code in [200, 401]
