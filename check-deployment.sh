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
kubectl get all -l "app.kubernetes.io/name=argo-workflows" --all-namespaces
echo

# Check for components in default namespace that shouldn't be there
echo "⚠️  Components in default namespace:"
kubectl get all -n default -l "app.kubernetes.io/instance=argo-stack"
echo

# Check namespace definitions
echo "📁 Available namespaces:"
kubectl get namespaces | grep -E "(argo|wf-poc|security|default)"
echo

# Check if Helm chart is using correct namespaces
echo "🔧 Helm chart namespace configuration:"
helm get values argo-stack -n default 2>/dev/null | grep -A 10 "namespaces:" || echo "No values found"
