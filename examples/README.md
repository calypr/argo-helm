# Examples

This directory contains example configurations for the Argo Stack Helm chart.

> **⚠️ IMPORTANT**: The legacy configuration pattern using `.Values.applications` has been REMOVED. 
> You MUST use the RepoRegistration pattern for repository onboarding.
> See [DEPRECATION_NOTICE.md](../docs/DEPRECATION_NOTICE.md) for migration guidance.

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

This will deploy the stack without any applications, allowing you to add your own using RepoRegistration.

## RepoRegistration-Based Configuration (Recommended)

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
- [RepoRegistration User Guide](../docs/REPO_REGISTRATION_USER_GUIDE.md) - Comprehensive user documentation
- [RepoRegistration CRD](../helm/argo-stack/crds/repo-registration-crd.yaml) - Schema definition
- [Deprecation Notice](../docs/DEPRECATION_NOTICE.md) - Migration from legacy pattern

### See Also

- [Admin Guide](../docs/admin-guide.md) - Detailed configuration instructions
- [User Guide](../docs/user-guide.md) - How to retrieve workflow outputs
- [Workflow Troubleshooting](../docs/workflow-troubleshooting.md) - Debugging artifact issues
