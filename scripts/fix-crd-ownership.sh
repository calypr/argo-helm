#!/bin/bash

set -e

echo "🔧 Fixing CRD ownership conflicts..."

# List of CRDs that might have ownership conflicts
CRDS=(
    "applications.argoproj.io"
    "workflows.argoproj.io" 
    "workflowtemplates.argoproj.io"
    "cronworkflows.argoproj.io"
    "clusterworkflowtemplates.argoproj.io"
)

echo "Checking for conflicting CRD annotations..."

for crd in "${CRDS[@]}"; do
    if kubectl get crd $crd >/dev/null 2>&1; then
        echo "Found CRD: $crd"
        
        # Get current annotations
        current_namespace=$(kubectl get crd $crd -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-namespace}' 2>/dev/null || echo "")
        current_name=$(kubectl get crd $crd -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}' 2>/dev/null || echo "")
        
        echo "  Current release-namespace: $current_namespace"
        echo "  Current release-name: $current_name"
        
        if [[ "$current_namespace" == "default" ]]; then
            echo "  🔄 Removing conflicting Helm annotations from $crd"
            kubectl annotate crd $crd meta.helm.sh/release-namespace- || true
            kubectl annotate crd $crd meta.helm.sh/release-name- || true
            kubectl label crd $crd app.kubernetes.io/managed-by- || true
        fi
    else
        echo "CRD not found: $crd (OK)"
    fi
done

echo "✅ CRD ownership conflicts resolved!"
