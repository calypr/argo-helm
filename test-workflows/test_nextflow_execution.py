#!/usr/bin/env python3
"""Test script to submit and monitor Nextflow workflow execution in Argo Workflows."""

import requests
import yaml
import time
import json
import sys
import argparse
from typing import Dict, Any, Optional

class ArgoWorkflowTester:
    """Test harness for Argo Workflows and Nextflow integration."""
    
    def __init__(self, base_url: str = "http://localhost:2746"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        
    def submit_workflow(self, workflow_yaml: str) -> Dict[str, Any]:
        """Submit a workflow to Argo Workflows."""
        with open(workflow_yaml, 'r') as f:
            workflow_spec = yaml.safe_load(f)
        
        url = f"{self.api_url}/workflows/wf-poc"
        headers = {'Content-Type': 'application/json'}
        
        print(f"Submitting workflow to {url}")
        print(f"Workflow name pattern: {workflow_spec['metadata']['generateName']}")

        # Argo Workflows API expects the workflow to be wrapped in a request body
        request_body = {
            "workflow": workflow_spec
        }
        
        
        response = requests.post(url, json=request_body, headers=headers)
        
        if response.status_code in [200, 201]:
            workflow = response.json()
            print(f"✓ Workflow submitted successfully: {workflow['metadata']['name']}")
            return workflow
        else:
            print(f"✗ Failed to submit workflow: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Check for RBAC issues
            if "forbidden" in response.text.lower() or response.status_code == 403:
                print("\n🔒 RBAC Permission Issue Detected!")
                print("This appears to be a Kubernetes RBAC (Role-Based Access Control) issue.")
                print("Please ensure the following resources are applied:")
                print("  kubectl apply -f rbac/workflow-rbac.yaml")
                print("\nOr create the necessary RBAC resources manually:")
                print("  1. ServiceAccount: nextflow-workflow-sa")
                print("  2. Role with pod creation permissions")
                print("  3. RoleBinding linking the ServiceAccount to the Role")
            
            raise Exception(f"Workflow submission failed: {response.status_code}")
    
    def get_workflow_status(self, namespace: str, name: str) -> Dict[str, Any]:
        """Get workflow status."""
        url = f"{self.api_url}/workflows/{namespace}/{name}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get workflow status: {response.status_code}")
    
    def get_workflow_logs(self, namespace: str, name: str) -> Optional[str]:
        """Get workflow logs."""
        try:
            url = f"{self.api_url}/workflows/{namespace}/{name}/log"
            response = requests.get(url)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Could not retrieve logs: {e}")
        return None
    
    def wait_for_completion(self, namespace: str, name: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for workflow to complete."""
        start_time = time.time()
        
        print(f"⏳ Waiting for workflow {name} to complete (timeout: {timeout}s)...")
        
        while time.time() - start_time < timeout:
            try:
                workflow = self.get_workflow_status(namespace, name)
                phase = workflow.get('status', {}).get('phase', 'Unknown')
                progress = workflow.get('status', {}).get('progress', 'Unknown')
                
                elapsed = int(time.time() - start_time)
                print(f"[{elapsed:3d}s] Workflow {name} status: {phase} (progress: {progress})")
                
                # Check for RBAC errors in workflow status
                if phase == 'Failed':
                    status = workflow.get('status', {})
                    message = status.get('message', '')
                    if 'forbidden' in message.lower() or 'serviceaccount' in message.lower():
                        print(f"\n🔒 RBAC Error detected in workflow: {message}")
                        print("Please apply RBAC configuration: kubectl apply -f rbac/workflow-rbac.yaml")
                        return workflow
                
                if phase in ['Succeeded', 'Failed', 'Error']:
                    return workflow
                
                time.sleep(10)
            except Exception as e:
                print(f"Error checking workflow status: {e}")
                time.sleep(5)
        
        raise Exception(f"Workflow did not complete within {timeout} seconds")
    
    def test_nextflow_hello_world(self, workflow_file: str = 'test-workflows/nextflow-hello-world.yaml') -> bool:
        """Test Nextflow hello world workflow execution."""
        try:
            print("🚀 Starting Nextflow Hello World test...")
            print(f"Using workflow file: {workflow_file}")
            
            # Submit workflow
            workflow = self.submit_workflow(workflow_file)
            namespace = workflow['metadata']['namespace']
            name = workflow['metadata']['name']
            
            # Wait for completion
            final_workflow = self.wait_for_completion(namespace, name, timeout=600)  # 10 minute timeout
            
            # Check result
            phase = final_workflow.get('status', {}).get('phase', 'Unknown')
            
            if phase == 'Succeeded':
                print("✅ Nextflow Hello World workflow completed successfully!")
                
                # Get and display logs
                logs = self.get_workflow_logs(namespace, name)
                if logs:
                    print("📋 Workflow logs:")
                    print("-" * 50)
                    print(logs)
                    print("-" * 50)
                
                # Display workflow summary
                status = final_workflow.get('status', {})
                if 'startedAt' in status and 'finishedAt' in status:
                    print(f"📊 Execution time: {status['startedAt']} → {status['finishedAt']}")
                
                return True
            else:
                print(f"❌ Workflow failed with phase: {phase}")
                
                # Print failure details
                status = final_workflow.get('status', {})
                if 'message' in status:
                    print(f"Error message: {status['message']}")
                
                # Try to get logs for debugging
                logs = self.get_workflow_logs(namespace, name)
                if logs:
                    print("📋 Failure logs:")
                    print(logs)
                
                return False
                
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            return False

def test_connectivity(base_url: str) -> bool:
    """Test connectivity to Argo Workflows API."""
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"✓ Argo Workflows API accessible at {base_url} (status: {response.status_code})")
        return True
    except Exception as e:
        print(f"✗ Cannot access Argo Workflows API at {base_url}: {e}")
        return False

def verify_namespace_setup() -> bool:
    """Verify that required namespaces and RBAC are properly configured."""
    try:
        import subprocess
        
        print("🔍 Verifying namespace and RBAC setup...")
        
        # Check if required namespaces exist
        required_namespaces = ['argo-workflows', 'wf-poc', 'security']
        
        for ns in required_namespaces:
            result = subprocess.run(['kubectl', 'get', 'namespace', ns], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ Namespace '{ns}' exists")
            else:
                print(f"✗ Namespace '{ns}' not found")
                print(f"  Create with: kubectl create namespace {ns}")
                return False
        
        # Check if ServiceAccount exists in wf-poc namespace
        result = subprocess.run(['kubectl', 'get', 'serviceaccount', 'nextflow-workflow-sa', '-n', 'wf-poc'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ ServiceAccount 'nextflow-workflow-sa' exists in wf-poc namespace")
        else:
            print("✗ ServiceAccount 'nextflow-workflow-sa' not found in wf-poc namespace")
            print("  Apply RBAC with: kubectl apply -f rbac/workflow-rbac.yaml")
            return False
        
        # Check Argo Workflows deployment location
        result = subprocess.run(['kubectl', 'get', 'deployment', '-l', 'app.kubernetes.io/name=argo-workflows-server', '--all-namespaces'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("🔍 Argo Workflows server deployment locations:")
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split()
                    namespace = parts[0]
                    deployment = parts[1]
                    print(f"  - {deployment} in namespace '{namespace}'")
                    if namespace != 'argo-workflows':
                        print(f"    ⚠️  Expected in 'argo-workflows' namespace, found in '{namespace}'")
        
        return True
        
    except Exception as e:
        print(f"Error verifying setup: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test Nextflow workflow execution in Argo Workflows')
    parser.add_argument('--argo-url', default='http://localhost:2746', 
                       help='Argo Workflows server URL (default: http://localhost:2746)')
    parser.add_argument('--workflow-file', default='test-workflows/nextflow-hello-world.yaml',
                       help='Workflow YAML file to submit (default: test-workflows/nextflow-hello-world.yaml)')
    parser.add_argument('--skip-connectivity-check', action='store_true',
                       help='Skip initial connectivity check')
    
    args = parser.parse_args()
    
    print("🧪 Nextflow Workflow Execution Test")
    print("===================================")
    print(f"Argo Workflows URL: {args.argo_url}")
    print(f"Workflow file: {args.workflow_file}")
    print()
    
    # Verify namespace setup first
    if not verify_namespace_setup():
        print("\n❌ Namespace/RBAC setup verification failed!")
        print("Please fix the issues above before running workflows.")
        sys.exit(1)
    
    print("\n📋 Prerequisites:")
    print("  1. Argo Workflows server running and accessible")
    print("  2. RBAC resources applied: kubectl apply -f rbac/workflow-rbac.yaml")
    print("  3. All required namespaces exist and are properly configured")
    print()
    
    # Test connectivity to Argo Workflows
    if not args.skip_connectivity_check:
        if not test_connectivity(args.argo_url):
            sys.exit(1)
        print()
    
    # Run the test
    tester = ArgoWorkflowTester(args.argo_url)
    success = tester.test_nextflow_hello_world(args.workflow_file)
    
    if success:
        print("\n🎉 All tests passed!")
        print("Nextflow hello world workflow executed successfully in Argo Workflows!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        print("Check the logs above for error details.")
        sys.exit(1)

if __name__ == "__main__":
    main()