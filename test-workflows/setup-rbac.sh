#!/bin/bash

echo "🔒 Setting up RBAC for Nextflow workflows..."

# Create namespace if it doesn't exist
echo "Creating namespace 'wf-poc' if it doesn't exist..."
kubectl create namespace wf-poc --dry-run=client -o yaml | kubectl apply -f -

# Apply RBAC resources
echo "Applying RBAC resources..."
kubectl apply -f rbac/workflow-rbac.yaml

# Verify setup
echo "Verifying RBAC setup..."
kubectl get serviceaccount nextflow-workflow-sa -n wf-poc
kubectl get role nextflow-workflow-role -n wf-poc
kubectl get rolebinding nextflow-workflow-binding -n wf-poc

echo "✅ RBAC setup complete!"
echo ""
echo "You can now run workflows with the nextflow-workflow-sa service account."
echo "Test with: python test-workflows/test_nextflow_execution.py"
