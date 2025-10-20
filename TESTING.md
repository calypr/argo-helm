# TESTING.md

## Overview
This document shows how to run all project tests locally:

- Helm chart linting & template validation
- Kubernetes schema validation (kubeconform)
- Chart Testing (`ct`) on a local **kind** cluster (install + smoke)
- `authz-adapter` unit tests (pytest)
- Optional: full manual Helm install for interactive testing

---

## 0) Prerequisites (install once)

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

> On Linux without Homebrew, you can run kubeconform via Docker (see §1).

---

## 1) Fast checks: Helm lint, template, kubeconform

```bash
# From repo root
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Lint the umbrella chart
helm lint helm/argo-stack --values helm/argo-stack/values.yaml

# Render the chart to plain YAML
helm dependency build helm/argo-stack
helm template argo-stack helm/argo-stack   --values helm/argo-stack/values.yaml   --namespace argocd > rendered.yaml

# Validate rendered manifests (skip CRDs and Argo custom resources)
kubeconform -strict -ignore-missing-schemas   -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate'   -summary rendered.yaml
```

Run kubeconform via Docker instead of installing locally:
```bash
docker run --rm -v "$PWD:/work" ghcr.io/yannh/kubeconform:latest-alpine   -strict -ignore-missing-schemas   -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate'   -summary /work/rendered.yaml
```

---

## 2) Chart Testing (ct) with a local kind cluster

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
ct install --config .ct.yaml --print-logs
```

**Notes**
- `ct` uses the working tree and `.ct.yaml` to find `helm/argo-stack`.
- To test with custom values, commit a `ci-values.yaml` or temporarily edit `values.yaml` before running.

---

## 3) Run the authz-adapter unit tests

```bash
cd authz-adapter
python3 -m pip install -r requirements.txt pytest
pytest -q
```

What’s tested:
- `decide_groups(...)` logic (mapping `/user/user` authz JSON to groups like `argo-runner` and `argo-viewer`).

---

## 4) Optional: full manual Helm install (for interactive play)

```bash
# Create namespaces (chart can also create them)
kubectl create ns argocd || true
kubectl create ns argo || true
kubectl create ns wf-poc || true
kubectl create ns security || true

# Install umbrella chart with defaults
helm upgrade --install argo-stack ./helm/argo-stack -n argocd --create-namespace

# Wait for pods
kubectl -n argocd get pods
kubectl -n argo get pods
kubectl -n security get pods

# Port-forward UIs
kubectl -n argo port-forward svc/argo-workflows-server 2746:2746
kubectl -n argocd port-forward svc/argocd-server 8080:80
```

Open:
- Argo Workflows → http://localhost:2746  
- Argo CD → http://localhost:8080

---

## 5) Troubleshooting

- **kubeconform errors on CRDs**  
  Keep skipping `CustomResourceDefinition|Application|Workflow|WorkflowTemplate` or provide schemas for these CRDs.

- **`ct install` hangs or times out**  
  Use `--print-logs` to inspect controller/server logs. Ensure Docker has enough CPU/RAM for kind.

- **Argo CD Application points to a repo path with no manifests**  
  That’s fine as a placeholder; it syncs “empty”. Add K8s manifests or a `kustomization.yaml` in that repo path for real resources.

- **Port-forward conflicts**  
  Change the left port: e.g., `8081:80`, `2747:2746`.

---

## TL;DR

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
ct install --config .ct.yaml --print-logs

# adapter tests
cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q
```
