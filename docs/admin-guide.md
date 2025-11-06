# 🧰 Administrator Guide — Managing Argo Events and Nextflow Integration

This document describes how administrators configure the Argo environment so that GitHub repositories can automatically trigger **Nextflow workflows**.

---

## 🧠 Architecture Overview

```mermaid
flowchart LR
  A[GitHub Repo] -->|push webhook| B[Argo Events<br>EventSource]
  B -->|event| C[Sensor]
  C -->|submit| D[Argo Workflows]
  D -->|run| E[(Nextflow Pipeline)]
```

**Components:**
- **Argo CD** — manages deployment of charts and manifests.
- **Argo Events** — listens for GitHub events and triggers Sensors.
- **Argo Workflows** — executes Nextflow pipelines.
- **EventSource + Sensor** — glue logic between GitHub and Workflows.

---

## ⚙️ Environment Variables

Before installing via the Makefile or Helm:

```bash
export GITHUB_PAT=<github_personal_access_token>
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)
export ARGO_HOSTNAME=<public-dns-or-domain>
```

---

## 🧩 Installation via Makefile

```bash
make deploy
```

This wraps the Helm upgrade/install command for the `argo-stack` chart and sets the secrets and ingress hosts.

---

## 🔐 GitHub Token Secret

Create or verify the token secret:

```bash
kubectl -n argo-events create secret generic github-secret --from-literal=token=$GITHUB_PAT
```

---

## 🪣 Per-Repository Artifact Configuration

### Overview

The Argo stack supports **per-repository S3 buckets** for workflow artifacts. This enables:
- **Tenant isolation**: Each repository's artifacts are stored separately
- **Traceability**: Outputs are linked to source repository and commits
- **Data governance**: Per-repository retention, encryption, and access policies
- **Multi-tenancy**: Different teams can use different S3 buckets/accounts

### Configuration in values.yaml

Add an `artifacts` block to each application:

```yaml
applications:
  - name: nextflow-hello-project
    repoURL: https://github.com/bwalsh/nextflow-hello-project.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    artifacts:
      bucket: calypr-nextflow-hello
      keyPrefix: workflows/
      endpoint: https://s3.us-west-2.amazonaws.com
      region: us-west-2
      insecure: false
      credentialsSecret: s3-cred-nextflow-hello
      # Optional fields:
      # useSDKCreds: true              # Use IRSA/Workload Identity
      # pathStyle: true                # MinIO compatibility
      # accessKeyKey: accessKey        # Custom secret key name
      # secretKeyKey: secretKey        # Custom secret key name
```

### What Gets Created

When an application has an `artifacts` configuration, the Helm chart creates:

1. **ConfigMap**: `argo-artifacts-<app-name>` in `argo-workflows` namespace
   - Contains the S3 artifact repository configuration
   - Referenced by WorkflowTemplates via `artifactRepositoryRef`

2. **WorkflowTemplate**: `<app-name>-template` in the workflow namespace
   - Pre-configured with the artifact repository reference
   - Can be used by Sensors or manual workflow submissions

### Credential Management Options

#### Option 1: IRSA (AWS) - Recommended

For AWS EKS clusters, use IAM Roles for Service Accounts:

```yaml
artifacts:
  bucket: my-app-bucket
  region: us-west-2
  useSDKCreds: true  # Use pod's IAM role
```

Annotate the service account:
```bash
kubectl annotate serviceaccount wf-runner \
  -n wf-poc \
  eks.amazonaws.com/role-arn=arn:aws:iam::ACCOUNT:role/my-app-s3-access
```

#### Option 2: Workload Identity (GCP)

For GKE clusters:
```yaml
artifacts:
  bucket: my-app-bucket
  useSDKCreds: true
```

Bind service account to GCP service account:
```bash
gcloud iam service-accounts add-iam-policy-binding \
  my-app-gsa@PROJECT.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:PROJECT.svc.id.goog[wf-poc/wf-runner]"
```

#### Option 3: Static Credentials with ExternalSecrets (Recommended)

Use External Secrets Operator to sync from AWS Secrets Manager:

```yaml
# Create ExternalSecret CR
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: s3-cred-nextflow-hello
  namespace: wf-poc
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: s3-cred-nextflow-hello
  data:
    - secretKey: accessKey
      remoteRef:
        key: nextflow-hello/s3-credentials
        property: access_key
    - secretKey: secretKey
      remoteRef:
        key: nextflow-hello/s3-credentials
        property: secret_key
```

Then reference in values.yaml:
```yaml
artifacts:
  bucket: calypr-nextflow-hello
  credentialsSecret: s3-cred-nextflow-hello
```

#### Option 4: Static Credentials Secret (Development Only)

**⚠️ Not recommended for production**

```bash
kubectl create secret generic s3-cred-nextflow-hello \
  -n wf-poc \
  --from-literal=accessKey=AKIAIOSFODNN7EXAMPLE \
  --from-literal=secretKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

### MinIO Configuration

For on-premise MinIO deployments:

```yaml
artifacts:
  bucket: nextflow-hello
  endpoint: http://minio.storage.svc.cluster.local:9000
  region: us-east-1
  insecure: true       # HTTP instead of HTTPS
  pathStyle: true      # Required for MinIO
  credentialsSecret: s3-cred-nextflow-hello
```

### Verification

After deploying:

```bash
# 1. Check ConfigMap created
kubectl -n argo-workflows get cm argo-artifacts-nextflow-hello-project -o yaml

# 2. Verify WorkflowTemplate
kubectl -n wf-poc get workflowtemplate nextflow-hello-project-template -o yaml

# 3. Test artifact upload (submit a test workflow)
argo -n wf-poc submit --from workflowtemplate/nextflow-hello-project-template

# 4. Check S3 bucket
aws s3 ls s3://calypr-nextflow-hello/workflows/
```

### Global Fallback

Applications without an `artifacts` configuration will use the global S3 settings:

```yaml
s3:
  enabled: true
  hostname: "minio.storage.local"
  bucket: "argo-artifacts"
  region: "us-west-2"
  accessKey: "..."
  secretKey: "..."
```

This creates a ConfigMap `artifact-repositories` in the `argo-workflows` namespace.

### Security Best Practices

1. **Never commit credentials** to Git repositories
2. **Use IRSA/Workload Identity** when possible
3. **Rotate credentials** regularly via ExternalSecrets
4. **Apply least-privilege** IAM policies per repository
5. **Enable S3 encryption** at rest and in transit
6. **Configure bucket policies** to restrict access by prefix
7. **Set lifecycle policies** for automatic cleanup of old artifacts

### Example IAM Policy (IRSA)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::calypr-nextflow-hello/workflows/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::calypr-nextflow-hello",
      "Condition": {
        "StringLike": {
          "s3:prefix": "workflows/*"
        }
      }
    }
  ]
}
```

---

## 🪣 Workflow Configuration

Sensors trigger WorkflowTemplates such as:

```yaml
spec:
  dependencies:
    - name: push
      eventSourceName: github
      eventName: repo-push
  triggers:
    - template:
        argoWorkflow:
          source:
            resource:
              metadata:
                generateName: nextflow-hello-
                namespace: wf-poc
              spec:
                entrypoint: main
                workflowTemplateRef:
                  name: nextflow-hello-template
```

Ensure that the referenced `WorkflowTemplate` exists in `wf-poc` or `argo`.

---

## 🔏 RBAC Configuration

Sensors need permission to submit workflows to the target namespace.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: argo-events-workflow-submit
  namespace: argo
rules:
  - apiGroups: ["argoproj.io"]
    resources: ["workflows", "workflowtemplates"]
    verbs: ["get", "list", "watch", "create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: argo-events-workflow-submit
  namespace: argo
subjects:
  - kind: ServiceAccount
    name: argo-events-sa
    namespace: argo-events
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: argo-events-workflow-submit
```

---

## 🌐 Network and Ports

| Port | Service | Purpose |
|------|----------|----------|
| 8080 / 443 | Argo CD server | Web UI |
| 2746 | Argo Workflows server | Workflow UI |
| 12000 | GitHub EventSource | Webhook endpoint |
| 80 / 443 | NGINX ingress | External entrypoint |

---

## 🔍 Troubleshooting

### EventSource says “no need to create webhooks”
→ Either `apiToken` is missing or `webhook.url` is empty.

### Ingress validation errors
→ Ensure either `rules` or `defaultBackend` is present.

### Webhook not firing
- Verify GitHub PAT scopes.
- Check EventSource logs:
  ```bash
  kubectl -n argo-events logs -l eventsource-name=github
  ```

### Workflows not created
- Check Sensor logs:
  ```bash
  kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push
  ```
- Verify RBAC and WorkflowTemplate existence.

---

## 🧭 Post-Install Access

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443 &
kubectl -n argo port-forward svc/argo-workflows-server 2746:2746 &
```

- **Argo CD UI:** http://localhost:8080  
- **Argo Workflows UI:** http://localhost:2746

---

## 🧹 Uninstall

```bash
kind delete cluster;
```

Removes all Argo resources and namespaces.

---

## ✅ Summary

| Component | Purpose | Namespace |
|------------|----------|------------|
| **Argo CD** | GitOps + chart management | `argocd` |
| **Argo Events** | GitHub event listener | `argo-events` |
| **Argo Workflows** | Workflow execution engine | `argo` |
| **Nextflow templates** | Reusable workflow definitions | `wf-poc` or `argo` |

---

This configuration enables a Git-driven automation pipeline where each push event runs a reproducible Nextflow workflow in the Argo environment.
