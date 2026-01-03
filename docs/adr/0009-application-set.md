Below is a **complete Architecture Decision Record (ADR)** that documents the pattern **“Helm chart in one repo, values in another”**, with a **concrete `ApplicationSet` example**, and explicit **multi-tenancy considerations**. This is written to be drop-in ready for your repo.

---

# ADR-0002: Separate Helm Chart Repository from Values Repository using Argo CD ApplicationSet

## Status

**Accepted**

## Date

2025-01-XX

## Decision Makers

Platform / DevOps / GitOps Architecture

---

## Context

We operate a **multi-tenant GitOps platform** based on **Argo CD** and **Helm**.

We need to manage:

* **Stable platform and tenant Helm charts**

  * Versioned, reviewed, promoted deliberately
  * Owned by platform engineering
* **Frequently changing tenant/repo configuration**

  * One file per tenant or repo
  * Owned by application teams or onboarding automation
  * High churn, low blast radius

Previously, charts and values were co-located, creating:

* merge conflicts,
* unclear ownership boundaries,
* coupling between platform code and tenant onboarding.

---

## Decision

We will:

1. **Store Helm charts in a dedicated repository**

   * Example: `github.com/org/argo-helm`
2. **Store per-tenant / per-repo values in a separate configuration repository**

   * Example: `github.com/org/gitops-config`
3. **Use Argo CD ApplicationSet with *multiple sources***

   * One source for the chart
   * One source for the values
4. **Enforce multi-tenancy using Argo CD Projects**

   * Repo allowlists
   * Namespace allowlists
   * Optional cluster separation

---

## Repository Layout

### Chart repository (platform-owned)

```
argo-helm/
└── charts/
    └── repo-registration/
        ├── Chart.yaml
        ├── values.yaml        # defaults only
        └── templates/
```

### Values repository (tenant/onboarding-owned)

```
gitops-config/
└── environments/
    └── prod/
        └── repos/
            ├── acme-rnaseq.yaml
            ├── bwalsh-nextflow.yaml
            └── foo-bar.yaml
```

Each file represents **one tenant or one repo**.

---

## Concrete ApplicationSet (with documentation)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: repo-registrations-prod
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/org/gitops-config.git
        revision: main
        files:
          - path: environments/prod/repos/*.yaml
```

### Generator explanation

* Scans the **values repository**
* Each matched YAML file becomes **one generated Application**
* This avoids shared lists and merge conflicts

---

### Application template

```yaml
  template:
    metadata:
      name: rr-{{path.basename}}
    spec:
      project: tenant-workflows
```

* `path.basename` becomes the application name
* One Argo CD Application per repo/tenant
* Application name is stable and auditable

---

### Multiple sources (critical part)

```yaml
      sources:
        # Source 1: Helm chart
        - repoURL: https://github.com/org/argo-helm.git
          targetRevision: main
          path: charts/repo-registration

        # Source 2: Values/config repo
        - repoURL: https://github.com/org/gitops-config.git
          targetRevision: main
          ref: values
```

**Why this matters**

* Helm charts and values live in **different repos**
* Argo CD stitches them together at render time
* No copying, no vendoring, no sync hacks

---

### Helm values reference

```yaml
      helm:
        valueFiles:
          - $values/environments/prod/repos/{{path.basename}}
```

* `$values` refers to the repo with `ref: values`
* Helm reads the values file from the **config repo**
* This is the only supported way to mix repos with Helm

---

### Deployment target

```yaml
      destination:
        server: https://kubernetes.default.svc
        namespace: argocd
```

* `namespace` is the default for namespaced resources
* Charts may (and usually will) create resources in tenant namespaces explicitly

---

### Sync policy

```yaml
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

* **Automated**: no click-ops
* **Prune**: deleting a values file deletes tenant resources
* **SelfHeal**: drift is corrected automatically

---

## Multi-Tenancy Model

### Argo CD Project (mandatory)

Each tenant group is isolated using an Argo CD Project:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: tenant-workflows
  namespace: argocd
spec:
  sourceRepos:
    - https://github.com/org/argo-helm.git
    - https://github.com/org/gitops-config.git
  destinations:
    - namespace: wf-*
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  namespaceResourceWhitelist:
    - group: argoproj.io
      kind: WorkflowTemplate
    - group: ""
      kind: ServiceAccount
    - group: rbac.authorization.k8s.io
      kind: Role
    - group: rbac.authorization.k8s.io
      kind: RoleBinding
```

### What this enforces

* Applications **cannot deploy outside allowed namespaces**
* Charts **cannot read from unapproved repos**
* Tenants are isolated even if they share a cluster

---

## Why this decision works

### Benefits

* Clear ownership boundaries (platform vs onboarding)
* Zero merge conflicts during tenant onboarding
* Safe promotion of charts across environments
* Independent rollback per tenant
* Strong multi-tenant security posture

### Trade-offs

* Slightly more verbose ApplicationSet
* Requires understanding Argo CD multiple sources
* More Argo CD Applications (intentional)

---

## Alternatives Considered

### Single repo for charts + values

Rejected due to:

* merge conflicts
* poor separation of duties
* accidental platform changes

### Copy values into chart repo

Rejected:

* breaks audit trail
* forces config churn into platform repo

### Custom controller instead of Helm

Deferred:

* Helm + ApplicationSet is sufficient today
* This architecture keeps the door open for controllers later

---

## References

* Argo CD ApplicationSet overview
  [https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)

* Git generator (`files`, `path.basename`)
  [https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/)

* Multiple sources in Argo CD Applications
  [https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/)

* Helm support in Argo CD
  [https://argo-cd.readthedocs.io/en/stable/user-guide/helm/](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/)

* Argo CD Projects and multi-tenancy
  [https://argo-cd.readthedocs.io/en/stable/user-guide/projects/](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/)

---

## Summary

This ADR establishes a **clean, scalable, and secure GitOps pattern**:

> **Charts are platform-owned.
> Values are tenant-owned.
> ApplicationSets assemble them safely.**

## Example


```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: repo-registrations-prod
  namespace: argocd
spec:
  # Use Go templating so we can strip ".yaml" and do safer string ops.
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]

  generators:
    - git:
        repoURL: https://github.com/your-org/gitops-config.git
        revision: main
        files:
          - path: environments/prod/repos/*.yaml

  template:
    metadata:
      # Example: environments/prod/repos/acme-rnaseq.yaml -> rr-acme-rnaseq
      name: 'rr-{{ regexReplaceAll "\\.yaml$" .path.basename "" }}'
      labels:
        calypr.io/env: prod
        calypr.io/generated-by: applicationset

    spec:
      # Multi-tenancy boundary: this AppProject should restrict
      # source repos + destination namespaces + resource kinds.
      project: tenant-workflows-prod

      # Multi-source: chart in one repo, values in another.
      sources:
        # Source 1: Chart repo
        - repoURL: https://github.com/your-org/argo-helm.git
          targetRevision: main
          path: charts/repo-registration-resources
          helm:
            # Pull the values file from the second source using $values/
            valueFiles:
              - '$values/{{ .path.path }}/{{ .path.basename }}'
            # Optional: set a few shared helm parameters (if you want)
            # parameters:
            #   - name: global.environment
            #     value: prod

        # Source 2: Values repo (ref=values). No path => used only as a values source.
        - repoURL: https://github.com/your-org/gitops-config.git
          targetRevision: main
          ref: values

      destination:
        server: https://kubernetes.default.svc

        # The destination namespace is where the Argo CD Application object lives / defaults.
        # Your chart can still create resources in tenant namespaces explicitly.
        namespace: argocd

      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          # Create namespaces if your chart contains Namespace manifests
          - CreateNamespace=true

          # Optional but often useful in GitOps repos that evolve:
          # - RespectIgnoreDifferences=true

      # Optional: avoid constant churn on fields that are mutated by controllers.
      # ignoreDifferences:
      #   - group: ""
      #     kind: Secret
      #     jsonPointers:
      #       - /data

```

Below is an **amendment to the ADR** that **explicitly documents the `AppProject`** as the **enforcement mechanism for multi-tenancy**, written to drop directly into the ADR you already have.

I’ve kept this **minimal but correct**, and aligned it with the model you described:

> *one ApplicationSet → many Applications → one restricted AppProject*

---

# ADR-0002 (Amendment): AppProject as the Multi-Tenancy Enforcement Boundary

## Amendment Status

**Accepted**

## Date

2025-01-XX

---

## Background

This ADR establishes a GitOps pattern using **Argo CD ApplicationSet** to generate one Argo CD `Application` per tenant/repo, where:

* Helm charts live in a **platform-owned repository**
* Values live in a **tenant/onboarding repository**
* Applications are generated automatically from values files

This amendment formally documents the **AppProject** as the **policy enforcement boundary** that makes this setup multi-tenant safe.

---

## Decision (Amended)

All Applications generated by the `ApplicationSet` **MUST**:

1. Be assigned to a **non-default AppProject**
2. Be constrained by that AppProject’s:

   * allowed source repositories
   * allowed destination namespaces
   * allowed resource kinds (namespaced and cluster-scoped)

The AppProject is the **sole mechanism** that enforces multi-tenant isolation in this architecture.

---

## Role of AppProject in This Architecture

The AppProject acts as the **contract and guardrail** between:

* **Platform-owned automation** (ApplicationSet + charts)
* **Tenant-owned configuration** (values files)

It ensures that *even if a values file or chart is modified incorrectly*, the resulting Application **cannot escape its tenant boundary**.

---

## Concrete AppProject Definition (Minimal, Correct)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: tenant-workflows-prod
  namespace: argocd
spec:
  description: >
    Multi-tenant project for repo-registered workflow tenants.
    All Applications generated by the repo-registration ApplicationSet
    must run within this project.

  # Only these Git repos may be referenced by Applications
  sourceRepos:
    - https://github.com/your-org/argo-helm.git
    - https://github.com/your-org/gitops-config.git

  # Applications may only deploy to these destinations
  destinations:
    - server: https://kubernetes.default.svc
      namespace: wf-*

  # Cluster-scoped resources are disallowed by default
  # (recommended for strict multi-tenancy)
  clusterResourceBlacklist:
    - group: "*"
      kind: "*"

  # Explicitly allow only the namespaced resources required
  namespaceResourceWhitelist:
    - group: ""
      kind: Namespace
    - group: ""
      kind: ServiceAccount
    - group: ""
      kind: ConfigMap
    - group: ""
      kind: Secret
    - group: rbac.authorization.k8s.io
      kind: Role
    - group: rbac.authorization.k8s.io
      kind: RoleBinding
    - group: argoproj.io
      kind: WorkflowTemplate
    - group: argoproj.io
      kind: EventSource
    - group: argoproj.io
      kind: Sensor
```

---

## Enforcement Guarantees Provided

With this AppProject in place:

| Risk                                              | Mitigation                            |
| ------------------------------------------------- | ------------------------------------- |
| Tenant points Application at a different Git repo | Blocked by `sourceRepos`              |
| Tenant deploys into another tenant’s namespace    | Blocked by `destinations`             |
| Chart attempts to create cluster-wide RBAC        | Blocked by `clusterResourceBlacklist` |
| Accidental CRD or ClusterRole creation            | Blocked                               |
| Values file typo expands scope                    | Contained                             |

This is what makes the setup **actually multi-tenant**, not just “many apps.”

---

## Relationship to ApplicationSet

The corresponding `ApplicationSet` **must** set:

```yaml
spec:
  project: tenant-workflows-prod
```

This ensures:

* Every generated Application inherits the AppProject’s restrictions
* No generated Application can opt out of enforcement

---

## Minimal vs. Expanded Models

### Minimal (this ADR)

* One AppProject
* One ApplicationSet
* Many Applications
* One namespace per tenant (pattern: `wf-*`)

### Expanded (future)

* One AppProject per tenant group
* One ApplicationSet per environment or tenant class
* Separate projects for “infra” vs “workloads”
* Cluster-level isolation (separate clusters per trust zone)

This ADR intentionally documents the **minimum safe baseline**.

---

## Consequences (Amended)

### Positive

* Strong isolation with minimal moving parts
* No custom controllers required
* Aligns with Argo CD’s intended security model
* Easy to audit and reason about

### Negative

* Charts must be carefully reviewed to ensure they only create allowed kinds
* Namespace creation must follow strict naming conventions
* AppProject updates require platform-level access

---

## Summary (Updated)

> **Multi-tenancy is enforced by the AppProject, not the ApplicationSet.**
> The ApplicationSet automates scale.
> The AppProject defines trust boundaries.

This amendment formally establishes the AppProject as a **required component** of the architecture, completing the multi-tenant GitOps design.

