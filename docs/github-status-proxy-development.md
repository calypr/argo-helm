# GitHub Status Proxy - Development Guide

This guide covers building, deploying, and testing the GitHub Status Proxy locally.

## Prerequisites

- Go 1.22 or later
- Docker
- kind (Kubernetes in Docker)
- kubectl
- Helm 3.x

## Quick Start

### 1. Build and Test

```bash
# Run unit tests
make github-status-proxy

# Build the Go binary
make build-proxy-binary

# Build the Docker image
make build-proxy-image
```

### 2. Deploy to kind Cluster

```bash
# Create a kind cluster (if you don't have one)
make kind

# Set required environment variables
export GITHUB_APP_ID="your-app-id"
export GITHUB_APP_PRIVATE_KEY_FILE="/path/to/private-key.pem"

# Build and deploy the proxy
make deploy-proxy
```

The `deploy-proxy` target will:
1. Build the Go binary
2. Build the Docker image
3. Load the image into the kind cluster
4. Create a Kubernetes secret with your GitHub App credentials
5. Deploy the proxy using Helm

### 3. Verify Deployment

```bash
# Check pod status
kubectl get pods -n argocd -l app=github-status-proxy

# View logs
kubectl logs -n argocd -l app=github-status-proxy -f

# Test the healthz endpoint
kubectl port-forward -n argocd svc/github-status-proxy 8080:8080
curl http://localhost:8080/healthz
```

## Makefile Targets

### Build Targets

- **`build-proxy-binary`**: Builds the Go binary for Linux AMD64
  ```bash
  make build-proxy-binary
  ```

- **`build-proxy-image`**: Builds the Docker image (builds binary first)
  ```bash
  make build-proxy-image
  
  # Or with custom image name/tag
  make build-proxy-image PROXY_IMAGE=myregistry/proxy PROXY_TAG=dev
  ```

### Deployment Targets

- **`load-proxy-image`**: Loads the Docker image into kind cluster
  ```bash
  make load-proxy-image
  ```

- **`deploy-proxy`**: Full deployment (build, load, and deploy to cluster)
  ```bash
  export GITHUB_APP_ID="123456"
  export GITHUB_APP_PRIVATE_KEY_FILE="./private-key.pem"
  make deploy-proxy
  ```

### Test Targets

- **`github-status-proxy`**: Runs Go unit tests
  ```bash
  make github-status-proxy
  ```

## Configuration Variables

The Makefile supports the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_IMAGE` | `ghcr.io/calypr/github-status-proxy` | Docker image name |
| `PROXY_TAG` | `latest` | Docker image tag |
| `GITHUB_APP_ID` | (required for deploy) | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_FILE` | (required for deploy) | Path to private key PEM file |

Example:
```bash
export PROXY_IMAGE="myregistry/github-status-proxy"
export PROXY_TAG="v1.0.0"
make build-proxy-image
```

## Manual Build Process

If you need to build manually:

### Build Binary

```bash
cd github-status-proxy
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -installsuffix cgo -o github-status-proxy .
```

### Build Docker Image

```bash
cd github-status-proxy
docker build -t ghcr.io/calypr/github-status-proxy:latest .
```

### Load into kind

```bash
kind load docker-image ghcr.io/calypr/github-status-proxy:latest
```

## Testing the Proxy

### Unit Tests

```bash
cd github-status-proxy
go test -v ./...

# With coverage
go test -v -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

### Integration Testing

1. Deploy the proxy to a kind cluster
2. Create a test Argo CD Application pointing at a GitHub repository
3. Trigger a sync
4. Verify commit status appears on GitHub

## Troubleshooting

### Binary Build Issues

If you encounter Go build errors:
```bash
cd github-status-proxy
go mod tidy
go mod download
go build .
```

### Docker Build Issues

If the Docker build fails:
- Ensure you've built the binary first: `make build-proxy-binary`
- Check Docker is running: `docker ps`
- Try building manually: `cd github-status-proxy && docker build -t test .`

### Kind Load Issues

If loading into kind fails:
- Verify kind cluster exists: `kind get clusters`
- Create a cluster: `make kind`
- Check Docker images: `docker images | grep proxy`

### Deployment Issues

If deployment fails:
- Check environment variables are set:
  ```bash
  echo $GITHUB_APP_ID
  echo $GITHUB_APP_PRIVATE_KEY_FILE
  ```
- Verify the private key file exists and is readable
- Check Helm release: `helm list -n argocd`
- View pod events: `kubectl describe pod -n argocd -l app=github-status-proxy`

## Development Workflow

Typical development workflow:

```bash
# 1. Make code changes
vim github-status-proxy/main.go

# 2. Run tests
make github-status-proxy

# 3. Build and deploy
make deploy-proxy

# 4. Test the changes
kubectl logs -n argocd -l app=github-status-proxy -f

# 5. Iterate
# Make more changes and repeat steps 2-4
```

## CI/CD Integration

The Makefile targets can be used in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Build proxy image
  run: make build-proxy-image

- name: Push image
  run: |
    docker push ${{ env.PROXY_IMAGE }}:${{ env.PROXY_TAG }}
```

## Related Documentation

- [Setup Guide](./github-status-proxy-setup.md) - Production deployment guide
- [API Documentation](../github-status-proxy/README.md) - Service API details
- [ADR](./adr/0001-github-status-proxy-for-multi-tenant-github-apps.md) - Architecture decision record
