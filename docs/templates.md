[Home](index.md) > Architecture and Design > Templates

# Helm Template Reference

## Purpose

The `helm/argo-stack` chart renders every component of the local Argo platform (Argo CD, Argo Workflows, Argo Events, Vault integration, External Secrets, MinIO, ingress, landing page, GitHub Status Proxy, and helper services). This page explains how templates are structured, how values flow from `my-values.yaml` and environment variables, and how to extend the chart safely.

---

## Chart Layout

| Area | Contents | Notes |
|------|----------|-------|
| `helm/argo-stack/Chart.yaml` | Chart metadata | Lists component versions and chart dependency constraints. |
| `helm/argo-stack/values.yaml` | Default values | Provides sane defaults for local development. |
| `helm/argo-stack/templates/*.yaml` | Component manifests | Deployments, Services, RBAC, ExternalSecrets, Ingress objects, and ConfigMaps for each subsystem. |
| `helm/argo-stack/overlays/ingress-authz-overlay` | Optional overlay | Adds the ingress authorization adapter plus NGINX settings used in `make ports`. |

The templating model assumes you supply a `my-values.yaml` (tracked locally) whose values are merged after environment substitution, then layered with `admin-values.yaml`.

---

## Rendering Workflow

1. **Set environment** – export required variables (`ARGO_HOSTNAME`, `S3_*`, `GITHUBHAPP_*`, etc.). See `check-vars` in the root `Makefile`.
2. **Render templates** – run `make template`, which executes:
   ```bash
   envsubst < my-values.yaml | helm template argo-stack helm/argo-stack ... -f - -f helm/argo-stack/admin-values.yaml
   ```
   The first `-f` injects the substituted `my-values.yaml`; the second applies `admin-values.yaml`.
3. **Validate manifests** – run `make validate` (kubeconform) or `make lint` (helm lint).
4. **Install/upgrade** – `make argo-stack` applies the same merged values with `helm upgrade --install`.
5. **Continuous testing** – `make ct` (chart-testing) ensures lint/install success in CI.

---

## Key Values and Corresponding Templates

| Value path | Affects templates | Description |
|------------|------------------|-------------|
| `global.imagePullSecrets`, `global.nodeSelector`, `global.tolerations` | Everywhere | Shared knobs for advanced scheduling. |
| `ingress.*` | Ingress templates | Sets hosts, TLS secrets, authz overlay, and gitapp callback exposure. |
| `s3.*` | Workflow artifact secret + ConfigMaps | Controls MinIO/S3 connectivity; also referenced in per-tenant `ExternalSecret` templates. |
| `githubApp.*` | GitHub Secret + ExternalSecret templates | Enables ArgoCD + GitHub Status Proxy GitHub App integration. |
| `events.github.*` | Argo Events EventSource/Sensor templates | Sets webhook ingress, callback path, and shared secret. |
| `externalSecrets.*` | ExternalSecret and SecretStore templates | Wiring to Vault and per-tenant credentials. |
| `vault.*` | SecretStore + auth templates | Configures Vault address, auth role, and TLS usage. |
| `githubStatusProxy.*` | Deployment, Service, Secret mounts | Enables the status proxy sidecar. |
| `landingPage.*` | Deployment + ConfigMap | Controls the landing page image and branding strings. |
| `tenants.*` | RepoRegistration, WorkflowTemplate, per-namespace resources | Used to stamp out tenant namespaces, S3 creds, and GitHub tokens. |

---

## Value Files and Priority

1. **Chart defaults** (`values.yaml`)
2. **Admin overlay** (`admin-values.yaml`)
3. **User overrides** (`my-values.yaml`, injected via `envsubst`)
4. **CLI flags** in `make template` / `make argo-stack` (`--set-string ...`), which enforce dynamic values such as `ARGO_HOSTNAME` or secrets pulled from the environment.

Remember: later sources override earlier ones. If a field appears both in `admin-values.yaml` and your `my-values.yaml`, whichever is loaded later wins (your file, because it is piped in immediately before the admin overlay).

---

## Common Customizations

### Override file example

```yaml
# my-values.yaml
global:
  nodeSelector:
    kubernetes.io/arch: amd64

ingress:
  className: nginx
  argocd:
    host: "${ARGO_HOSTNAME}"
  argoWorkflows:
    host: "${ARGO_HOSTNAME}"
  gitappCallback:
    enabled: true
    host: "${ARGO_HOSTNAME}"

s3:
  enabled: ${S3_ENABLED}
  bucket: ${S3_BUCKET}
  hostname: ${S3_HOSTNAME}
  region: ${S3_REGION}
  insecure: true
  pathStyle: true

githubApp:
  enabled: true
  appId: "${GITHUBHAPP_APP_ID}"
  installationId: "${GITHUBHAPP_INSTALLATION_ID}"
  privateKeySecretName: "${GITHUBHAPP_PRIVATE_KEY_SECRET_NAME}"
  privateKeyVaultPath: "${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}"

githubStatusProxy:
  enabled: true
  image:
    repository: ${PROXY_IMAGE}
    tag: ${PROXY_TAG}
```

Because `envsubst` runs before Helm parses the file, keep templated values inside `"${VAR}"`.

### Enabling/disabling components

| Component | Toggle |
|-----------|--------|
| Landing page | `landingPage.enabled` |
| GitHub Status Proxy | `githubStatusProxy.enabled` |
| GitHub App ingress callback | `ingress.gitappCallback.enabled` |
| Repo registrations | Add/remove entries beneath `tenants.repoRegistrations`. |
| MinIO artifacts | Set `s3.enabled=false` to skip the in-cluster MinIO resources and rely on external S3 credentials. |

---

## External Secrets and Vault Wiring

1. `vault-auth` Makefile target writes policy `argo-stack` and binds the `external-secrets-system/eso-vault-auth` ServiceAccount.
2. `helm/argo-stack` installs:
   - A `SecretStore` that points to Vault using the Kubernetes auth role (`githubApp.privateKeyVaultPath`, `externalSecrets.vaultAddress`, etc.).
   - `ExternalSecret` manifests per component and per tenant; each merges data from Vault paths such as `kv/argo/argocd/admin` or `kv/argo/apps/<tenant>/s3`.
3. Ensure the path names in values match the seeded data created by `make vault-seed`. Adjust paths in `my-values.yaml` if you add tenants.

To add a new ExternalSecret, copy one of the existing template stanzas, set `spec.data` entries to the Vault key, and include the namespace reference under `tenants`.

---

## GitHub Webhook and App Templates

- `events.github.secret.*` values generate a Kubernetes `Secret` accessible by the Argo Events `EventSource`.
- `events.github.webhook` drives the ingress host/path (`https://${ARGO_HOSTNAME}/events`) and ensures sensors reference the correct service.
- GitHub App values map to:
  - ExternalSecret for the private key (populated via Vault).
  - ConfigMap/Secret used by the GitHub Status Proxy deployment.
  - Ingress callback route for handling installation events.

When rotating secrets, update the Vault path and re-run `make vault-seed-github-app` or reseed manually, then `kubectl rollout restart deployment -n argocd github-status-proxy`.

---

## Template Development Guidelines

1. **Naming** – follow `<component>-<purpose>.yaml` inside `templates/`.
2. **Helpers** – use Go template helpers defined in `_helpers.tpl` for labels, names, and image references to avoid duplication.
3. **Annotations/labels** – ensure every resource calls the standard label helper to stay consistent with selectors used by other manifests.
4. **Vault paths** – never hardcode secrets; reference values like `.Values.githubApp.privateKeyVaultPath`.
5. **Conditionals** – wrap optional components in `{{- if .Values.<component>.enabled }}` blocks so disabling a feature removes all related manifests.
6. **Namespace ownership** – multi-namespace resources (e.g., Argo Events) should accept the namespace from values rather than assuming `argocd`.
7. **Validation** – run `make lint template validate` before committing.

---

## Verifying Changes Before Commit

1. `make lint` – catches Helm syntax and schema issues.
2. `make template` – dumps rendered manifests to `rendered.yaml`; inspect diffs for unintended changes.
3. `make validate` – runs kubeconform (skipping CRD types excluded via regex).
4. `make ct` – optional but strongly recommended before opening PRs; uses chart-testing with Kind.
5. Document updates – whenever a new template, value, or component is added, update `docs/templates.md` (this file) and any related troubleshooting entry.

By following this workflow, `docs/templates.md` stays aligned with the latest `helm/argo-stack` capabilities and provides a single reference for anyone extending or consuming the chart.

## Template List

# Helm Template Inventory

## `helm/argo-stack/templates/` Directory

| Template | Purpose | Status |
|----------|---------|--------|
| `_eso-helpers.tpl` | Helper functions for External Secrets templating (Vault paths, secret names) | ✅ Active |
| `00-namespaces.yaml` | Creates core namespaces: `argocd`, `argo-workflows`, `argo-events`, `vault`, `minio-system` | ✅ Active |
| `01-tenant-namespaces-from-repo-registrations.yaml` | Dynamically generates per-tenant namespaces from `tenants.repoRegistrations` list | ✅ Active |
| `11-tenant-rbac-from-repo-registrations.yaml` | Stamps out RBAC (ServiceAccounts, Roles, RoleBindings) per tenant namespace | ✅ Active |
| `12-artifact-repository-rbac.yaml` | RBAC for artifact repository access across namespaces | ✅ Active |
| `20-artifact-repositories.yaml` | Configures global artifact repository (MinIO or S3) for Argo Workflows | ✅ Active |
| `22-tenant-artifact-repositories-from-repo-registrations.yaml` | Per-tenant artifact repository configurations | ✅ Active |
| `30-authz-adapter.yaml` | Deploys the authorization adapter sidecar/proxy | ✅ Active |
| `31-landing-page.yaml` | Landing page Deployment, Service, and ConfigMap (conditional on `landingPage.enabled`) | ✅ Active |
| `32-gitapp-callback.yaml` | GitHub App installation callback handler (conditional on `ingress.gitappCallback.enabled`) | ✅ Active |
| `35-github-status-proxy.yaml` | GitHub Status Proxy Deployment, Service, and Secret mounts (conditional on `githubStatusProxy.enabled`) | ✅ Active |
| `40-argo-workflows-ingress.yaml` | Ingress for Argo Workflows UI (`ingress.argoWorkflows.host`) | ✅ Active |
| `41-argocd-ingress.yaml` | Ingress for Argo CD UI (`ingress.argocd.host`) | ✅ Active |
| `90-argocd-application.yaml` | ArgoCD Application resource for managing the Argo stack itself (self-managed, conditional) | ✅ Active |

### `helm/argo-stack/templates/argocd/` Subdirectory

| Template | Purpose | Status |
|----------|---------|--------|
| `applications-from-repo-registrations.yaml` | Generates Argo CD Application manifests per tenant repo registration | ✅ Active |
| `notifications-cm.yaml` | ConfigMap for Argo CD notifications (GitHub status updates, Slack, etc.) | ✅ Active |
| `repo-creds-github-app.yaml` | Repository credentials Secret for GitHub App authentication in Argo CD | ✅ Active |

### `helm/argo-stack/templates/eso/` Subdirectory

| Template | Purpose | Status |
|----------|---------|--------|
| `externalsecret-argocd.yaml` | ExternalSecret syncing Vault secrets to Argo CD (admin password, OIDC, server key) | ✅ Active |
| `externalsecret-github-app.yaml` | ExternalSecret syncing GitHub App private key from Vault | ✅ Active |
| `externalsecret-notifications.yaml` | ExternalSecret for Argo CD notifications credentials | ✅ Active |
| `externalsecret-repo-registrations-github.yaml` | Per-tenant ExternalSecrets for GitHub tokens from Vault | ✅ Active |
| `externalsecret-repo-registrations-s3.yaml` | Per-tenant ExternalSecrets for S3/MinIO credentials from Vault | ✅ Active |
| `secretstore.yaml` | SecretStore linking to Vault via Kubernetes auth | ✅ Active |
| `serviceaccount.yaml` | ServiceAccount for External Secrets Operator with Vault auth binding | ✅ Active |

### `helm/argo-stack/templates/events/` Subdirectory

| Template | Purpose | Status |
|----------|---------|--------|
| `eventbus.yaml` | Argo Events EventBus configuration (native or jetstream) | ✅ Active |
| `eventsource-github-from-repo-registrations.yaml` | Per-tenant GitHub EventSource for webhook ingestion | ✅ Active |
| `secret-github.yaml` | Secret containing GitHub webhook shared token and credentials | ✅ Active |
| `sensor-github-push.yaml` | Argo Events Sensor triggering workflows on GitHub push events | ✅ Active |

### `helm/argo-stack/templates/roles/` Subdirectory

| Template | Purpose | Status |
|----------|---------|--------|
| `workflow-rbac.yaml` | RBAC for Argo Workflows (ServiceAccount, ClusterRole, ClusterRoleBinding) | ✅ Active |

### `helm/argo-stack/templates/workflows/` Subdirectory

| Template | Purpose | Status |
|----------|---------|--------|
| `clusterworkflowtemplate-github-notifications.yaml` | ClusterWorkflowTemplate for GitHub status notifications | ✅ Active |
| `clusterworkflowtemplate-rbac.yaml` | RBAC for ClusterWorkflowTemplate access | ✅ Active |
| `per-tenant-workflowtemplates.yaml` | Per-tenant WorkflowTemplates stamped from `tenants.repoRegistrations` | ✅ Active |
| `workflowtemplate-nextflow-repo-runner.yaml` | WorkflowTemplate for Nextflow repository execution | ⚠️ **Consider Deprecating** – appears hardcoded for specific repo; consider making generic via templating |

---

## `helm/argo-stack/overlays/ingress-authz-overlay/` Directory

| Template | Purpose | Status |
|----------|---------|--------|
| `templates/_helpers.tpl` | Helper functions for the ingress authz overlay chart | ✅ Active |
| `templates/authz-adapter.yaml` | Authorization adapter Deployment for NGINX ingress | ✅ Active |
| `templates/externalname-services.yaml` | ExternalName Services routing to external backends (optional) | ✅ Active |
| `templates/ingress-authz.yaml` | Ingress resources with authorization headers and authz adapter integration | ✅ Active |

### `helm/argo-stack/overlays/ingress-authz-overlay/` Supporting Files

| File | Purpose | Status |
|------|---------|--------|
| `cluster-issuer-letsencrypt.deprecated` | Deprecated Let's Encrypt ClusterIssuer (marked for removal) | 🚫 **Deprecated** |
| `README.md` | Documentation for the ingress authz overlay | ✅ Active |
| `values.yaml` | Default values for the overlay | ✅ Active |
| `values-ingress-nginx.yaml` | NGINX Ingress Controller specific configuration | ✅ Active |

---

## Summary

**Active Templates:** 37  
**Deprecated:** 1 (`cluster-issuer-letsencrypt.deprecated`)  
**Candidates for Review:** 1 (`workflowtemplate-nextflow-repo-runner.yaml` – consider generalizing or moving to tenant templating)

### Deprecation Flags

- **`cluster-issuer-letsencrypt.deprecated`** – Already marked; remove if no longer used or transition to cert-manager automation via Helm values.
- **`workflowtemplate-nextflow-repo-runner.yaml`** – Hardcoded for Nextflow; should either be parameterized per tenant or documented as a reference template.
