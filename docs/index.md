[Home](index.md)

# Argo Stack Documentation Index

Welcome to the documentation for the Argo Stack (feature/repo-registration).
This collection of documents covers the multi-tenant Argo Workflows stack,
RepoRegistration architecture, Vault-backed secret management, template
structure, development workflows, testing, and troubleshooting.

---

# Table of Contents

## 1. User Guides
- [User Guide](user-guide.md) - Comprehensive guide for running Nextflow workflows from GitHub

## 2. Operations and Administration
- [Repo Registration Guide](repo-registration-guide.md) - Self-service repository onboarding
- [Tenant Onboarding](tenant-onboarding.md) - Step-by-step tenant setup
- [Admin Guide](admin-guide.md) - Platform administration and operations
- [Secrets With Vault](secrets-with-vault.md) - Complete Vault + External Secrets Operator guide
- [Trouble Shooting](troubleshooting.md) - Comprehensive troubleshooting for all components

## 3. Architecture and Design
- [Templates Reference](templates.md) - Helm template documentation
- [Vault Architecture Diagrams](vault-architecture-diagrams.md) - Vault integration diagrams
- [Vault Seeding Strategy](vault-seeding-strategy.md) - Vault initialization strategy
- [Vault Integration Summary](vault-integration-summary.md) - High-level Vault integration overview
- [ADR GitHub status proxy for multi tenant github apps](adr/0001-github-status-proxy-for-multi-tenant-github-apps.md) - Design decision for GitHub status proxy
- [ADR GitHub app secrets handling](adr/0002-github-app-secrets-handling.md) - Design decision for GitHub App secret management
- [ADR Workflow GitHub Status](adr/0003-Workflow-GitHub-Status.md) - Authenticating and posting status updates from workflows
- [ADR Multi Tenant Namespaces](adr/0004-multi-tenant-namespaces.md) - Multi-tenancy architecture decisions
- [ADR Authz Adapter](adr/0005-authz-adapter.md) - Fence-based authorization adapter design
 
## 4. Development
- [Development Guide](development.md) - Developer setup and workflows
- [Testing Guide](testing.md) - Testing strategies and procedures
- [Testing Vault Integration](testing-vault-integration.md) - Vault-specific testing
- [Engineering Note: Resource Creation Order](engineering-note-resource-creation-order.md) - Resource dependency management
- [Debugging Vault External Secrets](debugging-vault-external-secrets.md) - Vault debugging techniques

---

## Document Summaries

### User Guides

**[User Guide](user-guide.md)** - Comprehensive guide for data managers and developers to run Nextflow workflows from GitHub, including GitHub integration, artifact storage, and self-service repository registration.

### Operations and Administration

**[Repo Registration Guide](repo-registration-guide.md)** - Details on the RepoRegistration custom resource, required fields, and how it automates namespace, RBAC, workflow templates, and artifact repository wiring.

**[Tenant Onboarding](tenant-onboarding.md)** - Step-by-step checklist for onboarding a new GitHub repository as a tenant.

**[Admin Guide](admin-guide.md)** - Operational guidance for platform administrators managing the Argo Stack, including deployment, monitoring, and maintenance.

**[Secrets With Vault](secrets-with-vault.md)** - Complete guide to managing secrets using HashiCorp Vault and External Secrets Operator, including authentication methods, secret rotation, and troubleshooting.

**[Troubleshooting](troubleshooting.md)** - Comprehensive troubleshooting guide covering GitHub webhooks, Argo Events, Argo Workflows, artifact storage, and Vault integration.

### Architecture and Design

**[ADR Multi Tenant Namespaces](adr-multi-tenant-namespaces.md)** - Architecture decision record documenting the choice of per-tenant namespaces and trade-offs.

**[Artifact Repository Reference](artifact-repository-ref.md)** - How artifact repository references are resolved at global, app, and tenant levels.

**[Templates Reference](templates.md)** - Complete reference for all Helm templates in helm/argo-stack/templates.

**[Vault Architecture Diagrams](vault-architecture-diagrams.md)** - Collection of diagrams showing Vault, SecretStore, ExternalSecret, and controller interactions.

**[Vault Seeding Strategy](vault-seeding-strategy.md)** - How Vault is initially seeded and updated with secrets required by the stack.

**[Vault Integration Summary](vault-integration-summary.md)** - High-level summary of Vault integration across Argo components and tenants.

### Development

**[Development Guide](development.md)** - Guide for contributors covering repo layout, local development workflows, and coding conventions.

**[Testing Guide](testing.md)** - General testing strategies for workflows, templates, and events.

**[Testing Vault Integration](testing-vault-integration.md)** - How to validate Vault and External Secrets integration end-to-end.

**[Engineering Note: Resource Creation Order](engineering-note-resource-creation-order.md)** - Resource creation order to avoid race conditions and failed dependencies.

**[Debugging Vault External Secrets](debugging-vault-external-secrets.md)** - Practical debugging techniques for Vault, SecretStore, and ExternalSecret issues.
