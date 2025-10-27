#!/bin/bash

set -e

echo "🧹 Cleaning up existing Helm installation..."

# Function to safely delete resources
safe_delete() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    
    if kubectl get $resource_type $resource_name -n $namespace >/dev/null 2>&1; then
        echo "Deleting $resource_type/$resource_name in namespace $namespace"
        kubectl delete $resource_type $resource_name -n $namespace --ignore-not-found
    else
        echo "$resource_type/$resource_name not found in namespace $namespace (skipping)"
    fi
}

# Check if Helm release exists and uninstall it
if helm list -n default | grep -q argo-stack; then
    echo "Uninstalling Helm release argo-stack from default namespace..."
    helm uninstall argo-stack -n default
else
    echo "No Helm release 'argo-stack' found in default namespace"
fi

# Check other namespaces for the release
for ns in argo-workflows argo argocd; do
    if helm list -n $ns 2>/dev/null | grep -q argo-stack; then
        echo "Uninstalling Helm release argo-stack from $ns namespace..."
        helm uninstall argo-stack -n $ns
    fi
done

# Clean up specific resources that might be orphaned
echo "Cleaning up potentially orphaned resources..."

# Clean up authz-adapter resources
safe_delete deployment authz-adapter security
safe_delete service authz-adapter security
safe_delete deployment authz-adapter default
safe_delete service authz-adapter default

# Wait a bit for resources to be fully deleted
echo "Waiting for resources to be fully deleted..."
sleep 5

# Optionally clean up namespaces (commented out by default to be safe)
# Uncomment if you want to start completely fresh
# echo "Cleaning up namespaces (uncomment if desired)..."
# kubectl delete namespace wf-poc argocd argo-workflows security --ignore-not-found

echo "✅ Cleanup completed!"
echo
echo "🚀 Installing fresh Helm release..."

# Install in argo-workflows namespace
helm install argo-stack ./helm/argo-stack \
    --namespace argo-workflows \
    --create-namespace \
    --wait \
    --timeout 10m

echo "✅ Installation completed!"
echo
echo "🔍 Checking deployment status..."
./check-deployment.sh
