# Multi-Repository Artifact Storage with `artifactRepositoryRef`

## Overview

This feature enables Argo Workflows to dynamically select different S3 artifact repositories for each workflow execution using the `spec.artifactRepositoryRef` field. This is particularly useful in multi-tenant environments where different teams or projects need to store workflow artifacts in separate buckets.

## Background

By default, Argo Workflows uses a single artifact repository defined in the `workflow-controller-configmap` ConfigMap. With `artifactRepositoryRef`, workflows can override this default and select a specific repository at runtime.

**Official Documentation:**
- [Configure Artifact Repository](https://argo-workflows.readthedocs.io/en/latest/configure-artifact-repository/)
- [Workflow Artifact Repository Reference](https://argo-workflows.readthedocs.io/en/latest/workflow-artifact-repository-ref/)

## How It Works

### 1. ConfigMap Structure

The `artifact-repositories` ConfigMap in the `argo-workflows` namespace contains multiple repository configurations:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: artifact-repositories
  namespace: argo-workflows
data:
  # Legacy default for backward compatibility
  default-v1: |
    archiveLogs: true
    s3:
      bucket: default-bucket
      endpoint: s3.amazonaws.com
      # ... credentials ...
  
  # Multi-repository configuration
  artifactRepositories: |
    # Default repository
    default:
      archiveLogs: true
      s3:
        bucket: default-bucket
        # ...
    
    # Per-project repositories
    my-project:
      archiveLogs: true
      s3:
        bucket: my-project-artifacts
        endpoint: s3.us-west-2.amazonaws.com
        region: us-west-2
        accessKeySecret:
          name: s3-credentials-my-project
          key: AWS_ACCESS_KEY_ID
        secretKeySecret:
          name: s3-credentials-my-project
          key: AWS_SECRET_ACCESS_KEY
```

### 2. Workflow Configuration

Workflows reference a specific repository using `artifactRepositoryRef`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: my-workflow-
spec:
  # Select the artifact repository for this workflow
  artifactRepositoryRef:
    configMap: artifact-repositories
    key: artifactRepositories.my-project
  
  serviceAccountName: wf-runner
  entrypoint: main
  templates:
    - name: main
      container:
        image: alpine
        command: [sh, -c]
        args: ["echo 'Hello World' > /tmp/output.txt"]
      outputs:
        artifacts:
          - name: result
            path: /tmp/output.txt
```

### 3. Automatic Configuration from RepoRegistrations

When you define a `RepoRegistration` with an `artifactBucket`, the system automatically:

1. Adds an entry to the `artifactRepositories` section of the ConfigMap
2. Creates necessary S3 credentials via ExternalSecrets
3. Configures WorkflowTemplates to use `artifactRepositoryRef`
4. Sets up RBAC permissions for workflows to read the ConfigMap

**Example RepoRegistration:**

```yaml
repoRegistrations:
  - name: genomics-pipeline
    repoUrl: https://github.com/myorg/genomics-pipeline.git
    defaultBranch: main
    tenant: research-team
    
    artifactBucket:
      hostname: s3.us-west-2.amazonaws.com
      bucket: genomics-artifacts
      region: us-west-2
      keyPrefix: workflows/
      insecure: false
      pathStyle: false
      externalSecretPath: argo/apps/genomics-pipeline/s3/artifacts
```

This automatically creates:
- An artifact repository entry named `genomics-pipeline`
- An ExternalSecret to sync S3 credentials from Vault
- A WorkflowTemplate configured to use this repository

## RBAC Requirements

Workflows must have permission to read the `artifact-repositories` ConfigMap. This is automatically configured for tenant namespaces created from RepoRegistrations.

**Manual RBAC (if needed):**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: artifact-repository-reader
  namespace: argo-workflows
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["artifact-repositories"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: artifact-repository-reader
  namespace: argo-workflows
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: artifact-repository-reader
subjects:
  - kind: ServiceAccount
    name: wf-runner
    namespace: my-tenant-namespace
```

## Submitting Workflows via CLI

You can also specify the artifact repository when submitting workflows from the command line:

```bash
# Using argo submit
argo submit workflow.yaml \
  --from workflowtemplate/my-template \
  --artifact-repository-ref genomics-pipeline

# Or in the workflow spec
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: test-
spec:
  artifactRepositoryRef:
    configMap: artifact-repositories
    key: artifactRepositories.genomics-pipeline
  workflowTemplateRef:
    name: nextflow-repo-runner
EOF
```

## Use Cases

### 1. Multi-Tenant Isolation

Different teams store artifacts in their own buckets:
- Research team → `research-artifacts` bucket
- Engineering team → `engineering-artifacts` bucket
- Clinical team → `clinical-artifacts` bucket

### 2. Environment Separation

Different environments use different storage:
- Development → `dev-artifacts` bucket
- Staging → `staging-artifacts` bucket
- Production → `prod-artifacts` bucket

### 3. Compliance & Data Residency

Projects with specific compliance requirements:
- HIPAA-compliant workloads → encrypted bucket in specific region
- Public research → open-access bucket
- Confidential projects → private bucket with strict access controls

### 4. Cost Optimization

Different storage tiers based on data lifecycle:
- Active workflows → Standard S3 storage
- Archive workflows → Glacier storage
- Temporary workflows → bucket with lifecycle policy to auto-delete

## Validation

### Check ConfigMap

```bash
kubectl get configmap artifact-repositories -n argo-workflows -o yaml
```

### Verify RBAC

```bash
# Test if ServiceAccount can read the ConfigMap
kubectl auth can-i get configmap/artifact-repositories \
  --as=system:serviceaccount:my-tenant-namespace:wf-runner \
  -n argo-workflows
```

### Test Workflow

```bash
# Submit a test workflow
argo submit -n my-tenant-namespace --watch <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: artifact-test-
spec:
  serviceAccountName: wf-runner
  artifactRepositoryRef:
    configMap: artifact-repositories
    key: artifactRepositories.my-project
  entrypoint: main
  templates:
    - name: main
      container:
        image: alpine
        command: [sh, -c]
        args: ["echo 'test' > /tmp/test.txt"]
      outputs:
        artifacts:
          - name: result
            path: /tmp/test.txt
EOF
```

### Verify Artifact Location

After the workflow completes, check the artifact was stored in the correct bucket:

```bash
# Get workflow details
argo get <workflow-name> -n my-tenant-namespace

# Check S3 bucket (adjust for your S3 client)
aws s3 ls s3://my-project-artifacts/workflows/
```

## Troubleshooting

### Error: "configmaps \"artifact-repositories\" not found"

**Cause:** ConfigMap doesn't exist in the argo-workflows namespace.

**Solution:** Ensure the helm chart is deployed with `s3.enabled: true` or with repoRegistrations defined.

### Error: "forbidden: error looking up service account"

**Cause:** RBAC permissions are missing.

**Solution:** Verify RoleBinding exists:
```bash
kubectl get rolebinding -n argo-workflows | grep artifact-repository-reader
```

### Artifacts Not Appearing in Expected Bucket

**Cause:** Repository key name mismatch or credentials issue.

**Solution:**
1. Verify the key name in ConfigMap matches the one in `artifactRepositoryRef`
2. Check S3 credentials Secret exists and is valid
3. Review workflow controller logs:
   ```bash
   kubectl logs -n argo-workflows deploy/argo-workflows-workflow-controller | grep artifact
   ```

### Permission Denied Writing to S3

**Cause:** S3 credentials are missing or incorrect.

**Solution:**
1. Verify the Secret exists:
   ```bash
   kubectl get secret s3-credentials-my-project -n my-tenant-namespace
   ```
2. Check ExternalSecret sync status:
   ```bash
   kubectl get externalsecret -n my-tenant-namespace
   ```
3. Verify Vault path contains valid credentials

## References

- [Argo Workflows Documentation](https://argo-workflows.readthedocs.io/)
- [Configure Artifact Repository](https://argo-workflows.readthedocs.io/en/latest/configure-artifact-repository/)
- [Workflow Artifact Repository Reference](https://argo-workflows.readthedocs.io/en/latest/workflow-artifact-repository-ref/)
- [S3 Artifacts](https://argo-workflows.readthedocs.io/en/latest/s3-artifacts/)
- [RepoRegistration Guide](./repo-registration-guide.md)
- [Vault Integration](./secrets-with-vault.md)
