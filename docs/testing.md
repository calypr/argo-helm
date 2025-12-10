[Home](index.md) > Testing and Troubleshooting

# Testing Guide

This document describes the testing infrastructure for the argo-helm chart, with a focus on validating Helm template rendering for the `repoRegistrations` feature.

## Overview

The test suite ensures that Helm templates correctly render Kubernetes resources from `repoRegistrations` configuration. This is critical for self-service repository onboarding, where users define Git repositories and the chart automatically generates all necessary ArgoCD Applications, ExternalSecrets, ConfigMaps, and EventSources.

## Test Suite Structure

### Location

All tests are located in the `tests/` directory:

```
tests/
├── README.md                              # Quick reference for running tests
├── pytest.ini                             # Pytest configuration
└── test_repo_registrations_rendering.py   # Main test suite
```

### Test File: `test_repo_registrations_rendering.py`

This is the primary test suite that validates Helm template rendering. It contains:

- **Test Class**: `TestRepoRegistrationsRendering` with 9 test methods
- **Setup**: Automatically runs `helm template` with `my-values.yaml` before tests
- **Validation**: Parses rendered YAML and validates resource counts, names, and configurations

## Prerequisites

### Required Tools

1. **Helm** - For rendering templates
2. **Python 3.x** - For running pytest
3. **pytest** - Testing framework
4. **PyYAML** - For parsing YAML output

### Installation

Install Python dependencies:

```bash
pip install pytest pyyaml
```

Or install from the repository root if a requirements file exists:

```bash
pip install -r requirements-dev.txt  # If available
```

## Running Tests

### Quick Start

From the repository root, run all tests with:

```bash
pytest tests/test_repo_registrations_rendering.py -v
```

Or execute the test file directly:

```bash
python tests/test_repo_registrations_rendering.py
```

### Running Specific Tests

Run a single test method:

```bash
pytest tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count -v
```

Run with verbose output and stop on first failure:

```bash
pytest tests/test_repo_registrations_rendering.py -vx
```

### Test Output Options

- **Verbose**: `-v` - Shows detailed test names and progress
- **Quiet**: `-q` - Minimal output
- **Show print statements**: `-s` - Display print() output from tests
- **Stop on first failure**: `-x` - Exit immediately on first test failure
- **Show local variables**: `-l` - Show local variables in tracebacks

Example:
```bash
pytest tests/test_repo_registrations_rendering.py -vsl
```

## Test Configuration

### Environment Variables

The test suite uses the following environment variables (all have defaults):

| Variable | Default | Purpose |
|----------|---------|---------|
| `GITHUB_PAT` | `dummy-github-pat-token` | GitHub personal access token |
| `ARGOCD_SECRET_KEY` | `dummy-argocd-secret-key-12345678` | ArgoCD server secret key |
| `ARGO_HOSTNAME` | `localhost` | Hostname for webhook ingress |
| `S3_ENABLED` | `true` | Enable S3 artifact storage |
| `S3_BUCKET` | `test-bucket` | Default S3 bucket name |
| `S3_REGION` | `us-west-2` | AWS region |
| `S3_HOSTNAME` | `s3.us-west-2.amazonaws.com` | S3 endpoint |
| `S3_ACCESS_KEY_ID` | `dummy-access-key` | S3 access key |
| `S3_SECRET_ACCESS_KEY` | `dummy-secret-key` | S3 secret key |

### Test Data

Tests use `my-values.yaml` in the repository root, which contains 3 example `repoRegistrations`:

1. **nextflow-hello-project**
   - Basic Nextflow pipeline
   - Single artifact bucket (AWS S3)
   - Standard configuration

2. **genomics-variant-calling**
   - Genomics pipeline
   - Separate artifact and data buckets
   - Multiple admin and read-only users

3. **local-dev-workflows**
   - Local development setup
   - MinIO S3-compatible storage
   - pathStyle and insecure flags enabled

## Test Coverage

### Test Methods

The test suite includes 9 test methods that validate different aspects of the rendered output:

#### 1. `test_argocd_applications_count`
**Purpose**: Verify exactly 3 ArgoCD Applications are generated

**Validates**:
- Correct count of Applications
- Applications have `source: repo-registration` label

**Expected Result**: 3 Applications

---

#### 2. `test_argocd_applications_names`
**Purpose**: Verify Applications have correct names from repoRegistrations

**Validates**:
- Application names match `repoRegistrations[].name` values
- All expected Applications are present

**Expected Names**:
- `nextflow-hello-project`
- `genomics-variant-calling`
- `local-dev-workflows`

---

#### 3. `test_external_secrets_count`
**Purpose**: Verify total ExternalSecret count

**Validates**:
- Correct total count across all types
- All secrets have `source: repo-registration` label

**Expected Result**: 7 ExternalSecrets total

---

#### 4. `test_external_secrets_github_credentials`
**Purpose**: Verify GitHub credential ExternalSecrets

**Validates**:
- Correct count of GitHub secrets
- Secret names match `githubSecretName` values
- Secrets have `secret-type: github-credentials` label

**Expected Result**: 3 GitHub secrets
- `github-secret-nextflow-hello`
- `github-secret-genomics`
- `github-secret-internal-dev`

---

#### 5. `test_external_secrets_s3_credentials`
**Purpose**: Verify S3 credential ExternalSecrets

**Validates**:
- Correct count of S3 secrets (artifact + data buckets)
- Secret names follow naming convention
- Secrets have appropriate `secret-type` labels

**Expected Result**: 4 S3 secrets
- `s3-credentials-nextflow-hello-project` (artifact)
- `s3-credentials-genomics-variant-calling` (artifact)
- `s3-data-credentials-genomics-variant-calling` (data bucket)
- `s3-credentials-local-dev-workflows` (artifact)

---

#### 6. `test_artifact_repository_configmaps_count`
**Purpose**: Verify Artifact Repository ConfigMap count

**Validates**:
- Correct count of ConfigMaps
- ConfigMaps have `source: repo-registration` label

**Expected Result**: 3 ConfigMaps

---

#### 7. `test_artifact_repository_configmaps_s3_config`
**Purpose**: Verify S3 configurations in ConfigMaps

**Validates**:
- Bucket names match `artifactBucket.bucket` values
- Endpoints match `artifactBucket.hostname` values
- Regions match `artifactBucket.region` values
- pathStyle flags are correct (especially for MinIO)
- insecure flags are correct
- keyPrefix settings are correct

**Specific Validations**:
- **nextflow-hello-project**: Standard AWS S3 with pathStyle=false
- **genomics-variant-calling**: Standard AWS S3
- **local-dev-workflows**: MinIO with pathStyle=true and insecure=true

---

#### 8. `test_eventsource_count`
**Purpose**: Verify EventSource count

**Validates**:
- Exactly one EventSource is generated
- EventSource has `source: repo-registration` label

**Expected Result**: 1 EventSource

---

#### 9. `test_eventsource_webhook_configurations`
**Purpose**: Verify all webhook configurations in EventSource

**Validates**:
- All 3 repositories have webhook entries
- Owner names extracted correctly from URLs
- Repository names extracted correctly from URLs
- Events configured correctly (push)
- Active status set correctly

**Expected Webhooks**:
- `repo_push_nextflow_hello`: owner=`bwalsh`, repo=`nextflow-hello-project`
- `repo_push_genomics`: owner=`genomics-lab`, repo=`variant-calling-pipeline`
- `repo_push_local_dev`: owner=`internal`, repo=`dev-workflows`

## Test Implementation Details

### How Tests Work

1. **Setup Phase** (`setup_class` method):
   - Sets environment variables with defaults
   - Runs `helm template` command with all required parameters
   - Captures rendered YAML output
   - Raises error if template rendering fails

2. **Test Execution**:
   - Each test method parses the rendered YAML
   - Filters resources by Kubernetes `kind`
   - Filters by labels to isolate repoRegistration resources
   - Validates counts, names, and configurations
   - Assertions fail with descriptive error messages

3. **Helper Methods**:
   - `_parse_yaml_documents()`: Splits rendered output into separate K8s resources
   - `_filter_by_kind()`: Filters resources by type (Application, ExternalSecret, etc.)
   - `_filter_by_label()`: Filters resources by metadata labels

### Key Design Decisions

1. **Class-level setup**: Template rendering happens once for all tests (faster execution)
2. **Label-based filtering**: Uses `source: repo-registration` label to isolate test resources
3. **Descriptive assertions**: Error messages show expected vs actual values
4. **YAML parsing**: Uses PyYAML to validate nested configurations

## Example Test Output

### Successful Run

```bash
$ pytest tests/test_repo_registrations_rendering.py -v

🔧 Rendering Helm templates...
✅ Templates rendered successfully

tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count PASSED [ 11%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_names PASSED [ 22%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_external_secrets_count PASSED [ 33%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_external_secrets_github_credentials PASSED [ 44%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_external_secrets_s3_credentials PASSED [ 55%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_artifact_repository_configmaps_count PASSED [ 66%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_artifact_repository_configmaps_s3_config PASSED [ 77%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_eventsource_count PASSED [ 88%]
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_eventsource_webhook_configurations PASSED [100%]

====================================== 9 passed in 28.12s =======================================
```

### Failed Test Example

```bash
tests/test_repo_registrations_rendering.py::TestRepoRegistrationsRendering::test_argocd_applications_count FAILED

=================================== FAILURES ===================================
_____ TestRepoRegistrationsRendering.test_argocd_applications_count ______

    def test_argocd_applications_count(self):
        """Test that exactly 3 ArgoCD Applications are generated."""
        print("\n🧪 Testing ArgoCD Applications count...")
        
        applications = self._filter_by_kind('Application')
        repo_reg_apps = self._filter_by_label(applications, 'source', 'repo-registration')
        
        expected_count = 3
        actual_count = len(repo_reg_apps)
        
>       assert actual_count == expected_count, (
            f"Expected {expected_count} ArgoCD Applications from repoRegistrations, "
            f"but found {actual_count}"
        )
E       AssertionError: Expected 3 ArgoCD Applications from repoRegistrations, but found 2
```

## Troubleshooting

### Common Issues

#### 1. Helm Command Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'helm'`

**Solution**: Install Helm or ensure it's in your PATH
```bash
# On macOS
brew install helm

# On Linux
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 2. Chart Dependencies Missing

**Error**: `Error: found in Chart.yaml, but missing in charts/ directory`

**Solution**: The chart has some dependencies commented out in Chart.yaml for testing. This is expected for local development.

#### 3. YAML Parsing Errors

**Error**: `yaml.scanner.ScannerError`

**Solution**: The rendered output may contain invalid YAML. Check Helm template syntax in the chart.

#### 4. Environment Variable Issues

**Error**: Test failures related to missing configuration

**Solution**: Set required environment variables or rely on defaults:
```bash
export GITHUB_PAT="your-github-token"
export ARGOCD_SECRET_KEY="$(openssl rand -hex 32)"
pytest tests/test_repo_registrations_rendering.py -v
```

## Continuous Integration

### Running in CI/CD

Example GitHub Actions workflow:

```yaml
name: Test Helm Templates

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: 'v3.12.0'
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pytest pyyaml
      
      - name: Run tests
        run: |
          pytest tests/test_repo_registrations_rendering.py -v
```

## Extending the Tests

### Adding New Test Cases

To add validation for additional resources:

1. Add a new test method to `TestRepoRegistrationsRendering`
2. Use helper methods to filter resources
3. Write clear assertions with descriptive messages

Example:

```python
def test_new_resource_type(self):
    """Test that new resource type is generated correctly."""
    print("\n🧪 Testing new resource type...")
    
    resources = self._filter_by_kind('NewResourceKind')
    repo_reg_resources = self._filter_by_label(resources, 'source', 'repo-registration')
    
    expected_count = 3
    actual_count = len(repo_reg_resources)
    
    assert actual_count == expected_count, (
        f"Expected {expected_count} resources, but found {actual_count}"
    )
    print(f"✅ Found {actual_count} new resources")
```

### Testing Different Configurations

To test with different `repoRegistrations` configurations:

1. Create a new values file (e.g., `test-values-custom.yaml`)
2. Modify test setup to use the new file
3. Adjust expected counts and values accordingly

## Authz-Adapter Testing

The authz-adapter is a Flask-based authorization service that validates user access. It has its own comprehensive test suite located in `authz-adapter/tests/`.

### Test Structure

```
authz-adapter/
├── app.py                    # Main Flask application
├── Makefile                  # Test commands
├── pytest.ini                # Pytest configuration
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Development/test dependencies
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures
    ├── test_app.py           # Main application tests
    ├── test_groups.py        # Group authorization tests
    ├── test_integration.py   # Integration tests
    └── test_performance.py   # Performance tests
```

### Running Authz-Adapter Tests

From the `authz-adapter/` directory:

```bash
# Install dependencies and run all tests with coverage
make test

# Run only unit tests
make test-unit

# Run with coverage report
make test-coverage

# Clean up test artifacts
make clean
```

### Test Classes

#### TestAppBasic
Basic Flask application tests:
- App creation verification
- Health check endpoint (`/healthz`)
- Missing authorization header handling

#### TestFetchUserDoc
Tests for fetching user documents from Fence:
- Bearer token validation
- Service token fallback
- Non-200 response handling
- Timeout and connection error handling
- Invalid JSON response handling

#### TestCheckEndpoint
Tests for the `/check` authorization endpoint:
- Valid user authorization
- Invalid/inactive user handling
- Response header validation

#### TestGetDebuggingVars
Tests for the `get_debugging_vars()` function that supports debug mode:

| Test | Description |
|------|-------------|
| `test_get_debugging_vars_returns_none_when_no_debug_email` | Returns `(None, None)` when `DEBUG_EMAIL` env is not set |
| `test_get_debugging_vars_with_debug_email_env_only` | Works with only `DEBUG_EMAIL` env var set |
| `test_get_debugging_vars_with_debug_email_and_groups_env` | Works with both `DEBUG_EMAIL` and `DEBUG_GROUPS` env vars |
| `test_get_debugging_vars_query_params_override_env` | Query params override env vars when `DEBUG_EMAIL` is set |
| `test_get_debugging_vars_query_email_only` | Query param `debug_email` works with env `DEBUG_EMAIL` |
| `test_get_debugging_vars_query_groups_with_env_email` | Query param `debug_groups` works with env `DEBUG_EMAIL` |
| `test_get_debugging_vars_single_group` | Single group parsing works correctly |
| `test_get_debugging_vars_query_params_ignored_without_debug_email_env` | Query params are ignored without `DEBUG_EMAIL` env (security gate) |

#### TestCheckWithDebuggingVars
Tests for `/check` endpoint behavior with debug variables:

| Test | Description |
|------|-------------|
| `test_check_bypasses_auth_with_debug_email_and_groups` | Auth is bypassed when both `DEBUG_EMAIL` and `DEBUG_GROUPS` are set |
| `test_check_falls_back_to_auth_when_only_debug_email_set` | Falls back to real auth when only `DEBUG_EMAIL` is set (no groups) |
| `test_check_with_debug_query_params` | Query params `debug_email` and `debug_groups` work correctly |
| `test_check_with_debug_groups_override_in_query` | Query `debug_groups` overrides env `DEBUG_GROUPS` |
| `test_check_query_params_ignored_without_debug_email_env` | Query params ignored without `DEBUG_EMAIL` env (security) |
| `test_check_without_auth_fails_when_debug_incomplete` | Returns 401 when debug vars incomplete and no auth provided |
| `test_check_with_empty_debug_groups` | Empty `DEBUG_GROUPS` falls back to real auth |

### Debug Mode Environment Variables

The authz-adapter supports debug mode for testing purposes:

| Variable | Description |
|----------|-------------|
| `DEBUG_EMAIL` | When set, enables debug mode and allows `debug_email`/`debug_groups` query params |
| `DEBUG_GROUPS` | Comma-separated list of groups to assign to the debug user |

**Query Parameters** (only work when `DEBUG_EMAIL` env is set):

| Parameter | Description |
|-----------|-------------|
| `debug_email` | Override the debug email address |
| `debug_groups` | Override the debug groups (comma-separated) |

**Example: Bypass auth for testing**

```bash
# Set environment variables
export DEBUG_EMAIL="test@example.com"
export DEBUG_GROUPS="argo-runner,argo-viewer"

# Start the authz-adapter
python app.py

# Test /check endpoint without Authorization header
curl http://localhost:8080/check
# Returns 200 with X-Auth-Request-Groups: argo-runner,argo-viewer
```

**Example: Use query params to override**

```bash
# With DEBUG_EMAIL env set, use query params
curl "http://localhost:8080/check?debug_email=other@example.com&debug_groups=argo-admin"
# Returns 200 with:
#   X-Auth-Request-Email: other@example.com
#   X-Auth-Request-Groups: argo-admin
```

### Test Coverage

The authz-adapter test suite maintains >80% code coverage. Run the following command to see the current coverage report:

```bash
# Run tests with coverage report
cd authz-adapter
make test-coverage
```

## Related Documentation

- [RepoRegistration User Guide](repo-registration-guide.md) - How to use repoRegistrations
- [Development Guide](development.md) - General development practices
- [Troubleshooting](troubleshooting.md) - General troubleshooting guide

## Summary

The test suites provide comprehensive validation for both Helm template rendering and authz-adapter functionality:

**Helm Template Tests** (`tests/`):
- ✅ All expected Kubernetes resources are generated
- ✅ Resource names and labels are correct
- ✅ Configurations match input values
- ✅ S3 bucket settings are properly templated
- ✅ GitHub webhooks are configured correctly

**Authz-Adapter Tests** (`authz-adapter/tests/`):
- ✅ Authorization flow with Fence integration
- ✅ Debug mode for testing without Fence
- ✅ Query param and env var precedence
- ✅ Error handling for various failure scenarios
- ✅ Performance and resource usage validation

Run the tests regularly during development to catch errors early and maintain high quality standards.
