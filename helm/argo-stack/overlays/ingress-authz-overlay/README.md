# Ingress AuthZ Overlay

A Helm overlay chart providing unified, path-based ingress with centralized authorization for multi-tenant Argo Stack deployments.

## Overview

This overlay provides a **single host, path-based ingress** for all major UIs and APIs:

| Path | Service | Description |
|------|---------|-------------|
| `/workflows` | Argo Workflows Server | Workflow UI (port 2746) |
| `/applications` | Argo CD Server | GitOps applications UI (port 8080) |
| `/registrations` | GitHub EventSource | Repository registration events (port 12000) |
| `/api` | Calypr API | Platform API service (port 3000) |
| `/tenants` | Calypr Tenants | Tenant portal (port 3001) |

All endpoints are protected by the `authz-adapter` via NGINX external authentication.

## AuthZ Adapter Configuration

**Important**: By default, this overlay does **not** deploy its own authz-adapter. Instead, it reuses the centralized authz-adapter deployed by the main `argo-stack` chart in the `security` namespace.

### Default Configuration (Recommended)

The overlay is configured to use the existing authz-adapter in the `security` namespace:

```yaml
ingressAuthzOverlay:
  authzAdapter:
    deploy: false                # Do NOT deploy a separate adapter
    namespace: security          # Point to security namespace
    serviceName: authz-adapter
    port: 8080
```

This ensures a single, centralized authz-adapter handles authentication for all ingress routes.

### Deploying a Separate Adapter (Advanced)

If you need the overlay to deploy its own authz-adapter instance:

```yaml
ingressAuthzOverlay:
  authzAdapter:
    deploy: true                 # Deploy a separate adapter
    namespace: argo-stack        # In the overlay's namespace
    serviceName: authz-adapter
    port: 8080
```

**Note**: Having multiple authz-adapter instances may cause configuration drift and is not recommended.

## Quick Start

```bash
# Install the overlay
helm upgrade --install ingress-authz-overlay \
  helm/argo-stack/overlays/ingress-authz-overlay \
  --namespace argo-stack \
  --create-namespace

# With custom host
helm upgrade --install ingress-authz-overlay \
  helm/argo-stack/overlays/ingress-authz-overlay \
  --namespace argo-stack \
  --set ingressAuthzOverlay.host=my-domain.example.com
```

## Configuration

See [`values.yaml`](values.yaml) for all configurable options.

Key settings:

```yaml
ingressAuthzOverlay:
  enabled: true
  host: calypr-demo.ddns.net
  tls:
    enabled: true
    secretName: calypr-demo-tls
    clusterIssuer: letsencrypt-prod
```

## Documentation

- [User Guide](docs/authz-ingress-user-guide.md) - Complete installation and configuration guide
- [Acceptance Tests](tests/authz-ingress.feature) - Gherkin-style test scenarios

## Architecture

See the [User Guide](docs/authz-ingress-user-guide.md) for architecture diagrams and detailed flow descriptions.

## Requirements

- Kubernetes 1.19+
- Helm 3.x
- NGINX Ingress Controller
- cert-manager (for TLS) - **must be installed before deploying this overlay**

### TLS Certificate Ownership

When using cert-manager's ingress-shim, only **one** ingress resource can "own" a Certificate. 
This overlay uses a `primary: true` flag on routes to designate which ingress should have the 
`cert-manager.io/cluster-issuer` annotation.

By default, the `workflows` route is set as primary. Other ingresses reference the same TLS 
secret but without the cluster-issuer annotation, avoiding the "certificate resource is not 
owned by this object" error.

To change the primary route:

```yaml
ingressAuthzOverlay:
  routes:
    workflows:
      primary: false  # Remove primary from workflows
    applications:
      primary: true   # Make applications the primary
```

### Installing cert-manager

If you see `no matches for kind "ClusterIssuer"`, cert-manager is not installed:

```bash
# Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true

# Wait for cert-manager to be ready
kubectl wait --for=condition=Ready pods --all -n cert-manager --timeout=120s
```

See the [User Guide](docs/authz-ingress-user-guide.md) for complete setup instructions including ClusterIssuer configuration.
