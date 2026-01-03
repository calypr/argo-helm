# Workflow Template Versioning Documentation

## Overview

Workflow templates in the argo-wrapper ecosystem use a **Git-based versioning strategy** where template names include Git commit hashes to ensure reproducible, traceable workflow executions.  Templates are pre-deployed Argo `WorkflowTemplate` resources that define the actual computational steps, while argo-wrapper dynamically references these templates when users submit workflows.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Template Repository (vadc-genesis-cwl)                 │
│  https://github.com/uc-cdis/vadc-genesis-cwl            │
│                                                         │
│  /argo/gwas-workflows/                                  │
│  ├── gwas-template-abc1234.yaml  (git hash: abc1234)   │
│  ├── gwas-template-def5678.yaml  (git hash: def5678)   │
│  └── plp-template-v1.2.3.yaml                           │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Manual deployment: 
                  │ 1. Clone repository
                  │ 2. SCP template. yaml to cluster
                  │ 3. argo template create -n argo template. yaml
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Kubernetes Cluster (namespace: argo)                   │
│                                                         │
│  WorkflowTemplates:                                     │
│  ├── gwas-template-abc1234                              │
│  ├── gwas-template-def5678                              │
│  ├── gwas-template-latest  (points to newest)           │
│  └── plp-template-v1.2.3                                │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Referenced by workflowTemplateRef
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  User Workflow Submission                               │
│                                                         │
│  POST /submit                                           │
│  {                                                      │
│    "template_version": "gwas-template-abc1234",         │
│    "n_pcs": 3,                                          │
│    "outcome":  2000006885,                               │
│    ...                                                   │
│  }                                                      │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Argo Workflow Instance                                 │
│                                                         │
│  spec:                                                  │
│    workflowTemplateRef:                                 │
│      name: gwas-template-abc1234                        │
│    arguments:                                           │
│      parameters:  [...]                                  │
└─────────────────────────────────────────────────────────┘
```

## Template Naming Convention

### Format

```
{workflow-type}-template-{version-identifier}
```

### Workflow Types

| Prefix | Workflow Type | Description |
|--------|--------------|-------------|
| `gwas-template` | Genome-Wide Association Study | Statistical genetics analysis pipeline |
| `plp-template` | Patient Level Prediction | Machine learning prediction workflows |

### Version Identifiers

| Type | Example | Use Case |
|------|---------|----------|
| **Git Commit Hash** | `gwas-template-abc1234567` | Specific immutable version |
| **Git Short Hash** | `gwas-template-abc1234` | 7-character commit hash |
| **Semantic Version** | `plp-template-v1.2.3` | Release-based versioning |
| **Latest** | `gwas-template-latest` | Always points to newest version |

### Example Template Names

```yaml
# Production templates (immutable)
gwas-template-6226080403eb62585981d9782aec0f3a82a7e906  # Full Git hash
gwas-template-6226080                                    # Short Git hash
plp-template-v1.2.3                                      # Semantic version

# Development/testing templates
gwas-template-latest                                     # Latest stable
gwas-template-dev                                        # Development branch
plp-template-staging                                     # Staging environment
```

## Template Versioning Workflow

### 1. **Template Development**

Templates are developed in the `vadc-genesis-cwl` repository: 

**Repository**:  [uc-cdis/vadc-genesis-cwl](https://github.com/uc-cdis/vadc-genesis-cwl)

**Location**: `/argo/gwas-workflows/`

**Example template structure**: 
```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: gwas-template-abc1234
  namespace: argo
spec: 
  entrypoint: gwas-workflow
  templates:
    - name: gwas-workflow
      steps:
        - - name: prepare-phenotype
            template: prepare-phenotype-step
        - - name: run-null-model
            template: run-null-model-step
        # ... more steps
```

### 2. **Git Commit and Hash Generation**

When a template is modified and committed: 

```bash
# Make changes to template
vim gwas-workflow.yaml

# Commit changes
git add gwas-workflow.yaml
git commit -m "Add new QC step to GWAS pipeline"

# Get commit hash
GIT_HASH=$(git rev-parse HEAD)
# e.g., 6226080403eb62585981d9782aec0f3a82a7e906

# Update template name with git hash
sed -i "s/name: gwas-template-. */name: gwas-template-${GIT_HASH}/" gwas-workflow.yaml
```

### 3. **Template Deployment**

**Source**: `docs/readmes/argo-templates.md`

Manual deployment process: 

```bash
# Step 1: Clone the template repository
git clone https://github.com/uc-cdis/vadc-genesis-cwl. git
cd vadc-genesis-cwl/argo/gwas-workflows

# Step 2: SCP template to cluster
scp gwas-template-abc1234.yaml user@cluster. example.com:/tmp/

# Step 3: SSH to cluster and create template
ssh user@cluster.example. com

# Step 4: Create the WorkflowTemplate in Argo
argo template create -n argo /tmp/gwas-template-abc1234.yaml

# Step 5: Verify deployment
argo template list -n argo

# Expected output:
# NAME                        CREATED
# gwas-template-abc1234       2025-01-15T10:30:00Z
# gwas-template-latest        2025-01-15T10:30:00Z
# plp-template-v1.2.3         2025-01-10T14:20:00Z
```

### 4. **Template Updates**

If changes are needed: 

```bash
# Delete old template
argo template delete -n argo gwas-template-abc1234

# Repeat deployment steps 1-5
```

## How Templates Are Referenced

### 1. **User Request**

User submits workflow via API:

```bash
curl -X POST https://example.com/ga4gh/wes/v2/submit \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "template_version": "gwas-template-6226080",
    "team_project": "my-research",
    "n_pcs":  3,
    "case_cohort_definition_id": 401,
    "outcome": 2000006885,
    "variables": [... ],
    "genome_build": "hg19"
  }'
```

### 2. **Workflow Factory Pattern**

The `WorkflowFactory` determines which workflow class to instantiate:

**Source**: `src/argowrapper/engine/helpers/workflow_factory.py`
```python
class WorkflowFactory:
    @staticmethod
    def _get_workflow(
        namespace:  str,
        request_body: Dict[str, Any],
        auth_header: Optional[str],
    ):
        # Determine workflow type from template_version prefix
        if request_body["template_version"].startswith("plp-template"):
            workflow = PLP
        elif request_body["template_version"].startswith("gwas-template"):
            workflow = GWAS
        
        return workflow(namespace, request_body, auth_header)
```

**Decision Logic**:
- `template_version` starting with `plp-template` → `PLP` class
- `template_version` starting with `gwas-template` → `GWAS` class

### 3. **Template Reference Assignment**

The workflow class sets the template reference:

**Source**: `src/argowrapper/workflows/argo_workflows/gwas. py`
```python
class GWAS(WorkflowBase):
    def setup_spec(self):
        super().setup_spec()
        self.spec. set_podGC_strategy(POD_COMPLETION_STRATEGY. ONPODCOMPLETION. value)
        self._add_spec_scaling_group()
        self._add_spec_podMetadata_annotations()
        self._add_spec_podMetadata_labels()
        self._add_spec_parameters()
        self._add_spec_volumes()
        
        # Set the workflow template reference from user's template_version
        self.spec. set_workflow_template_ref(
            self.workflow_parameters.get("template_version")
        )
```

**Source**: `src/argowrapper/workflows/workflow_spec.py`
```python
class WorkflowSpec:
    def set_workflow_template_ref(self, workflow_template_name: str) -> None:
        self.workflowTemplateRef = {"name": workflow_template_name}
```

### 4. **Generated Workflow YAML**

The submitted workflow references the template:

```yaml
apiVersion: argoproj.io/v1alpha1
kind:  Workflow
metadata:
  name:  gwas-workflow-1234567890
  namespace: argo
  labels:
    gen3username: "user-alice"
    gen3teamproject: "my-research"
spec:
  # Reference to the WorkflowTemplate
  workflowTemplateRef:
    name:  gwas-template-6226080
  
  # User-provided parameters
  arguments:
    parameters: 
      - name: n_pcs
        value: "3"
      - name: outcome
        value: "2000006885"
      - name: case_cohort_definition_id
        value: "401"
      # ... more parameters
```

### 5. **Argo Resolution**

When Argo executes the workflow: 

1. Argo reads the `workflowTemplateRef`
2. Looks up `gwas-template-6226080` in the `argo` namespace
3. Merges the template definition with workflow parameters
4. Executes the resulting workflow steps

## Version Management Strategies

### Production Deployments

```bash
# 1. Use full Git commit hashes for traceability
gwas-template-6226080403eb62585981d9782aec0f3a82a7e906

# 2. Create a "latest" alias pointing to newest version
kubectl create -f gwas-template-latest.yaml

# 3. Tag releases in Git
git tag -a v2.1.0 -m "Release 2.1.0: Add new QC filters"
git push origin v2.1.0
```

### Rollback Procedures

```bash
# 1. List available templates
argo template list -n argo

# 2. Identify previous version
# gwas-template-olderhash  (previously deployed)

# 3. Update "latest" to point to older version
argo template create -n argo gwas-template-olderhash. yaml --overwrite
```

### Multiple Environment Strategy

| Environment | Template Name | Version Strategy |
|-------------|--------------|------------------|
| **Development** | `gwas-template-dev` | Latest commit on `develop` branch |
| **Staging** | `gwas-template-staging` | Release candidates (e.g., `v2.1.0-rc1`) |
| **Production** | `gwas-template-{hash}` | Immutable Git commit hashes |
| **Production Latest** | `gwas-template-latest` | Alias to current production version |

## Template Validation

### 1. **Required Template Reference**

Workflow spec validation:

**Source**: `src/argowrapper/workflows/workflow_spec. py`
```python
class WorkflowSpec:
    def to_argo_spec_dict(self):
        if not self.entrypoint:
            logger.error("workflow must have an entrypoint")
            return {}
        
        # Template reference is REQUIRED
        if not self.workflowTemplateRef:
            logger.error("workflow must refer to an existing workflow template")
            return {}
        
        return self._to_dict()
```

### 2. **Template Existence Check**

Before submitting, verify template exists:

```bash
# Check if template exists
argo template get -n argo gwas-template-abc1234

# If not found, deployment will fail with: 
# Error: WorkflowTemplate "gwas-template-abc1234" not found
```

## Example:  End-to-End Versioning Workflow

### Scenario: Deploying a New GWAS Template Version

```bash
# ==========================================
# Step 1: Development (in vadc-genesis-cwl repo)
# ==========================================
cd vadc-genesis-cwl/argo/gwas-workflows

# Make changes to the workflow
vim gwas-workflow.yaml
# ...  add new QC step ...

# ==========================================
# Step 2: Commit and Generate Version
# ==========================================
git add gwas-workflow.yaml
git commit -m "feat: Add imputation score QC filter"

# Get commit hash
GIT_HASH=$(git rev-parse --short HEAD)  # e.g., "abc1234"

# Update template metadata
cat > gwas-template-${GIT_HASH}.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: gwas-template-${GIT_HASH}
  namespace: argo
  labels:
    version: ${GIT_HASH}
    workflow-type: gwas
spec: 
  # ... workflow definition ...
EOF

git add gwas-template-${GIT_HASH}.yaml
git commit -m "chore: Create versioned template for ${GIT_HASH}"
git push origin master

# ==========================================
# Step 3: Deploy to Cluster
# ==========================================
# SCP to cluster
scp gwas-template-${GIT_HASH}. yaml admin@cluster:/tmp/

# SSH and create template
ssh admin@cluster
argo template create -n argo /tmp/gwas-template-${GIT_HASH}.yaml

# Verify
argo template get -n argo gwas-template-${GIT_HASH}

# ==========================================
# Step 4: Update "latest" Alias (Optional)
# ==========================================
# Create/update gwas-template-latest to point to new version
cp gwas-template-${GIT_HASH}.yaml gwas-template-latest.yaml
sed -i 's/name: gwas-template-. */name: gwas-template-latest/' gwas-template-latest.yaml
argo template create -n argo gwas-template-latest.yaml

# ==========================================
# Step 5: User Submission
# ==========================================
# Users can now reference the new version
curl -X POST https://example.com/ga4gh/wes/v2/submit \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "template_version":  "gwas-template-abc1234",
    "n_pcs": 3,
    ... 
  }'

# Or use "latest"
curl -X POST https://example.com/ga4gh/wes/v2/submit \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "template_version": "gwas-template-latest",
    "n_pcs": 3,
    ...
  }'
```

## Testing Template Versions

### Test Request Examples

**Source**: `test/test_gwas_workflow.py`
```python
# Testing with specific template version
request_body = {
    "n_pcs": 3,
    "variables": [... ],
    "out_prefix": "vadc_genesis",
    "outcome": 1,
    "maf_threshold": 0.01,
    "imputation_score_cutoff": 0.3,
    "template_version":  "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
    "source_id": 4,
    "case_cohort_definition_id":  70,
    "team_project": "dummy-team-project",
}

# Create workflow instance
gwas = GWAS(ARGO_NAMESPACE, request_body, EXAMPLE_AUTH_HEADER)
gwas_yaml = gwas._to_dict()

# Verify template reference
assert gwas_yaml["spec"]["workflowTemplateRef"]["name"] == \
    "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906"
```

## Version Tracking and Auditing

### Workflow Metadata

Every submitted workflow includes template version in metadata:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  name: gwas-workflow-1234567890
  annotations:
    workflow_name: "my-gwas-analysis"
    workflows.argoproj.io/version: ">= 3.1.0"
    template_version: "gwas-template-abc1234"  # Stored for audit
spec:
  workflowTemplateRef:
    name: gwas-template-abc1234
```

### Query Workflows by Template Version

```bash
# List all workflows using a specific template
kubectl get workflows -n argo -l template-version=gwas-template-abc1234

# Get workflow history for template
argo list -n argo --label template-version=gwas-template-abc1234
```

## Best Practices

### 1. **Immutable Versioning**
- ✅ Use Git commit hashes for production templates
- ✅ Never modify deployed templates in-place
- ✅ Deploy new version instead of updating existing

### 2. **Version Documentation**
- ✅ Include Git hash in template name
- ✅ Add labels for version, type, environment
- ✅ Maintain CHANGELOG in template repository

### 3. **Backward Compatibility**
- ✅ Keep old template versions deployed for historical workflows
- ✅ Test new versions in staging before production
- ✅ Document breaking changes in template parameters

### 4. **Deployment Automation**
- ⚠️ Currently manual - consider automating with: 
  - GitHub Actions (on tag/release)
  - ArgoCD (GitOps sync)
  - CI/CD pipeline

### 5. **Template Lifecycle**
```
Development → Testing → Staging → Production
    ↓           ↓          ↓           ↓
dev-hash   test-hash  staging-hash  {git-hash}
                                       ↓
                                   latest (alias)
```

## Common Issues and Solutions

### Issue 1: Template Not Found

**Error**:
```
Error: WorkflowTemplate "gwas-template-abc1234" not found
```

**Solution**:
```bash
# Verify template exists
argo template list -n argo | grep abc1234

# If missing, deploy template
argo template create -n argo gwas-template-abc1234.yaml
```

### Issue 2: Template Version Mismatch

**Error**: 
```
Error: Parameter mismatch - expected "n_segments" but not found
```

**Solution**:
- Check template version in request matches deployed template
- Verify template parameter definitions
- Update request to match template expectations

### Issue 3: Outdated "Latest" Alias

**Problem**:  `gwas-template-latest` points to old version

**Solution**:
```bash
# Delete old "latest"
argo template delete -n argo gwas-template-latest

# Create new "latest" pointing to newest version
argo template create -n argo gwas-template-newest.yaml
```

## Future Enhancements

### Automated GitOps Deployment

**Proposed CI/CD Pipeline**:
```yaml
# .github/workflows/deploy-templates.yml
name: Deploy Workflow Templates

on:
  push:
    tags:
      - 'v*'
    paths:
      - 'argo/gwas-workflows/*. yaml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Get Git Hash
        run: echo "GIT_HASH=$(git rev-parse --short HEAD)" >> $GITHUB_ENV
      
      - name: Deploy to Staging
        run: |
          kubectl config use-context staging
          argo template create -n argo gwas-template-${GIT_HASH}.yaml
      
      - name: Deploy to Production (on release)
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          kubectl config use-context production
          argo template create -n argo gwas-template-${GIT_HASH}.yaml
```

### Version Discovery API

**Proposed Endpoint**:
```bash
GET /templates? workflow_type=gwas

Response:
{
  "templates":  [
    {
      "name": "gwas-template-abc1234",
      "version":  "abc1234",
      "created": "2025-01-15T10:30:00Z",
      "git_hash": "abc1234567890",
      "status": "active"
    },
    {
      "name":  "gwas-template-latest",
      "version": "latest",
      "points_to": "gwas-template-abc1234"
    }
  ]
}
```

---

**Document Version**:  1.0  
**Last Updated**: 2025-12-29  
**Repository**: [uc-cdis/argo-wrapper](https://github.com/uc-cdis/argo-wrapper)  
**Template Repository**: [uc-cdis/vadc-genesis-cwl](https://github.com/uc-cdis/vadc-genesis-cwl)