# Testing Guide: Vault + ESO Integration

This guide describes how to test the Vault and External Secrets Operator integration with the argo-stack chart.

## Prerequisites

- Kubernetes cluster (Kind, k3d, or similar for local testing)
- Helm 3.x
- kubectl

## Test Scenarios

### 1. Template Validation (No Cluster Required)

Validate that templates render correctly without requiring a cluster or dependencies:

```bash
# Run automated template validation
python3 test-eso-templates.py

# Expected output: All tests should PASS
```

This validates:
- Helper template definitions
- Values.yaml schema correctness
- Template conditional logic
- Secret path format conversions
- Backward compatibility

### 2. Local Development with Vault in Kubernetes

Test the full integration locally using Vault deployed in your Kubernetes cluster.

#### Step 1: Create Kind Cluster

```bash
# Create a Kind cluster
kind create cluster --name argo-test

# Verify cluster is ready
kubectl cluster-info --context kind-argo-test
```

#### Step 2: Install Vault Dev Server in Cluster

```bash
# Install Vault using Helm in the cluster
make vault-dev

# Verify Vault is running
make vault-status

# Seed with test data
make vault-seed
```

The Vault dev server will be deployed to the `vault` namespace at `vault.vault.svc.cluster.local:8200` with root token `root`.

#### Step 2b: Install MinIO for S3 Storage (Optional)

If you want to test S3 artifact storage, install MinIO:

```bash
# Install MinIO using Helm in the cluster
make minio-dev

# Create the default bucket
make minio-create-bucket

# Verify MinIO is running
make minio-status
```

MinIO will be deployed to the `minio` namespace at `minio.minio.svc.cluster.local:9000` with credentials `minioadmin/minioadmin`.

#### Step 3: Install External Secrets Operator

Install ESO using the Makefile target (recommended):

```bash
make eso-install
```

Or install manually:

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system --create-namespace \
  --set installCRDs=true
```

Wait for ESO to be ready:

```bash
kubectl wait --for=condition=Ready pod \
  -l app.kubernetes.io/name=external-secrets \
  -n external-secrets-system --timeout=120s
```

#### Step 4: Install argo-stack with Vault

```bash
helm install argo-stack ./helm/argo-stack \
  -f examples/vault/dev-values.yaml \
  --namespace argocd --create-namespace
```

#### Step 5: Verify Secret Synchronization

Check that ExternalSecrets are created and syncing:

```bash
# List all ExternalSecrets
kubectl get externalsecrets -A

# Check specific ExternalSecret status
kubectl describe externalsecret github-secret -n argo-events

# Verify the synced Kubernetes Secret exists
kubectl get secret github-secret -n argo-events -o yaml

# Check if secret contains the expected data
kubectl get secret github-secret -n argo-events \
  -o jsonpath='{.data.token}' | base64 -d
```

#### Step 6: Test Secret Rotation

Update a secret in Vault and verify it syncs:

```bash
# Update GitHub token in Vault
kubectl exec -n vault vault-0 -- vault kv put kv/argo/events/github \
  token="ghp_new_test_token_updated"

# Force immediate sync (or wait for refreshInterval)
kubectl annotate externalsecret github-secret \
  force-sync=$(date +%s) -n argo-events --overwrite

# Verify the secret was updated
kubectl get secret github-secret -n argo-events \
  -o jsonpath='{.data.token}' | base64 -d
```

### 3. Backward Compatibility Test

Verify the chart still works without ESO enabled:

```bash
# Create values file with ESO disabled
cat > /tmp/no-eso-values.yaml << 'EOF'
externalSecrets:
  enabled: false
  installOperator: false

s3:
  enabled: true
  hostname: "s3.amazonaws.com"
  bucket: "test-bucket"
  region: "us-west-2"
  accessKeyId: "AKIATEST"
  secretAccessKey: "secrettest"

events:
  enabled: true
  github:
    enabled: true
    secret:
      create: true
      name: "github-secret"
      tokenKey: "token"
      tokenValue: "ghp_test_token"

argo-cd:
  enabled: false
argo-workflows:
  enabled: false
EOF

# Install with ESO disabled
helm install argo-stack-no-eso ./helm/argo-stack \
  -f /tmp/no-eso-values.yaml \
  --namespace test-no-eso --create-namespace

# Verify traditional secrets are created
kubectl get secret github-secret -n argo-events
kubectl get secret s3-credentials -n wf-poc
```

### 4. Authentication Methods Testing

#### Kubernetes Auth

Already tested in Step 5 above. This is the recommended method for production.

#### AppRole Auth

```bash
# Enable AppRole in Vault
kubectl exec -n vault vault-0 -- vault auth enable approle

# Create policy
kubectl exec -n vault vault-0 -- sh -c 'vault policy write argo-stack-policy - <<EOF
path "kv/data/argo/*" {
  capabilities = ["read", "list"]
}
EOF'

# Create role
kubectl exec -n vault vault-0 -- vault write auth/approle/role/argo-stack \
  secret_id_ttl=24h \
  token_ttl=1h \
  policies=argo-stack-policy

# Get role ID
ROLE_ID=$(kubectl exec -n vault vault-0 -- vault read -field=role_id auth/approle/role/argo-stack/role-id)

# Generate secret ID
SECRET_ID=$(kubectl exec -n vault vault-0 -- vault write -field=secret_id -f auth/approle/role/argo-stack/secret-id)

# Create Kubernetes secret
kubectl create secret generic vault-approle-secret \
  --from-literal=secretId="$SECRET_ID" \
  -n argocd

# Update values to use AppRole
# Edit examples/vault/approle-auth-values.yaml with your ROLE_ID

# Install
helm install argo-stack-approle ./helm/argo-stack \
  -f examples/vault/approle-auth-values.yaml \
  --set externalSecrets.vault.auth.approle.roleId="$ROLE_ID" \
  --namespace argocd --create-namespace
```

### 5. Error Handling Tests

#### Missing Vault Secret

```bash
# Try to create an ExternalSecret for a non-existent path
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: test-missing
  namespace: argocd
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: SecretStore
    name: argo-stack-vault
  target:
    name: test-missing
  data:
    - secretKey: value
      remoteRef:
        key: nonexistent/path#key
EOF

# Check status - should show error
kubectl describe externalsecret test-missing -n argocd

# Expected: SecretSyncedError with message about missing key
```

#### Invalid Vault Address

```bash
# Install with invalid Vault address
helm install argo-stack-bad-vault ./helm/argo-stack \
  -f examples/vault/dev-values.yaml \
  --set externalSecrets.vault.address="http://invalid-vault:8200" \
  --namespace test-bad-vault --create-namespace

# Check SecretStore status
kubectl describe secretstore argo-stack-vault -n argocd

# Expected: Connection errors in status
```

## Cleanup

```bash
# Remove test installations
helm uninstall argo-stack -n argocd
helm uninstall argo-stack-no-eso -n test-no-eso
helm uninstall external-secrets -n external-secrets-system

# Delete namespaces
kubectl delete namespace argocd test-no-eso external-secrets-system

# Stop Vault dev server
make vault-cleanup

# Delete Kind cluster
kind delete cluster --name argo-test
```

## Continuous Integration

The chart includes CI configuration that automatically disables ESO for testing:

```bash
# Run CI tests (requires chart-testing CLI)
ct lint --config .ct.yaml --debug
ct install --config .ct.yaml --debug
```

## Troubleshooting Common Issues

### Issue: ExternalSecret stuck in "SecretSyncedError"

**Check:**
1. Vault connectivity: `kubectl run -it --rm debug --image=curlimages/curl -- curl -v http://vault.vault.svc.cluster.local:8200/v1/sys/health`
2. SecretStore status: `kubectl describe secretstore -n argocd`
3. ESO logs: `kubectl logs -l app.kubernetes.io/name=external-secrets -n external-secrets-system`
4. Secret path exists in Vault: `kubectl exec -n vault vault-0 -- vault kv get kv/argo/path/to/secret`

### Issue: Vault authentication fails

**Check:**
1. ServiceAccount exists: `kubectl get sa eso-vault-auth -n argocd`
2. Vault role configuration: `kubectl exec -n vault vault-0 -- vault read auth/kubernetes/role/argo-stack`
3. Test auth manually: Create a token and try logging in

### Issue: Dependencies missing during helm install

**Solution:** Either:
1. Install ESO separately first, or
2. Set `externalSecrets.installOperator=true` to install as part of the chart

## Performance Testing

Test secret sync performance with many secrets:

```bash
# Create 100 test secrets in Vault
for i in {1..100}; do
  kubectl exec -n vault vault-0 -- vault kv put kv/argo/test/secret-$i value="test-value-$i"
done

# Create ExternalSecrets for all
# Monitor sync time and ESO resource usage
kubectl top pods -n external-secrets-system
```

## Security Testing

1. **Test RBAC**: Verify ESO ServiceAccount has minimum required permissions
2. **Test Policy Enforcement**: Create Vault policies that deny access, verify errors
3. **Test Secret Rotation**: Verify pods pick up rotated secrets (may require pod restart)
4. **Test Audit Logging**: Check Vault audit logs for secret access

## Documentation Validation

Verify all documentation examples work:

```bash
# Test all commands in docs/secrets-with-vault.md
# Test all examples in examples/vault/README.md
# Verify Makefile targets work as documented
```

## Success Criteria

All tests should pass with:
- ✅ Templates validate correctly
- ✅ Secrets sync from Vault to Kubernetes
- ✅ Secret rotation works automatically
- ✅ Backward compatibility maintained (ESO disabled)
- ✅ Both Kubernetes and AppRole auth work
- ✅ Error handling is graceful
- ✅ Documentation examples are accurate
