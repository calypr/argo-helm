[Home](index.md)

# Argo Stack Documentation Index

Welcome to the documentation for the Argo Stack (feature/repo-registration).
This collection of documents covers the multi-tenant Argo Workflows stack,
RepoRegistration architecture, Vault-backed secret management, template
structure, development workflows, testing, and troubleshooting.

---

# Table of Contents

## 1. User Guides
- [User Guide](user-guide.md)
- [User Guide New](user-guide-new.md)
- [Repo Registration Guide](repo-registration-guide.md)
- [Tenant Onboarding](tenant-onboarding.md)
- [GitHub Integration Guide](github.md)

## 2. Architecture and Design
- [ADR Multi Tenant Namespaces](adr-multi-tenant-namespaces.md)
- [Artifact Repository Reference](artifact-repository-ref.md)
- [Template Overlap Analysis](template-overlap-analysis.md)
- [Templates Reference](templates.md)
- [Vault Architecture Diagrams](vault-architecture-diagrams.md)
- [Vault Seeding Strategy](vault-seeding-strategy.md)
- [Vault Integration Summary](vault-integration-summary.md)

## 3. Development and Engineering Notes
- [Development Guide](development.md)
- [Engineering Note Resource Creation Order](engineering-note-resource-creation-order.md)
- [Admin Guide](admin-guide.md)

## 4. Secrets, Vault, and External Secrets Operator
- [Secrets With Vault](secrets-with-vault.md)
- [Debugging Vault External Secrets](debugging-vault-external-secrets.md)
- [Testing Vault Integration](testing-vault-integration.md)

## 5. Testing and Troubleshooting
- [Testing Guide](testing.md)
- [Troubleshooting](troubleshooting.md)
- [Workflow Troubleshooting](workflow-troubleshooting.md)

---

## Document Summaries

### User Guide (user-guide.md)
High level introduction to the Argo Stack multi tenant architecture, including
namespaces, RepoRegistration, workflows, RBAC, and artifact repositories.

### User Guide New (user-guide-new.md)
An updated and refined version of the User Guide with improved diagrams and
clearer explanations.

### Repo Registration Guide (repo-registration-guide.md)
Explains the RepoRegistration custom resource, required fields, and how it
drives namespace, RBAC, workflow templates, and artifact repository wiring.

### Tenant Onboarding (tenant-onboarding.md)
Step by step checklist for onboarding a new GitHub repository as a tenant.

### GitHub Integration Guide (github.md)
Describes GitHub webhook configuration, expected payloads, and how GitHub
events flow into Argo Events and Argo Workflows.

### ADR Multi Tenant Namespaces (adr-multi-tenant-namespaces.md)
Architecture decision record documenting the choice of per tenant namespaces
and trade offs.

### Artifact Repository Reference (artifact-repository-ref.md)
Details how artifact repository references are resolved at global, app, and
tenant levels.

### Template Overlap Analysis (template-overlap-analysis.md)
Analysis of template usage before and after the repo registration refactor.

### Templates Reference (templates.md)
Complete reference for all Helm templates in helm/argo-stack/templates.

### Vault Architecture Diagrams (vault-architecture-diagrams.md)
Collection of diagrams showing Vault, SecretStore, ExternalSecret, and
controller interactions.

### Vault Seeding Strategy (vault-seeding-strategy.md)
Explains how Vault is initially seeded and updated with secrets required by
the stack.

### Vault Integration Summary (vault-integration-summary.md)
High level summary of Vault integration across Argo components and tenants.

### Development Guide (development.md)
Guide for contributors covering repo layout, local development workflows,
and coding conventions.

### Engineering Note Resource Creation Order (engineering-note-resource-creation-order.md)
Explains the order in which resources must be created to avoid race conditions
and failed dependencies.

### Admin Guide (admin-guide.md)
Operational guidance for platform administrators managing the Argo Stack.

### Secrets With Vault (secrets-with-vault.md)
Explains how secrets are stored in Vault and exposed to Kubernetes using
External Secrets.

### Debugging Vault External Secrets (debugging-vault-external-secrets.md)
Practical troubleshooting guide for Vault, SecretStore, and ExternalSecret
issues.

### Testing Vault Integration (testing-vault-integration.md)
Describes how to validate Vault and External Secrets integration end to end.

### Testing Guide (testing.md)
General testing strategies for workflows, templates, and events.

### Troubleshooting (troubleshooting.md)
Central troubleshooting guide for common issues across the stack.

### Workflow Troubleshooting (workflow-troubleshooting.md)
Focused guide for diagnosing workflow level failures and misconfigurations.
