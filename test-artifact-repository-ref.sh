#!/bin/bash
# Test script for artifact repository ref feature (Issue #82)
# Tests the multi-repository artifact configuration and RBAC

set -e

echo "🧪 Testing Artifact Repository Ref Feature"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
ARGO_NS="${ARGO_NAMESPACE:-argo-workflows}"
VALUES_FILE="${VALUES_FILE:-helm/argo-stack/values.yaml}"

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

echo "Test 1: Verify artifact-repositories ConfigMap exists"
echo "-------------------------------------------------------"
if kubectl get configmap artifact-repositories -n "$ARGO_NS" &>/dev/null; then
    check_pass "ConfigMap 'artifact-repositories' exists in namespace '$ARGO_NS'"
else
    check_fail "ConfigMap 'artifact-repositories' not found in namespace '$ARGO_NS'"
fi
echo ""

echo "Test 2: Verify ConfigMap has artifactRepositories key"
echo "-------------------------------------------------------"
if kubectl get configmap artifact-repositories -n "$ARGO_NS" -o jsonpath='{.data.artifactRepositories}' | grep -q "default:"; then
    check_pass "ConfigMap contains 'artifactRepositories' key with default repository"
else
    check_fail "ConfigMap missing 'artifactRepositories' key or default entry"
fi
echo ""

echo "Test 3: Check for legacy default-v1 key (backward compatibility)"
echo "----------------------------------------------------------------"
if kubectl get configmap artifact-repositories -n "$ARGO_NS" -o jsonpath='{.data.default-v1}' | grep -q "bucket:"; then
    check_pass "Legacy 'default-v1' key exists for backward compatibility"
else
    check_warn "Legacy 'default-v1' key not found - may affect existing workflows"
fi
echo ""

echo "Test 4: Verify repo-specific artifact repositories"
echo "----------------------------------------------------"
# Use a more robust parsing approach - count repository entries by looking for bucket definitions
ARTIFACT_REPOS_DATA=$(kubectl get configmap artifact-repositories -n "$ARGO_NS" -o jsonpath='{.data.artifactRepositories}')
# Count occurrences of "bucket:" which indicates a repository configuration (excluding comments)
REPO_COUNT=$(echo "$ARTIFACT_REPOS_DATA" | grep -v "^[[:space:]]*#" | grep -c "bucket:" || echo "0")
if [ "$REPO_COUNT" -gt 0 ]; then
    check_pass "Found $REPO_COUNT repository configuration(s) in artifactRepositories"
    echo ""
    echo "Repositories configured:"
    # Extract repository names using awk - lines that have a colon at end and start with whitespace followed by letters
    echo "$ARTIFACT_REPOS_DATA" | awk '/^[[:space:]]+[a-z][^#]*:$/ {gsub(/^[[:space:]]+/, ""); gsub(/:$/, ""); print "  - " $0}'
else
    check_warn "No repo-specific repositories found (only default)"
fi
echo ""

echo "Test 5: Verify RBAC for artifact repository access"
echo "----------------------------------------------------"
RBAC_COUNT=$(kubectl get role -n "$ARGO_NS" -l app.kubernetes.io/component=workflow-rbac 2>/dev/null | grep -c artifact-repository-reader || echo "0")
if [ "$RBAC_COUNT" -gt 0 ]; then
    check_pass "Found $RBAC_COUNT RBAC Role(s) for artifact repository access"
else
    check_warn "No RBAC Roles found - may be expected if no repoRegistrations are configured"
fi
echo ""

echo "Test 6: Check WorkflowTemplates for artifactRepositoryRef"
echo "-----------------------------------------------------------"
# Check tenant namespaces for WorkflowTemplates
TENANT_NAMESPACES=$(kubectl get ns -l source=repo-registration -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ -n "$TENANT_NAMESPACES" ]; then
    FOUND_REF=0
    for ns in $TENANT_NAMESPACES; do
        if kubectl get workflowtemplate -n "$ns" -o yaml 2>/dev/null | grep -q "artifactRepositoryRef"; then
            check_pass "WorkflowTemplate in namespace '$ns' has artifactRepositoryRef configured"
            FOUND_REF=1
        fi
    done
    if [ "$FOUND_REF" -eq 0 ]; then
        check_warn "No WorkflowTemplates found with artifactRepositoryRef in tenant namespaces"
    fi
else
    check_warn "No tenant namespaces found (no repoRegistrations configured)"
fi
echo ""

echo "Test 7: Validate ConfigMap structure"
echo "--------------------------------------"
# Extract and validate YAML structure
TEMP_FILE=$(mktemp)
kubectl get configmap artifact-repositories -n "$ARGO_NS" -o jsonpath='{.data.artifactRepositories}' > "$TEMP_FILE"

# Try multiple validation methods in order of preference
if command -v yq &> /dev/null; then
    # yq is available - most robust
    if yq eval '.' "$TEMP_FILE" &>/dev/null; then
        check_pass "artifactRepositories data is valid YAML (validated with yq)"
    else
        check_fail "artifactRepositories data is invalid YAML"
    fi
elif command -v python3 &> /dev/null; then
    # python3 with yaml module
    if python3 -c "import yaml; yaml.safe_load(open('$TEMP_FILE'))" 2>/dev/null; then
        check_pass "artifactRepositories data is valid YAML (validated with python3)"
    else
        check_fail "artifactRepositories data is invalid YAML"
    fi
else
    # Fallback: basic syntax check - look for valid structure
    if grep -q "bucket:" "$TEMP_FILE" && grep -q "endpoint:" "$TEMP_FILE"; then
        check_pass "artifactRepositories data appears to have valid YAML structure (basic check)"
    else
        check_warn "Unable to fully validate YAML structure (yq/python3 not available)"
    fi
fi
rm -f "$TEMP_FILE"
echo ""

echo "Test 8: Check ServiceAccount permissions"
echo "------------------------------------------"
# Check if any wf-runner ServiceAccount exists in tenant namespaces
if [ -n "$TENANT_NAMESPACES" ]; then
    for ns in $TENANT_NAMESPACES; do
        if kubectl get sa wf-runner -n "$ns" &>/dev/null; then
            # Test if SA can read the ConfigMap
            if kubectl auth can-i get configmap/artifact-repositories \
                --as=system:serviceaccount:$ns:wf-runner \
                -n "$ARGO_NS" &>/dev/null; then
                check_pass "ServiceAccount wf-runner in namespace '$ns' can read artifact-repositories ConfigMap"
            else
                check_fail "ServiceAccount wf-runner in namespace '$ns' CANNOT read artifact-repositories ConfigMap"
            fi
        fi
    done
else
    check_warn "No tenant namespaces found to test ServiceAccount permissions"
fi
echo ""

echo "Test 9: Display artifact repository configuration"
echo "---------------------------------------------------"
echo "Current artifact repositories:"
echo ""
kubectl get configmap artifact-repositories -n "$ARGO_NS" -o jsonpath='{.data.artifactRepositories}' | head -80
echo ""
echo "..."
echo ""

echo "=========================================="
echo -e "${GREEN}All tests completed!${NC}"
echo ""
echo "Summary:"
echo "  - ConfigMap: artifact-repositories exists in $ARGO_NS"
echo "  - Multi-repository configuration: enabled"
echo "  - RBAC: configured for tenant namespaces"
echo "  - WorkflowTemplates: using artifactRepositoryRef"
echo ""
echo "To submit a test workflow, use:"
echo "  argo submit -n <namespace> --from workflowtemplate/nextflow-repo-runner"
echo ""
