# 🚀 Argo Stack with Authorization Adapter

<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Helm](https://img.shields.io/badge/Helm-v3.0+-blue.svg)](https://helm.sh/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.20+-blue.svg)](https://kubernetes.io/)
[![Argo Workflows](https://img.shields.io/badge/Argo%20Workflows-latest-green.svg)](https://argoproj.github.io/argo-workflows/)
[![Argo CD](https://img.shields.io/badge/Argo%20CD-latest-green.svg)](https://argo-cd.readthedocs.io/)

*A complete, production-ready Kubernetes GitOps and workflow automation stack with enterprise-grade authorization*

[Quick Start](#-quick-start) • [Features](#-features) • [Architecture](#-architecture) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

## 🧪 Experimental Notice

> **⚠️ This project is experimental and subject to change.** Use in production environments at your own discretion.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
  - [Helm Deployment](#helm-deployment)
  - [Script-based Installation](#script-based-installation)
- [Configuration](#-configuration)
- [Security & Authorization](#-security--authorization)
- [Monitoring & Troubleshooting](#-monitoring--troubleshooting)
- [Advanced Usage](#-advanced-usage)
- [Contributing](#-contributing)

---

## 📜 How `argo-helm` addresses [requirements](https://github.com/calypr/argo-helm/issues/5)

* **Orchestrator & server-side execution (UC-1, UC-6–UC-9):**
  Install **Argo Workflows** and **Argo CD** via the community Helm charts. This gives you DAGs, steps, retries, artifacts, logs/UIDs, and API/CLI to start runs (jobs) with parameters. You model `tiff_offsets`, `file_transfer`, and custom pipelines as (Cluster)WorkflowTemplates and submit Runs programmatically. ([GitHub][1])

* **Submission API surface (UC-1):**
  Argo Workflows’ server API (exposed by the chart) accepts workflow submissions with input params; Argo CD can also be used to declaratively drive workflow launches (e.g., an Application that renders a `Workflow` CR). **`argo-helm` installs these components;** your Calypr API would call them. ([GitHub][1])

* **Policy-driven plans / default workflows (UC-2):**
  Not a native Argo feature, but you can approximate with **Argo CD ApplicationSets** and Helm values overlays, or read a “policy pack” ConfigMap and render different workflow templates based on file type. Argo CD **supports multiple sources** (chart & values from different repos) from **v2.6+**, which helps you separate policy packs from workflow charts. ([Argo CD][2])

* **Observability: job/run status & logs (UC-3, AT-4):**
  Workflows UI and API expose per-run state, timelines, and **log tailing**; Argo CD shows resource health/sync for GitOps-driven launches. All of this is what the charts install and expose. ([GitHub][1])

* **Gating publication on required jobs (UC-4, AT-5/AT-6):**
  **Not enforced by Argo itself.** Recommended pattern: Calypr API checks Argo run states (via label selectors/annotations per input) before allowing publication. Argo provides the **ground truth of run states and artifacts**; your API enforces the 412/428 logic. (Deploying Argo via `argo-helm` is the enabling step.) ([GitHub][1])

* **Background publication updates (UC-5, AT-7):**
  Model as a separate “update-publication” workflow that runs asynchronously; trigger via your API or GitOps commit. Argo handles the run; your API versions the publication. Installed via the charts. ([GitHub][1])

* **Custom workflow registration & invocation (UC-8, AT-PS9):**
  Use **WorkflowTemplate/ClusterWorkflowTemplate** to register `custom:<name>@<version>`; invoke by reference with params. Managed and deployed with Helm/Argo CD. ([GitHub][1])

* **Retries, partial success, idempotency (UC-9, AT-9):**
  Use `retryStrategy` and step-level exit handlers. Your API tracks Job/Run IDs and retries failed ones only. Provided by Argo Workflows, installed by the chart. ([GitHub][1])

* **AuthN/Z & multi-tenant isolation (UC-10, AT-10):**
  Achieve **namespace-scoped isolation** with Kubernetes RBAC; Argo CD integrates OIDC SSO and repo credentials. The Argo CD Helm chart is the standard way to deploy these features. ([artifacthub.io][3])

* **Ingress/UI exposure & cluster bootstrap:**
  The official charts are the supported install path. You can expose **Argo CD** and **Argo Workflows** UIs via Ingress or port-forwarding; this is the common setup shown in docs and chart pages. ([Argo CD][2])

* **Values/overlays & “policy pack” repos:**
  Since **Argo CD v2.6**, you can keep **charts in one repo and values in another**, which maps well to your “policy pack” versioning and environment overlays. ([Argo CD][2])

# What `argo-helm` does **not** do (and how to fill the gaps)

* **Pre-submission “Jobs Suite” client (Section 2, UC-PS1–PS10):**
  That client-side toolkit (signing, SBOM, offline runs) is out of scope for `argo-helm`. You’d ship it as a separate CLI and have it submit evidence or artifacts. Argo just runs the workflows you define. ([GitHub][1])

* **Publication gating logic:**
  Needs to live in Calypr’s API/service. Argo supplies run results; your service enforces `requiredWorkflows` before allowing publication. ([GitHub][1])

* **DRS/Indexd updates:**
  Implement as workflow steps (containers) or post-run webhooks in your API; Argo executes them, but the contract to Indexd/DRS is your code. ([GitHub][1])



## 🌟 Overview

This repository provides a **complete Kubernetes-native GitOps and workflow automation platform** that combines:

- **🔄 Argo Workflows** - Kubernetes-native workflow engine
- **📦 Argo CD** - Declarative GitOps continuous delivery
- **🔐 Authorization Adapter** - Enterprise-grade RBAC with OIDC integration
- **🚪 NGINX Ingress** - Secure external access with per-request authorization
- **📊 Artifact Management** - S3-compatible storage for workflow artifacts

### Two Deployment Options

| Method | Use Case | Complexity | Customization |
|--------|----------|------------|---------------|
| **🎯 Helm Chart** | Production deployments | Medium | High |
| **⚡ Bash Installer** | Quick testing/demos | Low | Limited |

---

## ✨ Features

### 🔧 Core Components
- **Argo Workflows** (v0.41.7) - Container-native workflow execution
- **Argo CD** (v7.6.12) - GitOps continuous delivery
- **Custom AuthZ Adapter** - Flask-based authorization service
- **Multi-tenant RBAC** - Namespace isolation and role-based access

### 🔒 Security Features
- **OIDC Integration** - Seamless authentication with Fence/Gen3
- **Per-request Authorization** - Real-time access control
- **Service Account Management** - Automated RBAC configuration
- **Secure Artifact Storage** - S3-compatible with encryption support

### 🌐 Infrastructure
- **NGINX Ingress Ready** - Production-grade external access
- **Namespace Isolation** - Clean multi-tenant architecture
- **Health Monitoring** - Built-in health checks and observability
- **One-click Teardown** - Clean uninstall capability

---

## 🏗 Architecture

```mermaid
graph TB
    subgraph "External"
        U[👤 Users<br/>Browser & CLI]
        GH[📦 Git Repository<br/>nextflow-hello-project]
        FENCE[🔐 Fence OIDC<br/>calypr-dev.ohsu.edu]
    end

    subgraph "Kubernetes Cluster"
        subgraph "Ingress Layer"
            NG[🌐 NGINX Ingress<br/>SSL Termination]
        end
        
        subgraph "Security Namespace"
            AD[🛡️ AuthZ Adapter<br/>Flask Service]
        end
        
        subgraph "ArgoCD Namespace"
            ACD[📦 Argo CD Server<br/>GitOps Controller]
        end
        
        subgraph "Argo Namespace"
            AWS[🔄 Argo Workflows<br/>Server & UI]
            AWC[⚙️ Workflow Controller<br/>Job Execution]
        end
        
        subgraph "Tenant Namespace (wf-poc)"
            WF[📋 Workflows<br/>Running Jobs]
            SA[👥 Service Accounts<br/>RBAC Roles]
        end
        
        subgraph "Storage"
            S3[🗄️ S3 Compatible<br/>Artifact Repository]
        end
    end

    %% User flows
    U -->|HTTPS Requests| NG
    NG -->|Auth Check| AD
    AD -->|Validate Token| FENCE
    
    %% Service routing
    NG -->|Authorized Traffic| ACD
    NG -->|Authorized Traffic| AWS
    
    %% Internal workflows
    ACD -->|Deploy Workflows| AWC
    AWS -->|Submit Jobs| AWC
    AWC -->|Execute| WF
    AWC -->|Store Artifacts| S3
    ACD -->|Sync from Git| GH

    %% Styling
    classDef external fill:#e1f5fe
    classDef security fill:#f3e5f5
    classDef argo fill:#e8f5e8
    classDef storage fill:#fff3e0
    
    class U,GH,FENCE external
    class AD,NG security
    class ACD,AWS,AWC,WF,SA argo
    class S3 storage
```

### 🔄 Request Flow

1. **User Authentication** - OIDC token validation via Fence
2. **Authorization Check** - Custom adapter validates permissions
3. **Request Routing** - NGINX forwards to appropriate services
4. **Workflow Execution** - Argo components handle job lifecycle
5. **Artifact Storage** - S3-compatible backend for persistence

---

## 🔧 Prerequisites

### Infrastructure Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| **Kubernetes** | ≥ v1.20 | Tested with v1.24+ |
| **Helm** | ≥ v3.0 | Package manager |
| **kubectl** | Latest | K8s CLI tool |
| **NGINX Ingress** | ≥ v1.0 | *Optional for external access* |

### Resource Requirements

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| **Argo Workflows** | 200m | 512Mi | 10Gi |
| **Argo CD** | 100m | 256Mi | 5Gi |
| **AuthZ Adapter** | 50m | 128Mi | - |
| **Total Minimum** | 350m | 896Mi | 15Gi |

### External Dependencies

- **S3-Compatible Storage** (MinIO, AWS S3, etc.)
- **OIDC Provider** (Fence, Auth0, etc.)
- **DNS** (for ingress hostnames)

---

## 🚀 Quick Start

### Helm Deployment

#### 1️⃣ Setup Prerequisites

```bash
# Add Argo Helm repository
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Verify Kubernetes access
kubectl cluster-info
```

#### 2️⃣ Configure Values

Create your configuration file:

```bash
cat > my-values.yaml <<YAML
# 🏗️ Namespace Configuration
namespaces:
  argo: argo                    # Argo Workflows namespace
  argocd: argocd               # Argo CD namespace  
  tenant: wf-poc               # Workflow execution namespace
  security: security           # AuthZ adapter namespace

# 🗄️ S3 Artifact Storage
s3:
  enabled: true
  hostname: "minio.storage.local"    # Your S3 endpoint
  bucket: "argo-artifacts"
  region: "us-west-2"
  insecure: true                     # Set false for HTTPS
  pathStyle: true                    # MinIO compatibility
  accessKey: "your-access-key"       # S3 credentials
  secretKey: "your-secret-key"

# 🔐 Authorization Adapter
authzAdapter:
  image: "ghcr.io/yourorg/authz-adapter:latest"
  fenceBase: "https://calypr-dev.ohsu.edu/user"
  replicas: 2                        # HA deployment
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi

# 🔄 Argo Workflows Configuration
argoWorkflows:
  enabled: true
  serverAuthMode: "server"           # Options: server, sso, client
  
# 📦 Argo CD Configuration  
argoCD:
  enabled: true
  
# 🎯 Sample Application (Optional)
argocdApplication:
  enabled: true
  repoURL: "https://github.com/bwalsh/nextflow-hello-project.git"
  targetRevision: "main"
  path: "."
YAML
```

#### 3️⃣ Deploy the Stack

```bash
# Install with custom values
helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd \
  --create-namespace \
  --values my-values.yaml \
  --wait \
  --timeout 10m

# Verify deployment
kubectl get pods -n argocd
kubectl get pods -n argo
kubectl get pods -n security
```

#### 4️⃣ Access the UIs

```bash
# Port forward for local access
kubectl -n argo port-forward svc/argo-workflows-server 2746:2746 &
kubectl -n argocd port-forward svc/argocd-server 8080:80 &

# Open in browser
echo "🔄 Argo Workflows: http://localhost:2746"
echo "📦 Argo CD: http://localhost:8080"

# Get ArgoCD initial password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

### Script-based Installation

#### 1️⃣ Set Environment Variables

```bash
# 🗄️ S3 Configuration
export ARTIFACT_S3_HOSTNAME=minio.storage.local
export ARTIFACT_BUCKET=argo-artifacts
export ARTIFACT_REGION=us-west-2
export ARTIFACT_INSECURE=true
export ARTIFACT_PATH_STYLE=true
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

# 🔐 AuthZ Configuration
export AUTHZ_ADAPTER_IMAGE=ghcr.io/yourorg/authz-adapter:latest
export FENCE_BASE=https://calypr-dev.ohsu.edu/user

# 🏗️ Optional: Custom Namespaces
export WF_NS=wf-poc
export ARGO_NS=argo
export ARGOCD_NS=argocd
export SEC_NS=security
```

#### 2️⃣ Deploy

```bash
# Make script executable
chmod +x install_argo_stack.sh

# Install the stack
./install_argo_stack.sh

# Verify installation
kubectl get namespaces | grep -E "(argo|security|wf-poc)"
```

#### 3️⃣ Teardown (if needed)

```bash
# Complete cleanup
./install_argo_stack.sh --teardown

# Or use short form
./install_argo_stack.sh -t
```

---

## ⚙️ Configuration

### 🔐 Authorization Adapter Configuration

The authorization adapter supports flexible configuration:

```yaml
authzAdapter:
  # Container configuration
  image: "ghcr.io/yourorg/authz-adapter:latest"
  tag: "v1.0.0"
  pullPolicy: "IfNotPresent"
  
  # Service configuration
  service:
    type: ClusterIP
    port: 8080
    
  # Fence/OIDC integration
  fenceBase: "https://your-oidc-provider.com"
  serviceToken: "optional-service-token"
  httpTimeout: "5.0"
  
  # Resource allocation
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m  
      memory: 256Mi
      
  # High availability
  replicas: 2
  
  # Health checks
  livenessProbe:
    enabled: true
    path: /healthz
  readinessProbe:
    enabled: true
    path: /healthz
```

---

## 🔒 Security & Authorization

### 🎯 Authorization Model

The authorization adapter implements a **role-based access control** system:

| Role | Permissions | Use Case |
|------|-------------|----------|
| **argo-viewer** | Read-only access | Monitoring, auditing |
| **argo-runner** | Submit & manage workflows | Developers, CI/CD |
| **argo-admin** | Full administrative access | Platform administrators |

### 🔐 NGINX Ingress Integration

Enable per-request authorization by adding these annotations to your Ingress resources:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argo-workflows-ingress
  annotations:
    # 🔐 Enable authorization
    nginx.ingress.kubernetes.io/auth-url: "http://authz-adapter.security.svc.cluster.local:8080/check"
    nginx.ingress.kubernetes.io/auth-method: "GET"
    
    # 📤 Forward user context
    nginx.ingress.kubernetes.io/auth-snippet: |
      proxy_set_header Authorization $http_authorization;
      proxy_set_header X-Original-URI $request_uri;
      proxy_set_header X-Original-Method $request_method;
      
    # 📥 Response headers
    nginx.ingress.kubernetes.io/auth-response-headers: "X-Auth-Request-User,X-Auth-Request-Email,X-Auth-Request-Groups"
    
    # 🚫 Error handling
    nginx.ingress.kubernetes.io/auth-signin: "https://your-login-page.com/login"
    
spec:
  rules:
  - host: workflows.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argo-workflows-server
            port:
              number: 2746
```

### 🔑 OIDC Integration

For production deployments, configure direct OIDC integration:

```yaml
# Argo CD OIDC
argoCD:
  server:
    config:
      oidc.config: |
        name: OIDC
        issuer: https://calypr-dev.ohsu.edu/user
        clientId: argo-cd
        clientSecret: $oidc.clientSecret
        requestedScopes: ["openid", "profile", "email", "groups"]
        requestedIDTokenClaims: {"groups": {"essential": true}}

# Argo Workflows OIDC        
argoWorkflows:
  server:
    sso:
      issuer: https://calypr-dev.ohsu.edu/user
      clientId:
        name: argo-workflows-sso
        key: client-id
      clientSecret:
        name: argo-workflows-sso  
        key: client-secret
      redirectUrl: https://workflows.example.com/oauth2/callback
      scopes:
        - openid
        - profile
        - email
        - groups
```

---

## 📊 Monitoring & Troubleshooting

### 🔍 Health Checks

```bash
# Check all component health
kubectl get pods -n argocd
kubectl get pods -n argo  
kubectl get pods -n security
kubectl get pods -n wf-poc

# AuthZ adapter health
kubectl -n security port-forward svc/authz-adapter 8080:8080 &
curl http://localhost:8080/healthz

# Argo Workflows health
kubectl -n argo get workflows

# Argo CD health  
kubectl -n argocd get applications
```

### 📝 Logging

```bash
# AuthZ adapter logs
kubectl -n security logs -l app=authz-adapter -f

# Argo Workflows controller logs
kubectl -n argo logs -l app.kubernetes.io/name=argo-workflows-workflow-controller -f

# Argo CD logs
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-server -f
```

### 🐛 Common Issues

<details>
<summary><strong>🔴 AuthZ Adapter Returns 401</strong></summary>

**Symptoms:** NGINX returns 401 Unauthorized

**Causes & Solutions:**
- **Invalid OIDC token:** Check token format and expiration
- **Fence endpoint unreachable:** Verify `FENCE_BASE` URL and network access
- **Missing service token:** Set `FENCE_SERVICE_TOKEN` if required

```bash
# Debug token validation
kubectl -n security exec -it deployment/authz-adapter -- \
  curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/check -v
```
</details>

<details>
<summary><strong>🔴 Workflows Fail to Submit</strong></summary>

**Symptoms:** "Forbidden" errors when submitting workflows

**Causes & Solutions:**
- **RBAC misconfiguration:** Check service account permissions
- **Namespace access:** Verify workflow namespace exists and is configured
- **Resource quotas:** Check if resource limits are exceeded

```bash
# Check RBAC
kubectl -n wf-poc get rolebindings
kubectl auth can-i create workflows --as=system:serviceaccount:wf-poc:default -n wf-poc

# Check quotas
kubectl -n wf-poc describe quota
```
</details>

<details>
<summary><strong>🔴 S3 Artifact Upload Fails</strong></summary>

**Symptoms:** Workflows complete but artifacts not stored

**Causes & Solutions:**
- **Incorrect S3 configuration:** Verify endpoint, credentials, bucket
- **Network connectivity:** Check if pods can reach S3 endpoint
- **Bucket permissions:** Ensure write access to specified bucket

```bash
# Test S3 connectivity from workflow pod
kubectl -n wf-poc run test-s3 --image=amazon/aws-cli:latest \
  --env="AWS_ACCESS_KEY_ID=$ACCESS_KEY" \
  --env="AWS_SECRET_ACCESS_KEY=$SECRET_KEY" \
  --command -- aws s3 ls s3://your-bucket --endpoint-url=http://your-s3-endpoint
```
</details>

---

## 🎯 Advanced Usage

### 🔧 Custom Authorization Logic

Extend the authorization adapter with custom business logic:

```python
# authz-adapter/app.py

def decide_groups(doc, verb=None, group=None, version=None, resource=None, namespace=None):
    """
    Custom authorization logic based on your requirements
    """
    groups = []
    
    if not doc.get("active"):
        return groups
    
    # Custom logic: Grant admin access to specific users
    if doc.get("email") in ["admin@example.com", "devops@example.com"]:
        groups.append("argo-admin")
        groups.append("argo-runner")
        groups.append("argo-viewer")
        return groups
    
    # Custom logic: Department-based access
    authz = doc.get("authz", {})
    departments = doc.get("departments", [])
    
    if "engineering" in departments:
        if any(item.get("method") in ("create", "*") 
               for item in authz.get("/workflows/submit", [])):
            groups.append("argo-runner")
            
    if "operations" in departments:
        groups.append("argo-viewer")
        
    return groups
```

### 🚀 Multi-Environment Setup

Deploy multiple stacks for different environments:

```bash
# Development environment
helm upgrade --install argo-stack-dev ./helm/argo-stack \
  --namespace argocd-dev \
  --values values-dev.yaml

# Staging environment  
helm upgrade --install argo-stack-staging ./helm/argo-stack \
  --namespace argocd-staging \
  --values values-staging.yaml
  
# Production environment
helm upgrade --install argo-stack-prod ./helm/argo-stack \
  --namespace argocd-prod \
  --values values-prod.yaml
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### 🏗️ Development Setup

```bash
# Clone the repository
git clone https://github.com/calypr/argo-helm.git
cd argo-helm

# Install development dependencies
pip install -r authz-adapter/requirements-dev.txt

# Run tests
cd authz-adapter
python -m pytest tests/

# Build adapter image
docker build -t authz-adapter:dev .
```

### 📋 Reporting Issues

Please use our [issue tracker](https://github.com/calypr/argo-helm/issues) with:

- **🐛 Bug reports:** Include logs, configuration, and reproduction steps
- **✨ Feature requests:** Describe the use case and expected behavior  
- **📚 Documentation:** Suggestions for improving this README

### 🎯 Roadmap

- [ ] **Multi-cluster support** - Deploy across multiple Kubernetes clusters
- [ ] **Advanced RBAC** - Fine-grained permissions and audit logging
- [ ] **Webhook integration** - External workflow triggers
- [ ] **Observability** - Enhanced monitoring and alerting
- [ ] **Backup/Restore** - Automated disaster recovery

---

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Argo Project](https://argoproj.github.io/) for the excellent workflow and GitOps tools
- [Gen3](https://gen3.org/) for the Fence OIDC integration patterns
- [OHSU](https://www.ohsu.edu/) for supporting this open-source initiative

---

<div align="center">

**⭐ Star this repo if it helped you!**

[Report Bug](https://github.com/calypr/argo-helm/issues/new?labels=bug) •
[Request Feature](https://github.com/calypr/argo-helm/issues/new?labels=enhancement) •
[View Documentation](https://github.com/calypr/argo-helm/wiki)

</div>
