
# 🧑‍💻 Argo Stack Development Guide

This document explains how to use the **Makefile** in this repository to deploy, test, and iterate on the Argo stack locally or in a development Kubernetes cluster.

---

## ⚙️ Prerequisites

Before using the Makefile, ensure you have:

- **kubectl** (≥ v1.25)
- **Helm** (≥ v3.10)
- **make**
- A running **Kubernetes cluster** (e.g. kind, minikube, or EKS)
- **Docker** and **Docker Compose** (for local MinIO)
- Internet connectivity for pulling Argo container images

---

## 🗄️ Local MinIO for Development

For local development and testing, you can run a MinIO instance to provide S3-compatible object storage without requiring AWS.

### Quick Start with MinIO

1. **Start MinIO**:
   ```bash
   ./dev-minio.sh start
   ```

2. **Access MinIO Console**:
   - URL: http://localhost:9001
   - Username: `minioadmin`
   - Password: `minioadmin`

3. **Use MinIO in Helm deployment**:
   ```bash
   helm upgrade --install argo-stack ./helm/argo-stack \
     --namespace argocd --create-namespace \
     --values local-dev-values.yaml \
     --wait
   ```

### MinIO Helper Commands

The `dev-minio.sh` script provides several useful commands:

| Command | Description |
|---------|-------------|
| `./dev-minio.sh start` | Start MinIO server and create default buckets |
| `./dev-minio.sh stop` | Stop MinIO server (preserves data) |
| `./dev-minio.sh clean` | Stop MinIO and delete all data |
| `./dev-minio.sh status` | Check if MinIO is running |
| `./dev-minio.sh logs` | Show MinIO logs (follow mode) |
| `./dev-minio.sh values` | Print Helm values for MinIO config |

### Default MinIO Buckets

The MinIO setup automatically creates these buckets:
- `argo-artifacts` - Global artifacts (production-like)
- `argo-artifacts-dev` - Development artifacts
- `calypr-nextflow-hello` - Example app bucket
- `calypr-nextflow-hello-2` - Example app bucket

### MinIO Configuration

The MinIO instance runs with these defaults:

| Setting | Value |
|---------|-------|
| **S3 API Endpoint** | `http://localhost:9000` |
| **Console URL** | `http://localhost:9001` |
| **Access Key** | `minioadmin` |
| **Secret Key** | `minioadmin` |
| **Region** | `us-east-1` |

⚠️ **Warning**: These are development credentials only. Never use them in production!

### Using MinIO with Helm

See `local-dev-values.yaml` for a complete configuration example. Key settings:

```yaml
s3:
  enabled: true
  hostname: "localhost:9000"
  bucket: "argo-artifacts-dev"
  region: "us-east-1"
  insecure: true      # HTTP instead of HTTPS
  pathStyle: true     # Required for MinIO
  accessKey: "minioadmin"
  secretKey: "minioadmin"
```

---

## 🌱 Environment Setup

The Makefile expects three environment variables:

```bash
export GITHUB_PAT=<your-personal-access-token>
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)
export ARGO_HOSTNAME=<your-hostname-or-elb>
````

### 🔑 Variable details

| Variable              | Description                                                                                                                                                                                                                                                   | Example                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **GITHUB_PAT**        | GitHub Personal Access Token used by the Argo Events GitHub EventSource to automatically create a webhook. Must include scopes:<br>Fine-grained → **Webhooks: Read/Write**, **Contents: Read**, **Metadata: Read**<br>Classic → **repo**, **admin:repo_hook** | `github_pat_11AAALVQA0n9Un6...`                     |
| **ARGOCD_SECRET_KEY** | Used by Argo CD server for JWT signing. Generate with `openssl rand -hex 32`.                                                                                                                                                                                 | `439db941bec3bdcf...`                               |
| **ARGO_HOSTNAME**     | The external DNS name or public hostname where the Argo CD and Workflows UIs will be reachable.                                                                                                                                                               | `ec2-34-217-38-185.us-west-2.compute.amazonaws.com` |

You can persist these in your shell profile, or source a local `.env` file before running make commands.

---

## 🧩 Makefile Targets

Common developer targets (run with `make <target>`):

| Target                 | Description                                                                                                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **make install**       | Installs or upgrades the full Argo stack Helm chart (`helm/argo-stack`) into the `argocd` and `argo-events` namespaces. Uses `GITHUB_PAT`, `ARGOCD_SECRET_KEY`, and `ARGO_HOSTNAME`. |
| **make logs**          | Streams logs from Argo CD, Argo Workflows, and Argo Events pods for debugging.                                                                                                       |
| **make port-forward**  | Starts local port-forwards for Argo CD (8080→443) and Argo Workflows (2746).                                                                                                         |
| **make uninstall**     | Removes all Argo stack resources and namespaces.                                                                                                                                     |
| **make stern-install** | Installs the `stern` log-tailing utility on Linux.                                                                                                                                   |

---

## 🌐 Required Network Ports

| Port           | Service                             | Purpose                            |
| -------------- | ----------------------------------- | ---------------------------------- |
| **443 / 8080** | Argo CD server                      | Web UI and API access              |
| **2746**       | Argo Workflows server               | Workflow UI and API                |
| **12000**      | GitHub EventSource                  | GitHub → Argo Events webhook       |
| **80 / 443**   | (Optional) NGINX Ingress controller | Public ingress for external access |

If you’re running on EC2, ensure these ports are open in your instance’s security group.

---

## 🚀 Deploying the Stack

```bash
make install
```

This command wraps:

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd --create-namespace \
  --wait --atomic \
  --set-string events.github.secret.tokenValue="${GITHUB_PAT}" \
  --set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
  --set-string events.github.webhook.ingress.enabled=true \
  --set-string events.github.webhook.ingress.className=nginx \
  --set-string events.github.webhook.ingress.hosts[0]="${ARGO_HOSTNAME}"
```

After deployment:

```bash
kubectl get pods -A | grep argo
```

All Argo pods should be in **Running** state.

---

## 🔓 Getting the Argo CD Admin Password

```bash
ARGOCD_POD=$(kubectl -n argocd get pod -l app.kubernetes.io/name=argocd-server -o name)
kubectl -n argocd exec -it ${ARGOCD_POD} -- argocd admin initial-password
```

Copy the password and log in at:

```
https://<ARGO_HOSTNAME>:8080
```

Username: **admin**
Password: *(value above)*

---

## 🧭 Accessing the UIs

### Option A — Port Forward (local testing)

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443 &
kubectl -n argo port-forward svc/argo-workflows-server 2746:2746 &
```

* **Argo CD UI:** [http://localhost:8080](http://localhost:8080)
* **Argo Workflows UI:** [http://localhost:2746](http://localhost:2746)

### Option B — Ingress (if configured)

* **Argo CD:** `https://argocd.${ARGO_HOSTNAME}`
* **Workflows:** `https://argo.${ARGO_HOSTNAME}`
* **Events Webhook:** `https://${ARGO_HOSTNAME}/events`

---

## 🔁 Testing GitHub Push → Workflow Trigger

1. Ensure the **GitHub EventSource** is running:

   ```bash
   kubectl -n argo-events get eventsource
   kubectl -n argo-events logs -l eventsource-name=github
   ```

2. Verify the webhook exists in your repository:
   **GitHub → Settings → Webhooks**

   You should see an entry pointing to:

   ```
   https://${ARGO_HOSTNAME}/events
   ```

3. Push a commit to your repository’s default branch:

   ```bash
   git commit --allow-empty -m "Trigger Argo workflow"
   git push
   ```

4. Confirm the event reached the cluster:

   ```bash
   kubectl -n argo-events logs -l eventsource-name=github | grep push
   kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push | grep trigger
   ```

5. View the triggered workflow:

   ```bash
   kubectl -n argo get wf
   ```

6. Open the Workflows UI ([http://localhost:2746](http://localhost:2746) or Ingress URL) to visualize execution.

---

## 🧹 Cleanup

```bash
make uninstall
```

This removes all Argo resources and namespaces.

To also clean up MinIO:

```bash
./dev-minio.sh clean
```

---

## 🧪 Testing Workflows with MinIO

Once you have the stack deployed with MinIO, you can test workflow artifact storage:

### 1. Submit a Test Workflow

```bash
# List available workflow templates
kubectl -n wf-poc get workflowtemplate

# Submit the example template
argo -n wf-poc submit --from workflowtemplate/nextflow-hello-template

# Watch the workflow
argo -n wf-poc watch @latest
```

### 2. Verify Artifacts in MinIO

Open the MinIO Console at http://localhost:9001 and:
1. Login with `minioadmin` / `minioadmin`
2. Navigate to the `argo-artifacts-dev` bucket
3. Browse workflow artifacts and logs

Or use the MinIO CLI:

```bash
# Install mc (MinIO Client) if needed
brew install minio/stable/mc  # macOS
# or download from https://min.io/docs/minio/linux/reference/minio-mc.html

# Configure alias
mc alias set local http://localhost:9000 minioadmin minioadmin

# List artifacts
mc ls local/argo-artifacts-dev/

# Download an artifact
mc cp local/argo-artifacts-dev/wf-poc/my-workflow/main.log ./
```

### 3. Test Per-Repository Artifacts

Create a test application with dedicated bucket:

```bash
cat > my-test-app.yaml <<EOF
applications:
  - name: test-workflow
    repoURL: https://github.com/YOUR_ORG/YOUR_REPO.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
    artifacts:
      bucket: calypr-nextflow-hello
      endpoint: http://localhost:9000
      region: us-east-1
      insecure: true
      pathStyle: true
      credentialsSecret: minio-creds
EOF

# Create credentials secret
kubectl create secret generic minio-creds -n wf-poc \
  --from-literal=accessKey=minioadmin \
  --from-literal=secretKey=minioadmin

# Deploy with your application
helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd \
  --values local-dev-values.yaml \
  --values my-test-app.yaml \
  --wait
```

---

## 🔧 Troubleshooting MinIO

### MinIO Won't Start

```bash
# Check if containers are running
docker-compose ps

# View logs
docker-compose logs minio

# Ensure ports are not in use
lsof -i :9000
lsof -i :9001
```

### Workflows Can't Connect to MinIO

If running in Kind/Minikube, workflows inside the cluster can't reach `localhost:9000`. Options:

**Option 1: Use host.docker.internal (Docker Desktop)**
```yaml
s3:
  hostname: "host.docker.internal:9000"
```

**Option 2: Deploy MinIO inside the cluster**
```bash
# Deploy MinIO using Helm
helm repo add minio https://charts.min.io/
helm install minio minio/minio \
  --namespace minio-system --create-namespace \
  --set rootUser=minioadmin \
  --set rootPassword=minioadmin \
  --set persistence.enabled=false \
  --set mode=standalone

# Then use cluster endpoint
s3:
  hostname: "minio.minio-system.svc.cluster.local:9000"
```

**Option 3: Run Kind with extra port mappings**
```bash
# Delete existing cluster
kind delete cluster

# Create with port mapping
cat > kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30900
    hostPort: 9000
    protocol: TCP
EOF

kind create cluster --config kind-config.yaml

# Expose MinIO via NodePort
kubectl create service nodeport minio-external \
  --tcp=9000:9000 --node-port=30900
```

### Artifacts Not Appearing

```bash
# Check workflow logs
argo -n wf-poc logs @latest

# Verify ConfigMap exists
kubectl -n argo-workflows get cm artifact-repositories -o yaml

# Check service account permissions
kubectl -n wf-poc describe sa wf-runner
```

---

## 🧠 Tips

* Render manifests for inspection:

  ```bash
  make template
  ```
* Debug Helm chart values:

  ```bash
  helm get values argo-stack -n argocd -a
  ```
* Tail logs for all Argo components:

  ```bash
  make logs
  ```
