# Orphan Resources Analysis

This document identifies "dead" or "orphan" values, templates, and documentation in the argo-helm repository following the migration to the RepoRegistration pattern.

## Executive Summary

The migration to `repoRegistrations` pattern has left several legacy configurations and templates that are either:
1. **Deprecated but documented** - Kept for migration reference
2. **Hardcoded values** - Should be parameterized or removed
3. **Unused templates** - Still reference the old `applications` array
4. **Inconsistent namespace references** - Mix of hardcoded `wf-poc` and templated values

---

## 1. Deprecated Legacy Values (Documented but Orphaned)

### 1.1 `applications` Array (values.yaml:242)
**Status**: DEPRECATED and documented  
**Location**: `helm/argo-stack/values.yaml`  
**References**: 
- Line 242: `applications: []` with deprecation notice
- Template: `templates/workflows/per-app-workflowtemplates.yaml` (line 6) still iterates over this

**Issue**: The `per-app-workflowtemplates.yaml` template still uses `{{- range .Values.applications }}` but this array is deprecated.

**Recommendation**: 
- Remove `templates/workflows/per-app-workflowtemplates.yaml` entirely
- Remove the `applications: []` value from `values.yaml`
- Update `values-multi-app.yaml` to use `repoRegistrations` instead

### 1.2 `events.github.repositories` Array (values.yaml:278)
**Status**: DEPRECATED and documented  
**Location**: `helm/argo-stack/values.yaml`  
**References**: Line 278: `repositories: []` with deprecation notice

**Issue**: Documented as removed but still present in values.yaml

**Recommendation**: 
- Remove the `repositories: []` entry (keep the deprecation comment for one more release)

### 1.3 Legacy Event Sensor Configuration (values.yaml:310-317)
**Status**: ORPHANED - No template uses this  
**Location**: `helm/argo-stack/values.yaml`
```yaml
sensor:
  enabled: true
  name: run-nextflow-on-push
  workflowNamespace: wf-poc
  workflowTemplateRef: nextflow-hello-template
  parameters:
    - name: git_revision
      valueFrom: "{{(events.push.body.head_commit.id)}}"
```

**Issue**: No template references `.Values.events.sensor.*` anymore. The new sensor is generated from `repoRegistrations` in `templates/events/sensor-github-push.yaml`

**Recommendation**: Remove this entire `sensor` block from values.yaml

---

## 2. Hardcoded Namespace Values

### 2.1 `wf-poc` Hardcoded in RBAC Templates
**Status**: INCONSISTENT - Should use templated values  
**Locations**:
- `templates/workflows/argo-workflow-runner-rbac.yaml` (lines 6, 12, 21, 43, 47)
- `templates/events/role-wf-submit.yaml` (multiple lines)
- `templates/10-rbac.yaml` (lines 65, 91, 105)

**Issue**: These templates hardcode `wf-poc` instead of using `{{ .Values.namespaces.tenant }}`

**Recommendation**: Replace all hardcoded `wf-poc` references with `{{ .Values.namespaces.tenant }}` in:
- `templates/workflows/argo-workflow-runner-rbac.yaml`
- `templates/events/role-wf-submit.yaml` (if it exists)
- `templates/10-rbac.yaml`

### 2.2 `namespaces.tenant` Value
**Status**: ORPHANED - Not used by RepoRegistration pattern  
**Location**: `helm/argo-stack/values.yaml:11`
```yaml
namespaces:
  tenant: wf-poc
```

**Issue**: The RepoRegistration pattern creates per-tenant namespaces (`wf-<org>-<repo>`) dynamically. The static `tenant` namespace is only used by legacy templates.

**Current Usage**:
- Referenced by `templates/10-rbac.yaml` for `nextflow-launcher` ServiceAccount
- Referenced by `templates/20-artifact-repositories.yaml` for legacy S3 credentials
- Referenced by legacy templates

**Recommendation**: 
- Keep for backward compatibility if needed
- Document clearly that it's only for legacy/example templates
- Or remove entirely if not needed (check if anyone deploys without repoRegistrations)

---

## 3. Orphaned Workflow Templates

### 3.1 `workflowtemplate-nextflow-hello.yaml`
**Status**: EXAMPLE/LEGACY  
**Location**: `templates/workflows/workflowtemplate-nextflow-hello.yaml`

**Issue**: Creates a simple example WorkflowTemplate controlled by `workflowTemplates.createExample`. Only used for demonstrations, not by RepoRegistration pattern.

**Recommendation**: 
- Keep as an example if useful for testing
- Clearly document it's for testing/examples only
- Consider moving to an examples/ directory

### 3.2 `workflowtemplate-nextflow-runner.yaml`
**Status**: LEGACY - Superseded by `nextflow-repo-runner`  
**Location**: `templates/workflows/workflowtemplate-nextflow-runner.yaml`

**Issue**: This creates a `nextflow-runner` WorkflowTemplate in the `argo-workflows` namespace. The new pattern uses `nextflow-repo-runner` created per-tenant.

**Current References**:
- Not referenced by `repoRegistrations` (which use `nextflow-repo-runner`)
- May be used by manual workflow submissions

**Recommendation**: 
- If not used, remove it
- If kept for manual testing, document clearly
- Check if anyone uses it outside of RepoRegistration

### 3.3 `per-app-workflowtemplates.yaml`
**Status**: ORPHANED - Uses deprecated `applications` array  
**Location**: `templates/workflows/per-app-workflowtemplates.yaml`

**Issue**: Iterates over `.Values.applications` which is deprecated

**Recommendation**: Remove this template entirely (replaced by `per-tenant-workflowtemplates.yaml`)

---

## 4. Orphaned Values Configuration Blocks

### 4.1 `workflowTemplates` Block (values.yaml:319-328)
**Status**: PARTIALLY ORPHANED  
**Location**: `helm/argo-stack/values.yaml`
```yaml
workflowTemplates:
  createExample: true
  namespace: wf-poc
  nextflowHello:
    name: nextflow-hello-template
    image: alpine:3.20
    command: ["/bin/sh", "-c"]
    args:
      - echo "Hello from Argo Events!"
```

**Usage**: 
- Only used by `templates/workflows/workflowtemplate-nextflow-hello.yaml`
- Not used by RepoRegistration pattern

**Recommendation**: 
- Keep if the example template is useful
- Otherwise remove

### 4.2 `workflows` Block (values.yaml:329-332)
**Status**: MOSTLY ORPHANED  
**Location**: `helm/argo-stack/values.yaml`
```yaml
workflows:
  namespace: wf-poc
  runnerServiceAccount: wf-runner
  templateRef: nextflow-hello-template
```

**Usage**:
- `runnerServiceAccount` is used in `templates/events/sensor-github-push.yaml:54`
- Other fields appear unused

**Recommendation**: 
- Keep `runnerServiceAccount` with better documentation
- Remove `namespace` and `templateRef` (not used by repoRegistrations)

### 4.3 `s3` Block (values.yaml:188-195)
**Status**: LEGACY - Superseded by repoRegistrations.artifactBucket  
**Location**: `helm/argo-stack/values.yaml`
```yaml
s3:
  enabled: false
  hostname: ""
  bucket: ""
  region: ""
  insecure: false
  pathStyle: true
  accessKey: ""
  secretKey: ""
```

**Usage**:
- Used by `templates/20-artifact-repositories.yaml` for global artifact repository
- Superseded by per-repo artifact configuration in RepoRegistrations

**Recommendation**: 
- Keep for backward compatibility (some may want a global default)
- Document that repoRegistrations.artifactBucket is preferred
- Or remove if truly not needed

---

## 5. Documentation Analysis

### 5.1 Current Documentation Files
All documentation appears current and relevant:
- ✅ `docs/DEPRECATION_NOTICE.md` - Documents migration from old patterns
- ✅ `docs/repo-registration-guide.md` - User guide for new pattern
- ✅ `docs/template-overlap-analysis.md` - Analysis of template overlap
- ✅ Other docs appear current and useful

**Recommendation**: No changes needed to documentation

### 5.2 Example Files
- ✅ `examples/repo-registrations-example.yaml` - Current
- ✅ `examples/repo-registrations-values.yaml` - Current
- ⚠️ `values-multi-app.yaml` - Uses deprecated `applications` array

**Recommendation**: 
- Update `values-multi-app.yaml` to demonstrate `repoRegistrations` instead of `applications`

---

## 6. Orphaned Artifact Repository Templates

### 6.1 `20-artifact-repositories.yaml`
**Status**: LEGACY - For global S3 config  
**Location**: `templates/20-artifact-repositories.yaml`

**Issue**: Creates a global `artifact-repositories` ConfigMap in the `argo-workflows` namespace when `s3.enabled: true`. RepoRegistrations create per-tenant ConfigMaps instead.

**Recommendation**: 
- Keep for backward compatibility with non-RepoRegistration deployments
- Document that it's only used when `s3.enabled: true` and not using RepoRegistrations

### 6.2 `21-per-app-artifact-repositories-from-repo-registrations.yaml`
**Status**: ACTIVE but misnamed  
**Location**: `templates/21-per-app-artifact-repositories-from-repo-registrations.yaml`

**Issue**: Name suggests "per-app" but it's actually "per-repo" using RepoRegistrations

**Recommendation**: Consider renaming for clarity (or keep for backward compatibility)

---

## Summary of Recommendations

### ✅ Completed (High Priority)
1. ✅ **REMOVED** `templates/workflows/per-app-workflowtemplates.yaml` (used deprecated `applications`)
2. ✅ **REMOVED** `events.sensor` block from `values.yaml` (lines 310-317)
3. ✅ **REMOVED** `events.github.repositories: []` from `values.yaml`
4. ✅ **REMOVED** `applications: []` from `values.yaml`

### ✅ Completed (Medium Priority)
5. ✅ **REPLACED** hardcoded `wf-poc` with `{{ .Values.namespaces.tenant }}` in:
   - `templates/workflows/argo-workflow-runner-rbac.yaml`
   - `templates/10-rbac.yaml`
   - `templates/events/role-wf-submit.yaml`
   - `templates/workflows/sensor-argo-events-rbac.yaml`

6. ✅ **UPDATED** `values-multi-app.yaml` to use `repoRegistrations` instead of `applications`

7. ✅ **SIMPLIFIED** `workflows` block in `values.yaml`:
   - Kept: `runnerServiceAccount`
   - Removed: `namespace`, `templateRef`

### 🔍 Remaining Items for Consideration (Low Priority)
8. ⚠️ **EVALUATE** if `workflowtemplate-nextflow-runner.yaml` is still needed
   - Status: KEPT - May be used for manual testing
   - Location: `templates/workflows/workflowtemplate-nextflow-runner.yaml`
   
9. ⚠️ **EVALUATE** if `workflowtemplate-nextflow-hello.yaml` should be kept as example
   - Status: KEPT - Useful for testing and examples
   - Location: `templates/workflows/workflowtemplate-nextflow-hello.yaml`
   
10. ⚠️ **DOCUMENT** that `s3` block is legacy (or remove if truly unused)
    - Status: KEPT - Provides backward compatibility for global artifact config
    - Location: `values.yaml:188-195`
    
11. ⚠️ **DOCUMENT** that `namespaces.tenant` is for backward compatibility only
    - Status: KEPT - Used by legacy RBAC templates and examples
    - Location: `values.yaml:11`

---

## Changes Made

### Commit 1: Analysis
- Created comprehensive ORPHAN_ANALYSIS.md document

### Commit 2: Cleanup
- **Removed** `per-app-workflowtemplates.yaml` - obsolete template using deprecated `applications` array
- **Updated** `values.yaml`:
  - Removed `applications: []` declaration
  - Removed `events.github.repositories: []` declaration
  - Removed `events.sensor` configuration block
  - Simplified `workflows` block (kept only `runnerServiceAccount`)
  - Updated deprecation comments to reference correct documentation
- **Updated** all RBAC templates to use `{{ .Values.namespaces.tenant }}` instead of hardcoded `wf-poc`:
  - `templates/10-rbac.yaml`
  - `templates/events/role-wf-submit.yaml`
  - `templates/workflows/argo-workflow-runner-rbac.yaml`
  - `templates/workflows/sensor-argo-events-rbac.yaml`
- **Updated** `values-multi-app.yaml` to demonstrate `repoRegistrations` pattern instead of deprecated `applications`

### Impact
- **Breaking Changes**: None - removed only already-deprecated and unused configurations
- **Improved Consistency**: All namespace references now use templated values
- **Better Documentation**: Clearer migration guidance with correct doc links
- **Reduced Confusion**: Removed orphaned configuration blocks that no longer work

---

## Files That Are NOT Orphaned (Keep)

These are actively used by the RepoRegistration pattern:
- ✅ `templates/01-tenant-namespaces-from-repo-registrations.yaml`
- ✅ `templates/11-tenant-rbac-from-repo-registrations.yaml`
- ✅ `templates/22-tenant-artifact-repositories-from-repo-registrations.yaml`
- ✅ `templates/argocd/applications-from-repo-registrations.yaml`
- ✅ `templates/events/eventsource-github-from-repo-registrations.yaml`
- ✅ `templates/events/sensor-github-push.yaml`
- ✅ `templates/eso/externalsecret-repo-registrations-github.yaml`
- ✅ `templates/eso/externalsecret-repo-registrations-s3.yaml`
- ✅ `templates/workflows/per-tenant-workflowtemplates.yaml`
- ✅ `templates/workflows/workflowtemplate-nextflow-repo-runner.yaml`

---

## Testing Recommendations

Before removing any files:
1. Verify no one is using the legacy `applications` pattern in production
2. Verify no manual workflows depend on `nextflow-runner` template
3. Verify the hardcoded `wf-poc` replacement doesn't break existing deployments
4. Test with `helm template` to ensure no rendering errors
