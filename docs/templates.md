# Argo Stack Template Documentation

This document provides **complete documentation for every Helm template** in the `helm/argo-stack/templates` directory.

## Directory Structure

```
helm/argo-stack/templates/
├── 00-namespaces.yaml
├── 01-tenant-namespaces-from-repo-registrations.yaml
├── 11-tenant-rbac-from-repo-registrations.yaml
├── 12-artifact-repository-rbac.yaml
├── 20-artifact-repositories.yaml
├── 22-tenant-artifact-repositories-from-repo-registrations.yaml
├── 30-authz-adapter.yaml
├── 40-argo-workflows-ingress.yaml
├── 41-argocd-ingress.yaml
├── 90-argocd-application.yaml
├── _eso-helpers.tpl
├── argocd
│   └── applications-from-repo-registrations.yaml
├── eso
│   ├── externalsecret-argocd.yaml
│   ├── externalsecret-repo-registrations-github.yaml
│   ├── externalsecret-repo-registrations-s3.yaml
│   ├── secretstore.yaml
│   └── serviceaccount.yaml
├── events
│   ├── eventbus.yaml
│   ├── eventsource-github-from-repo-registrations.yaml
│   ├── secret-github.yaml
│   └── sensor-github-push.yaml
└── workflows
    ├── per-tenant-workflowtemplates.yaml
    └── workflowtemplate-nextflow-repo-runner.yaml
```

---

# Template Reference

## 00-namespaces.yaml
Creates foundational namespaces required by the Argo Stack (argocd, argo-events, argo-workflows).  
These are cluster-level system namespaces, not tenant namespaces.

---

## 01-tenant-namespaces-from-repo-registrations.yaml
Creates **one namespace per RepoRegistration**.  
Derives namespace from:
```
spec.namespace
```

Injects labels for:
- multi-tenant visibility
- resource grouping

---

## 11-tenant-rbac-from-repo-registrations.yaml
Creates per-tenant RBAC:
- ServiceAccount: `<tenant>-submitter`
- Role with permissions:
  - workflows create
  - workflowtemplates get/list
- RoleBinding linking SA → Role

Ensures tenants can submit workflows securely.

---

## 12-artifact-repository-rbac.yaml
Provides RBAC required for Argo Workflows to access artifact repository objects.  
Applied cluster-wide or per tenant depending on configuration.

---

## 20-artifact-repositories.yaml
Defines **global** artifact repository used as fallback.  
Values taken from:
```
artifactRepositories.global
```

---

## 22-tenant-artifact-repositories-from-repo-registrations.yaml
Creates per-tenant artifact repository CRs using the reference in RepoRegistration:
```
spec.artifactRepositoryRef.name
```

Each CR is materialized as:
```
artifactrepositories.argoproj.io/<tenant>
```

---

## 30-authz-adapter.yaml
Deploys a small auth adapter that:
- Ensures only tenant-scoped service accounts can access workflow submission endpoints  
- Integrates with NGINX auth hooks

---

## 40-argo-workflows-ingress.yaml
Creates Ingress for Argo Workflows UI when enabled:
```
ingress.argoWorkflows.enabled=true
```

---

## 41-argocd-ingress.yaml
Creates Ingress for ArgoCD UI when enabled:
```
ingress.argocd.enabled=true
```

---

## 90-argocd-application.yaml
Allows the stack to declare self-managed ArgoCD Applications.  
This template is optional and used only when ArgoCD should deploy additional charts.

---

## _eso-helpers.tpl
Common helper functions used by External Secrets templates.

---

# ArgoCD Subdirectory

## argocd/applications-from-repo-registrations.yaml
Generates ArgoCD `Application` resources for each RepoRegistration.  
Allows GitHub repos to deploy UI or infrastructure components alongside workflow automation.

---

# External Secrets (ESO) Subdirectory

## externalsecret-argocd.yaml
Manages ArgoCD admin or webhook secrets through ESO.

## externalsecret-repo-registrations-github.yaml
Creates secrets for GitHub webhook tokens derived from RepoRegistration definitions.

## externalsecret-repo-registrations-s3.yaml
Creates S3 credentials for tenant artifact repositories or workflow execution requirements.

## secretstore.yaml
ESO SecretStore configuration for Vault or AWS Secrets Manager.

## serviceaccount.yaml
ESO-specific ServiceAccount enabling secret fetch permissions.

---

# Events Subdirectory

## eventbus.yaml
Creates the central NATS-based EventBus.

## eventsource-github-from-repo-registrations.yaml
Creates GitHub EventSources dynamically based on RepoRegistration entries:
- repo name
- webhook secret
- events to listen for

## secret-github.yaml
Contains the GitHub webhook secret (ESO-managed).

## sensor-github-push.yaml
Creates a Sensor that:
- Listens for push events
- Resolves RepoRegistration
- Submits workflow to tenant namespace

---

# Workflows Subdirectory

## per-tenant-workflowtemplates.yaml
Fetches workflow templates from GitHub repositories based on:
```
spec.workflowTemplates[*].sourceRef.path
```

Injects:
- serviceAccountName
- artifact repository reference
- labels and annotations

## workflowtemplate-nextflow-repo-runner.yaml
Provides a default Nextflow runner WorkflowTemplate used as a fallback or example.

---

