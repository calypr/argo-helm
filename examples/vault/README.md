# Vault Integration Examples

This directory contains example configuration files for integrating the Argo Stack with HashiCorp Vault via External Secrets Operator.

## 📁 Files

- **`kubernetes-auth-values.yaml`** - Production-ready configuration using Kubernetes authentication (recommended)
- **`approle-auth-values.yaml`** - Configuration using AppRole authentication (for CI/CD or non-K8s scenarios)
- **`dev-values.yaml`** - Local development configuration with Vault dev server

## 🚀 Quick Start

### Local Development

1. Create a Kubernetes cluster (if you don't have one):
   ```bash
   kind create cluster
   ```

2. Install Vault dev server in the cluster and seed with test data:
   ```bash
   make vault-dev
   make vault-seed
   ```

3. (Optional) Install MinIO for S3 artifact storage:
   ```bash
   make minio-dev
   make minio-create-bucket
   ```

4. Install the chart with Vault integration:
   ```bash
   helm install argo-stack ./helm/argo-stack \
     -f examples/vault/dev-values.yaml \
     --namespace argocd --create-namespace
   ```

5. Verify secrets are synced:
   ```bash
   kubectl get externalsecrets -A
   kubectl get secrets -n argo-events github-secret
   kubectl get secrets -n wf-poc s3-credentials
   ```

### Production Setup with Kubernetes Auth

1. Enable Kubernetes auth in Vault:
   ```bash
   vault auth enable kubernetes
   
   vault write auth/kubernetes/config \
     kubernetes_host="https://kubernetes.default.svc:443"
   ```

2. Create Vault policy:
   ```bash
   vault policy write argo-stack-policy - <<EOF
   path "kv/data/argo/*" {
     capabilities = ["read", "list"]
   }
   path "kv/metadata/argo/*" {
     capabilities = ["list", "read"]
   }
   EOF
   ```

3. Create Vault role:
   ```bash
   vault write auth/kubernetes/role/argo-stack \
     bound_service_account_names=eso-vault-auth \
     bound_service_account_namespaces=argocd \
     policies=argo-stack-policy \
     ttl=1h
   ```

4. Seed Vault with secrets:
   ```bash
   # Argo CD admin password
   vault kv put kv/argo/argocd/admin \
     password="SecurePassword123!" \
     bcryptHash='$2a$10$...'
   
   # Argo CD server secret
   vault kv put kv/argo/argocd/server \
     secretKey="$(openssl rand -hex 32)"
   
   # S3 credentials
   vault kv put kv/argo/workflows/artifacts \
     accessKey="YOUR_ACCESS_KEY" \
     secretKey="YOUR_SECRET_KEY"
   
   # GitHub token
   vault kv put kv/argo/events/github \
     token="ghp_your_token_here"
   ```

5. Update `kubernetes-auth-values.yaml` with your Vault address:
   ```yaml
   externalSecrets:
     vault:
       address: "https://vault.your-domain.com"
   ```

6. Install the chart:
   ```bash
   helm install argo-stack ./helm/argo-stack \
     -f examples/vault/kubernetes-auth-values.yaml \
     --namespace argocd --create-namespace
   ```

### AppRole Authentication

1. Enable AppRole in Vault:
   ```bash
   vault auth enable approle
   ```

2. Create role:
   ```bash
   vault write auth/approle/role/argo-stack \
     secret_id_ttl=24h \
     token_ttl=1h \
     token_max_ttl=24h \
     policies=argo-stack-policy
   ```

3. Get role ID and secret ID:
   ```bash
   ROLE_ID=$(vault read -field=role_id auth/approle/role/argo-stack/role-id)
   SECRET_ID=$(vault write -field=secret_id -f auth/approle/role/argo-stack/secret-id)
   ```

4. Create Kubernetes secret:
   ```bash
   kubectl create secret generic vault-approle-secret \
     --from-literal=secretId="$SECRET_ID" \
     -n argocd
   ```

5. Update `approle-auth-values.yaml` with your role ID and Vault address

6. Install the chart:
   ```bash
   helm install argo-stack ./helm/argo-stack \
     -f examples/vault/approle-auth-values.yaml \
     --namespace argocd --create-namespace
   ```

## 🔍 Verification

After installation, verify everything is working:

```bash
# Check SecretStore status
kubectl get secretstore -n argocd
kubectl describe secretstore argo-stack-vault -n argocd

# Check ExternalSecrets
kubectl get externalsecrets -A
kubectl describe externalsecret github-secret -n argo-events

# Verify synced secrets exist
kubectl get secret github-secret -n argo-events
kubectl get secret s3-credentials -n wf-poc
kubectl get secret argocd-secret -n argocd
kubectl get secret argocd-initial-admin-secret -n argocd

# Check ESO logs
kubectl logs -l app.kubernetes.io/name=external-secrets -n argocd
```

## 📚 Documentation

For detailed information, see:
- [Secrets with Vault Guide](../../docs/secrets-with-vault.md)
- [External Secrets Operator Docs](https://external-secrets.io/)
- [Vault Kubernetes Auth](https://developer.hashicorp.com/vault/docs/auth/kubernetes)

## 🐛 Troubleshooting

### Secrets not syncing

1. Check ExternalSecret status:
   ```bash
   kubectl describe externalsecret <name> -n <namespace>
   ```

2. Check ESO logs:
   ```bash
   kubectl logs -l app.kubernetes.io/name=external-secrets -n argocd
   ```

3. Verify Vault connectivity:
   ```bash
   kubectl run -it --rm debug --image=curlimages/curl -- \
     curl -v http://vault.vault.svc.cluster.local:8200/v1/sys/health
   ```

### Authentication errors

1. Verify ServiceAccount exists:
   ```bash
   kubectl get sa eso-vault-auth -n argocd
   ```

2. Check Vault role configuration:
   ```bash
   vault read auth/kubernetes/role/argo-stack
   ```

3. Test authentication manually:
   ```bash
   # Get SA token
   TOKEN=$(kubectl create token eso-vault-auth -n argocd)
   
   # Try logging in
   vault write auth/kubernetes/login role=argo-stack jwt=$TOKEN
   ```

## 🔐 Security Notes

- **Dev mode**: Vault dev server stores data in memory. DO NOT use in production.
- **TLS**: Always use HTTPS for Vault in production.
- **Policies**: Follow least-privilege principle. Create separate policies per component.
- **Rotation**: Use `refreshInterval` in ExternalSecrets to control sync frequency.
- **Secrets in Git**: Never commit actual secret values to Git.
