# RepoRegistrations Rendering Tests

This directory contains tests to validate that Helm templates correctly render resources from `repoRegistrations` configuration.

## Test File

- `test_repo_registrations_rendering.py` - Validates that `make template` with `my-values.yaml` generates the expected resources

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

# Or run directly
python tests/test_repo_registrations_rendering.py
```

### Run Specific Test

```bash
pytest tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count -v
```

## Test Coverage

The test suite validates:

### 1. ArgoCD Applications (3 total)
- ✅ Correct count of Applications
- ✅ Correct Application names matching repoRegistrations

### 2. ExternalSecrets (7 total)
- ✅ Correct total count
- ✅ 3 GitHub credential secrets with correct names
- ✅ 4 S3 credential secrets (3 artifact + 1 data bucket)

### 3. Artifact Repository ConfigMaps (3 total)
- ✅ Correct count of ConfigMaps
- ✅ S3 bucket configurations:
  - Bucket names
  - Regions and endpoints
  - pathStyle flags (especially for MinIO)
  - insecure flags
  - keyPrefix settings

### 4. EventSource (1 total)
- ✅ Single EventSource generated
- ✅ All 3 repository webhook configurations:
  - Owner and repository names extracted correctly from URLs
  - Events configured (push)
  - Active status

## Example Output

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

## Configuration

Tests use the `my-values.yaml` file in the repository root, which contains 3 example repoRegistrations:
1. `nextflow-hello-project` - Basic Nextflow pipeline with artifact bucket
2. `genomics-variant-calling` - Genomics pipeline with both artifact and data buckets
3. `local-dev-workflows` - Local development using MinIO
