[Home](index.md) > Development and Engineering Notes


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

For local development and testing, the Makefile automatically deploys MinIO inside your Kubernetes cluster to provide S3-compatible object storage without requiring AWS.

### Quick Start with MinIO

The `make deploy` target automatically:
1. Creates a Kind cluster
2. Deploys MinIO inside the cluster
3. Deploys the Argo stack configured to use MinIO

```bash
# Set required environment variables
export GITHUB_PAT=<your-github-token>
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)
export ARGO_HOSTNAME=<your-hostname>

# Deploy everything (includes MinIO)
make deploy
```

### Manual MinIO Deployment

To deploy only MinIO to an existing cluster:

```bash
make minio
```

This deploys MinIO using Helm with the following configuration:
- **Namespace**: `minio-system`
- **Endpoint**: `minio.minio-system.svc.cluster.local:9000`
- **Access Key**: `minioadmin`
- **Secret Key**: `minioadmin`
- **Mode**: Standalone (single instance)
- **Persistence**: Disabled (data is ephemeral)
- **Resources**: 512Mi memory request, 1Gi limit (optimized for Kind/Minikube)
- **Default Bucket**: `argo-artifacts` (automatically created)
- **Protocol**: HTTP (insecure mode for development)

### MinIO Configuration

The Makefile configures the following defaults for S3/MinIO:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `S3_ENABLED` | `true` | Enable S3 artifact storage |
| `S3_ACCESS_KEY_ID` | `minioadmin` | MinIO access key |
| `S3_SECRET_ACCESS_KEY` | `minioadmin` | MinIO secret key |
| `S3_BUCKET` | `argo-artifacts` | Default bucket name |
| `S3_REGION` | `us-east-1` | AWS region (MinIO default) |
| `S3_HOSTNAME` | `minio.minio-system.svc.cluster.local:9000` | MinIO cluster endpoint |

You can override these by setting environment variables before running `make deploy`.

⚠️ **Warning**: Default credentials are for development only. Never use them in production!

### Accessing MinIO Console

To access the MinIO web console, port-forward the service:

```bash
kubectl port-forward svc/minio -n minio-system 9001:9001
```

Then open http://localhost:9001 in your browser and login with:
- Username: `minioadmin`
- Password: `minioadmin`

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
| **make deploy**        | Complete deployment: creates Kind cluster, deploys MinIO, then installs Argo stack. Uses `GITHUB_PAT`, `ARGOCD_SECRET_KEY`, and `ARGO_HOSTNAME`. |
| **make minio**         | Deploys MinIO to the cluster using Helm. Automatically called by `make deploy`. |
| **make kind**          | Creates a new Kind cluster (deletes existing one first). |
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
make deploy
```

This command:
1. Creates a Kind cluster
2. Deploys MinIO inside the cluster
3. Installs the Argo stack configured to use MinIO

The stack is deployed with:
- MinIO at `minio.minio-system.svc.cluster.local:9000`
- S3 credentials: `minioadmin` / `minioadmin`
- Default bucket: `argo-artifacts`

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

Access the MinIO Console:

```bash
# Port-forward MinIO console
kubectl port-forward svc/minio -n minio-system 9001:9001
```

Then open http://localhost:9001 in your browser and:
1. Login with `minioadmin` / `minioadmin`
2. Navigate to the `argo-artifacts` bucket
3. Browse workflow artifacts and logs

Or use the MinIO CLI:

```bash
# Install mc (MinIO Client) if needed
brew install minio/stable/mc  # macOS
# or download from https://min.io/docs/minio/linux/reference/minio-mc.html

# Port-forward MinIO S3 API
kubectl port-forward svc/minio -n minio-system 9000:9000

# Configure alias
mc alias set local http://localhost:9000 minioadmin minioadmin

# List artifacts
mc ls local/argo-artifacts/

# Download an artifact
mc cp local/argo-artifacts/wf-poc/my-workflow/main.log ./
```

### 3. Test Per-Repository Artifacts

The MinIO instance deployed by `make minio` is a single-instance server. To test per-repository artifacts, you can create buckets manually:

```bash
# Port-forward MinIO
kubectl port-forward svc/minio -n minio-system 9000:9000

# Create additional buckets
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/my-app-bucket
```

Then configure your application to use the in-cluster MinIO endpoint:

```yaml
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
      bucket: my-app-bucket
      endpoint: http://minio.minio-system.svc.cluster.local:9000
      region: us-east-1
      insecure: true
      pathStyle: true
      credentialsSecret: minio-creds
```

Create the credentials secret:

```bash
kubectl create secret generic minio-creds -n wf-poc \
  --from-literal=accessKey=minioadmin \
  --from-literal=secretKey=minioadmin
```

---

## 🔧 Troubleshooting MinIO

### MinIO Pod Not Running

```bash
# Check MinIO pod status
kubectl get pods -n minio-system

# View MinIO logs
kubectl logs -n minio-system -l app=minio

# Check MinIO service
kubectl get svc -n minio-system
```

### Workflows Can't Connect to MinIO

Verify the MinIO service is accessible from the workflow namespace:

```bash
# Test connectivity from a pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -I http://minio.minio-system.svc.cluster.local:9000

# Check if MinIO is responding
kubectl run -it --rm debug --image=amazon/aws-cli --restart=Never -- \
  aws s3 ls --endpoint-url http://minio.minio-system.svc.cluster.local:9000
```

### Reinstall MinIO

```bash
# Remove existing MinIO
helm uninstall minio -n minio-system

# Reinstall
make minio
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
