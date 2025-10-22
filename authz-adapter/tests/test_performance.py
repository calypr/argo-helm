"""Performance and load tests for the authz-adapter service."""

import concurrent.futures
import time
import pytest
import statistics
from unittest.mock import patch

# Import the app module
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import app


class TestPerformance:
    """Performance tests for authorization decisions."""

    @pytest.mark.slow
    def test_decide_groups_performance(self):
        """Test performance of decide_groups function."""
        # Create a complex user document
        complex_doc = {
            "active": True,
            "email": "perf@example.com",
            "authz": {
                f"/services/workflow/service-{i}": [
                    {"method": "create", "service": f"service-{i}"},
                    {"method": "read", "service": f"service-{i}"},
                    {"method": "update", "service": f"service-{i}"},
                    {"method": "delete", "service": f"service-{i}"}
                ] for i in range(100)  # 100 different services
            }
        }
        
        # Add the target service
        complex_doc["authz"]["/services/workflow/gen3-workflow"] = [
            {"method": "create", "service": "gen3-workflow"}
        ]
        
        # Measure execution time
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            groups = app.decide_groups(
                complex_doc,
                verb="CREATE",
                group="argoproj.io",
                version="v1alpha1",
                resource="workflows",
                namespace="wf-poc"
            )
            end = time.perf_counter()
            times.append(end - start)
            
            # Verify correct result
            assert "argo-runner" in groups
            assert "argo-viewer" in groups
        
        # Performance assertions
        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]  # 95th percentile
        max_time = max(times)
        
        assert avg_time < 0.001, f"Average time {avg_time:.6f}s exceeds 1ms"
        assert p95_time < 0.005, f"95th percentile {p95_time:.6f}s exceeds 5ms"
        assert max_time < 0.01, f"Max time {max_time:.6f}s exceeds 10ms"

    @pytest.mark.slow
    def test_authorization_endpoint_performance(self, mock_requests):
        """Test performance of the /check endpoint."""
        # Setup mock response
        user_doc = {
            "active": True,
            "email": "perf@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        fence_url = "https://test-fence.example.com/user/user"
        mock_requests.get(fence_url, json=user_doc, status_code=200)
        
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'HTTP_TIMEOUT': '1.0'
        }
        
        with patch.dict('os.environ', env_vars):
            client = app.app.test_client()
            
            # Measure response times
            times = []
            for i in range(100):
                start = time.perf_counter()
                response = client.get('/check', headers={
                    'Authorization': f'Bearer perf-token-{i}'
                })
                end = time.perf_counter()
                
                assert response.status_code == 200
                times.append(end - start)
            
            # Performance assertions (excluding network time since mocked)
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18]
            max_time = max(times)
            
            assert avg_time < 0.01, f"Average response time {avg_time:.6f}s exceeds 10ms"
            assert p95_time < 0.05, f"95th percentile {p95_time:.6f}s exceeds 50ms"
            assert max_time < 0.1, f"Max response time {max_time:.6f}s exceeds 100ms"

    @pytest.mark.slow
    def test_concurrent_performance(self, mock_requests):
        """Test performance under concurrent load."""
        user_doc = {
            "active": True,
            "email": "concurrent@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        fence_url = "https://test-fence.example.com/user/user"
        mock_requests.get(fence_url, json=user_doc, status_code=200)
        
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'HTTP_TIMEOUT': '5.0'
        }
        
        def make_request(request_id):
            """Make a single authorization request."""
            with patch.dict('os.environ', env_vars):
                client = app.app.test_client()
                start = time.perf_counter()
                response = client.get('/check', headers={
                    'Authorization': f'Bearer concurrent-token-{request_id}'
                })
                end = time.perf_counter()
                return response.status_code, end - start
        
        # Test with different concurrency levels
        for num_workers in [5, 10, 20]:
            num_requests = num_workers * 10
            
            start_time = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(make_request, i) for i in range(num_requests)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.perf_counter()
            
            # Verify all requests succeeded
            status_codes, response_times = zip(*results)
            assert all(code == 200 for code in status_codes)
            
            # Performance metrics
            total_time = end_time - start_time
            avg_response_time = statistics.mean(response_times)
            throughput = num_requests / total_time
            
            print(f"Concurrency {num_workers}: {throughput:.1f} req/s, "
                  f"avg response: {avg_response_time:.3f}s")
            
            # Assertions
            assert avg_response_time < 0.1, f"Average response time too high: {avg_response_time:.3f}s"
            assert throughput > 50, f"Throughput too low: {throughput:.1f} req/s"

    @pytest.mark.slow
    def test_memory_usage(self):
        """Test memory usage doesn't grow excessively."""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Create user document
        user_doc = {
            "active": True,
            "email": "memory@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        # Run many authorization decisions
        for i in range(10000):
            groups = app.decide_groups(
                user_doc,
                verb="CREATE",
                group="argoproj.io",
                version="v1alpha1",
                resource="workflows",
                namespace="wf-poc"
            )
            assert "argo-runner" in groups
            
            # Force garbage collection periodically
            if i % 1000 == 0:
                gc.collect()
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        memory_growth_mb = memory_growth / 1024 / 1024
        
        # Memory growth should be minimal (less than 10MB)
        assert memory_growth_mb < 10, f"Memory growth too high: {memory_growth_mb:.1f}MB"

    @pytest.mark.slow
    def test_large_authorization_document(self):
        """Test performance with very large authorization documents."""
        # Create a document with many authorization entries
        large_doc = {
            "active": True,
            "email": "large@example.com",
            "authz": {}
        }
        
        # Add 1000 different authorization paths
        for i in range(1000):
            path = f"/services/workflow/service-{i:04d}"
            large_doc["authz"][path] = [
                {"method": "create", "service": f"service-{i:04d}"},
                {"method": "read", "service": f"service-{i:04d}"},
                {"method": "update", "service": f"service-{i:04d}"},
                {"method": "delete", "service": f"service-{i:04d}"}
            ]
        
        # Add the target service at the end
        large_doc["authz"]["/services/workflow/gen3-workflow"] = [
            {"method": "create", "service": "gen3-workflow"}
        ]
        
        # Measure performance
        times = []
        for _ in range(100):
            start = time.perf_counter()
            groups = app.decide_groups(
                large_doc,
                verb="CREATE",
                group="argoproj.io",
                version="v1alpha1",
                resource="workflows",
                namespace="wf-poc"
            )
            end = time.perf_counter()
            times.append(end - start)
            
            assert "argo-runner" in groups
            assert "argo-viewer" in groups
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Should still be fast even with large documents
        assert avg_time < 0.01, f"Average time {avg_time:.6f}s too high for large document"
        assert max_time < 0.05, f"Max time {max_time:.6f}s too high for large document"

    @pytest.mark.slow
    def test_stress_test_health_endpoint(self):
        """Stress test the health endpoint."""
        client = app.app.test_client()
        
        # Make many rapid requests
        start_time = time.perf_counter()
        for i in range(1000):
            response = client.get('/healthz')
            assert response.status_code == 200
            assert response.data == b'ok'
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        throughput = 1000 / total_time
        
        # Health endpoint should be very fast
        assert throughput > 1000, f"Health endpoint throughput too low: {throughput:.1f} req/s"
        assert total_time < 1.0, f"1000 health checks took too long: {total_time:.3f}s"


class TestResourceUsage:
    """Test resource usage patterns."""

    def test_cpu_usage_pattern(self, mock_requests):
        """Test CPU usage remains reasonable under load."""
        import psutil
        import threading
        
        user_doc = {
            "active": True,
            "email": "cpu@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        fence_url = "https://test-fence.example.com/user/user"
        mock_requests.get(fence_url, json=user_doc, status_code=200)
        
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'HTTP_TIMEOUT': '1.0'
        }
        
        # Monitor CPU usage
        process = psutil.Process()
        cpu_percentages = []
        stop_monitoring = threading.Event()
        
        def monitor_cpu():
            """Monitor CPU usage in background."""
            while not stop_monitoring.is_set():
                cpu_percentages.append(process.cpu_percent())
                time.sleep(0.1)
        
        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.start()
        
        try:
            with patch.dict('os.environ', env_vars):
                client = app.app.test_client()
                
                # Generate load
                for i in range(100):
                    response = client.get('/check', headers={
                        'Authorization': f'Bearer cpu-token-{i}'
                    })
                    assert response.status_code == 200
        finally:
            stop_monitoring.set()
            monitor_thread.join()
        
        if cpu_percentages:
            avg_cpu = statistics.mean(cpu_percentages)
            max_cpu = max(cpu_percentages)
            
            # CPU usage should be reasonable
            assert avg_cpu < 50, f"Average CPU usage too high: {avg_cpu:.1f}%"
            assert max_cpu < 80, f"Peak CPU usage too high: {max_cpu:.1f}%"

    def test_response_time_consistency(self, mock_requests):
        """Test that response times are consistent."""
        user_doc = {
            "active": True,
            "email": "consistency@example.com",
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"}
                ]
            }
        }
        
        fence_url = "https://test-fence.example.com/user/user"
        mock_requests.get(fence_url, json=user_doc, status_code=200)
        
        env_vars = {
            'FENCE_BASE': 'https://test-fence.example.com/user',
            'HTTP_TIMEOUT': '1.0'
        }
        
        with patch.dict('os.environ', env_vars):
            client = app.app.test_client()
            
            response_times = []
            for i in range(200):
                start = time.perf_counter()
                response = client.get('/check', headers={
                    'Authorization': f'Bearer consistency-token-{i}'
                })
                end = time.perf_counter()
                
                assert response.status_code == 200
                response_times.append(end - start)
            
            # Calculate consistency metrics
            mean_time = statistics.mean(response_times)
            stdev_time = statistics.stdev(response_times)
            coefficient_of_variation = stdev_time / mean_time
            
            # Response times should be consistent (low coefficient of variation)
            assert coefficient_of_variation < 0.5, f"Response times too variable: CV={coefficient_of_variation:.3f}"
            
            # No response should be more than 3 standard deviations from mean
            outliers = [t for t in response_times if abs(t - mean_time) > 3 * stdev_time]
            outlier_percentage = len(outliers) / len(response_times) * 100
            assert outlier_percentage < 1, f"Too many outliers: {outlier_percentage:.1f}%"
