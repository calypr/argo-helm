# Examples

This directory contains example configurations for the Argo Stack Helm chart.

> **⚠️ IMPORTANT**: The chart's default `values.yaml` does NOT include any repository configurations. 
> You MUST provide your own repository URLs and settings at deployment time using these examples as templates.

## Quick Start

For local development and testing, use the pre-configured local development values:

```bash
# Start local MinIO (S3-compatible storage)
./dev-minio.sh start

# Deploy with local development configuration
helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd --create-namespace \
  --values local-dev-values.yaml \
  --wait
```

This will deploy the stack without any applications, allowing you to add your own.

## Per-Repository Artifact Configuration

**File:** `per-repo-artifacts-values.yaml`

This example demonstrates how to configure multiple applications with separate S3 buckets for workflow artifacts, enabling:

- **Tenant isolation**: Each repository's artifacts stored separately
- **Traceability**: Outputs linked to source repository and commits
- **Data governance**: Per-repository retention, encryption, and access policies
- **Multi-tenancy**: Different teams using different S3 buckets/accounts

### Key Features Demonstrated

1. **Application 1 (nextflow-hello-project)**
   - Uses IRSA (IAM Roles for Service Accounts) for AWS authentication
   - Dedicated S3 bucket: `calypr-nextflow-hello`
   - No static credentials stored in Kubernetes

2. **Application 2 (nextflow-hello-project-2)**
   - Uses static credentials via Kubernetes Secret
   - Dedicated S3 bucket: `calypr-nextflow-hello-2`
   - Separate bucket for tenant isolation

3. **Application 3 (generic-workflow-app)**
   - No specific artifacts configuration
   - Falls back to global S3 settings
   - Demonstrates backward compatibility

### Usage

Deploy with this example configuration:

```bash
# For IRSA (Application 1), first annotate the service account:
kubectl annotate serviceaccount wf-runner \
  -n wf-poc \
  eks.amazonaws.com/role-arn=arn:aws:iam::ACCOUNT_ID:role/nextflow-hello-s3-access

# For static credentials (Application 2), create the secret:
kubectl create secret generic s3-cred-nextflow-hello-2 \
  -n wf-poc \
  --from-literal=accessKey=YOUR_ACCESS_KEY \
  --from-literal=secretKey=YOUR_SECRET_KEY

# Deploy the stack:
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd \
  --create-namespace \
  --values examples/per-repo-artifacts-values.yaml \
  --wait
```

### Verification

After deployment, verify the resources were created:

```bash
# Check ConfigMaps for artifact configurations
kubectl -n argo-workflows get cm -l app.kubernetes.io/component=artifact-repository

# View a specific app's artifact config
kubectl -n argo-workflows get cm argo-artifacts-nextflow-hello-project -o yaml

# Check WorkflowTemplates
kubectl -n wf-poc get workflowtemplate

# Verify a WorkflowTemplate references the correct artifact repository
kubectl -n wf-poc get workflowtemplate nextflow-hello-project-template -o yaml | grep -A3 artifactRepositoryRef
```

### Testing Artifact Upload

Submit a test workflow and verify artifacts are stored in the correct bucket:

```bash
# Submit a test workflow
argo -n wf-poc submit --from workflowtemplate/nextflow-hello-project-template

# Check the workflow status
argo -n wf-poc list

# Verify artifacts in S3 (for app 1)
aws s3 ls s3://calypr-nextflow-hello/workflows/

# Verify artifacts in S3 (for app 2)
aws s3 ls s3://calypr-nextflow-hello-2/workflows/
```

### Security Notes

1. **IRSA is recommended** for production AWS deployments
2. **Never commit credentials** to version control
3. **Use External Secrets Operator** for static credentials when IRSA isn't available
4. **Apply least-privilege IAM policies** per repository
5. **Enable S3 encryption** and versioning on production buckets

### See Also

- [Admin Guide](../docs/admin-guide.md) - Detailed configuration instructions
- [User Guide](../docs/user-guide.md) - How to retrieve workflow outputs
- [Workflow Troubleshooting](../docs/workflow-troubleshooting.md) - Debugging artifact issues

## RepoRegistration-Based Configuration (Declarative)

**Files:** 
- `repo-registrations-example.yaml` - Example RepoRegistration custom resources
- `repo-registrations-values.yaml` - Helm values using repoRegistrations array

This approach provides a **declarative, self-service model** for repository onboarding using the `RepoRegistration` custom resource definition. Instead of manually configuring ArgoCD Applications and Argo Events separately, you define repositories using a unified schema.

### Key Benefits

- **Single source of truth**: One resource defines repo URL, S3 buckets, secrets, and access control
- **Vault integration**: Automatic ExternalSecret creation for S3 and GitHub credentials
- **Standardized onboarding**: Consistent configuration across all repositories
- **Access control**: Built-in support for Fence/Arborist-aligned user permissions
- **Multi-bucket support**: Separate artifact and data buckets per repository

### Two Deployment Methods

#### Method 1: Using RepoRegistration CRDs (Runtime)

Create `RepoRegistration` custom resources that will be processed by a controller:

```bash
# Install the CRD
kubectl apply -f helm/argo-stack/crds/repo-registration-crd.yaml

# Create your repository registrations
kubectl apply -f examples/repo-registrations-example.yaml

# Verify status
kubectl get reporegistration -A
kubectl describe reporegistration nextflow-hello-project -n wf-poc
```

**Note:** This method requires a RepoRegistration controller/operator to be running to transform CRs into ArgoCD Applications and EventSources.

#### Method 2: Using repoRegistrations in values.yaml (Deployment Time)

Define repositories in Helm values, and the chart will generate resources at deployment time:

```bash
# Deploy with repoRegistrations values
helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd --create-namespace \
  --values examples/repo-registrations-values.yaml \
  --wait

# Verify generated resources
kubectl get application -n argocd
kubectl get eventsource -n argo-events
kubectl get externalsecret -n wf-poc
kubectl get configmap -n argo-workflows | grep argo-artifacts
```

### What Gets Created

For each entry in `repoRegistrations`, the Helm chart generates:

1. **ArgoCD Application** (in `argocd` namespace)
   - Syncs the Git repository
   - Manages continuous deployment

2. **Argo Events GitHub EventSource** (in `argo-events` namespace)
   - Watches for push events
   - Triggers workflows on commits

3. **ExternalSecrets** (in workflow namespace)
   - `s3-credentials-<repo-name>` - Artifact bucket credentials
   - `s3-data-credentials-<repo-name>` - Data bucket credentials (if different)
   - `<githubSecretName>` - GitHub PAT for webhooks

4. **Artifact Repository ConfigMap** (in `argo-workflows` namespace)
   - `argo-artifacts-<repo-name>` - S3 configuration for workflow outputs

### Vault Prerequisites

Before deployment, store credentials in Vault:

```bash
# S3 credentials
vault kv put kv/argo/apps/my-repo/s3/artifacts \
  AWS_ACCESS_KEY_ID=AKIAXXXXXXXX \
  AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxx

# GitHub token
vault kv put kv/argo/apps/my-repo/github \
  token=github_pat_XXXXXXXXXX
```

### Example Configuration

```yaml
repoRegistrations:
  - name: nextflow-hello-project
    repoUrl: https://github.com/myorg/nextflow-hello-project.git
    defaultBranch: main
    tenant: research-team
    namespace: wf-poc
    workflowTemplateRef: nextflow-repo-runner
    
    artifactBucket:
      hostname: https://s3.us-west-2.amazonaws.com
      bucket: research-team-artifacts
      region: us-west-2
      externalSecretPath: argo/apps/nextflow-hello-project/s3/artifacts
    
    githubSecretName: github-secret-nextflow-hello
    githubSecretPath: argo/apps/nextflow-hello-project/github
    
    adminUsers:
      - pi@research.edu
    readUsers:
      - postdoc@research.edu
```

### Documentation

For complete documentation on RepoRegistration, see:
- [RepoRegistration Guide](../docs/repo-registration-guide.md) - Comprehensive user documentation
- [RepoRegistration CRD](../helm/argo-stack/crds/repo-registration-crd.yaml) - Schema definition

### Comparison: Applications vs RepoRegistrations

| Feature | Manual (applications) | Declarative (repoRegistrations) |
|---------|----------------------|----------------------------------|
| Configuration file | Multiple (apps, events, secrets) | Single unified definition |
| Secret management | Manual ExternalSecret creation | Automatic from Vault paths |
| Access control | External (Fence/Arborist only) | Defined in spec (adminUsers/readUsers) |
| S3 buckets | Configured separately | Part of registration spec |
| Onboarding complexity | Medium (multiple resources) | Low (one resource) |
| Best for | Legacy systems, custom setups | Standardized, self-service onboarding |

### See Also

- [Admin Guide](../docs/admin-guide.md) - Detailed configuration instructions
- [User Guide](../docs/user-guide.md) - How to retrieve workflow outputs
- [Workflow Troubleshooting](../docs/workflow-troubleshooting.md) - Debugging artifact issues
- [RepoRegistration Guide](../docs/repo-registration-guide.md) - Self-service onboarding documentation
