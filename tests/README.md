# RepoRegistrations Test Suite

This directory contains tests to validate that Helm templates correctly render resources from `repoRegistrations` configuration and that Vault is properly seeded with required secrets.

## Test Files

- `test_repo_registrations_rendering.py` - Validates that `make template` with `my-values.yaml` generates the expected resources
- `test_vault_seeding.py` - Validates that Vault contains all required secrets for repoRegistrations

## Running Tests

### Prerequisites

Install pytest and PyYAML:

```bash
pip install pytest pyyaml
```

### Run All Tests

```bash
# From repository root
pytest tests/test_repo_registrations_rendering.py -v
pytest tests/test_vault_seeding.py -v

# Or run all tests
pytest tests/ -v

# Or run directly
python tests/test_repo_registrations_rendering.py
python tests/test_vault_seeding.py
```

### Run Specific Test

```bash
pytest tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count -v
```

## Test Coverage

### Helm Template Rendering Tests (`test_repo_registrations_rendering.py`)

The test suite validates:

#### 1. ArgoCD Applications (3 total)
- ✅ Correct count of Applications
- ✅ Correct Application names matching repoRegistrations

#### 2. ExternalSecrets (7 total)
- ✅ Correct total count
- ✅ 3 GitHub credential secrets with correct names
- ✅ 4 S3 credential secrets (3 artifact + 1 data bucket)

#### 3. Artifact Repository ConfigMaps (3 total)
- ✅ Correct count of ConfigMaps
- ✅ S3 bucket configurations:
  - Bucket names
  - Regions and endpoints
  - pathStyle flags (especially for MinIO)
  - insecure flags
  - keyPrefix settings

#### 4. EventSource (1 total)
- ✅ Single EventSource generated
- ✅ All 3 repository webhook configurations:
  - Owner and repository names extracted correctly from URLs
  - Events configured (push)
  - Active status

#### 5. Tenant Namespaces (3 total)
- ✅ Per-tenant namespaces created with `wf-<org>-<repo>` naming pattern
- ✅ Correct namespace labels
- ✅ Legacy `wf-poc` namespace NOT used
- ✅ RBAC resources (ServiceAccounts, Roles, RoleBindings) created

### Vault Seeding Tests (`test_vault_seeding.py`)

The test suite validates that Vault is properly seeded with all required secrets:

#### 1. Vault Accessibility
- ✅ Vault is running and accessible
- ✅ Vault is initialized and unsealed
- ✅ KV v2 secrets engine is enabled at `kv/` path

#### 2. GitHub Credential Secrets
- ✅ All GitHub credential secrets exist
- ✅ Each secret has the required `token` key
- ✅ Paths match those in repoRegistrations

#### 3. S3 Artifact Bucket Secrets
- ✅ All S3 artifact bucket credential secrets exist
- ✅ Each secret has `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- ✅ Paths match those in repoRegistrations

#### 4. S3 Data Bucket Secrets
- ✅ All S3 data bucket credential secrets exist (if configured)
- ✅ Each secret has required AWS credential keys
- ✅ Paths match those in repoRegistrations

#### 5. Complete Coverage
- ✅ Every repoRegistration has all its required secrets
- ✅ Vault paths are formatted correctly for ExternalSecret templates

## Example Output

### Template Rendering Tests

```
🔧 Rendering Helm templates...
✅ Templates rendered successfully

🧪 Testing ArgoCD Applications count...
✅ Found 3 ArgoCD Applications

🧪 Testing ArgoCD Applications names...
✅ Applications have correct names: {'nextflow-hello-project', 'genomics-variant-calling', 'local-dev-workflows'}

...

PASSED tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count
PASSED tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_external_secrets_count
...
```

### Vault Seeding Tests

```
🧪 Testing Vault accessibility...
✅ Vault is accessible and unsealed

🧪 Testing KV secrets engine...
✅ KV v2 secrets engine is enabled at kv/

🧪 Testing GitHub credential secrets...
✅ Found 3 GitHub credential secrets:
   ✓ kv/argo/apps/genomics/github
   ✓ kv/argo/apps/internal-dev/github
   ✓ kv/argo/apps/nextflow-hello-project/github

🧪 Testing S3 artifact bucket credential secrets...
✅ Found 3 S3 artifact credential secrets:
   ✓ kv/argo/apps/genomics/s3/artifacts
   ✓ kv/argo/apps/internal-dev/minio
   ✓ kv/argo/apps/nextflow-hello-project/s3/artifacts

...

PASSED tests/test_vault_seeding.py::TestVaultSeeding::test_vault_is_accessible
PASSED tests/test_vault_seeding.py::TestVaultSeeding::test_github_secrets_exist
...
```

## Configuration

Tests use the `my-values.yaml` file in the repository root, which contains 3 example repoRegistrations:
1. `nextflow-hello-project` - Basic Nextflow pipeline with artifact bucket
2. `genomics-variant-calling` - Genomics pipeline with both artifact and data buckets
3. `local-dev-workflows` - Local development using MinIO

## Prerequisites for Vault Tests

The vault seeding tests require:
1. A running Kubernetes cluster (e.g., `kind`)
2. Vault dev server running: `make vault-dev`
3. Vault seeded with secrets: `make vault-seed`

To run the full test suite:

```bash
# Start cluster and vault
make kind
make vault-dev
make vault-seed

# Run tests
pytest tests/test_vault_seeding.py -v
```

## Troubleshooting

### Vault Tests Fail

If vault tests fail, check:

1. Is Vault running?
   ```bash
   make vault-status
   ```

2. Are secrets seeded?
   ```bash
   make vault-list
   ```

3. Re-seed if needed:
   ```bash
   make vault-seed
   ```

### Template Rendering Tests Fail

If template rendering tests fail:

1. Check environment variables are set:
   ```bash
   export GITHUB_PAT=dummy-token
   export ARGOCD_SECRET_KEY=dummy-secret
   export ARGO_HOSTNAME=localhost
   ```

2. Update Helm dependencies:
   ```bash
   make deps
   ```

3. Validate my-values.yaml syntax:
   ```bash
   yamllint my-values.yaml
   ```

## See Also

- [Vault Seeding Strategy](../docs/vault-seeding-strategy.md) - Detailed documentation on vault seeding
- [RepoRegistration Documentation](../docs/repo-registration.md) - User-facing repoRegistration documentation
