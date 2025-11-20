# Deprecation Notice - Legacy Configuration Pattern

**Date**: 2025-11-20  
**Effective Version**: Current  
**Status**: REMOVED

## Summary

The legacy configuration pattern using `.Values.applications` and `.Values.events.github.repositories` has been **removed** in favor of the RepoRegistration CRD pattern.

## Removed Templates

The following legacy templates have been removed:

### 1. Artifact Repository Templates
- ❌ `helm/argo-stack/templates/21-per-app-artifact-repositories.yaml`
  - **Replaced by**: `helm/argo-stack/templates/21-per-app-artifact-repositories-from-repo-registrations.yaml`
  - **Migration**: Use `.Values.repoRegistrations` instead of `.Values.applications`

### 2. ArgoCD Application Templates
- ❌ `helm/argo-stack/templates/argocd/applications.yaml`
  - **Replaced by**: `helm/argo-stack/templates/argocd/applications-from-repo-registrations.yaml`
  - **Migration**: Use `.Values.repoRegistrations` instead of `.Values.applications`

### 3. ExternalSecret Templates
- ❌ `helm/argo-stack/templates/eso/externalsecret-github.yaml`
  - **Replaced by**: `helm/argo-stack/templates/eso/externalsecret-repo-registrations-github.yaml`
  - **Migration**: Use `.Values.repoRegistrations[].githubSecretName` instead of `.Values.events.github.secret`

- ❌ `helm/argo-stack/templates/eso/externalsecret-s3.yaml`
  - **Replaced by**: `helm/argo-stack/templates/eso/externalsecret-repo-registrations-s3.yaml`
  - **Migration**: Use `.Values.repoRegistrations[].artifactBucket.externalSecretPath` instead of `.Values.externalSecrets.secrets.workflows`

- ❌ `helm/argo-stack/templates/eso/externalsecret-per-app-s3.yaml`
  - **Replaced by**: `helm/argo-stack/templates/eso/externalsecret-repo-registrations-s3.yaml`
  - **Migration**: Use `.Values.repoRegistrations` instead of `.Values.externalSecrets.secrets.perAppS3`

### 4. Argo Events Templates
- ❌ `helm/argo-stack/templates/events/eventsource-github.yaml`
  - **Replaced by**: `helm/argo-stack/templates/events/eventsource-github-from-repo-registrations.yaml`
  - **Migration**: Use `.Values.repoRegistrations` instead of `.Values.events.github.repositories`

## Migration Guide

### From Legacy Pattern to RepoRegistration

#### Before (Legacy Pattern - REMOVED)
```yaml
# values.yaml
applications:
  - name: my-repo
    repoURL: https://github.com/org/my-repo.git
    targetRevision: main
    artifacts:
      bucket: my-bucket
      endpoint: s3.example.com
      region: us-east-1
      credentialsSecret: s3-cred-my-repo

events:
  github:
    repositories:
      - owner: org
        repository: my-repo
        events:
          - push
```

#### After (RepoRegistration Pattern - CURRENT)
```yaml
# values.yaml
repoRegistrations:
  - name: my-repo
    repoUrl: https://github.com/org/my-repo.git
    githubSecretName: github-token-my-repo
    artifactBucket:
      hostname: s3.example.com
      bucket: my-bucket
      region: us-east-1
      externalSecretPath: secret/data/s3/my-repo
    dataBucket:
      hostname: s3.example.com
      bucket: my-data-bucket
      region: us-east-1
      externalSecretPath: secret/data/s3/my-repo
    adminUsers:
      - admin@example.com
    readUsers:
      - viewer@example.com
```

## Benefits of RepoRegistration Pattern

1. **Self-Service Onboarding**: Teams can register repositories via CRD without platform team intervention
2. **Vault Integration**: All secrets managed centrally in Vault, synced via External Secrets Operator
3. **Per-Repo Isolation**: Each repository has its own S3 credentials and GitHub token
4. **Access Control**: Email-based admin and read-only user lists aligned with Fence/Arborist
5. **Automatic Resource Creation**: Controller automatically creates ExternalSecrets, ConfigMaps, ArgoCD Applications, and EventSources

## Configuration Changes Required

### Remove Legacy Configuration Blocks

Remove the following sections from your `values.yaml`:

```yaml
# REMOVE THESE:
applications: []

events:
  github:
    repositories: []

externalSecrets:
  secrets:
    workflows:
      artifactAccessKeyPath: "..."
      artifactSecretKeyPath: "..."
    perAppS3: {}
```

### Add RepoRegistration Configuration

Add RepoRegistration entries instead:

```yaml
# ADD THIS:
repoRegistrations:
  - name: my-first-repo
    repoUrl: https://github.com/org/my-first-repo.git
    githubSecretName: github-token-my-first-repo
    artifactBucket:
      hostname: s3.example.com
      bucket: artifacts
      region: us-east-1
      externalSecretPath: secret/data/s3/my-first-repo
    adminUsers:
      - admin@example.com
    readUsers:
      - team@example.com
```

## Vault Secret Structure

For each RepoRegistration, ensure Vault has the required secrets:

### S3 Credentials
Path: `<artifactBucket.externalSecretPath>`
```json
{
  "AWS_ACCESS_KEY_ID": "AKIA...",
  "AWS_SECRET_ACCESS_KEY": "secret..."
}
```

### GitHub Token
Path: Configured in Vault, referenced by `githubSecretName`
```json
{
  "token": "ghp_..."
}
```

## Frequently Asked Questions

### Q: Can I use both patterns simultaneously?
**A**: No, the legacy pattern has been removed. You must use RepoRegistration.

### Q: What if I have existing applications using the legacy pattern?
**A**: You must migrate to RepoRegistration. Follow the migration guide above.

### Q: How do I create the GitHub and S3 secrets in Vault?
**A**: Use your Vault CLI or UI to create secrets at the paths specified in `externalSecretPath` and configure the GitHub token path.

### Q: Will my existing workflows break?
**A**: Yes, if they rely on legacy templates. Update your `values.yaml` to use RepoRegistration format.

### Q: How do I validate my RepoRegistration configuration?
**A**: Use `kubectl apply --dry-run=client -f` with your RepoRegistration manifest.

## Support

For questions or issues with migration:
- Review the [RepoRegistration User Guide](./REPO_REGISTRATION_USER_GUIDE.md)
- Review the [Template Overlap Analysis](./template-overlap-analysis.md)
- Open an issue at https://github.com/calypr/argo-helm/issues

## Timeline

- **2025-11-20**: Legacy templates removed
- **Current**: Only RepoRegistration pattern supported

---

**Note**: This is a breaking change. All users must migrate to the RepoRegistration pattern.
