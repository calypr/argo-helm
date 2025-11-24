[Home](index.md) > Architecture and Design

# Template Overlap and Redundancy Analysis

## Executive Summary

**UPDATE 2025-11-20**: Legacy templates have been removed. This document now serves as historical reference.

This analysis previously examined the Helm templates in `helm/argo-stack/templates/` to identify overlaps and redundancies. The templates originally supported two configuration patterns:
1. **Legacy Pattern** (REMOVED): Direct configuration via `values.yaml` using `.Values.applications` and `.Values.events.github.repositories`
2. **RepoRegistration Pattern** (CURRENT): Self-service onboarding via `RepoRegistration` CRD using `.Values.repoRegistrations`

**All legacy templates have been removed. Only the RepoRegistration pattern is now supported.**

See [DEPRECATION_NOTICE.md](./DEPRECATION_NOTICE.md) for migration guidance.

## Template Categorization

### 1. Workflow Templates

| Template | Purpose | Configuration Source | Redundancy Level |
|----------|---------|---------------------|------------------|
| `workflowtemplate-nextflow-repo-runner.yaml` | Git repo pipeline runner with S3 artifacts | Static/RepoRegistration | **Primary** |
| `workflowtemplate-nextflow-runner.yaml` | Generic Nextflow runner with embedded/remote pipeline | Static | **Overlapping** |
| `workflowtemplate-nextflow-hello.yaml` | Example/test template | Static | **Example only** |

**Overlap Analysis:**
- `nextflow-repo-runner` and `nextflow-runner` both run Nextflow pipelines
- `nextflow-repo-runner` is optimized for RepoRegistration pattern (uses `repo-name` parameter for secret lookup)
- `nextflow-runner` uses hardcoded secret names (`s3-credentials`) and supports inline pipelines
- **Recommendation**: These serve different use cases:
  - Keep `nextflow-repo-runner` for RepoRegistration-driven workflows
  - Keep `nextflow-runner` for ad-hoc/development workflows
  - Consider adding a parameter to `nextflow-runner` to accept custom secret names for better flexibility

**Key Differences:**
```yaml
# nextflow-repo-runner: Per-repo secrets
env:
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: s3-cred-{{workflow.parameters.repo-name}}  # Dynamic
        key: AWS_ACCESS_KEY_ID

# nextflow-runner: Global secrets
volumeMounts:
  - name: s3-credentials
    mountPath: /secrets/s3
volumes:
  - name: s3-credentials
    secret:
      secretName: s3-credentials  # Static
```

### 2. ExternalSecret Templates

**Legacy templates REMOVED**:
- ❌ `externalsecret-github.yaml` (was: GitHub token for events from static config)
- ❌ `externalsecret-s3.yaml` (was: Global S3 credentials from static config)
- ❌ `externalsecret-per-app-s3.yaml` (was: Per-app S3 credentials)

**Current templates**:
- ✅ `externalsecret-repo-registrations-github.yaml` | Per-repo GitHub tokens | RepoRegistration | `{{githubSecretName}}`
- ✅ `externalsecret-repo-registrations-s3.yaml` | Per-repo S3 credentials | RepoRegistration | `s3-credentials-{{name}}`

**Resolution:**
- All legacy S3 and GitHub credential patterns have been removed
- Only per-repo secrets via RepoRegistration are supported
- This eliminates the three-pattern overlap that previously existed

### 3. Artifact Repository ConfigMaps

**Legacy templates REMOVED**:
- ❌ `21-per-app-artifact-repositories.yaml` (was: Per-app artifact repos from `.Values.applications[].artifacts`)

**Current templates**:
- ✅ `20-artifact-repositories.yaml` | Global artifact repo | `.Values.s3` | `artifact-repositories` | **Global fallback**
- ✅ `21-per-app-artifact-repositories-from-repo-registrations.yaml` | Per-repo artifact repos | `.Values.repoRegistrations[].artifactBucket` | `argo-artifacts-{{name}}` | **Primary**

**Resolution:**
- Legacy per-app template removed
- No more naming conflicts - only RepoRegistration creates per-repo ConfigMaps
- Global artifact repository retained as fallback for workflows not using RepoRegistration

### 4. ArgoCD Application Templates

**Legacy templates REMOVED**:
- ❌ `argocd/applications.yaml` (was: ArgoCD apps from `.Values.applications`)

**Current templates**:
- ✅ `argocd/applications-from-repo-registrations.yaml` | ArgoCD apps from RepoRegistration | `.Values.repoRegistrations` | `{{.name}}`

**Resolution:**
- Legacy template removed
- No more naming conflicts
- All ArgoCD Applications created from RepoRegistration with consistent tenant labels and conventions

### 5. Argo Events EventSource Templates

**Legacy templates REMOVED**:
- ❌ `events/eventsource-github.yaml` (was: GitHub webhook events from `.Values.events.github.repositories`)

**Current templates**:
- ✅ `events/eventsource-github-from-repo-registrations.yaml` | GitHub events from RepoRegistration | `.Values.repoRegistrations` | `github-repo-registrations`

**Resolution:**
- Legacy template removed
- No more webhook path conflicts
- All EventSources created from RepoRegistration with consistent naming

## Summary of Changes

### Removed Templates (Legacy Pattern)

All legacy templates have been removed as of 2025-11-20:

1. ❌ **ConfigMap**: `21-per-app-artifact-repositories.yaml` - Artifact repository configurations from `.Values.applications`
2. ❌ **ArgoCD Application**: `argocd/applications.yaml` - Application manifests from `.Values.applications`
3. ❌ **ExternalSecret**: `eso/externalsecret-github.yaml` - Global GitHub token
4. ❌ **ExternalSecret**: `eso/externalsecret-s3.yaml` - Global S3 credentials
5. ❌ **ExternalSecret**: `eso/externalsecret-per-app-s3.yaml` - Per-app S3 credentials
6. ❌ **EventSource**: `events/eventsource-github.yaml` - GitHub webhooks from `.Values.events.github.repositories`

### Remaining Templates (RepoRegistration Pattern)

✅ **Active templates** - all driven by `.Values.repoRegistrations`:

1. ✅ `21-per-app-artifact-repositories-from-repo-registrations.yaml` - Per-repo artifact ConfigMaps
2. ✅ `argocd/applications-from-repo-registrations.yaml` - ArgoCD Applications
3. ✅ `eso/externalsecret-repo-registrations-github.yaml` - Per-repo GitHub tokens
4. ✅ `eso/externalsecret-repo-registrations-s3.yaml` - Per-repo S3 credentials
5. ✅ `events/eventsource-github-from-repo-registrations.yaml` - GitHub webhooks

✅ **Retained global defaults**:
- `20-artifact-repositories.yaml` - Global artifact repository fallback

### Issues Resolved

All previously identified conflicts have been resolved:

1. ✅ **ConfigMap Naming Conflict** - RESOLVED: Only RepoRegistration creates per-repo ConfigMaps
2. ✅ **ArgoCD Application Naming Conflict** - RESOLVED: Only RepoRegistration creates Applications
3. ✅ **Ingress Path Conflict** - RESOLVED: Only RepoRegistration creates EventSources
4. ✅ **Multiple S3 Secret Patterns** - RESOLVED: Only per-repo pattern remains
5. ✅ **GitHub Secret Patterns** - RESOLVED: Only per-repo pattern remains

## Consolidation Strategy

### Implemented: Complete Legacy Removal

The aggressive consolidation approach has been implemented:

✅ **All legacy templates removed** - Clean break from old pattern  
✅ **No naming conflicts** - Single source of truth via RepoRegistration  
✅ **Simplified codebase** - Fewer templates to maintain  
✅ **Clear migration path** - See [DEPRECATION_NOTICE.md](./DEPRECATION_NOTICE.md)

### Current Architecture

The chart now follows a single, consistent pattern:

```
RepoRegistration CRD
        ↓
  Helm Templates
        ↓
    ┌───┴───┬────────┬──────────┬────────┐
    ↓       ↓        ↓          ↓        ↓
ConfigMap  ArgoCD  GitHub   S3       EventSource
           App     Secret   Secret
```

**Benefits**:
- ✅ Single configuration source (`.Values.repoRegistrations`)
- ✅ No resource conflicts
- ✅ Consistent naming conventions
- ✅ Self-service onboarding
- ✅ Vault-backed security

**Retained for flexibility**:
- Global artifact repository (`20-artifact-repositories.yaml`)
- Multiple Nextflow WorkflowTemplates for different use cases
- Example templates (`workflowtemplate-nextflow-hello.yaml`)

## Recommendations

### ✅ Completed Actions

1. ✅ **Removed all legacy templates** - No more name conflicts or overlapping patterns
2. ✅ **Created deprecation documentation** - Clear migration guide available
3. ✅ **Simplified template structure** - Single pattern, easier to understand and maintain

### Current State

The chart now exclusively uses the RepoRegistration pattern:
- ✅ All resources created from `.Values.repoRegistrations`
- ✅ No conflicts between configuration sources
- ✅ Consistent naming and labeling
- ✅ Vault integration for all secrets

### For Users

**If migrating from legacy pattern**:
1. Read [DEPRECATION_NOTICE.md](./DEPRECATION_NOTICE.md)
2. Convert `.Values.applications` entries to `.Values.repoRegistrations` format
3. Ensure Vault secrets are configured at the paths specified in RepoRegistration
4. Test with `helm template` before deploying
5. Deploy and verify all resources are created correctly

**For new deployments**:
1. Read [REPO_REGISTRATION_USER_GUIDE.md](./REPO_REGISTRATION_USER_GUIDE.md)
2. Configure `.Values.repoRegistrations` in your `values.yaml`
3. Deploy the chart

### Next Steps

Potential future enhancements:
- Add validation webhook for RepoRegistration CRD
- Add status conditions to RepoRegistration for better observability
- Consider controller for dynamic reconciliation
- Add more WorkflowTemplate examples

## Pattern Comparison

### Before (Removed) vs After (Current)

| Feature | Legacy Pattern (REMOVED) | RepoRegistration Pattern (CURRENT) |
|---------|-------------------------|-------------------------------------|
| Configuration | Manual YAML in `values.yaml` | CRD + `.Values.repoRegistrations` |
| S3 Credentials | Global or per-app | Per-repo from Vault |
| GitHub Credentials | Global | Per-repo from Vault |
| Artifact Repository | Shared or per-app | Per-repo |
| ArgoCD Integration | Manual Application | Auto-generated |
| Argo Events | Manual EventSource | Auto-generated |
| Multi-tenancy | Limited | Built-in (tenant labels) |
| Self-service | No | Yes |
| Resource Conflicts | Possible | Eliminated |
| Migration Required | N/A | Yes (see DEPRECATION_NOTICE.md) |

## Conclusion

**Status**: Legacy templates removed as of 2025-11-20

The template structure has been simplified to support only the RepoRegistration pattern:

✅ **All conflicts resolved** - No more naming collisions or routing ambiguity  
✅ **Single source of truth** - `.Values.repoRegistrations` only  
✅ **Clear architecture** - One pattern, well-documented  
✅ **Migration path** - Documented in [DEPRECATION_NOTICE.md](./DEPRECATION_NOTICE.md)

**Key Outcomes:**
1. ✅ Naming conflicts eliminated
2. ✅ Webhook routing conflicts eliminated
3. ✅ S3 credential patterns unified (per-repo only)
4. ✅ Codebase simplified and easier to maintain

**For existing users:**
- Migration to RepoRegistration is **required**
- Follow the guide in [DEPRECATION_NOTICE.md](./DEPRECATION_NOTICE.md)
- Vault setup required for secret management

**For new users:**
- Start with [REPO_REGISTRATION_USER_GUIDE.md](./REPO_REGISTRATION_USER_GUIDE.md)
- Use only `.Values.repoRegistrations` configuration
- Enjoy self-service onboarding and Vault integration

This analysis now serves as historical reference for the consolidation decision and as documentation of the resolved conflicts.
