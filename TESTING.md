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

```bash
# Update base
sudo yum -y install git docker
sudo yum -y update || sudo dnf -y update
sudo yum -y install git curl tar gzip python3 python3-pip jq --allowerasing
# || sudo dnf -y install git curl tar gzip python3 python3-pip jq

# Requires Docker. Install if needed:
if ! command -v docker >/dev/null; then
  sudo yum -y install docker || sudo dnf -y install docker
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  echo ">> Log out/in (or 'newgrp docker') to use docker without sudo."
fi


# ---------- Helm ----------
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version

# install python 3.13
sudo yum -y install gcc openssl-devel bzip2-devel libffi-devel
sudo dnf install python3.13 -y

# ---------- yamllint ----------
python3 -m pip install --upgrade pip && pip install yamllint

# cosign (for signing container images, used in some CI)
 curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
    sudo mv cosign-linux-amd64 /usr/local/bin/cosign
    sudo chmod +x /usr/local/bin/cosign

git clone https://github.com/calypr/argo-helm
cd argo-helm
export GITHUB_PATH=$PWD
# ? 
#sudo yum install go -y
#mkdir -p $HOME/.cosign
#GOBIN=$(go env GOPATH)/bin
#go install github.com/sigstore/cosign/cmd/cosign@main
#ln -s $GOBIN/cosign $HOME/.cosign/cosign
# echo "$HOME/.cosign" >> $GITHUB_PATH

# chart testing
mkdir chart-testing-install
cd chart-testing-install
#curl -LO https://github.com/helm/chart-testing/releases/download/v3.14.0/chart-testing_3.14.0_darwin_amd64.tar.gz
#tar -xvf chart-testing_3.14.0_darwin_amd64.tar.gz
curl -LO https://github.com/helm/chart-testing/releases/download/v3.13.0/chart-testing_3.13.0_linux_amd64.tar.gz
tar -xvf chart-testing_3.13.0_linux_amd64.tar.gz
sudo mv ct /usr/local/bin/ct
sudo chmod +x /usr/local/bin/ct
sudo mv etc/chart_schema.yaml /etc/chart_schema.yaml
sudo mv etc/lintconf.yaml /etc/lintconf.yaml
ct version
cd ..
rm -rf chart-testing-install

           
# ---------- kind (Kubernetes-in-Docker) ----------

# Install kind (linux/amd64)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
kind --version

# ---------- Python tooling for adapter tests ----------
python3 -m pip install --upgrade pip
python3 -m pip install --user pytest
# Optional: make 'pipx' available for nicer CLI installs
python3 -m pip install --user pipx
python3 -m pipx ensurepath


# ---------- kubeconform (schema validation) ----------
KCF_URL="$(curl -s https://api.github.com/repos/yannh/kubeconform/releases/latest | jq -r '.assets[] | select(.name|test("linux-amd64\\.tar\\.gz$")).browser_download_url')"
curl -L "$KCF_URL" | tar xz kubeconform
sudo mv kubeconform /usr/local/bin/
kubeconform -v

# ---------- kubectl ----------
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl 

# ---------- k9s (Kubernetes CLI UI) ----------
curl --silent --location "https://github.com/derailed/k9s/releases/latest/download/k9s_Linux_amd64.tar.gz" | tar xz -C /tmp
sudo cp /tmp/k9s /usr/local/bin
k9s version
```

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
ct install --config .ct.yaml --debug
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


kubectl delete ns argocd || true
kubectl delete ns argo || true
kubectl delete ns wf-poc || true
kubectl delete ns security || true

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
  Use `--debug` to inspect controller/server logs. Ensure Docker has enough CPU/RAM for kind.

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
ct install --config .ct.yaml --debug

# adapter tests
cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q
```
