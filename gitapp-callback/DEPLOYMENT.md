# GitHub App Callback Service Deployment

This document describes the integration of the gitapp-callback service into the Argo Helm chart deployment.

## Overview

The gitapp-callback service has been integrated into the `argo-stack` Helm chart as a standard deployment alongside other services like `authz-adapter` and `landing-page`.

## Components Added

### 1. Helm Templates

**`helm/argo-stack/templates/32-gitapp-callback.yaml`**
- Kubernetes Deployment for the gitapp-callback service
- Kubernetes Service exposing port 8080
- Health check probes (liveness and readiness)
- Environment variables for configuration (SECRET_KEY, GITHUB_APP_NAME)
- Runs in the `security` namespace

**`helm/argo-stack/templates/42-gitapp-callback-ingress.yaml`**
- Ingress configuration for the callback service
- Routes `/registrations` path to the service
- Uses nginx ingress controller
- Optional TLS configuration
- Public endpoint (no authentication required for GitHub callbacks)

### 2. Helm Values Configuration

**`helm/argo-stack/values.yaml`**

Added `gitappCallback` section after `landingPage`:
```yaml
gitappCallback:
  enabled: true
  image:
    repository: gitapp-callback
    tag: v1.0.0
    pullPolicy: IfNotPresent
  replicas: 2
  secretKey: "change-me-in-production-use-vault"
  githubAppName: "calypr-workflows"
```

Added `ingress.gitappCallback` section:
```yaml
ingress:
  gitappCallback:
    enabled: false
    host: ""
    tls:
      enabled: false
      secretName: ""
```

### 3. Makefile Integration

**Docker Build Target**

Added `docker-gitapp-callback` target to build and load the Docker image:
```makefile
docker-gitapp-callback:
	cd gitapp-callback ; docker build -t gitapp-callback:v1.0.0 -f Dockerfile .
	kind load docker-image gitapp-callback:v1.0.0 --name kind
	docker exec -it kind-control-plane crictl images | grep gitapp-callback
	@echo "✅ loaded docker gitapp-callback"
```

Updated `docker-install` to include the new target:
```makefile
docker-install: docker-runner docker-authz docker-landing-page docker-gitapp-callback
```

**Helm Deployment Configuration**

Updated `argo-stack` target to enable ingress:
```makefile
--set-string ingress.gitappCallback.enabled=true \
--set-string ingress.gitappCallback.host=${ARGO_HOSTNAME} \
```

Updated `template` target for templating:
```makefile
--set-string ingress.gitappCallback.enabled=true \
--set-string ingress.gitappCallback.host=${ARGO_HOSTNAME} \
```

## Deployment

### Building the Docker Image

```bash
make docker-gitapp-callback
```

This will:
1. Build the Docker image from `gitapp-callback/Dockerfile`
2. Tag it as `gitapp-callback:v1.0.0`
3. Load it into the kind cluster
4. Verify the image is available

### Full Deployment

The service is automatically deployed when you run:

```bash
make deploy
```

Or just the argo-stack:

```bash
make argo-stack
```

### Manual Deployment

To deploy just the gitapp-callback:

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd --create-namespace \
  --set gitappCallback.enabled=true \
  --set ingress.gitappCallback.enabled=true \
  --set ingress.gitappCallback.host=your-domain.com
```

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key for session management (configure in values.yaml or via Vault)
- `GITHUB_APP_NAME`: GitHub App name displayed in the UI

### Ingress Path

The service is accessible at:
```
https://your-domain.com/registrations
```

This matches the GitHub App "Post-installation redirect URL" configuration.

### GitHub App Configuration

In your GitHub App settings, set the **Post-installation redirect URL** to:
```
https://your-domain.com/registrations
```

GitHub will automatically append query parameters:
```
https://your-domain.com/registrations?installation_id=12345678&setup_action=install
```

### Database Persistence

The service stores registration data in a SQLite database at `/var/registrations/registrations.sqlite`.

**Persistence Options:**

1. **Host-Mounted Volumes (kind clusters with extraMounts)**
   ```yaml
   gitappCallback:
     persistence:
       enabled: true
       useExtraMounts: true
       registrationsPath: "/var/registrations"
   ```
   
   This requires matching configuration in `kind-config.yaml`:
   ```yaml
   extraMounts:
     - hostPath: $PWD/registrations
       containerPath: /var/registrations
   ```
   
   The `registrationsPath` value must match the `containerPath` in kind-config.yaml.
   
   **When to use:** Local development with kind clusters that have extraMounts configured.

2. **PersistentVolumeClaim (production clusters)**
   ```yaml
   gitappCallback:
     persistence:
       enabled: true
       useExtraMounts: false  # Disable host mounts to use PVC
       storageClass: "standard"
       size: "1Gi"
   ```
   
   A PVC named `gitapp-callback-data` will be automatically created.
   
   **When to use:** Production deployments or any cluster with dynamic PVC provisioning.

3. **Existing PVC**
   ```yaml
   gitappCallback:
     persistence:
       enabled: true
       useExtraMounts: false
       existingClaim: "my-existing-pvc"
   ```
   
   **When to use:** When you have pre-provisioned storage or specific PVC requirements.

4. **emptyDir (no persistence, data lost on pod restart)**
   ```yaml
   gitappCallback:
     persistence:
       enabled: false
   ```
   
   **When to use:** Testing only - all data is lost when pods restart.

**Default Configuration:**

By default, the service uses `useExtraMounts: true` with `registrationsPath: "/var/registrations"` to work with kind clusters that have the extraMounts configured.

**Priority:** When both `enabled=true` and `useExtraMounts=true`, hostPath takes priority over PVC.

## Architecture

```
GitHub App Installation
        ↓
  (User redirected)
        ↓
Ingress (/registrations)
        ↓
Service (gitapp-callback:8080)
        ↓
Deployment (2 replicas)
```

## Testing

1. **Build the image:**
   ```bash
   make docker-gitapp-callback
   ```

2. **Deploy to cluster:**
   ```bash
   make argo-stack
   ```

3. **Verify deployment:**
   ```bash
   kubectl get pods -n security | grep gitapp-callback
   kubectl get svc -n security | grep gitapp-callback
   kubectl get ingress -n security | grep gitapp-callback
   ```

4. **Check logs:**
   ```bash
   kubectl logs -n security -l app=gitapp-callback -f
   ```

5. **Test health endpoint:**
   ```bash
   kubectl run curl --rm -it --restart=Never --image=curlimages/curl -- \
     curl http://gitapp-callback.security.svc.cluster.local:8080/healthz
   ```

6. **Test registration endpoint:**
   ```bash
   curl https://your-domain.com/registrations?installation_id=test123
   ```

## Security Considerations

1. **Secret Key**: In production, store `SECRET_KEY` in Vault and use External Secrets Operator
2. **Public Endpoint**: The `/registrations` endpoint is public (required for GitHub callbacks)
3. **Input Validation**: The service validates all user input (emails, URLs, bucket configs)
4. **TLS**: Enable TLS in production (`ingress.gitappCallback.tls.enabled=true`)

## Troubleshooting

### Service not accessible

Check if the ingress is created:
```bash
kubectl get ingress -n security gitapp-callback -o yaml
```

### Pods not running

Check pod status:
```bash
kubectl describe pod -n security -l app=gitapp-callback
```

### Image pull errors

Ensure the image was loaded into kind:
```bash
docker exec -it kind-control-plane crictl images | grep gitapp-callback
```

## Future Enhancements

1. **Vault Integration**: Move SECRET_KEY to Vault with External Secrets Operator
2. **RepoRegistration CRD**: Wire form submission to create Kubernetes RepoRegistration resources
3. **GitHub API Integration**: Validate installation_id with GitHub API
4. **Metrics**: Add Prometheus metrics for monitoring form submissions
5. **Rate Limiting**: Add rate limiting for the public endpoint

## Related Documentation

- [GitHub App Callback Service](../gitapp-callback/README.md)
- [Argo Stack Helm Chart](./helm/argo-stack/README.md)
- [GitHub Apps Documentation](https://docs.github.com/en/apps)
