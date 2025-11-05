# 📚 Argo Stack User Guide

This guide provides step-by-step instructions for configuring and deploying the Argo Stack with multi-application and multi-repository support.

---

## 📑 Table of Contents

- [GitHub Personal Access Token Setup](#github-personal-access-token-setup)
- [Multi-Application Configuration](#multi-application-configuration)
- [Multi-Repository EventSource Configuration](#multi-repository-eventsource-configuration)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 🔐 GitHub Personal Access Token Setup

For Argo Events to automatically create and manage webhooks in your GitHub repositories, you need a Personal Access Token (PAT) with the appropriate permissions.

### Single Repository (Fine-Grained Token)

If you only need to monitor **one repository**, you can use a fine-grained token:

1. Go to [GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token**
3. Configure the token:
   - **Token name:** `argo-events-webhook`
   - **Expiration:** Choose appropriate expiration
   - **Repository access:** Select "Only select repositories" and choose your repository
4. Under **Repository permissions**, enable:
   - **Contents:** Read-only (to access repository metadata)
   - **Metadata:** Read-only (required)
   - **Webhooks:** Read and write (to create/manage webhooks)
5. Click **Generate token** and **copy the token immediately** (you won't be able to see it again)

### Multiple Repositories (Classic Token - Recommended)

If you need to monitor **multiple repositories** (e.g., both `nextflow-hello-project` and `nextflow-hello-project-2`), you should use a **classic Personal Access Token** because fine-grained tokens are limited to specific repositories:

1. Go to [GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Configure the token:
   - **Note:** `argo-events-multi-repo`
   - **Expiration:** Choose appropriate expiration (e.g., 90 days, 1 year, or no expiration)
4. Select the following scopes:
   - ✅ **`repo`** (Full control of private repositories) - This includes:
     - `repo:status` - Access commit status
     - `repo_deployment` - Access deployment status
     - `public_repo` - Access public repositories
     - `repo:invite` - Access repository invitations
   - ✅ **`admin:repo_hook`** (Full control of repository hooks) - This includes:
     - `write:repo_hook` - Write repository hooks
     - `read:repo_hook` - Read repository hooks
5. Click **Generate token** and **copy the token immediately**

### Important Notes

- **Never commit your PAT to Git** - Always pass it at deployment time using `--set-string`
- **Store it securely** - Use a password manager or secrets management system
- **Rotate regularly** - Set an expiration date and rotate your token periodically
- **Minimal permissions** - Only grant the scopes necessary for your use case
- **Organization repositories** - If your repositories are in an organization:
  1. After creating the token, click **Configure SSO** next to the token
  2. Authorize the token for your organization
  3. Ensure the organization settings allow PAT access

### Common Permission Issues

If you see errors like:
```
403 Resource not accessible by personal access token
```

This means:
- The PAT doesn't have access to the repository
- The PAT doesn't have the required scopes (`admin:repo_hook` or `repo`)
- The repository is in an organization and the token isn't authorized for that organization
- The organization has restricted PAT access

**Solution:** Regenerate the token with the correct scopes and organization authorization.

---

## 🚀 Multi-Application Configuration

The chart supports deploying multiple Argo CD Applications from a single Helm release.

### Example: Two Applications

```yaml
applications:
  - name: nextflow-hello-project
    repoURL: https://github.com/bwalsh/nextflow-hello-project.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    syncPolicy:
      automated:
        prune: true
        selfHeal: true

  - name: nextflow-hello-project-2
    repoURL: https://github.com/bwalsh/nextflow-hello-project-2.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
```

### Configuration Options

Each application supports:

- **`name`** (required) - Unique name for the Application resource
- **`repoURL`** (required) - Git repository URL
- **`targetRevision`** (optional, default: `main`) - Branch, tag, or commit SHA
- **`path`** (optional, default: `.`) - Path within the repository
- **`project`** (optional, default: `default`) - Argo CD project
- **`destination.server`** (optional, default: `https://kubernetes.default.svc`)
- **`destination.namespace`** (optional, default: `$.Values.namespaces.tenant`)
- **`syncPolicy.automated.prune`** (optional, default: `false`)
- **`syncPolicy.automated.selfHeal`** (optional, default: `false`)

---

## 🎯 Multi-Repository EventSource Configuration

Configure Argo Events to listen for webhook events from multiple GitHub repositories.

### Example: Two Repositories

```yaml
events:
  github:
    enabled: true
    
    repositories:
      - eventName: repo-push-project1
        owner: bwalsh
        repository: nextflow-hello-project
        events: ["push"]
        active: true
      
      - eventName: repo-push-project2
        owner: bwalsh
        repository: nextflow-hello-project-2
        events: ["push", "pull_request"]
        active: true
    
    secret:
      create: true
      name: github-secret
      tokenKey: token
    
    webhook:
      endpoint: /events
      port: 12000
      # URL must be set at deployment time (see below)
      service:
        type: ClusterIP
      ingress:
        enabled: true
        className: nginx
        hosts:
          - webhooks.example.com
```

### Important Requirements

1. **Unique Event Names:** Each repository must have a unique `eventName`
2. **Webhook URL:** Must be publicly accessible from GitHub (set at deployment time)
3. **GitHub PAT:** Must have `admin:repo_hook` or `repo` permissions for ALL repositories

---

## 🚀 Deployment

### Environment Variables

Set the following environment variables before deployment:

```bash
export GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxx  # Your GitHub PAT
export ARGO_HOSTNAME=webhooks.example.com    # Public hostname for webhooks
export ARGOCD_SECRET_KEY=your-secret-key     # ArgoCD secret key
```

### Deploy with Helm

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd --create-namespace \
  --set-string events.github.secret.tokenValue=${GITHUB_PAT} \
  --set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000 \
  --set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
  --set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
  --wait --atomic
```

### Using the Makefile

The repository includes a Makefile for common operations:

```bash
# Set environment variables
export GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxx
export ARGO_HOSTNAME=webhooks.example.com
export ARGOCD_SECRET_KEY=your-secret-key

# Deploy everything
make deploy
```

---

## 🔍 Troubleshooting

### Webhooks Not Created in GitHub

**Symptom:** Webhooks are created in some repositories but not others.

**Check EventSource logs:**
```bash
kubectl logs -n argo-events -l app.kubernetes.io/component=eventsource-controller --tail=100
```

**Common causes:**

1. **403 Permission Error**
   ```
   failed to list existing webhooks: 403 Resource not accessible by personal access token
   ```
   **Solution:** Use a classic PAT with `repo` and `admin:repo_hook` scopes

2. **Duplicate Event Names**
   ```yaml
   # ❌ WRONG - duplicate eventName
   repositories:
     - eventName: repo-push
       repository: project-1
     - eventName: repo-push  # Duplicate!
       repository: project-2
   
   # ✅ CORRECT - unique eventNames
   repositories:
     - eventName: repo-push-project1
       repository: project-1
     - eventName: repo-push-project2
       repository: project-2
   ```

3. **Webhook URL Not Set**
   - The webhook URL must be publicly accessible from GitHub
   - Set it using `--set-string events.github.webhook.url=http://your-domain.com:12000`

4. **Organization Authorization**
   - For organization repositories, authorize the PAT for the organization
   - Go to GitHub → Settings → Applications → Authorized OAuth Apps
   - Or click "Configure SSO" next to your PAT

### Verify EventSource Configuration

```bash
# Check if both repositories are in the EventSource spec
kubectl get eventsource github -n argo-events -o yaml | grep -A 10 "github:"

# Expected output should show both repositories with unique event names
```

### Verify Webhook Creation

Check your GitHub repository settings:
1. Go to `https://github.com/{owner}/{repo}/settings/hooks`
2. You should see a webhook pointing to your `ARGO_HOSTNAME`
3. Recent deliveries should show successful webhook calls

### Applications Not Syncing

**Check Argo CD Application status:**
```bash
kubectl get applications -n argocd
```

**View application details:**
```bash
argocd app get <application-name>
```

### EventBus Issues

**Check EventBus status:**
```bash
kubectl get eventbus -n argo-events
```

**Check NATS pods:**
```bash
kubectl get pods -n argo-events -l component=eventbus
```

---

## 📚 Additional Resources

- [Argo Events Documentation](https://argoproj.github.io/argo-events/)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [GitHub Webhooks Documentation](https://docs.github.com/en/webhooks)
- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

---

## 🆘 Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review the EventSource and Sensor logs
3. Verify your GitHub PAT has the correct permissions
4. Ensure your webhook URL is publicly accessible
5. Check the repository's GitHub issues for similar problems
