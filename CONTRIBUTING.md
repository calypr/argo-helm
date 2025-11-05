# Contributing to Argo Stack with Authorization Adapter

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/argo-helm.git
   cd argo-helm
   ```
3. **Create a feature branch** from main:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🏗️ Development Environment

### Prerequisites

- Docker
- Kubernetes cluster (kind, minikube, or cloud)
- Helm v3.x
- Python 3.9+ (for authz-adapter development)

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

- **kubeconform errors on CRDs**  
  Keep skipping `CustomResourceDefinition|Application|Workflow|WorkflowTemplate` or provide schemas for these CRDs.

- **`ct install` hangs or times out**  
  Use `--debug` to inspect controller/server logs. Ensure Docker has enough CPU/RAM for kind.

- **Argo CD Application points to a repo path with no manifests**  
  That’s fine as a placeholder; it syncs “empty”. Add K8s manifests or a `kustomization.yaml` in that repo path for real resources.

- **Port-forward conflicts**  
  Change the left port: e.g., `8081:80`, `2747:2746`.
