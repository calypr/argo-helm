# Multi-Tenant Artifact Storage

## Overview

This feature enables Argo Workflows to use different S3 artifact repositories for each tenant/project in a multi-tenant environment. Each tenant namespace gets its own dedicated artifact repository configuration, ensuring isolation and proper access control.

## Background

By default, Argo Workflows uses a single artifact repository defined in a ConfigMap. In multi-tenant environments, we need to support different artifact storage configurations per tenant while maintaining isolation.

**Official Documentation:**
- [Configure Artifact Repository](https://argo-workflows.readthedocs.io/en/latest/configure-artifact-repository/)
- [Workflow Artifact Repository Reference](https://argo-workflows.readthedocs.io/en/latest/workflow-artifact-repository-ref/)

## How It Works

### 1. Tenant Namespace ConfigMaps

Each tenant namespace created from a `RepoRegistration` gets its own `artifact-repositories` ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: artifact-repositories
  namespace: wf-myorg-myproject  # Tenant namespace
  labels:
    source: repo-registration
    calypr.io/application: myproject
  annotations:
    # This annotation tells Argo Workflows which key to use as the default
    workflows.argoproj.io/default-artifact-repository: default-v1
data:
  # Default key that Argo Workflows automatically discovers
  default-v1: |
    archiveLogs: true
    s3:
      bucket: myproject-artifacts
      endpoint: s3.us-west-2.amazonaws.com
      region: us-west-2
      keyPrefix: workflows/
      insecure: false
      pathStyle: false
      accessKeySecret:
        name: s3-credentials-myproject
        key: AWS_ACCESS_KEY_ID
      secretKeySecret:
        name: s3-credentials-myproject
        key: AWS_SECRET_ACCESS_KEY
      useSDKCreds: false
```

**Key Points:**
- Each tenant namespace has its own ConfigMap
- The `workflows.argoproj.io/default-artifact-repository` annotation specifies which key to use
- The ConfigMap uses the `default-v1` key containing the tenant-specific S3 configuration
- No explicit `artifactRepositoryRef` is needed in workflows
- Argo Workflows automatically discovers this ConfigMap based on the annotation

### Artifact Repository Resolution Order

Argo Workflows resolves artifact repositories in this order:

1. **Workflow-level override**: `spec.artifactRepositoryRef` in the Workflow spec (if present)
2. **Namespace default**: ConfigMap named `artifact-repositories` in the workflow's namespace with the `workflows.argoproj.io/default-artifact-repository` annotation
3. **Global default**: The controller's global ConfigMap in the `argo-workflows` namespace

Since we use option #2 (namespace default with annotation), workflows automatically use the correct tenant-specific repository without any explicit configuration.

### 2. Workflow Configuration

Workflows in a tenant namespace automatically use the namespace's artifact repository:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: my-workflow-
  namespace: wf-myorg-myproject
spec:
  # No artifactRepositoryRef needed - Argo Workflows automatically
  # uses the artifact-repositories ConfigMap in this namespace
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

1. Creates a tenant namespace (e.g., `wf-myorg-myproject`)
2. Creates an `artifact-repositories` ConfigMap in that namespace with `default-v1` key
3. Creates necessary S3 credentials via ExternalSecrets
4. Creates WorkflowTemplates in the tenant namespace
5. Sets up ServiceAccount and RBAC in the tenant namespace

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
- Namespace: `wf-myorg-genomics-pipeline`
- ConfigMap: `artifact-repositories` with proper S3 configuration and `workflows.argoproj.io/default-artifact-repository: default-v1` annotation
- ExternalSecret: Syncs S3 credentials from Vault to `s3-credentials-genomics-pipeline`
- WorkflowTemplate: `nextflow-repo-runner` in the tenant namespace
- ServiceAccount: `wf-runner` with necessary permissions

## RBAC Requirements

Workflows need permission to read the `artifact-repositories` ConfigMap in their namespace. This is automatically configured for tenant namespaces created from RepoRegistrations.

The ServiceAccount `wf-runner` in each tenant namespace is granted the necessary permissions via a Role and RoleBinding created automatically.

**Note:** Since the ConfigMap is in the same namespace as the workflows, no cross-namespace RBAC is needed.

## Submitting Workflows via CLI

Workflows automatically use the artifact repository configured in their namespace:

```bash
# Submit a workflow in a tenant namespace
# The workflow automatically uses the artifact-repositories ConfigMap in wf-myorg-myproject
argo submit -n wf-myorg-myproject --from workflowtemplate/nextflow-repo-runner

# Submit a standalone workflow
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: test-
  namespace: wf-myorg-myproject
spec:
  serviceAccountName: wf-runner
  workflowTemplateRef:
    name: nextflow-repo-runner
  arguments:
    parameters:
      - name: repo-url
        value: https://github.com/myorg/myproject
      - name: revision
        value: main
EOF
```

**Advanced: Override Artifact Repository (if needed)**

If you need to explicitly reference a different artifact repository, you can use `artifactRepositoryRef`:

```yaml
spec:
  # Optional: explicitly reference a ConfigMap key
  artifactRepositoryRef:
    configMap: artifact-repositories
    key: default-v1  # or another key if you have multiple configs
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

### Check Tenant Namespace ConfigMap

```bash
# List all tenant namespaces
kubectl get ns -l source=repo-registration

# Check ConfigMap in a specific tenant namespace
kubectl get configmap artifact-repositories -n wf-myorg-myproject -o yaml
```

### Verify RBAC

```bash
# Test if ServiceAccount can read the ConfigMap in its own namespace
kubectl auth can-i get configmap/artifact-repositories \
  --as=system:serviceaccount:wf-myorg-myproject:wf-runner \
  -n wf-myorg-myproject
```

### Test Workflow

```bash
# Submit a test workflow in a tenant namespace
argo submit -n wf-myorg-myproject --watch <<EOF
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

**Cause:** ConfigMap doesn't exist in the workflow's namespace.

**Solution:** 
1. Verify the RepoRegistration has `artifactBucket` configured
2. Check if the ConfigMap was created in the tenant namespace:
   ```bash
   kubectl get configmap artifact-repositories -n wf-myorg-myproject
   ```

### Error: "failed to resolve artifact repository"

**Cause:** Invalid `artifactRepositoryRef` configuration (if explicitly specified).

**Solution:** 
1. Remove explicit `artifactRepositoryRef` to use the default behavior
2. If you must use it, reference `default-v1` key:
   ```yaml
   artifactRepositoryRef:
     configMap: artifact-repositories
     key: default-v1
   ```

### Error: "forbidden: error looking up service account"

**Cause:** ServiceAccount is missing or RBAC permissions are incorrect.

**Solution:** 
1. Verify ServiceAccount exists in the tenant namespace:
   ```bash
   kubectl get sa wf-runner -n wf-myorg-myproject
   ```
2. Check that the namespace was created from a RepoRegistration

### Artifacts Not Appearing in Expected Bucket

**Cause:** Repository configuration or credentials issue.

**Solution:**
1. Check the ConfigMap configuration:
   ```bash
   kubectl get configmap artifact-repositories -n wf-myorg-myproject -o yaml
   ```
2. Verify S3 credentials Secret exists and is valid:
   ```bash
   kubectl get secret s3-credentials-myproject -n wf-myorg-myproject
   ```
3. Review workflow controller logs:
   ```bash
   kubectl logs -n argo-workflows deploy/argo-workflows-workflow-controller | grep artifact
   ```

### Permission Denied Writing to S3

**Cause:** S3 credentials are missing or incorrect.

**Solution:**
1. Verify the Secret exists:
   ```bash
   kubectl get secret s3-credentials-myproject -n wf-myorg-myproject
   ```
2. Check ExternalSecret sync status:
   ```bash
   kubectl get externalsecret -n wf-myorg-myproject
   kubectl describe externalsecret s3-credentials-myproject -n wf-myorg-myproject
   ```
3. Verify Vault path contains valid credentials:
   ```bash
   kubectl exec -n vault vault-0 -- vault kv get kv/argo/apps/myproject/s3/artifacts
   ```

## References

- [Argo Workflows Documentation](https://argo-workflows.readthedocs.io/)
- [Configure Artifact Repository](https://argo-workflows.readthedocs.io/en/latest/configure-artifact-repository/)
- [Workflow Artifact Repository Reference](https://argo-workflows.readthedocs.io/en/latest/workflow-artifact-repository-ref/)
- [S3 Artifacts](https://argo-workflows.readthedocs.io/en/latest/s3-artifacts/)
- [RepoRegistration Guide](./repo-registration-guide.md)
- [Vault Integration](./secrets-with-vault.md)
