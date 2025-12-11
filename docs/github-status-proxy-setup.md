# GitHub Status Proxy Setup Guide

This guide walks you through setting up the GitHub Status Proxy for self-service GitHub App integration with Argo CD.

## Overview

The GitHub Status Proxy enables Argo CD to automatically post commit statuses to GitHub repositories without requiring manual configuration of installation IDs. Users simply install a shared GitHub App on their repositories, and Argo CD begins posting statuses automatically.

## Prerequisites

1. A GitHub App with the following permissions:
   - **Repository permissions:**
     - Commit statuses: Read & Write
   - **Subscribe to events:** (optional, for future webhook integration)
     - Push
     - Pull Request

2. The GitHub App's private key (in PEM format)

3. The GitHub App's App ID (numeric ID from GitHub)

## Step 1: Create a GitHub App

If you don't already have a GitHub App, create one:

1. Go to GitHub Settings → Developer settings → GitHub Apps → New GitHub App
2. Fill in the basic information:
   - **GitHub App name**: `Argo CD Status Reporter` (or similar)
   - **Homepage URL**: Your Argo CD URL
   - **Webhook**: Disable for now (not required for status posting)
3. Set permissions:
   - Repository permissions → Commit statuses: **Read & write**
4. Click "Create GitHub App"
5. Note the **App ID** (you'll need this later)
6. Scroll down and click "Generate a private key"
7. Save the downloaded `.pem` file securely

## Step 2: Configure Secret Management

The GitHub Status Proxy needs access to your GitHub App's private key. There are two options:

**Important:** The proxy Deployment uses Helm post-install/post-upgrade hooks with weight 5, ensuring it deploys AFTER ExternalSecrets (weight 1) are created. This prevents startup failures when secrets are managed by Vault.

### Option A: Using Vault/External Secrets (Recommended for Production)

If you're using the External Secrets Operator with Vault, configure the GitHub App settings:

```yaml
githubApp:
  enabled: true
  appId: "123456"  # Your GitHub App ID
  installationId: "789012"  # Installation ID for your organization
  privateKeySecretName: github-app-private-key
  privateKeyVaultPath: "kv/argo/argocd/github-app"  # Path in Vault
```

This creates an ExternalSecret that syncs the private key from Vault to a Kubernetes secret with key `privateKey`.

The GitHub Status Proxy automatically reuses this same secret:

```yaml
githubStatusProxy:
  enabled: true
  githubAppId: "123456"  # Same App ID as above
  privateKeySecret:
    name: github-app-private-key  # Same secret name
    key: privateKey  # Key created by ExternalSecret
```

### Option B: Manual Secret Creation (Development/Testing)

For development or if not using Vault, create the secret manually:

```bash
kubectl create secret generic github-app-private-key \
  --from-file=privateKey=/path/to/your/private-key.pem \
  -n argocd
```

Then configure:

```yaml
githubStatusProxy:
  enabled: true
  githubAppId: "123456"
  privateKeySecret:
    name: github-app-private-key
    key: privateKey
```

## Step 3: Enable GitHub Status Proxy in Helm Values

Complete example with Vault integration:

```yaml
# GitHub App configuration (creates ExternalSecret)
githubApp:
  enabled: true
  appId: "123456"
  installationId: "789012"
  privateKeySecretName: github-app-private-key
  privateKeyVaultPath: "kv/argo/argocd/github-app"

# GitHub Status Proxy (reuses the ExternalSecret above)
githubStatusProxy:
  enabled: true
  image: github-status-proxy:latest  # For local development with kind
  # image: ghcr.io/calypr/github-status-proxy:v1.0.0  # For production
  imagePullPolicy: IfNotPresent  # Use Always for production
  githubAppId: "123456"  # Same App ID
  replicas: 2
  privateKeySecret:
    name: github-app-private-key  # Same secret name
    key: privateKey  # Key name in the secret
  logLevel: "INFO"  # or "DEBUG" for detailed logging
```

**Image Configuration:**
- **Development (local kind cluster):** Use `image: github-status-proxy:latest` with `imagePullPolicy: IfNotPresent` to use locally loaded images
- **Production:** Use a specific version tag like `ghcr.io/calypr/github-status-proxy:v1.0.0` with `imagePullPolicy: Always` to ensure latest updates

## Step 4: Deploy or Update the Helm Chart

Deploy the chart with the GitHub Status Proxy enabled:

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd --create-namespace \
  --set githubStatusProxy.enabled=true \
  --set githubStatusProxy.githubAppId=123456 \
  --wait
```

## Step 5: Verify Deployment

Check that the GitHub Status Proxy is running:

```bash
# Check pods
kubectl get pods -n argocd -l app=github-status-proxy

# Check service
kubectl get svc -n argocd github-status-proxy

# Check logs
kubectl logs -n argocd -l app=github-status-proxy
```

Expected output should show the proxy starting on port 8080.

## Step 6: Install GitHub App on Repositories

For each repository you want to integrate with Argo CD:

1. Go to the repository on GitHub
2. Navigate to Settings → GitHub Apps
3. Find your GitHub App and click "Install"
4. Select the repository and confirm

## Step 7: Create Argo CD Applications

Create Argo CD Applications that point to your GitHub repositories:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/myrepo
    targetRevision: main
    path: kubernetes
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Step 8: Verify Commit Statuses

When the application syncs, you should see commit statuses appear on GitHub:

1. Go to your repository on GitHub
2. Navigate to the commit that was synced
3. Look for a status check named `argocd/my-app`
4. The status should be:
   - ✓ Green check for successful sync
   - ✗ Red X for failed sync
   - ⊙ Yellow circle for sync in progress

## Configuration Reference

### Helm Values

```yaml
githubStatusProxy:
  # Enable or disable the GitHub Status Proxy
  enabled: false
  
  # Docker image for the proxy service
  image: ghcr.io/calypr/github-status-proxy:latest
  
  # Number of replicas for high availability
  replicas: 2
  
  # Namespace where the proxy will be deployed
  namespace: argocd
  
  # GitHub App ID (numeric ID from GitHub App settings)
  githubAppId: ""
  
  # Secret containing the GitHub App private key
  privateKeySecret:
    name: github-app-private-key
    key: private-key.pem
```

### Notification Templates

The following notification templates are automatically configured:

- `app-sync-succeeded`: Posted when an application syncs successfully
- `app-sync-failed`: Posted when an application sync fails
- `app-sync-running`: Posted when an application sync starts
- `app-deployed`: Posted when an application is deployed and healthy

### Triggers

The following triggers are enabled by default:

- `on-sync-succeeded`: Triggers when sync phase is 'Succeeded'
- `on-sync-failed`: Triggers when sync phase is 'Error' or 'Failed'
- `on-sync-running`: Triggers when sync phase is 'Running'
- `on-deployed`: Triggers when sync succeeds and app is healthy

## Troubleshooting

### Status not appearing on GitHub

1. **Check proxy logs:**
   ```bash
   kubectl logs -n argocd -l app=github-status-proxy
   ```

2. **Verify GitHub App is installed on the repository:**
   - Go to repository Settings → GitHub Apps
   - Confirm your app is installed

3. **Verify GitHub App has correct permissions:**
   - Commit statuses: Read & write

4. **Check notification logs:**
   ```bash
   kubectl logs -n argocd -l app.kubernetes.io/name=argocd-notifications-controller
   ```

### Authentication errors

If you see authentication errors in the logs:

1. **Verify the private key secret:**
   ```bash
   kubectl get secret github-app-private-key -n argocd
   kubectl get secret github-app-private-key -n argocd -o yaml
   ```

2. **Check the App ID is correct:**
   ```bash
   kubectl get deployment github-status-proxy -n argocd -o yaml | grep GITHUB_APP_ID
   ```

3. **Regenerate the private key** from GitHub if necessary

### Installation not found errors

If you see "GitHub App not installed on repository" errors:

1. Verify the App is installed on the specific repository (not just the organization)
2. Check the repository URL in the Application spec matches exactly
3. Try reinstalling the GitHub App on the repository

### Network connectivity issues

If the proxy can't reach GitHub:

1. **Check network policies:**
   ```bash
   kubectl get networkpolicies -n argocd
   ```

2. **Test connectivity from the pod:**
   ```bash
   kubectl exec -it -n argocd deployment/github-status-proxy -- wget -O- https://api.github.com
   ```

## Multi-Tenant Usage

The GitHub Status Proxy is designed for multi-tenant environments:

1. **One GitHub App** can be shared across multiple tenants
2. **Users install the App** on their own repositories
3. **No operator intervention** required for new repositories
4. **Automatic installation resolution** based on repository URL

Example multi-tenant setup:

```yaml
# Tenant A's application
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tenant-a-app
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/tenant-a/app
    # ...

# Tenant B's application
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tenant-b-app
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/tenant-b/app
    # ...
```

Both applications will receive commit statuses automatically once the GitHub App is installed on their respective repositories.

## Security Considerations

1. **Private key storage**: The GitHub App private key is stored as a Kubernetes secret and mounted read-only into the proxy pods

2. **In-cluster only**: The proxy service is a ClusterIP and only accessible from within the cluster

3. **Short-lived tokens**: Installation tokens are requested per-status-post and expire after 1 hour

4. **No credential storage**: The proxy does not cache or store GitHub credentials beyond the mounted private key

5. **Minimal permissions**: The GitHub App should only have "Commit statuses: Read & write" permissions

## Advanced Configuration

### Custom Context Names

By default, statuses are posted with context `argocd/<app-name>`. To customize:

Edit the notification template in `helm/argo-stack/templates/argocd/notifications-cm.yaml`:

```yaml
template.app-sync-succeeded: |
  webhook:
    github-status-proxy:
      method: POST
      path: /status
      body: |
        {
          "context": "my-custom-context/{{`{{.app.metadata.name}}`}}",
          # ...
        }
```

### Disabling Specific Triggers

To disable certain triggers, remove them from the `defaultTriggers` list:

```yaml
# Only send on-sync-succeeded and on-sync-failed
defaultTriggers: |
  - on-sync-succeeded
  - on-sync-failed
```

### Per-Application Notification Configuration

To override notifications for specific applications, add annotations:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  annotations:
    notifications.argoproj.io/subscribe.on-sync-succeeded.github-status-proxy: ""
    notifications.argoproj.io/subscribe.on-sync-failed.github-status-proxy: ""
```

## Related Documentation

- [Architecture Decision Record (ADR)](./adr/0001-github-status-proxy-for-multi-tenant-github-apps.md)
- [GitHub Status Proxy README](../github-status-proxy/README.md)
- [Argo CD Notifications](https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/)
- [GitHub Apps Documentation](https://docs.github.com/en/apps)

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review proxy logs: `kubectl logs -n argocd -l app=github-status-proxy`
3. Review notification logs: `kubectl logs -n argocd -l app.kubernetes.io/name=argocd-notifications-controller`
4. Open an issue in the repository with logs and configuration details
