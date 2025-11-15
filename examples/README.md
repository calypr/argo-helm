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
