# Template Overlap and Redundancy Analysis

## Executive Summary

This analysis examines the Helm templates in `helm/argo-stack/templates/` to identify overlaps, redundancies, and opportunities for consolidation. The templates support two configuration patterns:
1. **Legacy Pattern**: Direct configuration via `values.yaml` using `.Values.applications` and `.Values.events.github.repositories`
2. **RepoRegistration Pattern**: Self-service onboarding via `RepoRegistration` CRD using `.Values.repoRegistrations`

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

| Template | Purpose | Source | Target Secret Pattern | Redundancy |
|----------|---------|--------|----------------------|------------|
| `externalsecret-github.yaml` | GitHub token for events | Static config | `github-webhook` | **Legacy** |
| `externalsecret-repo-registrations-github.yaml` | Per-repo GitHub tokens | RepoRegistration | `{{githubSecretName}}` | **Replacement** |
| `externalsecret-s3.yaml` | Global S3 credentials | Static config | `s3-credentials` | **Legacy** |
| `externalsecret-repo-registrations-s3.yaml` | Per-repo S3 credentials | RepoRegistration | `s3-credentials-{{name}}` | **Replacement** |
| `externalsecret-per-app-s3.yaml` | Per-app S3 credentials | `.Values.externalSecrets.secrets.perAppS3` | `s3-cred-{{appName}}` | **Overlapping** |

**Overlap Analysis:**
- **Three patterns for S3 credentials**:
  1. Global: `s3-credentials` (from `externalsecret-s3.yaml`)
  2. Per-app: `s3-cred-{{appName}}` (from `externalsecret-per-app-s3.yaml`)
  3. Per-repo: `s3-credentials-{{name}}` (from `externalsecret-repo-registrations-s3.yaml`)

- **Two patterns for GitHub credentials**:
  1. Global: `github-webhook` (from `externalsecret-github.yaml`)
  2. Per-repo: `{{githubSecretName}}` (from `externalsecret-repo-registrations-github.yaml`)

**Recommendation:**
- **Keep all three S3 patterns** - they serve different use cases:
  - Global: Default for all workflows
  - Per-app: Legacy pattern for `.Values.applications`
  - Per-repo: New pattern for `.Values.repoRegistrations`
- **Consider deprecating** the global GitHub secret in favor of per-repo secrets
- **Consolidate** per-app-s3 and repo-registrations-s3 if `.Values.applications` pattern is being phased out

### 3. Artifact Repository ConfigMaps

| Template | Purpose | Source | ConfigMap Name Pattern | Redundancy |
|----------|---------|--------|----------------------|------------|
| `20-artifact-repositories.yaml` | Global artifact repo | `.Values.s3` | `artifact-repositories` | **Global** |
| `21-per-app-artifact-repositories.yaml` | Per-app artifact repos | `.Values.applications[].artifacts` | `argo-artifacts-{{name}}` | **Legacy** |
| `21-per-app-artifact-repositories-from-repo-registrations.yaml` | Per-repo artifact repos | `.Values.repoRegistrations[].artifactBucket` | `argo-artifacts-{{name}}` | **Replacement** |

**Overlap Analysis:**
- Two templates create ConfigMaps with **identical naming pattern** (`argo-artifacts-{{name}}`)
- Both reference different sources but serve the same purpose
- Only differ in feature flag checks and value paths

**Critical Issue:**
- If both `.Values.applications` and `.Values.repoRegistrations` contain entries with the same `name`, they will **conflict** and create duplicate ConfigMaps
- The templates have the same output structure but read from different input sources

**Recommendation:**
- **High Priority**: Add validation or mutual exclusion logic
- **Option 1**: Rename one pattern (e.g., `argo-artifacts-rr-{{name}}` for RepoRegistration)
- **Option 2**: Merge into a single template that handles both sources
- **Option 3**: Document that `applications[].name` and `repoRegistrations[].name` must be unique across both lists

### 4. ArgoCD Application Templates

| Template | Purpose | Source | Application Name | Redundancy |
|----------|---------|--------|-----------------|------------|
| `argocd/applications.yaml` | ArgoCD apps from static config | `.Values.applications` | `{{.name}}` | **Legacy** |
| `argocd/applications-from-repo-registrations.yaml` | ArgoCD apps from RepoRegistration | `.Values.repoRegistrations` | `{{.name}}` | **Replacement** |

**Overlap Analysis:**
- Both templates create ArgoCD `Application` resources
- Both use `{{.name}}` as the Application name - **potential for conflicts**
- Similar structure but different feature sets:
  - `applications.yaml`: More flexible (custom destination, custom annotations)
  - `applications-from-repo-registrations.yaml`: Opinionated defaults, tenant labels

**Recommendation:**
- Same issue as artifact repositories - names can conflict
- Document name uniqueness requirement OR use namespace separation
- Consider adding `source: repo-registration` label to distinguish them

### 5. Argo Events EventSource Templates

| Template | Purpose | Source | EventSource Name | Redundancy |
|----------|---------|--------|-----------------|------------|
| `events/eventsource-github.yaml` | GitHub webhook events | `.Values.events.github.repositories` | `github` | **Legacy** |
| `events/eventsource-github-from-repo-registrations.yaml` | GitHub events from RepoRegistration | `.Values.repoRegistrations` | `github-repo-registrations` | **Replacement** |

**Overlap Analysis:**
- Both create GitHub EventSources for webhooks
- Different names prevent conflicts (`github` vs `github-repo-registrations`)
- Both create separate Services and Ingresses
- Both use the same webhook endpoint path - **potential routing conflict**

**Recommendation:**
- Good: Names are different
- Issue: Both try to expose the same webhook path (`/events`) on the same Ingress host
- **Fix needed**: Use different paths or hostnames for each EventSource
- Consider path prefixes: `/events/static` vs `/events/repo-registrations`

## Summary of Redundancies

### High Priority Issues

1. **ConfigMap Naming Conflict** (`argo-artifacts-{{name}}`)
   - **Risk**: High - Direct resource conflict
   - **Impact**: Chart installation failure or undefined behavior
   - **Fix**: Rename one pattern or merge templates

2. **ArgoCD Application Naming Conflict** (both use `{{.name}}`)
   - **Risk**: High - ArgoCD Application conflict
   - **Impact**: One application overwrites the other
   - **Fix**: Enforce unique names or use namespace separation

3. **Ingress Path Conflict** (both use `/events`)
   - **Risk**: Medium - Webhook routing ambiguity
   - **Impact**: GitHub webhooks may route incorrectly
   - **Fix**: Use different paths or host-based routing

### Medium Priority Issues

4. **Three S3 Secret Patterns** (global, per-app, per-repo)
   - **Risk**: Low - Templates are conditional
   - **Impact**: Confusion about which to use
   - **Fix**: Document the pattern clearly, consider migration path from per-app to per-repo

5. **Two Nextflow WorkflowTemplates** (repo-runner vs runner)
   - **Risk**: Low - Different use cases
   - **Impact**: Confusion about which to use
   - **Fix**: Document use cases clearly, possibly add parameter for secret name flexibility

## Consolidation Opportunities

### Option A: Merge Templates (Aggressive)

Create unified templates that handle both legacy and RepoRegistration patterns:

```yaml
# Example: Unified ExternalSecret for S3
{{- if .Values.externalSecrets.enabled }}
  {{- if .Values.s3.enabled }}
    # Global S3 secret
  {{- end }}
  {{- range .Values.repoRegistrations }}
    # Per-repo S3 secrets
  {{- end }}
  {{- range $appName, $paths := .Values.externalSecrets.secrets.perAppS3 }}
    # Per-app S3 secrets
  {{- end }}
{{- end }}
```

**Pros**: Fewer files, single source of truth
**Cons**: More complex conditionals, harder to read

### Option B: Namespace Separation (Conservative)

Keep templates separate but use namespaces to avoid conflicts:
- Legacy pattern: Deploy to `argo` namespace
- RepoRegistration pattern: Deploy to `argo-tenant` namespace

**Pros**: Clean separation, no conflicts
**Cons**: Requires namespace management, more complex RBAC

### Option C: Name Prefixing (Moderate)

Add prefixes to distinguish resources:
- Legacy: `app-{{name}}`
- RepoRegistration: `repo-{{name}}`

**Pros**: Clear distinction, no conflicts
**Cons**: Breaking change for existing deployments

### Option D: Deprecation Path (Recommended)

1. Mark legacy templates as deprecated
2. Add validation to prevent name conflicts
3. Document migration from `.Values.applications` to `.Values.repoRegistrations`
4. Remove legacy templates in next major version

**Pros**: Clear migration path, backwards compatible
**Cons**: Temporary duplication

## Recommendations

### Immediate Actions

1. **Add validation** to prevent name conflicts:
   ```yaml
   {{- $allNames := list }}
   {{- range .Values.applications }}
     {{- $allNames = append $allNames .name }}
   {{- end }}
   {{- range .Values.repoRegistrations }}
     {{- if has .name $allNames }}
       {{- fail (printf "Duplicate name '%s' found in both applications and repoRegistrations" .name) }}
     {{- end }}
   {{- end }}
   ```

2. **Fix EventSource path conflict**:
   - Use different webhook paths: `/events/legacy` and `/events/repo-registrations`
   - OR use host-based routing with different subdomains

3. **Document the patterns clearly**:
   - When to use global vs per-app vs per-repo S3 credentials
   - When to use each Nextflow WorkflowTemplate
   - Migration path from legacy to RepoRegistration pattern

### Long-term Strategy

1. **Deprecate legacy pattern** (`.Values.applications`) in favor of RepoRegistration
2. **Merge per-app and per-repo templates** once migration is complete
3. **Standardize on per-repo secrets** for all use cases
4. **Keep example templates separate** (`nextflow-hello`) but clearly marked

## Pattern Comparison Matrix

| Feature | Legacy Pattern | RepoRegistration Pattern |
|---------|---------------|-------------------------|
| Configuration | Manual YAML | CRD-driven |
| S3 Credentials | Global or per-app | Per-repo from Vault |
| GitHub Credentials | Global | Per-repo from Vault |
| Artifact Repository | Shared or per-app | Per-repo |
| ArgoCD Integration | Manual Application | Auto-generated |
| Argo Events | Manual EventSource | Auto-generated |
| Multi-tenancy | Limited | Built-in (tenant labels) |
| Self-service | No | Yes |
| Migration Effort | N/A | Medium (requires Vault setup) |

## Conclusion

The current template structure supports two distinct patterns that overlap significantly:

**Overlaps are intentional** - the RepoRegistration pattern is designed to replace the legacy pattern while maintaining backwards compatibility.

**Key Issues:**
1. Name collision potential (high priority)
2. Webhook routing conflict (medium priority)
3. Multiple S3 credential patterns (low priority - by design)

**Recommended Path Forward:**
- Implement validation to prevent conflicts (immediate)
- Document both patterns clearly (immediate)
- Plan deprecation of legacy pattern (6-12 months)
- Consolidate templates in next major version (12+ months)

This analysis suggests the redundancy is **intentional for migration purposes** but needs **better conflict prevention** and **clearer documentation**.
