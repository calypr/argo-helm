#!/bin/bash
# Test script for per-application artifact repository rendering
# This validates that the Helm chart correctly generates ConfigMaps and WorkflowTemplates
# for applications with artifacts configuration.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="${SCRIPT_DIR}/helm/argo-stack"

echo "🧪 Testing Per-Application Artifact Repository Rendering"
echo "========================================================="

# Create a test values file
TEST_VALUES=$(mktemp)
cat > "${TEST_VALUES}" << 'EOF'
namespaces:
  argo: argo-workflows
  argocd: argocd
  tenant: wf-poc
  security: security
  argo-events: argo-events

argo-workflows:
  enabled: false
argo-cd:
  enabled: false
events:
  enabled: false
authzAdapter:
  replicas: 1
s3:
  enabled: false
workflowTemplates:
  createExample: false
  namespace: wf-poc
  nextflowHello:
    image: alpine:3.20

# Test applications with per-repository artifacts
applications:
  - name: test-app-1
    repoURL: https://github.com/test/app1.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    artifacts:
      bucket: test-bucket-1
      keyPrefix: app1/
      endpoint: https://s3.us-west-2.amazonaws.com
      region: us-west-2
      insecure: false
      credentialsSecret: s3-cred-app1

  - name: test-app-2
    repoURL: https://github.com/test/app2.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    artifacts:
      bucket: test-bucket-2
      keyPrefix: app2/
      endpoint: https://s3.us-east-1.amazonaws.com
      region: us-east-1
      credentialsSecret: s3-cred-app2

  - name: test-app-no-artifacts
    repoURL: https://github.com/test/app3.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
EOF

# Temporarily remove argo-events dependency to allow testing without network
CHART_YAML_BACKUP="${CHART_DIR}/Chart.yaml.test-backup"
cp "${CHART_DIR}/Chart.yaml" "${CHART_YAML_BACKUP}"
sed -i '/argo-events/,+2d' "${CHART_DIR}/Chart.yaml"

cleanup() {
  echo "🧹 Cleaning up..."
  mv "${CHART_YAML_BACKUP}" "${CHART_DIR}/Chart.yaml"
  rm -f "${TEST_VALUES}"
}
trap cleanup EXIT

echo ""
echo "📋 Test 1: Verify per-app artifact ConfigMaps are created"
echo "-----------------------------------------------------------"
OUTPUT=$(helm template test "${CHART_DIR}" --values "${TEST_VALUES}" --show-only templates/21-per-app-artifact-repositories.yaml 2>&1)

# Check for app1 ConfigMap
if echo "${OUTPUT}" | grep -q "name: argo-artifacts-test-app-1"; then
  echo "✅ ConfigMap for test-app-1 created"
else
  echo "❌ ConfigMap for test-app-1 NOT created"
  exit 1
fi

# Check for app2 ConfigMap
if echo "${OUTPUT}" | grep -q "name: argo-artifacts-test-app-2"; then
  echo "✅ ConfigMap for test-app-2 created"
else
  echo "❌ ConfigMap for test-app-2 NOT created"
  exit 1
fi

# Verify correct bucket names
if echo "${OUTPUT}" | grep -q "bucket: test-bucket-1"; then
  echo "✅ test-app-1 uses correct bucket (test-bucket-1)"
else
  echo "❌ test-app-1 bucket configuration incorrect"
  exit 1
fi

if echo "${OUTPUT}" | grep -q "bucket: test-bucket-2"; then
  echo "✅ test-app-2 uses correct bucket (test-bucket-2)"
else
  echo "❌ test-app-2 bucket configuration incorrect"
  exit 1
fi

# Verify key prefixes
if echo "${OUTPUT}" | grep -q "keyPrefix: app1/"; then
  echo "✅ test-app-1 has correct keyPrefix (app1/)"
else
  echo "❌ test-app-1 keyPrefix incorrect"
  exit 1
fi

# Verify credentials secrets
if echo "${OUTPUT}" | grep -q "name: s3-cred-app1"; then
  echo "✅ test-app-1 references correct credentials secret"
else
  echo "❌ test-app-1 credentials secret reference incorrect"
  exit 1
fi

echo ""
echo "📋 Test 2: Verify per-app WorkflowTemplates are created"
echo "-----------------------------------------------------------"
OUTPUT_WT=$(helm template test "${CHART_DIR}" --values "${TEST_VALUES}" --show-only templates/workflows/per-app-workflowtemplates.yaml 2>&1)

# Check for app1 WorkflowTemplate
if echo "${OUTPUT_WT}" | grep -q "name: test-app-1-template"; then
  echo "✅ WorkflowTemplate for test-app-1 created"
else
  echo "❌ WorkflowTemplate for test-app-1 NOT created"
  exit 1
fi

# Check artifactRepositoryRef in WorkflowTemplate
if echo "${OUTPUT_WT}" | grep -q "configMap: argo-artifacts-test-app-1"; then
  echo "✅ test-app-1 WorkflowTemplate references correct ConfigMap"
else
  echo "❌ test-app-1 WorkflowTemplate artifactRepositoryRef incorrect"
  exit 1
fi

echo ""
echo "📋 Test 3: Verify app without artifacts config doesn't get ConfigMap"
echo "-----------------------------------------------------------------------"
# The test-app-no-artifacts should NOT appear in the per-app artifacts template
if echo "${OUTPUT}" | grep -q "argo-artifacts-test-app-no-artifacts"; then
  echo "❌ App without artifacts config incorrectly got a ConfigMap"
  exit 1
else
  echo "✅ App without artifacts config correctly skipped"
fi

echo ""
echo "📋 Test 4: Verify namespace placement"
echo "-----------------------------------------------------------------------"
# ConfigMaps should be in argo-workflows namespace
if echo "${OUTPUT}" | grep -q "namespace: argo-workflows"; then
  echo "✅ Artifact ConfigMaps are in argo-workflows namespace"
else
  echo "❌ Artifact ConfigMaps namespace incorrect"
  exit 1
fi

# WorkflowTemplates should be in wf-poc namespace
if echo "${OUTPUT_WT}" | grep -q "namespace: wf-poc"; then
  echo "✅ WorkflowTemplates are in wf-poc namespace"
else
  echo "❌ WorkflowTemplates namespace incorrect"
  exit 1
fi

echo ""
echo "📋 Test 5: Verify labels are applied"
echo "-----------------------------------------------------------------------"
if echo "${OUTPUT}" | grep -q "calypr.io/application: test-app-1"; then
  echo "✅ Application label correctly applied to ConfigMap"
else
  echo "❌ Application label missing or incorrect"
  exit 1
fi

if echo "${OUTPUT_WT}" | grep -q "calypr.io/application: test-app-1"; then
  echo "✅ Application label correctly applied to WorkflowTemplate"
else
  echo "❌ Application label missing or incorrect on WorkflowTemplate"
  exit 1
fi

echo ""
echo "========================================================="
echo "✅ All per-application artifact repository tests passed!"
echo "========================================================="
