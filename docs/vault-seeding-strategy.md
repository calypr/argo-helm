[Home](index.md) > Architecture and Design

# Vault Seeding Strategy for RepoRegistrations

## Overview

The `make vault-seed` target automatically seeds HashiCorp Vault with all required secrets for the repoRegistrations defined in `my-values.yaml`. This ensures that External Secrets Operator (ESO) can successfully sync credentials into Kubernetes secrets.

## Strategy

### 1. Path Convention

All repoRegistration secrets follow the Vault path pattern:
```
kv/argo/apps/<project>/<credential-type>
```

Where:
- `kv/` - KV v2 secrets engine mount path
- `argo/apps/` - Standard prefix for application secrets
- `<project>` - Project identifier (e.g., `nextflow-hello-project`, `genomics`)
- `<credential-type>` - Type of credential (`github`, `s3/artifacts`, `s3/data`, `minio`)

### 2. Secret Types

For each repoRegistration, the following secrets may be created:

#### GitHub Credentials
- **Path**: `kv/argo/apps/<project>/github`
- **Keys**: `token`
- **Usage**: Used by Argo Events for webhook authentication and repository access

#### S3 Artifact Bucket Credentials
- **Path**: `kv/argo/apps/<project>/s3/artifacts`
- **Keys**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- **Usage**: Used by Argo Workflows for artifact storage

#### S3 Data Bucket Credentials (optional)
- **Path**: `kv/argo/apps/<project>/s3/data`
- **Keys**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- **Usage**: Used by workflows to access input data buckets

#### MinIO Credentials (for local development)
- **Path**: `kv/argo/apps/<project>/minio`
- **Keys**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- **Usage**: Used for local development with MinIO instead of AWS S3

### 3. Automatic Path Extraction

The vault-seed target automatically extracts paths from `my-values.yaml`:

```yaml
repoRegistrations:
  - name: my-project
    githubSecretPath: argo/apps/my-project/github      # → kv/argo/apps/my-project/github
    artifactBucket:
      externalSecretPath: argo/apps/my-project/s3/artifacts  # → kv/argo/apps/my-project/s3/artifacts
```

### 4. Implementation

The Makefile target performs these steps:

1. **Enable KV v2 engine** at `kv/` path
2. **Create core Argo secrets** (ArgoCD, Workflows, Events)
3. **Parse my-values.yaml** to extract repoRegistration paths
4. **Create secrets** for each repoRegistration:
   - GitHub credentials (if `githubSecretPath` is set)
   - S3 artifact credentials (if `artifactBucket.externalSecretPath` is set)
   - S3 data credentials (if `dataBucket.externalSecretPath` is set)
5. **Configure Kubernetes auth** for ESO to access Vault

## Usage

### Seed Vault with Defaults

```bash
make vault-seed
```

This will create all secrets defined in `my-values.yaml` repoRegistrations.

### Verify Vault Seeding

Run the automated test suite:

```bash
pytest tests/test_vault_seeding.py -v
```

The test suite validates:
- Vault is accessible and unsealed
- KV v2 engine is enabled
- All GitHub credential secrets exist
- All S3 artifact credential secrets exist
- All S3 data credential secrets exist (if configured)
- Each repoRegistration has all required secrets
- All paths follow the correct format

### Manual Verification

List all secrets in Vault:

```bash
make vault-list
```

Get a specific secret:

```bash
make vault-get VPATH=kv/argo/apps/nextflow-hello-project/github
```

## Current Secrets (from my-values.yaml)

Based on the current `my-values.yaml`, the following secrets are created:

### nextflow-hello-project
```
kv/argo/apps/nextflow-hello-project/github
kv/argo/apps/nextflow-hello-project/s3/artifacts
```

### genomics-variant-calling
```
kv/argo/apps/genomics/github
kv/argo/apps/genomics/s3/artifacts
kv/argo/apps/genomics/s3/data
```

### local-dev-workflows
```
kv/argo/apps/internal-dev/github
kv/argo/apps/internal-dev/minio
```

## Adding New RepoRegistrations

When adding a new repoRegistration to `my-values.yaml`:

1. **Update my-values.yaml** with the new repoRegistration
2. **Update Makefile vault-seed target** to include the new secret paths:

```makefile
vault-seed:
    # ... existing secrets ...
    
    @# your-new-project GitHub credentials
    @kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/your-project/github \
        token="$(GITHUB_PAT)"
    
    @# your-new-project S3 credentials
    @kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/your-project/s3/artifacts \
        AWS_ACCESS_KEY_ID="your-project-key" \
        AWS_SECRET_ACCESS_KEY="your-project-secret"
```

3. **Run vault-seed** to create the new secrets
4. **Run tests** to verify: `pytest tests/test_vault_seeding.py -v`

## Security Considerations

### Development vs Production

The current implementation is designed for **local development and testing**:

- Uses Vault dev mode (not suitable for production)
- Uses static credentials (minioadmin, dummy keys)
- Root token is set to a known value (`root`)

### Production Deployment

For production:

1. Use Vault in production mode with proper seal/unseal
2. Use real credentials from your cloud provider
3. Rotate secrets regularly
4. Use Vault policies to restrict access
5. Enable audit logging
6. Use AppRole or other auth methods instead of root token

### Credential Rotation

When rotating credentials:

1. Update the secret in Vault
2. ESO will automatically sync the new credentials to Kubernetes
3. Workflows will pick up new credentials on next execution
4. No need to restart pods or modify configurations

## Troubleshooting

### Vault Not Accessible

```bash
make vault-status
```

If Vault is not running:

```bash
make vault-dev
```

### Missing Secrets

Check what secrets exist:

```bash
make vault-list
```

Re-run seeding:

```bash
make vault-seed
```

### ExternalSecret Sync Failures

Check ExternalSecret status:

```bash
kubectl get externalsecret -A
kubectl describe externalsecret <name> -n <namespace>
```

Verify the secret exists in Vault:

```bash
make vault-get VPATH=kv/argo/apps/<project>/<type>
```

### Test Failures

Run tests with verbose output:

```bash
pytest tests/test_vault_seeding.py -v --tb=long
```

Check individual secret:

```bash
kubectl exec -n vault vault-0 -- vault kv get kv/argo/apps/<project>/<type>
```

## Integration with External Secrets Operator

The ExternalSecret templates in `helm/argo-stack/templates/eso/` automatically:

1. Reference the paths defined in `githubSecretPath` and `externalSecretPath`
2. Add the `kv/` prefix to form the complete Vault path
3. Extract the required keys (`token`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
4. Sync them into Kubernetes secrets in the tenant namespace

No manual intervention is required once Vault is seeded correctly.
