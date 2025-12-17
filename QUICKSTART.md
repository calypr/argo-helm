# 🚀 Quick Start Guide
## 🏗️ Development Environment

### Workflow Overview

0. **Setup** → Run `scripts/check_tools.sh`,
1. **Development** → Make changes in `authz-adapter/` or `helm/argo-stack/`
2. **Local Testing** → Run `scripts/check_tools.sh`, pytest, helm lint, kubeconform
3. **Integration Testing** → Use `ct` with kind cluster (automated in CI)
4. **Deployment** → Apply `helm/argo-stack/` chart and `k8s/` manifests to cluster
5. **Ingress Setup** → Configure no-ip DNS, deploy NGINX proxy, verify TLS certificates

### Prerequisites

See scripts/check_tools.sh for automated checks.
Currently, required tools and versions:

```text
Date: Wed Nov 26 13:02:26 UTC 2025
Hostname: ip-172-31-23-226.us-west-2.compute.internal
========================================
Checking for requested tools...

✓ kind is installed at: /usr/local/bin/kind
  Version: kind v0.23.0 go1.21.10 linux/amd64

✓ jq is installed at: /usr/bin/jq
  Version: jq-1.7.1

✓ k9s is installed at: /usr/local/bin/k9s
  Version: Version              v0.50.16
Commit               3c37ca2197ca48591566d1f599b7b3a50d54a408
Date                 2025-10-19T15:52:37Z

✓ stern is installed at: /usr/local/bin/stern
  Version: version: 1.33.0
commit: f79098037d951aad53e13aff1f86854b291baf01
built at: 2025-09-07T06:18:52Z

✓ helm is installed at: /usr/local/bin/helm
  Version: v3.19.0+g3d8990f

✓ kubectl is installed at: /usr/local/bin/kubectl
  Version: Client Version: v1.34.1

✓ docker is installed at: /usr/bin/docker
  Version: Docker version 25.0.13, build 0bab007

✓ git is installed at: /usr/bin/git
  Version: git version 2.50.1

✓ pytest is installed at: /home/ec2-user/.local/bin/pytest
  Version: pytest 8.4.2

✓ envsubst is installed at: /usr/bin/envsubst
  Version: envsubst (GNU gettext-runtime) 0.21

✓ python3 is installed at: /usr/bin/python3
  Version: Python 3.9.23

✓ certbot is installed at: /usr/bin/certbot
  Version: certbot 2.6.0

✓ go is installed at: /usr/bin/go
  Version: go version go1.24.7 linux/amd64

✓ gcc is installed at: /usr/bin/gcc
  Version: gcc (GCC) 11.5.0 20240719 (Red Hat 11.5.0-5)

✓ curl is installed at: /usr/bin/curl
  Version: curl 8.11.1 (x86_64-amazon-linux-gnu) libcurl/8.11.1 OpenSSL/3.2.2 zlib/1.2.11 libidn2/2.3.2 libpsl/0.21.5 nghttp2/1.59.0

✓ openssl is installed at: /usr/bin/openssl
  Version: OpenSSL 3.2.2 4 Jun 2024 (Library: OpenSSL 3.2.2 4 Jun 2024)

✓ sqlite3 is installed at: /usr/bin/sqlite3
  Version: 3.40.0 2023-06-02 12:56:32 00a1256aa915eba233626a380102f8e74157cde64f0cd68731893b588c97alt1

```



### Setup

```bash
# Install Python dependencies for authz-adapter
cd authz-adapter
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Build Docker image
docker build -t authz-adapter:dev .
```

## 🧪 Testing

### Quick Start

```bash
# Fast checks
helm repo add argo https://argoproj.github.io/argo-helm && helm repo update
helm lint helm/argo-stack --values helm/argo-stack/values.yaml
helm dependency build helm/argo-stack
helm template argo-stack helm/argo-stack --values helm/argo-stack/values.yaml --namespace argocd > rendered.yaml
kubeconform -strict -ignore-missing-schemas -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' -summary rendered.yaml

# kind + ct
kind create cluster
ct lint --config .ct.yaml
ct install --config .ct.yaml --debug

# adapter tests
cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q
```

### 0. Prerequisites

```bash
# Helm
brew install helm || sudo snap install helm --classic

# kind (Kubernetes-in-Docker)
brew install kind || GO111MODULE="on" go install sigs.k8s.io/kind@v0.23.0

# Python tooling for adapter tests
python3 -m pip install --upgrade pip
python3 -m pip install pytest

# chart-testing (ct)
brew install chart-testing || pipx install chart-testing

# kubeconform (schema validation)
brew install kubeconform ||   curl -L https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-linux-amd64.tar.gz   | tar xz && sudo mv kubeconform /usr/local/bin/
```


### 1. Helm lint, template, kubeconform

```bash
# From repo root
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Lint the umbrella chart
helm lint helm/argo-stack --values helm/argo-stack/values.yaml

# Render the chart to plain YAML
helm dependency build helm/argo-stack
helm template argo-stack helm/argo-stack --values helm/argo-stack/values.yaml --namespace argocd > rendered.yaml

# Validate rendered manifests (skip CRDs and Argo custom resources)
kubeconform -strict -ignore-missing-schemas -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' -summary rendered.yaml
```

### 2. Chart Testing (ct)

This replicates CI: spin up kind, lint, then install the chart and smoke test it.

```bash
# Fresh kind cluster
kind delete cluster || true
kind create cluster

# Ensure dependencies are built
helm dependency build helm/argo-stack

# Lint using ct (uses .ct.yaml)
ct lint --config .ct.yaml

# Install and smoke test
ct install --config .ct.yaml --debug
```

**Notes**
- `ct` uses the working tree and `.ct.yaml` to find `helm/argo-stack`.
- To test with custom values, commit a `ci-values.yaml` or temporarily edit `values.yaml` before running.

### 3. authz-adapter unit tests

```bash
cd authz-adapter
python3 -m pip install -r requirements.txt pytest
pytest -q
```

What’s tested:
- `decide_groups(...)` logic (mapping `/user/user` authz JSON to groups like `argo-runner` and `argo-viewer`).

### 4. Troubleshooting

See docs/troubleshooting.md for common issues and solutions.


## 📁 Project Structure

```text
.
├── authz-adapter/                          # Custom authorization adapter for Argo
│   ├── Dockerfile                          # Container image definition
│   ├── adapter.py                          # Main FastAPI authorization service
│   ├── requirements.txt                    # Runtime dependencies
│   ├── requirements-dev.txt                # Development and testing dependencies
│   └── tests/                              # Unit tests for authorization logic
├── helm/
│   └── argo-stack/                         # Umbrella Helm chart for the full stack
│       ├── Chart.yaml                      # Chart metadata and dependencies
│       ├── values.yaml                     # Default configuration values
│       ├── templates/                      # Kubernetes manifest templates
│       └── charts/                         # Downloaded dependency charts (gitignored)
├── k8s/                                    # Platform Kubernetes manifests
│   └── TODO                                # k8s manifests for ingress, TLS, DNS, etc.
├── scripts/                                # Development and automation scripts
│   └── check_tools.sh                      # Validates required tools and versions
├── docs/                                   # Documentation (if exists)
│   └── troubleshooting.md                  # Common issues and solutions
├── .ct.yaml                                # chart-testing (ct) configuration
├── .github/                                # GitHub Actions CI/CD workflows
│   └── workflows/
│       └── ci.yaml                         # Automated lint/test/build pipeline
├── CONTRIBUTING.md                         # This file
└── README.md                               # Project overview and quick start
```

### Key Directories

#### `authz-adapter/`
Custom Python authorization adapter that integrates Gen3's Fence, Arborist with Argo Workflows and Argo CD. Implements group-based RBAC by mapping user identities to groups like `argo-runner` and `argo-viewer`.

**Key files:**
- `adapter.py` - FastAPI service handling `/api/v1/auth` requests
- `tests/` - pytest unit tests for authorization logic
- `Dockerfile` - Builds the adapter container image

#### `helm/argo-stack/`
Umbrella chart that bundles:
- **Argo CD** - GitOps continuous delivery
- **Argo Workflows** - Container-native workflow engine
- **Argo Events** - Event-driven workflow automation
- **authz-adapter** - Custom authorization service (as a subchart or template)

**Key files:**
- `Chart.yaml` - Declares dependencies on upstream Argo charts
- `values.yaml` - Configures all components, includes authz adapter settings
- `templates/` - Additional manifests (e.g., RBAC, webhooks)

#### `k8s/`
Raw Kubernetes manifests for platform infrastructure that sit outside the Helm chart.

**Purpose:**
- **Ingress**: Path-based NGINX reverse proxy using `hostNetwork: true` for EC2
- **TLS**: cert-manager integration with Let's Encrypt
- **DNS**: Configuration for no-ip.com dynamic DNS

**Key files:**
- `nginx-reverse-proxy-path.yaml` - Single-host ingress with paths `/argo/`, `/applications/`, `/registrations/`, `/api/`, `/register/`
- `clusterissuer-letsencrypt.yaml` - ACME issuers for staging and production
- `noip-certificate.yaml` - Certificate resource for your no-ip domain

#### `scripts/`
Helper scripts for local development and CI setup.

**Key files:**
- `check_tools.sh` - Validates installed tools (kubectl, helm, kind, pytest, etc.)
- Other setup scripts for environment preparation

#### Continuous Integration

See .github/workflows/ci.yaml for the GitHub Actions pipeline that automates:
Configuration for [chart-testing](https://github.com/helm/chart-testing) used in CI.

Defines:
- Chart directories to test
- Helm lint rules
- Install test configuration


## 🚀 Deployment

### Quick Deploy with `make deploy`

The `make deploy` target provides a complete deployment workflow that sets up the entire Argo stack with all dependencies:

```bash
make deploy
```

#### What It Does

The `deploy` target executes the following steps in order:

1. **`make init`** - Initialize the cluster with all prerequisites:
   - Creates a kind cluster (`make kind`)
   - Raises inotify and file descriptor limits (`make bump-limits`)
   - Installs External Secrets Operator (`make eso-install`)
   - Deploys Vault dev server (`make vault-dev`)
   - Seeds Vault with test secrets (`make vault-seed`)
   - Installs MinIO for artifact storage (`make minio`)
   - Configures Vault authentication (`make vault-auth`)

2. **`make argo-stack`** - Deploys the Argo stack Helm chart:
   - Installs Argo CD, Argo Workflows, and Argo Events
   - Configures S3 artifact storage (MinIO)
   - Sets up GitHub webhook integration
   - Applies custom values from `my-values.yaml`

3. **`make docker-install`** - Builds and loads custom Docker images:
   - Builds `nextflow-runner:latest` from `nextflow-runner/Dockerfile`
   - Loads the image into the kind cluster

4. **`make ports`** - Configures ingress and TLS:
   - Creates TLS secrets from Let's Encrypt certificates
   - Installs the `ingress-authz-overlay` Helm chart
   - Deploys nginx-ingress controller with NodePort
   - Patches services to use external IP and NodePort

#### Prerequisites

Before running `make deploy`, ensure you have:

```bash
# Required environment variables
export GITHUB_PAT="your-github-personal-access-token"
export ARGOCD_SECRET_KEY="$(openssl rand -hex 32)"
export ARGO_HOSTNAME="your-domain.com"

# Optional S3/MinIO configuration (defaults provided)
export S3_ENABLED="true"
export S3_ACCESS_KEY_ID="minioadmin"
export S3_SECRET_ACCESS_KEY="minioadmin"
export S3_BUCKET="argo-artifacts"
```

#### TLS Certificate Requirements

The `make ports` step expects Let's Encrypt certificates at:

```text
/etc/letsencrypt/live/${ARGO_HOSTNAME}/fullchain.pem
/etc/letsencrypt/live/${ARGO_HOSTNAME}/privkey.pem
```

To get certificates:

```bash
sudo certbot certonly --standalone -d ${ARGO_HOSTNAME}
```

#### What Gets Deployed

After `make deploy` completes, you'll have:

- **Kubernetes Cluster**: kind cluster with raised system limits
- **Secret Management**: 
  - Vault dev server with test secrets
  - External Secrets Operator syncing secrets
- **Artifact Storage**: MinIO with `argo-artifacts` bucket
- **Argo Stack**:
  - Argo CD at `https://${ARGO_HOSTNAME}/applications/`
  - Argo Workflows at `https://${ARGO_HOSTNAME}/argo/`
  - Argo Events webhook receiver at `https://${ARGO_HOSTNAME}/registrations/`
- **Ingress**: nginx-ingress controller with TLS termination

#### Accessing Services

After deployment:

```bash
# Get Argo CD admin password
make password

# Login to Argo CD CLI
make login

# Access services via browser:
# https://${ARGO_HOSTNAME}/applications/  - Argo CD UI
# https://${ARGO_HOSTNAME}/argo/          - Argo Workflows UI
# https://${ARGO_HOSTNAME}/registrations/ - GitHub webhook endpoint
```

#### Troubleshooting Deployment

**Environment variable errors:**
```bash
# Validate all required variables are set
make check-vars
```

**Certificate not found:**
```bash
# Verify certificate path
sudo ls -la /etc/letsencrypt/live/${ARGO_HOSTNAME}/
```

**MinIO bucket isn't created:**
```bash
# Check MinIO status
make minio-status

# List bucket contents
make minio-ls

# Recreate if needed
make minio-cleanup
make minio
```

**Vault secrets not syncing:**
```bash
# Verify Vault is running
make vault-status

# Check ExternalSecret status
make test-secrets

# Reseed Vault if needed
make vault-seed
```

**Pods not starting:**
```bash
# Check system limits
make show-limits

# Increase if needed
make bump-limits
```

#### Clean Deployment

To start fresh:

```bash
# Remove everything and redeploy
kind delete cluster
make deploy
```

#### Customizing Deployment

To customize the deployment, edit `my-values.yaml` before running `make deploy`:

```yaml
# my-values.yaml
repoRegistrations:
 ...
```

Then deploy with custom values:

```bash
make deploy
```
