#!/bin/bash

echo "🔍 Checking Helm deployment and namespace usage..."
echo

# Check Helm releases
echo "📦 Helm releases:"
helm list --all-namespaces
echo

# Check all pods and their namespaces
echo "🐳 All pods by namespace:"
kubectl get pods --all-namespaces -l "app.kubernetes.io/managed-by=Helm"
echo

# Check specifically for Argo components
echo "🎯 Argo Workflows components:"
kubectl get pods   -n argocd
kubectl get pods   -n argo-workflows
kubectl get pods   -n security

echo

# Check for components in default namespace that shouldn't be there
echo "⚠️  Components in default namespace:(should be none)"
kubectl get all -n default -l "app.kubernetes.io/instance=argo-stack"
echo

# Check namespace definitions
echo "📁 Available namespaces:"
kubectl get namespaces | grep -E "(argo|wf-poc|security|default)"
echo

# # Check if Helm chart is using correct namespaces
# echo "🔧 Helm chart namespace configuration:"
# helm get values argo-stack -n default 2>/dev/null | grep -A 10 "namespaces:" || echo "No values found"
# echo

# # Check for existing resources that might conflict
# echo "🔍 Checking for existing conflicting resources:"

# # Check namespaces managed by Helm vs existing
# echo "Namespaces managed by different Helm releases:"
# for ns in wf-poc argocd argo-workflows security; do
#     if kubectl get namespace $ns >/dev/null 2>&1; then
#         managed_by=$(kubectl get namespace $ns -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}' 2>/dev/null)
#         instance=$(kubectl get namespace $ns -o jsonpath='{.metadata.labels.app\.kubernetes\.io/instance}' 2>/dev/null)
#         echo "  $ns: managed-by=$managed_by, instance=$instance"
#     else
#         echo "  $ns: does not exist"
#     fi
# done
# echo

# Check authz-adapter resources
echo "Authz-adapter resources:"
for ns in security ; do
    echo "  In namespace $ns:"
    kubectl get deployment authz-adapter -n $ns >/dev/null 2>&1 && echo "    deployment: exists" || echo "    deployment: not found"
    kubectl get service authz-adapter -n $ns >/dev/null 2>&1 && echo "    service: exists" || echo "    service: not found"
done
echo


# Check what's actually running
echo "🏃 Currently running pods:"
kubectl get pods --all-namespaces | grep -E "(argo|workflow|authz)"
