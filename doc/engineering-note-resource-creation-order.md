# Engineering Note: Helm Resource Creation Order for RepoRegistration

**Date**: 2025-11-20  
**Author**: Copilot SWE Agent  
**Issue**: Helm installation failures due to resource ordering dependencies  
**PR**: #[number] - Fix Helm resource ordering for RepoRegistration tenant namespaces

---

## Problem Statement

### Observed Behavior

The Helm installation was failing during deployment with the following error:

```
Error: unable to build kubernetes objects from release manifest: [
  resource mapping not found for name: "github-secret-nextflow-hello" 
  namespace: "wf-bwalsh-nextflow-hello-project" 
  from "": no matches for kind "ExternalSecret" in version "external-secrets.io/v1beta1"
  ensure CRDs are installed first,
  
  resource mapping not found for name: "s3-credentials-nextflow-hello-project" 
  namespace: "wf-bwalsh-nextflow-hello-project" 
  from "": no matches for kind "ExternalSecret" in version "external-secrets.io/v1beta1"
  ensure CRDs are installed first,
  ...
]
```

### Root Cause Analysis

The error message was misleading - it suggested CRDs were not installed, but the actual issue was different. Investigation revealed:

1. **ExternalSecret CRDs were properly installed** by the External Secrets Operator
2. **Tenant namespaces were created via Helm pre-install hooks** with weight `-10`
3. **ExternalSecret and RBAC resources were created during main installation phase**
4. **SecretStore/ClusterSecretStore was created via post-install hooks** (no explicit weight)

The problem occurred because Helm validates all resources during the main installation phase. When it tried to validate ExternalSecret resources that referenced tenant namespaces, those namespaces existed as hook resources but were not visible to the main installation's validation process. Additionally, the ExternalSecrets referenced a SecretStore that was scheduled to be created later via post-install hooks.

This created a circular dependency:
- ExternalSecrets (main install) → need → Tenant Namespaces (pre-install hooks)
- ExternalSecrets (main install) → need → SecretStore (post-install hooks)

Helm's validation failed because it couldn't resolve these dependencies during the main installation phase.

---

## Solution Design

### Strategy

Convert all resources that depend on tenant namespaces or the SecretStore to use Helm hooks with explicit ordering via hook weights. This ensures resources are created in proper dependency order outside the main installation phase.

### Resource Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│ PRE-INSTALL PHASE                                           │
├─────────────────────────────────────────────────────────────┤
│ Weight: -10                                                 │
│ • Tenant Namespaces (wf-{org}-{repo})                      │
│   - Created from repoRegistrations                          │
│   - Labeled with tenant metadata                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ MAIN INSTALL PHASE                                          │
├─────────────────────────────────────────────────────────────┤
│ • ArgoCD Applications (in argocd namespace)                 │
│ • ConfigMaps for artifact repositories (in argo namespace)  │
│ • Other non-tenant resources                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ POST-INSTALL PHASE                                          │
├─────────────────────────────────────────────────────────────┤
│ Weight: 0                                                   │
│ • ESO ServiceAccount (eso-vault-auth)                       │
│   - In external-secrets-system namespace                    │
│   - Used for Vault authentication                           │
│ • SecretStore / ClusterSecretStore                          │
│   - References ServiceAccount for Vault auth                │
│   - Required by all ExternalSecrets                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ POST-INSTALL PHASE                                          │
├─────────────────────────────────────────────────────────────┤
│ Weight: 1                                                   │
│ • Tenant RBAC Resources (in tenant namespaces)              │
│   - ServiceAccount: workflow-runner                         │
│   - Role: workflow-executor                                 │
│   - RoleBinding: workflow-executor-binding                  │
│   - Role: sensor-workflow-creator                           │
│   - RoleBinding: sensor-workflow-creator-binding            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ POST-INSTALL PHASE                                          │
├─────────────────────────────────────────────────────────────┤
│ Weight: 5                                                   │
│ • ExternalSecrets (in tenant namespaces)                    │
│   - S3 artifact bucket credentials                          │
│   - S3 data bucket credentials (if different)               │
│   - GitHub credentials                                      │
│   - References SecretStore (weight 0)                       │
│   - Creates actual Kubernetes Secrets from Vault            │
└─────────────────────────────────────────────────────────────┘
```

### Hook Weight Selection Rationale

- **Weight -10 (pre-install)**: Namespaces must be created first, before any other resources
- **Weight 0 (post-install)**: Foundation resources that other resources depend on
- **Weight 1 (post-install)**: RBAC resources that need namespaces and will be used by workflows
- **Weight 5 (post-install)**: ExternalSecrets that depend on both namespaces and SecretStore

The gap between weights (1 → 5) allows for future insertion of intermediate resources if needed.

---

## Implementation Details

### Files Modified

#### 1. ExternalSecret Templates (Commit f9b3147, Updated 2025-11-20)

**Files**:
- `helm/argo-stack/templates/eso/externalsecret-repo-registrations-s3.yaml`
- `helm/argo-stack/templates/eso/externalsecret-repo-registrations-github.yaml`

**Changes**: Added hook annotations to all ExternalSecret resources:

```yaml
metadata:
  annotations:
    helm.sh/hook: post-install,post-upgrade
    helm.sh/hook-weight: "5"
    # NOTE: helm.sh/hook-delete-policy removed - see Issue 2
```

**UPDATE (2025-11-20)**: Removed `helm.sh/hook-delete-policy: before-hook-creation` to prevent deletion errors during upgrades and rollbacks. ExternalSecrets now persist across Helm operations.

**Resources affected**:
- S3 artifact bucket credentials ExternalSecrets (one per RepoRegistration)
- S3 data bucket credentials ExternalSecrets (when different from artifact bucket)
- GitHub credentials ExternalSecrets (one per RepoRegistration)

**Reasoning**: These resources must be created after:
1. Tenant namespaces exist (pre-install, weight -10)
2. SecretStore is ready (post-install, weight 0)
3. RBAC is configured (post-install, weight 1)

#### 2. ESO Infrastructure Templates (Commit f9b3147)

**Files**:
- `helm/argo-stack/templates/eso/secretstore.yaml`
- `helm/argo-stack/templates/eso/serviceaccount.yaml`

**Changes**: Added explicit hook-weight to existing post-install hooks:

```yaml
metadata:
  annotations:
    "helm.sh/hook": post-install,post-upgrade
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
```

**Previous state**: These templates already had `post-install,post-upgrade` hooks but lacked explicit weights, which meant Helm could execute them in any order or potentially in parallel.

**Reasoning**: Explicit weight ensures deterministic ordering - these must be created before ExternalSecrets (weight 5).

#### 3. Tenant RBAC Templates (Commit 896f20b)

**File**:
- `helm/argo-stack/templates/11-tenant-rbac-from-repo-registrations.yaml`

**Changes**: Added hook annotations to all RBAC resources:

```yaml
metadata:
  annotations:
    helm.sh/hook: post-install,post-upgrade
    helm.sh/hook-weight: "1"
    helm.sh/hook-delete-policy: before-hook-creation
```

**Resources affected** (per RepoRegistration):
- ServiceAccount: `workflow-runner` (for workflow execution)
- Role: `workflow-executor` (permissions for workflow pods)
- RoleBinding: `workflow-executor-binding`
- Role: `sensor-workflow-creator` (for Argo Events sensors)
- RoleBinding: `sensor-workflow-creator-binding`

**Reasoning**: RBAC resources must be created after namespaces exist but before workflows or secrets are created. Weight 1 positions them between infrastructure (0) and secrets (5).

### Hook Delete Policy

All hooks use `before-hook-creation` delete policy:

```yaml
helm.sh/hook-delete-policy: before-hook-creation
```

**Rationale**: 
- On upgrades, the old hook resources are deleted before new ones are created
- Prevents conflicts from previous installations
- Ensures clean state for each Helm operation
- Resources created by hooks persist after the hook completes (they're not auto-deleted)

---

## Why Helm Hooks?

### Understanding Helm's Installation Phases

Helm processes resources in three distinct phases:

1. **Pre-install/Pre-upgrade hooks**: Run before any manifest is installed
2. **Main installation**: Install all non-hook resources
3. **Post-install/Post-upgrade hooks**: Run after main installation completes

Within each phase, resources with hooks are ordered by weight (ascending).

### The Validation Problem

During the main installation phase, Helm:
1. Collects all non-hook resources
2. Validates them against the Kubernetes API
3. Creates them in a batch

The validation step requires that:
- Referenced namespaces exist in the cluster
- Referenced CRDs exist in the cluster
- Referenced resources (like SecretStores) exist in the cluster

Since tenant namespaces were created via pre-install hooks, they existed in the cluster but weren't part of the main installation batch. Helm's validation couldn't see them, causing failures.

### Why Not Just Create Everything in Main Install?

We cannot move namespace creation to main install because:
1. Namespaces must exist before resources in those namespaces can be created
2. Helm creates main install resources in parallel batches
3. There's no guarantee of ordering within the main install phase
4. This could lead to race conditions

---

## Testing Strategy

### Validation Steps

1. **Clean installation test**:
   ```bash
   make deploy
   ```
   Should succeed without namespace-related errors.

2. **Verify resource creation order**:
   ```bash
   # Check namespaces created first
   kubectl get ns -l calypr.io/workflow-tenant=true
   
   # Check SecretStore exists
   kubectl get secretstore -A
   
   # Check RBAC in tenant namespaces
   kubectl get sa,role,rolebinding -n wf-{org}-{repo}
   
   # Check ExternalSecrets created
   kubectl get externalsecrets -A
   
   # Check actual Secrets synced from Vault
   kubectl get secrets -n wf-{org}-{repo}
   ```

3. **Upgrade test**:
   ```bash
   helm upgrade argo-stack ./helm/argo-stack -n argocd
   ```
   Should handle hook deletion and recreation cleanly.

4. **Hook execution verification**:
   ```bash
   # Check hook resources
   kubectl get all -A -l helm.sh/hook
   ```

### Expected Behavior

- No "resource mapping not found" errors
- All namespaces created before resources that reference them
- ExternalSecrets successfully sync secrets from Vault
- Workflows can execute using the RBAC and secrets

---

## Potential Issues and Mitigations

### Issue 1: Hook Execution Time

**Problem**: Hooks run sequentially by weight, which could slow down installation.

**Mitigation**: 
- Resources with the same weight run in parallel
- Only create weight gaps where strict ordering is required
- Current design has only 4 weight levels (-10, 0, 1, 5)

### Issue 2: Hook Resource Cleanup

**Problem**: Hook resources are not automatically deleted after use (despite the name `hook-delete-policy`).

**Clarification**: The `before-hook-creation` policy only deletes the hook resources from *previous* Helm operations, not the resources created by the current hook. This is desired behavior - we want the namespaces, RBAC, and secrets to persist.

**UPDATE (2025-11-20)**: The `before-hook-creation` policy on ExternalSecret resources caused installation failures when Helm attempted to delete old hook resources during upgrades or failed installations. The error "unable to build kubernetes object for deleting hook" occurred because the ExternalSecret CRD wasn't available during the deletion phase.

**Resolution**: Removed `helm.sh/hook-delete-policy: before-hook-creation` from ExternalSecret templates (`externalsecret-repo-registrations-github.yaml` and `externalsecret-repo-registrations-s3.yaml`). ExternalSecrets now persist across upgrades without being deleted and recreated, matching the behavior of `externalsecret-argocd.yaml`. This prevents deletion errors while maintaining proper hook ordering via `helm.sh/hook-weight`.

### Issue 3: Failure During Hook Execution

**Problem**: If a hook fails, the entire Helm operation fails.

**Mitigation**:
- Ensure Vault is running and seeded before installation
- Ensure External Secrets Operator is installed
- Use `--wait` flag to ensure resources are ready before proceeding
- Check Vault connectivity and authentication before installation

### Issue 4: Circular Dependencies

**Problem**: What if a hook resource depends on something from main install?

**Mitigation**: 
- Current design has no such dependencies
- ArgoCD Applications (main install) reference tenant namespaces, but only by name - Kubernetes allows creating resources with non-existent namespace references
- ConfigMaps (main install) reference secrets by name, which is also allowed

---

## Best Practices Established

1. **Always use explicit hook weights**: Even if resources could theoretically run in parallel, explicit weights make behavior predictable and debuggable.

2. **Document dependency relationships**: The dependency graph in this document should be updated when new resource types are added.

3. **Use meaningful weight gaps**: Gaps (like 1 → 5) allow for future insertions without renumbering everything.

4. **Test both install and upgrade**: Hooks behave differently in these scenarios due to the `before-hook-creation` policy.

5. **Validate hook execution order**: After changes, verify with `kubectl get events --sort-by='.lastTimestamp'` to see actual creation order.

---

## Future Considerations

### Scaling to More RepoRegistrations

The current design creates resources per RepoRegistration. With many registrations:
- Hook execution time increases linearly
- Consider batching or parallelization if this becomes a bottleneck
- Current implementation is adequate for dozens of registrations

### Adding New Resource Types

When adding new resources to tenant namespaces:

1. Determine dependencies (namespace, SecretStore, RBAC, secrets)
2. Choose appropriate hook weight based on dependency graph
3. Update this document with the new resource type
4. Test installation and upgrade scenarios

### Alternative Approaches Considered

**Operator Pattern**: 
- Could create a custom operator watching RepoRegistration CRDs
- Operator would manage resource creation order
- **Rejected**: Adds operational complexity, Helm hooks are simpler

**Namespace Pre-creation**:
- Could require namespaces to be created externally
- **Rejected**: Violates self-service onboarding goals

**No Hooks**:
- Create everything in main install and rely on Kubernetes eventual consistency
- **Rejected**: Causes Helm validation failures and race conditions

---

## References

- [Helm Hooks Documentation](https://helm.sh/docs/topics/charts_hooks/)
- [External Secrets Operator](https://external-secrets.io/)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- Original Issue: https://github.com/calypr/argo-helm/issues/[number]
- Pull Request: https://github.com/calypr/argo-helm/pull/[number]

---

## Revision History

| Date       | Author              | Changes                          |
|------------|---------------------|----------------------------------|
| 2025-11-20 | Copilot SWE Agent   | Initial document creation        |
| 2025-11-20 | Copilot SWE Agent   | Remove before-hook-creation from ExternalSecrets to fix deletion errors |

