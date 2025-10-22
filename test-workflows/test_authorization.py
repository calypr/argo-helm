#!/usr/bin/env python3
"""Test authorization for Nextflow workflow submission through the authz adapter."""

import requests
import json
import sys
import argparse
import time
from typing import Dict, Any, Optional

class AuthzValidationTester:
    """Test harness for authorization validation in the CI environment."""
    
    def __init__(self, authz_url: str = "http://localhost:5000", argo_url: str = "http://localhost:2746"):
        self.authz_url = authz_url
        self.argo_url = argo_url
        
    def test_authz_health(self) -> bool:
        """Test that the authz adapter is healthy."""
        try:
            response = requests.get(f"{self.authz_url}/healthz", timeout=5)
            if response.status_code == 200 and response.text == 'ok':
                print(f"✓ AuthZ adapter is healthy at {self.authz_url}")
                return True
            else:
                print(f"✗ AuthZ adapter health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Cannot reach AuthZ adapter at {self.authz_url}: {e}")
            return False
    
    def test_argo_accessibility(self) -> bool:
        """Test that Argo Workflows is accessible."""
        try:
            response = requests.get(f"{self.argo_url}/", timeout=5)
            print(f"✓ Argo Workflows is accessible at {self.argo_url} (status: {response.status_code})")
            return True
        except Exception as e:
            print(f"✗ Cannot reach Argo Workflows at {self.argo_url}: {e}")
            return False
    
    def test_workflow_submission_authorization(self) -> bool:
        """Test authorization for workflow submission."""
        print("🔐 Testing workflow submission authorization...")
        
        # Test cases for different authorization scenarios
        test_cases = [
            {
                "name": "Authorized user with workflow permissions",
                "headers": {
                    "Authorization": "Bearer valid-workflow-token",
                    "X-Original-URI": "/api/v1/workflows/argo-workflows",
                    "X-Original-Method": "POST"
                },
                "expected_status": 200,
                "expected_groups": ["argo-runner", "argo-viewer"]
            },
            {
                "name": "User with only read permissions",
                "headers": {
                    "Authorization": "Bearer readonly-token", 
                    "X-Original-URI": "/api/v1/workflows/argo-workflows/some-workflow",
                    "X-Original-Method": "GET"
                },
                "expected_status": 200,
                "expected_groups": ["argo-viewer"]
            },
            {
                "name": "Unauthorized user",
                "headers": {
                    "Authorization": "Bearer invalid-token",
                    "X-Original-URI": "/api/v1/workflows/argo-workflows",
                    "X-Original-Method": "POST"
                },
                "expected_status": 401,
                "expected_groups": []
            }
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            print(f"\n  Testing: {test_case['name']}")
            
            try:
                response = requests.get(
                    f"{self.authz_url}/check",
                    headers=test_case["headers"],
                    timeout=10
                )
                
                if response.status_code == test_case["expected_status"]:
                    print(f"    ✓ Status code: {response.status_code}")
                else:
                    print(f"    ✗ Expected status {test_case['expected_status']}, got {response.status_code}")
                    all_passed = False
                    continue
                
                # Check groups if auth was successful
                if response.status_code == 200:
                    groups_header = response.headers.get('X-Auth-Request-Groups', '')
                    
                    for expected_group in test_case["expected_groups"]:
                        if expected_group in groups_header:
                            print(f"    ✓ Group '{expected_group}' present")
                        else:
                            print(f"    ✗ Group '{expected_group}' missing from: {groups_header}")
                            all_passed = False
                
            except Exception as e:
                print(f"    ✗ Request failed: {e}")
                all_passed = False
        
        return all_passed
    
    def test_argo_resource_context_authorization(self) -> bool:
        """Test authorization with Argo resource context headers."""
        print("🎯 Testing Argo resource context authorization...")
        
        headers = {
            "Authorization": "Bearer argo-context-token",
            "X-Original-URI": "/api/v1/workflows/argo-workflows",
            "X-Original-Method": "POST",
            "X-Resource-Group": "argoproj.io",
            "X-Resource-Version": "v1alpha1", 
            "X-Resource-Kind": "workflows"
        }
        
        try:
            response = requests.get(
                f"{self.authz_url}/check",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                groups = response.headers.get('X-Auth-Request-Groups', '')
                print(f"  ✓ Authorization successful with groups: {groups}")
                
                # Should have runner permissions for Argo resources
                if 'argo-runner' in groups:
                    print("  ✓ Argo runner permissions granted")
                    return True
                else:
                    print("  ✗ Argo runner permissions not granted")
                    return False
            else:
                print(f"  ✗ Authorization failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ✗ Request failed: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all authorization validation tests."""
        print("🧪 Authorization Validation Test Suite")
        print("=====================================")
        
        tests = [
            ("AuthZ Health Check", self.test_authz_health),
            ("Argo Accessibility", self.test_argo_accessibility), 
            ("Workflow Submission Authorization", self.test_workflow_submission_authorization),
            ("Argo Resource Context Authorization", self.test_argo_resource_context_authorization)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            print(f"\n🔍 {test_name}")
            print("-" * (len(test_name) + 4))
            
            try:
                result = test_func()
                results.append(result)
                
                if result:
                    print(f"✅ {test_name}: PASSED")
                else:
                    print(f"❌ {test_name}: FAILED")
                    
            except Exception as e:
                print(f"💥 {test_name}: ERROR - {e}")
                results.append(False)
        
        # Summary
        passed = sum(results)
        total = len(results)
        
        print(f"\n📊 Test Summary")
        print("===============")
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if all(results):
            print("🎉 All authorization tests passed!")
            return True
        else:
            print("💥 Some authorization tests failed!")
            return False

def main():
    parser = argparse.ArgumentParser(description='Test authorization for Nextflow workflow submission')
    parser.add_argument('--authz-url', default='http://localhost:5000',
                       help='AuthZ adapter URL (default: http://localhost:5000)')
    parser.add_argument('--argo-url', default='http://localhost:2746',
                       help='Argo Workflows URL (default: http://localhost:2746)')
    
    args = parser.parse_args()
    
    tester = AuthzValidationTester(args.authz_url, args.argo_url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()