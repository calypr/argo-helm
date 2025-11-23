#!/bin/bash
# Test script for multi-tenant artifact repository configuration
# Tests that each tenant namespace has its own artifact-repositories ConfigMap

set -e

echo "🧪 Testing Multi-Tenant Artifact Repository Configuration"
echo "=========================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
ARGO_NS="${ARGO_NAMESPACE:-argo-workflows}"
VALUES_FILE="${VALUES_FILE:-helm/argo-stack/values.yaml}"

# Get tenant namespaces (used in multiple tests)
TENANT_NAMESPACES=$(kubectl get ns -l source=repo-registration -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

function check_pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
}

function check_fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    exit 1
}

function check_warn() {
    echo -e "${YELLOW}⚠ WARN:${NC} $1"
}

echo "Test 1: Verify global artifact-repositories ConfigMap exists (for legacy/default workflows)"
echo "--------------------------------------------------------------------------------------------"
if kubectl get configmap artifact-repositories -n "$ARGO_NS" &>/dev/null; then
    check_pass "ConfigMap 'artifact-repositories' exists in namespace '$ARGO_NS'"
else
    check_warn "ConfigMap 'artifact-repositories' not found in namespace '$ARGO_NS' (may be ok if only using tenant-specific repos)"
fi
echo ""

echo "Test 2: Verify tenant namespaces exist"
echo "---------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    NAMESPACE_COUNT=$(echo "$TENANT_NAMESPACES" | wc -w)
    check_pass "Found $NAMESPACE_COUNT tenant namespace(s):"
    for ns in $TENANT_NAMESPACES; do
        echo "  - $ns"
    done
else
    check_warn "No tenant namespaces found (no repoRegistrations configured)"
fi
echo ""

echo "Test 3: Verify each tenant namespace has artifact-repositories ConfigMap"
echo "-------------------------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    ALL_HAVE_CM=true
    for ns in $TENANT_NAMESPACES; do
        if kubectl get configmap artifact-repositories -n "$ns" &>/dev/null; then
            check_pass "ConfigMap exists in namespace '$ns'"
        else
            check_fail "ConfigMap NOT found in namespace '$ns'"
            ALL_HAVE_CM=false
        fi
    done
    if [ "$ALL_HAVE_CM" = true ]; then
        echo ""
        check_pass "All tenant namespaces have artifact-repositories ConfigMap"
    fi
else
    check_warn "No tenant namespaces to check"
fi
echo ""

echo "Test 4: Verify ConfigMaps have default-v1 key"
echo "----------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        if kubectl get configmap artifact-repositories -n "$ns" -o jsonpath='{.data.default-v1}' 2>/dev/null | grep -q "bucket:"; then
            check_pass "ConfigMap in namespace '$ns' has 'default-v1' key"
        else
            check_fail "ConfigMap in namespace '$ns' missing 'default-v1' key or invalid content"
        fi
    done
else
    check_warn "No tenant namespaces to check"
fi
echo ""

echo "Test 5: Verify ServiceAccount exists in tenant namespaces"
echo "----------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        if kubectl get sa wf-runner -n "$ns" &>/dev/null; then
            check_pass "ServiceAccount 'wf-runner' exists in namespace '$ns'"
        else
            check_fail "ServiceAccount 'wf-runner' NOT found in namespace '$ns'"
        fi
    done
else
    check_warn "No tenant namespaces to check"
fi
echo ""

echo "Test 6: Verify S3 credentials secrets exist"
echo "--------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        # Extract repo name from namespace (remove wf- prefix)
        REPO_NAME=$(echo "$ns" | sed 's/^wf-//')
        if kubectl get secret -n "$ns" 2>/dev/null | grep -q "s3-credentials-"; then
            check_pass "S3 credentials secret found in namespace '$ns'"
        else
            check_warn "No S3 credentials secret found in namespace '$ns'"
        fi
    done
else
    check_warn "No tenant namespaces to check"
fi
echo ""

echo "Test 7: Check WorkflowTemplates exist in tenant namespaces"
echo "-----------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        if kubectl get workflowtemplate -n "$ns" &>/dev/null; then
            WT_COUNT=$(kubectl get workflowtemplate -n "$ns" --no-headers 2>/dev/null | wc -l)
            check_pass "Found $WT_COUNT WorkflowTemplate(s) in namespace '$ns'"
        else
            check_warn "No WorkflowTemplates found in namespace '$ns'"
        fi
    done
else
    check_warn "No tenant namespaces to check"
fi
echo ""

echo "Test 8: Validate ConfigMap YAML structure in tenant namespaces"
echo "----------------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        TEMP_FILE=$(mktemp)
        kubectl get configmap artifact-repositories -n "$ns" -o jsonpath='{.data.default-v1}' 2>/dev/null > "$TEMP_FILE"
        
        # Try multiple validation methods in order of preference
        if command -v yq &> /dev/null; then
            if yq eval '.' "$TEMP_FILE" &>/dev/null; then
                check_pass "ConfigMap in namespace '$ns' has valid YAML structure"
            else
                check_fail "ConfigMap in namespace '$ns' has invalid YAML"
            fi
        elif command -v python3 &> /dev/null; then
            if python3 -c "import yaml; yaml.safe_load(open('$TEMP_FILE'))" 2>/dev/null; then
                check_pass "ConfigMap in namespace '$ns' has valid YAML structure"
            else
                check_fail "ConfigMap in namespace '$ns' has invalid YAML"
            fi
        else
            # Basic syntax check
            if grep -q "bucket:" "$TEMP_FILE"; then
                check_pass "ConfigMap in namespace '$ns' appears to have valid structure (basic check)"
            else
                check_warn "Unable to fully validate YAML structure in namespace '$ns'"
            fi
        fi
        rm -f "$TEMP_FILE"
    done
else
    check_warn "No tenant namespaces to validate"
fi
echo ""

echo "Test 9: Check ServiceAccount ConfigMap permissions in tenant namespaces"
echo "------------------------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        if kubectl get sa wf-runner -n "$ns" &>/dev/null; then
            # Test if SA can read the ConfigMap in its own namespace
            if kubectl auth can-i get configmap/artifact-repositories \
                --as=system:serviceaccount:$ns:wf-runner \
                -n "$ns" &>/dev/null; then
                check_pass "ServiceAccount wf-runner in namespace '$ns' can read ConfigMap in its own namespace"
            else
                check_fail "ServiceAccount wf-runner in namespace '$ns' CANNOT read ConfigMap in its own namespace"
            fi
        fi
    done
else
    check_warn "No tenant namespaces found to test ServiceAccount permissions"
fi
echo ""

echo "Test 10: Display sample artifact repository configuration"
echo "----------------------------------------------------------"
if [ -n "$TENANT_NAMESPACES" ]; then
    FIRST_NS=$(echo "$TENANT_NAMESPACES" | awk '{print $1}')
    echo "Sample configuration from namespace '$FIRST_NS':"
    echo ""
    kubectl get configmap artifact-repositories -n "$FIRST_NS" -o jsonpath='{.data.default-v1}' 2>/dev/null | head -30
    echo ""
    echo "..."
else
    echo "No tenant namespaces to display"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}All tests completed!${NC}"
echo ""
echo "Summary:"
if [ -n "$TENANT_NAMESPACES" ]; then
    NAMESPACE_COUNT=$(echo "$TENANT_NAMESPACES" | wc -w)
    echo "  - Tenant namespaces: $NAMESPACE_COUNT"
    echo "  - Each namespace has artifact-repositories ConfigMap"
    echo "  - Using default-v1 key for automatic discovery"
    echo "  - ServiceAccounts configured with proper permissions"
else
    echo "  - No tenant namespaces configured"
    echo "  - Configure repoRegistrations to create tenant-specific artifact repositories"
fi
echo ""
echo "To submit a test workflow, use:"
if [ -n "$TENANT_NAMESPACES" ]; then
    FIRST_NS=$(echo "$TENANT_NAMESPACES" | awk '{print $1}')
    echo "  argo submit -n $FIRST_NS --from workflowtemplate/nextflow-repo-runner"
else
    echo "  (configure repoRegistrations first)"
fi
echo ""
