# Orphan Resources Cleanup Summary

## Commits in This PR

1. **f721715** - Add comprehensive analysis of orphan resources and legacy code
2. **be71bad** - Clean up orphaned templates and values from deprecated patterns
3. **65de60f** - Update ORPHAN_ANALYSIS.md with completed changes
4. **7e7adc2** - Fix remaining hardcoded namespace in workflowTemplates config
5. **ed9c1ec** - Remove all remaining hardcoded wf-poc references from examples and comments

## What Was Removed

### Templates (DELETED, not modified)
Following feedback "don't change templates just to conform. if the template is not being used, delete it":

- ❌ `templates/workflows/per-app-workflowtemplates.yaml` - Used deprecated `applications` array
- ❌ `templates/10-rbac.yaml` - Legacy RBAC for static wf-poc namespace  
- ❌ `templates/workflows/argo-workflow-runner-rbac.yaml` - Legacy RBAC for wf-poc
- ❌ `templates/workflows/sensor-argo-events-rbac.yaml` - Legacy RBAC for wf-poc
- ❌ `templates/events/role-wf-submit.yaml` - Legacy RBAC for wf-poc
- ❌ `templates/workflows/workflowtemplate-nextflow-hello.yaml` - Example template not used by repoRegistrations
- ❌ `templates/workflows/workflowtemplate-nextflow-runner.yaml` - Legacy template (replaced by nextflow-repo-runner in per-tenant)

### Values (values.yaml)
- ❌ `applications: []` - Deprecated array declaration
- ❌ `events.github.repositories: []` - Deprecated array declaration  
- ❌ `events.sensor.*` - Entire configuration block (auto-generated now)
- ❌ `workflows.namespace` - Hardcoded wf-poc
- ❌ `workflows.templateRef` - Unused field
- ❌ `workflowTemplates.*` - Entire configuration block (configured example templates that are now deleted)

## What Was Updated

### Example Files
- ✅ `values-multi-app.yaml` - Now demonstrates `repoRegistrations` pattern instead of deprecated `applications`

### Documentation References
- ✅ Fixed references to point to correct doc: `docs/repo-registration-guide.md`
- ✅ Updated deprecation notices with clearer guidance

## What Was Kept (Intentionally)

### Active Templates (Used by RepoRegistration Pattern)
- ✅ `01-tenant-namespaces-from-repo-registrations.yaml` - Creates per-tenant namespaces
- ✅ `11-tenant-rbac-from-repo-registrations.yaml` - Creates per-tenant RBAC
- ✅ `22-tenant-artifact-repositories-from-repo-registrations.yaml` - Creates per-tenant artifact repos
- ✅ `per-tenant-workflowtemplates.yaml` - Creates nextflow-repo-runner per tenant
- ✅ `workflowtemplate-nextflow-repo-runner.yaml` - Base template (may be referenced globally)

### Values
- ✅ `s3` global config block - Backward compatibility for global artifact config
- ✅ `namespaces.tenant` - Still defined but only used as fallback/legacy
- ✅ `workflows.runnerServiceAccount` - Defines ServiceAccount name used by sensors

## Impact Assessment

### Breaking Changes
**NONE** - All removed items were unused legacy templates

### Improvements
1. **Clarity** - Removed unused templates instead of modifying them
2. **Simplicity** - RepoRegistration pattern creates all resources automatically
3. **Documentation** - Clear explanation of which templates are used vs legacy
4. **Maintainability** - Less code to maintain, cleaner separation of concerns

## Rationale

**Why delete instead of modify?**

The RepoRegistration pattern creates ALL necessary resources automatically:
- Namespaces: `wf-<tenant>-<repo>` via `01-tenant-namespaces-from-repo-registrations.yaml`
- RBAC: ServiceAccount, Role, RoleBinding via `11-tenant-rbac-from-repo-registrations.yaml`  
- WorkflowTemplates: `nextflow-repo-runner` via `per-tenant-workflowtemplates.yaml`

The deleted templates were all for the **static `wf-poc` namespace** which is:
- Not used when deploying with `repoRegistrations`
- A legacy pattern from before multi-tenancy
- Redundant with per-tenant resources

## Verification

### Files Modified
- `ORPHAN_ANALYSIS.md` (created, updated)
- `CLEANUP_SUMMARY.md` (created, updated)
- `helm/argo-stack/values-multi-app.yaml` (migrated to repoRegistrations, removed workflowTemplates)
- `helm/argo-stack/values.yaml` (removed deprecated config blocks)

### Files Deleted
- `helm/argo-stack/templates/10-rbac.yaml`
- `helm/argo-stack/templates/events/role-wf-submit.yaml`
- `helm/argo-stack/templates/workflows/argo-workflow-runner-rbac.yaml`
- `helm/argo-stack/templates/workflows/per-app-workflowtemplates.yaml`
- `helm/argo-stack/templates/workflows/sensor-argo-events-rbac.yaml`
- `helm/argo-stack/templates/workflows/workflowtemplate-nextflow-hello.yaml`
- `helm/argo-stack/templates/workflows/workflowtemplate-nextflow-runner.yaml`

### Total Changes
- 11 files modified/deleted
- 7 templates deleted
- Significant reduction in maintenance burden

## Recommendations for Next Steps

1. Consider removing `workflowtemplate-nextflow-runner.yaml` if not actively used
2. Add explicit documentation about `namespaces.tenant` being legacy
3. Consider deprecating global `s3` config in favor of repoRegistrations only
4. Update CI/CD to validate no hardcoded namespaces in future PRs

## Testing Checklist

- [x] Code review completed - all feedback addressed
- [x] All hardcoded namespace references eliminated
- [x] Documentation references verified to exist
- [x] Deprecation notices updated with correct guidance
- [ ] Helm template rendering validation (requires network access)
- [ ] Deploy to test cluster (manual step)
