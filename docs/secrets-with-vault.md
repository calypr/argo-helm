# 🔐 Maintaining Secrets with HashiCorp Vault

This guide describes how to manage all sensitive configuration for the **Argo Stack** using **HashiCorp Vault** as the single source of truth, synchronized into Kubernetes Secrets by the **External Secrets Operator (ESO)**.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Why Vault + ESO?](#-why-vault--eso)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Vault Path Conventions](#-vault-path-conventions)
- [Authentication Methods](#-authentication-methods)
- [Configuration Reference](#-configuration-reference)
- [Secret Rotation](#-secret-rotation)
- [Security Best Practices](#-security-best-practices)
- [Troubleshooting](#-troubleshooting)
- [Alternatives](#-alternatives)

---

## 🌟 Overview

The Argo Stack supports integration with **HashiCorp Vault** via the **External Secrets Operator** to:

- **Eliminate plaintext secrets** from Git repositories and Helm values
- **Centralize secret management** in Vault with audit logging
- **Enable automatic rotation** without Helm upgrades or pod restarts
- **Support multi-tenancy** with Vault policies and namespaced access
- **Provide self-service** for application teams to manage their own secrets

### Architecture

```mermaid
graph LR
    V[HashiCorp Vault<br/>KV v2 Engine] -->|Auth & Fetch| ESO[External Secrets<br/>Operator]
    ESO -->|Sync| S1[Secret: github-secret]
    ESO -->|Sync| S2[Secret: s3-credentials]
    ESO -->|Sync| S3[Secret: argocd-secret]
    S1 --> AE[Argo Events]
    S2 --> AW[Argo Workflows]
    S3 --> AC[Argo CD]
```

---

## 💡 Why Vault + ESO?

| Feature | Traditional Secrets | Vault + ESO |
|---------|---------------------|-------------|
| **Secret Storage** | Git (encrypted) or values.yaml | Vault KV engine |
| **Rotation** | Helm upgrade + redeploy | Update in Vault, auto-sync |
| **Audit Trail** | Git history | Vault audit log |
| **Access Control** | Kubernetes RBAC | Vault policies + K8s RBAC |
| **Multi-tenancy** | Manual per-namespace | Vault namespaces/policies |
| **Secret Generation** | Manual or scripts | Vault dynamic secrets |

---

## 🛠 Prerequisites

1. **HashiCorp Vault** instance (v1.11+ recommended)
   - Accessible from your Kubernetes cluster
   - KV v2 secrets engine enabled
   - Authentication method configured (Kubernetes auth recommended)

2. **External Secrets Operator**
   - Can be installed as part of this chart or cluster-wide
   - Version >=0.9.0

3. **Kubernetes cluster** (v1.20+)
   - Service accounts for ESO authentication
   - Network access to Vault

---

## 🚀 Quick Start

### Step 1: Start Vault Dev Server (Local Testing)

For local development, use the included Makefile targets:

```bash
# Start Vault dev server in Docker
make vault-dev

# Seed with test data
make vault-seed

# Check status
make vault-status
```

This creates a Vault dev server at `http://127.0.0.1:8200` with root token `root`.

> **⚠️ Warning:** Dev mode is **NOT** for production. Data is stored in memory and lost on restart.

### Step 2: Configure Helm Values

Create a `vault-values.yaml`:

```yaml
externalSecrets:
  enabled: true
  installOperator: true  # Set to false if ESO already installed
  
  vault:
    enabled: true
    address: "http://vault.vault.svc.cluster.local:8200"  # Or http://host.docker.internal:8200 for local Kind
    
    auth:
      method: "kubernetes"
      mount: "kubernetes"
      role: "argo-stack"
      serviceAccountName: "eso-vault-auth"
    
    kv:
      engineVersion: 2
      defaultPathPrefix: "kv/argo"
    
    scope: "namespaced"  # or "cluster" for ClusterSecretStore
    namespace: "argocd"

  secrets:
    argocd:
      adminPasswordPath: "argocd/admin#password"
      serverSecretKeyPath: "argocd/server#secretKey"
    
    workflows:
      artifactAccessKeyPath: "workflows/artifacts#accessKey"
      artifactSecretKeyPath: "workflows/artifacts#secretKey"
    
    github:
      tokenPath: "events/github#token"
```

### Step 3: Install the Chart

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd --create-namespace \
  -f vault-values.yaml
```

### Step 4: Verify Secret Synchronization

```bash
# Check ExternalSecret status
kubectl get externalsecrets -n argocd
kubectl get externalsecrets -n argo-events

# Verify synced secrets exist
kubectl get secret github-secret -n argo-events
kubectl get secret s3-credentials -n wf-poc
kubectl get secret argocd-secret -n argocd

# Check ESO logs for issues
kubectl logs -n argocd -l app.kubernetes.io/name=external-secrets
```

---

## 🗂 Vault Path Conventions

The chart follows a consistent path structure in Vault:

```
kv/argo/                              # Root prefix (configurable)
├── argocd/
│   ├── admin                        # password, bcryptHash
│   ├── oidc                         # clientSecret
│   └── server                       # secretKey
├── workflows/
│   ├── artifacts                    # accessKey, secretKey
│   └── oidc                         # clientSecret
├── authz/                           # clientSecret
├── events/
│   └── github                       # token
└── apps/
    ├── nextflow-hello/
    │   └── s3                       # accessKey, secretKey
    └── nextflow-hello-2/
        └── s3                       # accessKey, secretKey
```

### Creating Secrets in Vault

Use the Vault CLI or UI to create secrets:

```bash
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=root

# Argo CD admin password
vault kv put kv/argo/argocd/admin \
  password="MySecurePassword123!" \
  bcryptHash='$2a$10$...'  # bcrypt hash of password

# Argo CD server secret key (for session signing)
vault kv put kv/argo/argocd/server \
  secretKey="$(openssl rand -hex 32)"

# S3 credentials for workflow artifacts
vault kv put kv/argo/workflows/artifacts \
  accessKey="AKIAIOSFODNN7EXAMPLE" \
  secretKey="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# GitHub webhook token
vault kv put kv/argo/events/github \
  token="ghp_xxxxxxxxxxxxxxxxxxxx"

# Per-app S3 credentials
vault kv put kv/argo/apps/nextflow-hello/s3 \
  accessKey="app1-access-key" \
  secretKey="app1-secret-key"
```

### Viewing Secrets

```bash
# List all secrets under a path
vault kv list kv/argo

# Get a specific secret (JSON output)
vault kv get -format=json kv/argo/argocd/admin

# Get a specific field
vault kv get -field=password kv/argo/argocd/admin
```

---

## 🔑 Authentication Methods

ESO supports multiple authentication methods to Vault. Choose based on your security requirements and infrastructure.

### Option 1: Kubernetes Auth (Recommended)

**Best for:** Production Kubernetes clusters with Vault Kubernetes auth enabled.

**Advantages:**
- No credential management required (uses ServiceAccount tokens)
- Automatic token rotation by Kubernetes
- Scoped by namespace and ServiceAccount

**Setup:**

1. Enable Kubernetes auth in Vault:

```bash
vault auth enable kubernetes

# Configure Vault to talk to Kubernetes
vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc:443"
```

2. Create a Vault role for ESO:

```bash
vault write auth/kubernetes/role/argo-stack \
  bound_service_account_names=eso-vault-auth \
  bound_service_account_namespaces=argocd \
  policies=argo-stack-policy \
  ttl=1h
```

3. Create a Vault policy:

```bash
vault policy write argo-stack-policy - <<EOF
# Read access to all argo secrets
path "kv/data/argo/*" {
  capabilities = ["read", "list"]
}

# List capabilities for secret discovery
path "kv/metadata/argo/*" {
  capabilities = ["list", "read"]
}
EOF
```

4. Configure in values.yaml:

```yaml
externalSecrets:
  vault:
    auth:
      method: "kubernetes"
      mount: "kubernetes"
      role: "argo-stack"
      serviceAccountName: "eso-vault-auth"
```

### Option 2: AppRole Auth

**Best for:** External systems, CI/CD pipelines, or when Kubernetes auth is unavailable.

**Setup:**

1. Enable AppRole auth:

```bash
vault auth enable approle
```

2. Create role and policy:

```bash
vault write auth/approle/role/argo-stack \
  secret_id_ttl=24h \
  token_ttl=1h \
  token_max_ttl=24h \
  policies=argo-stack-policy

# Get role ID
vault read auth/approle/role/argo-stack/role-id

# Generate secret ID
vault write -f auth/approle/role/argo-stack/secret-id
```

3. Create Kubernetes secret with secret ID:

```bash
kubectl create secret generic vault-approle-secret \
  --from-literal=secretId='YOUR_SECRET_ID' \
  -n argocd
```

4. Configure in values.yaml:

```yaml
externalSecrets:
  vault:
    auth:
      method: "approle"
      mount: "approle"
      approle:
        roleId: "YOUR_ROLE_ID"
        secretRef:
          name: "vault-approle-secret"
          key: "secretId"
```

### Option 3: JWT Auth

**Best for:** Multi-cloud environments or OIDC-enabled clusters.

Similar to Kubernetes auth but uses OIDC/JWT tokens. See [Vault JWT auth docs](https://developer.hashicorp.com/vault/docs/auth/jwt).

---

## ⚙️ Configuration Reference

### Full values.yaml Example

```yaml
externalSecrets:
  enabled: true
  installOperator: true
  
  external-secrets:
    installCRDs: true
    namespaceOverride: ""
  
  vault:
    enabled: true
    address: "https://vault.example.com"
    
    # Optional: CA bundle for TLS
    caBundleSecretName: "vault-ca-bundle"
    caBundleSecretKey: "ca.crt"
    
    auth:
      method: "kubernetes"
      mount: "kubernetes"
      role: "argo-stack"
      serviceAccountName: "eso-vault-auth"
    
    kv:
      engineVersion: 2
      defaultPathPrefix: "kv/argo"
    
    scope: "namespaced"  # or "cluster"
    namespace: "argocd"
  
  secrets:
    argocd:
      adminPasswordPath: "argocd/admin#password"
      adminPasswordBcryptPath: "argocd/admin#bcryptHash"
      ssoClientSecretPath: "argocd/oidc#clientSecret"
      serverSecretKeyPath: "argocd/server#secretKey"
    
    workflows:
      artifactAccessKeyPath: "workflows/artifacts#accessKey"
      artifactSecretKeyPath: "workflows/artifacts#secretKey"
      ssoClientSecretPath: "workflows/oidc#clientSecret"
    
    authzAdapter:
      oidcClientSecretPath: "authz#clientSecret"
    
    github:
      tokenPath: "events/github#token"
    
    perAppS3:
      nextflow-hello:
        accessKeyPath: "apps/nextflow-hello/s3#accessKey"
        secretKeyPath: "apps/nextflow-hello/s3#secretKey"
```

### Path Format

Paths use the format: `<vault-path>#<key-name>`

- `<vault-path>`: Relative to `vault.kv.defaultPathPrefix`
- `#`: Separator (replaced with `/` internally)
- `<key-name>`: Field name in the KV secret

Example: `argocd/admin#password` → reads field `password` from `kv/argo/argocd/admin`

---

## 🔄 Secret Rotation

One of the key benefits of Vault + ESO is **transparent secret rotation**.

### Rotation Workflow

1. **Update secret in Vault**:

```bash
vault kv put kv/argo/argocd/admin password="NewPassword456!"
```

2. **ESO automatically detects change** (based on `refreshInterval`, default 1h)

3. **Kubernetes Secret is updated** automatically

4. **Pods consume new secret**:
   - Most apps pick up changes on next read (e.g., from mounted volume)
   - Some may require restart (use `Reloader` or manual restart)

### Force Immediate Sync

```bash
# Trigger immediate refresh by annotating the ExternalSecret
kubectl annotate externalsecret github-secret \
  force-sync=$(date +%s) -n argo-events --overwrite
```

### Automatic Pod Restart on Secret Change

Install [Reloader](https://github.com/stakater/Reloader) to automatically restart pods when secrets change:

```bash
helm repo add stakater https://stakater.github.io/stakater-charts
helm install reloader stakater/reloader
```

Then annotate Deployments:

```yaml
metadata:
  annotations:
    secret.reloader.stakater.com/reload: "github-secret"
```

---

## 🔒 Security Best Practices

### Least Privilege Policies

Create separate Vault policies per component:

```bash
# Policy for Argo CD secrets only
vault policy write argo-cd-policy - <<EOF
path "kv/data/argo/argocd/*" {
  capabilities = ["read"]
}
EOF

# Policy for Argo Workflows secrets only
vault policy write argo-workflows-policy - <<EOF
path "kv/data/argo/workflows/*" {
  capabilities = ["read"]
}
path "kv/data/argo/apps/*" {
  capabilities = ["read"]
}
EOF
```

### Use Namespaced SecretStores

Prefer `SecretStore` (namespace-scoped) over `ClusterSecretStore`:

```yaml
externalSecrets:
  vault:
    scope: "namespaced"  # Default
```

This limits blast radius if a SecretStore is compromised.

### TLS for Vault Communication

Always use HTTPS in production:

```yaml
externalSecrets:
  vault:
    address: "https://vault.example.com"
    caBundleSecretName: "vault-ca-bundle"
```

Create the CA bundle secret:

```bash
kubectl create secret generic vault-ca-bundle \
  --from-file=ca.crt=/path/to/vault-ca.pem \
  -n argocd
```

### Audit Logging

Enable Vault audit logging to track all secret access:

```bash
vault audit enable file file_path=/vault/logs/audit.log
```

### Secret Versioning

KV v2 maintains secret versions. Roll back if needed:

```bash
# View secret history
vault kv metadata get kv/argo/argocd/admin

# Restore previous version
vault kv rollback -version=2 kv/argo/argocd/admin
```

### Avoid Storing Secrets in Git

**Never** commit actual secret values to Git. Use placeholders and override at deployment:

```yaml
# values.yaml (committed to Git)
externalSecrets:
  enabled: true
  vault:
    address: "VAULT_ADDR_PLACEHOLDER"
```

```bash
# Runtime override
helm upgrade --install argo-stack ./helm/argo-stack \
  --set externalSecrets.vault.address="https://vault.prod.example.com"
```

---

## 🐛 Troubleshooting

### ExternalSecret Not Syncing

**Symptoms:** `kubectl get externalsecret` shows `SecretSyncedError`

**Check:**

```bash
kubectl describe externalsecret <name> -n <namespace>
```

**Common causes:**

1. **Vault path doesn't exist**
   - Verify path in Vault: `vault kv get kv/argo/path/to/secret`

2. **Authentication failure**
   - Check SecretStore: `kubectl describe secretstore -n argocd`
   - Verify Vault role and policy

3. **Network connectivity**
   - Test from pod: `kubectl run -it --rm debug --image=curlimages/curl -- curl -v $VAULT_ADDR/v1/sys/health`

### Secrets Not Updating After Rotation

**Symptoms:** Updated Vault secret, but K8s Secret unchanged

**Check:**

1. **Wait for refresh interval** (default 1h)
2. **Force sync** (see [Secret Rotation](#-secret-rotation))
3. **Check ESO logs**: `kubectl logs -l app.kubernetes.io/name=external-secrets -n <eso-namespace>`

### Vault Authentication Errors

**Kubernetes Auth:**

```bash
# Verify ServiceAccount exists
kubectl get sa eso-vault-auth -n argocd

# Check Vault role binding
vault read auth/kubernetes/role/argo-stack
```

**AppRole:**

```bash
# Verify secret exists
kubectl get secret vault-approle-secret -n argocd

# Test AppRole login manually
vault write auth/approle/login role_id=$ROLE_ID secret_id=$SECRET_ID
```

### Missing Keys in Synced Secret

**Symptoms:** Secret created but missing expected keys

**Check:**

1. **Verify key name in Vault**: `vault kv get kv/argo/path#key`
2. **Check path format**: Should be `path#key`, not `path/key`
3. **ESO version**: Ensure >=0.9.0

---

## 🔀 Alternatives

While this guide focuses on Vault + ESO, other options exist:

### Vault CSI Driver

**Pros:**
- Secrets mounted directly as files (no K8s Secret objects)
- Native Vault integration

**Cons:**
- CSI driver required on every node
- Harder to use with existing apps expecting env vars

**See:** [Vault CSI Provider](https://developer.hashicorp.com/vault/docs/platform/k8s/csi)

### Vault Agent Injector

**Pros:**
- Sidecar-based secret injection
- Template rendering

**Cons:**
- Adds sidecar to every pod
- More complex setup

**See:** [Vault Agent Injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)

### Sealed Secrets

**Pros:**
- Encrypted secrets in Git
- No external dependency

**Cons:**
- Manual rotation workflow
- No centralized audit log

**See:** [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)

---

## 📚 Additional Resources

- [External Secrets Operator Docs](https://external-secrets.io/)
- [Vault KV Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/kv)
- [Vault Kubernetes Auth](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [ESO Security Best Practices](https://external-secrets.io/latest/guides/security-best-practices/)
- [Argo CD Secret Management](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/)
- [Argo Workflows Secrets](https://argo-workflows.readthedocs.io/en/latest/walk-through/secrets/)

---

## 🆘 Need Help?

- File an issue: [GitHub Issues](https://github.com/calypr/argo-helm/issues)
- Check existing docs: [/docs](/docs)
- Consult Vault docs: [HashiCorp Learn](https://learn.hashicorp.com/vault)
