[Home](index.md) > User Guides

# GitHub App Authentication for Argo CD

This guide explains how to configure Argo CD to use GitHub App authentication instead of Personal Access Tokens (PAT) or SSH keys. GitHub App authentication provides more secure, auditable, and least-privilege access control for your repositories.

---

## Overview

```mermaid
sequenceDiagram
    participant ArgoCD as Argo CD Repo Server
    participant K8S as Kubernetes Secret
    participant GHApp as GitHub App
    participant GH as GitHub Repos

    ArgoCD->>K8S: Read githubAppID, installationID, privateKey
    ArgoCD->>GHApp: Create JWT signed with privateKey
    ArgoCD->>GHApp: Request installation access token
    GHApp-->>ArgoCD: Return short-lived installation token
    ArgoCD->>GH: Clone repo using installation token
    GH-->>ArgoCD: Repo contents (manifests)
```

---

## Benefits of GitHub App Authentication

| Feature | PAT/SSH | GitHub App |
|---------|---------|------------|
| Token Lifetime | Long-lived (until revoked) | Short-lived (60 minutes) |
| Per-repo Control | Limited | Fine-grained via GitHub UI |
| Audit Trail | Limited | Full GitHub audit logs |
| Multi-tenant | Shared tokens | Separate installations |
| Rotation | Manual | Automatic |
| Permissions | User-scoped | App-scoped, least-privilege |

---

## Prerequisites

- Kubernetes cluster with Argo CD installed
- GitHub organization admin access (to create the GitHub App)
- Helm v3+
- (Optional) HashiCorp Vault with External Secrets Operator for secure key management

---

## Step 1: Create a GitHub App

1. Go to your GitHub organization: **Settings → Developer settings → GitHub Apps → New GitHub App**

2. Configure the App:
   - **GitHub App name**: e.g., `ArgoCD-YourOrg`
   - **Homepage URL**: Your Argo CD URL or organization page
   - **Webhook**: Uncheck "Active" (not needed for repo access)

3. Set **Repository permissions** (minimum required):
   - **Contents**: Read-only
   - **Metadata**: Read-only

4. (Optional) For deployment status notifications, also add:
   - **Checks**: Read & write
   - **Statuses**: Read & write
   - **Pull requests**: Read & write

5. Under **Where can this GitHub App be installed?**, select:
   - **Only on this account** (recommended for security)

6. Click **Create GitHub App**

7. Note the **App ID** from the App settings page

---

## Step 2: Generate and Download the Private Key

1. On the GitHub App settings page, scroll to **Private keys**

2. Click **Generate a private key**

3. A `.pem` file will be downloaded - **store this securely**

4. The private key should look like:
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA...
   ...
   -----END RSA PRIVATE KEY-----
   ```

---

## Step 3: Install the GitHub App on Repositories

1. Go to your GitHub App settings page

2. Click **Install App** in the left sidebar

3. Choose the organization where you want to install it

4. Select either:
   - **All repositories** (for org-wide access)
   - **Only select repositories** (recommended for least-privilege)

5. Click **Install**

6. Note the **Installation ID** from the URL: `https://github.com/organizations/{org}/settings/installations/{installation_id}`

---

## Step 4: Store Credentials in Kubernetes

### Option A: Using External Secrets (Recommended)

If you're using Vault with External Secrets Operator, store the credentials in Vault:

```bash
# Store credentials in Vault
vault kv put kv/argo/argocd/github-app \
  appId="123456" \
  installationId="12345678" \
  privateKey="$(cat /path/to/your-app.private-key.pem)"
```

Then enable External Secrets integration in your values:

```yaml
# values.yaml
githubApp:
  enabled: true
  appId: "123456"
  installationId: "12345678"
  privateKey:
    externalSecrets:
      enabled: true
      path: "argo/argocd/github-app"
  repoCreds:
    enabled: true
    url: "https://github.com/your-org"
```

### Option B: Manual Secret Creation

Create a Kubernetes secret directly:

```bash
kubectl create secret generic argocd-github-app-repo-creds \
  --namespace argocd \
  --from-literal=url="https://github.com/your-org" \
  --from-literal=type="git" \
  --from-literal=githubAppID="123456" \
  --from-literal=githubAppInstallationID="12345678" \
  --from-file=githubAppPrivateKey=/path/to/your-app.private-key.pem

# Add the required label for Argo CD to recognize it
kubectl label secret argocd-github-app-repo-creds \
  --namespace argocd \
  argocd.argoproj.io/secret-type=repo-creds
```

Then reference the existing secret in your values:

```yaml
# values.yaml
githubApp:
  enabled: true
  privateKey:
    existingSecretName: "argocd-github-app-repo-creds"
  repoCreds:
    enabled: false  # Already created manually
```

---

## Step 5: Configure Helm Values

Add the GitHub App configuration to your values file:

```yaml
# values.yaml
githubApp:
  # Enable GitHub App authentication
  enabled: true
  
  # GitHub App ID (from GitHub App settings)
  appId: "123456"
  
  # Installation ID (from installation URL)
  installationId: "12345678"
  
  # Private key configuration
  privateKey:
    # Use External Secrets (recommended)
    externalSecrets:
      enabled: true
      path: "argo/argocd/github-app"
  
  # Repo-creds for org-wide access
  repoCreds:
    enabled: true
    url: "https://github.com/your-org"
    secretName: "argocd-github-app-repo-creds"
```

---

## Step 6: Deploy or Upgrade

Deploy the updated configuration:

```bash
helm upgrade --install argo-stack helm/argo-stack \
  --namespace argocd \
  --values helm/argo-stack/values.yaml \
  --values my-values.yaml
```

Or if using Argo CD for GitOps:

```bash
argocd app sync argo-stack
```

---

## Step 7: Verify Configuration

1. Check that the secret was created:
   ```bash
   kubectl get secret argocd-github-app-repo-creds -n argocd
   kubectl describe secret argocd-github-app-repo-creds -n argocd
   ```

2. Verify Argo CD recognizes the repo-creds:
   ```bash
   argocd repocreds list
   ```
   
   You should see:
   ```
   URL                              TYPE  
   https://github.com/your-org      git
   ```

3. Test repository connection:
   ```bash
   argocd repo add https://github.com/your-org/your-repo --upsert
   ```

4. Check Argo CD repo-server logs for any authentication errors:
   ```bash
   kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=100
   ```

---

## Multi-Tenant Configuration

For multi-tenant environments, you can create separate GitHub Apps per tenant:

```yaml
# tenant-a-values.yaml
githubApp:
  enabled: true
  appId: "111111"
  installationId: "11111111"
  privateKey:
    externalSecrets:
      enabled: true
      path: "tenants/tenant-a/github-app"
  repoCreds:
    enabled: true
    url: "https://github.com/tenant-a-org"
    secretName: "tenant-a-github-app-creds"
```

Each tenant's GitHub App can be installed only on their specific repositories, providing complete isolation.

---

## Migration from PAT to GitHub App

1. **Create the GitHub App** following Steps 1-3

2. **Install on target repositories** 

3. **Add repo-creds** via Helm (Steps 4-5)

4. **Test with a single application**:
   - Create a new Application pointing to a GitHub App-enabled repo
   - Verify sync works correctly

5. **Migrate existing Applications**:
   - No changes needed to Application manifests
   - The repo-creds will automatically match based on URL prefix

6. **Remove PAT-based secrets** once all applications are migrated:
   ```bash
   kubectl delete secret github-pat-secret -n argocd
   ```

---

## Troubleshooting

### Error: "permission denied" or "installation token invalid"

- Verify the GitHub App is installed on the repository
- Check the Installation ID is correct
- Verify the private key format (must include BEGIN/END markers)

### Error: "could not refresh installation token"

- The private key may be corrupted or incorrectly formatted
- Regenerate the private key in GitHub App settings

### Error: "repository not found"

- Verify the repository URL matches the repo-creds URL prefix
- Check the GitHub App has "Contents: Read" permission

### Checking Secret Contents

```bash
# View the secret (base64 decoded)
kubectl get secret argocd-github-app-repo-creds -n argocd -o jsonpath='{.data.githubAppPrivateKey}' | base64 -d | head -5
```

### Viewing Argo CD Logs

```bash
# Repo server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server -f

# Application controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller -f
```

---

## Security Considerations

1. **Private Key Storage**: Always use External Secrets or a secrets manager to store the private key - never commit it to Git

2. **Least Privilege**: Only grant the minimum required permissions (Contents: Read, Metadata: Read)

3. **Repository Selection**: Use "Only select repositories" when installing the App

4. **Key Rotation**: Periodically rotate the private key by generating a new one in GitHub App settings and updating the Kubernetes secret

5. **Audit Logs**: Review GitHub App audit logs regularly for unexpected access patterns

---

## Reference

- [Argo CD Private Repositories Documentation](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/)
- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps)
- [External Secrets Operator](https://external-secrets.io/)
