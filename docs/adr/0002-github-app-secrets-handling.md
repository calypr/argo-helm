# ADR 0002: GitHub App Secrets Handling for Self-Service Onboarding

## Status

Accepted

## Context

As we expand self-service onboarding for Git → Argo Workflows, users need a clear, standardized method to communicate secrets (GitHub App credentials, PATs, or Webhook HMACs) to the platform.

Secrets are required for:
- Creation of GitHub Webhooks for workflow triggers
- Authentication of Argo CD to private repositories  
- Verification of event payloads received by Argo Events

The platform needs to support multiple authentication modes to accommodate different security requirements, organizational policies, and use cases. Users range from individual developers to enterprise organizations with strict security controls.

Without a standardized approach to secret handling, we face:
- Inconsistent security practices across tenants
- Difficulty in onboarding new users
- Increased support burden for troubleshooting authentication issues
- Risk of credential exposure through insecure sharing methods

## Decision

We will support three authentication modes for GitHub integration, with GitHub App being the preferred method:

### 1. GitHub App Mode (Preferred)

**User Action:**
- Install the organization's GitHub App on their repository
- Confirm the App has required permissions:
  - `Contents: Read`
  - `Metadata: Read`
  - `Webhooks: Read/Write` (if Argo manages hooks automatically)

**Platform Configuration:**
Argo CD and Argo Events use GitHub App installation tokens instead of PATs.

Example Secret manifest:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-app-creds
  namespace: argocd
stringData:
  appID: "123456"
  installationID: "987654"
  privateKey: |
    -----BEGIN RSA PRIVATE KEY-----
    ...
    -----END RSA PRIVATE KEY-----
```

### 2. PAT Mode (Fine-Grained Token)

For simpler dev/testing scenarios, users can create a fine-grained GitHub PAT with minimal scopes (`Webhooks RW`, `Contents R`, `Metadata R`), share it securely via vault or one-time link.

```bash
kubectl -n argo-events create secret generic github-secret \
  --from-literal=token=$GITHUB_PAT
```

EventSource reference:
```yaml
spec:
  github:
    repo-push:
      owner: yourname
      repository: my-repo
      events: ["push"]
      apiToken:
        name: github-secret
        key: token
```

### 3. Manual Webhook (HMAC)

For external or offline repos, users generate a shared secret:

```bash
openssl rand -hex 20
```

Add to GitHub webhook "Secret", then mirror it:
```bash
kubectl -n argo-events create secret generic github-webhook-secret \
  --from-literal=token=<same-string>
```

Referenced via:
```yaml
spec:
  github:
    repo-push:
      owner: yourname
      repository: my-repo
      events: ["push"]
      webhookSecret:
        name: github-webhook-secret
        key: token
```

### Secret Rotation and Validation

| Type | Rotation Period | Verification Method |
|------|-----------------|---------------------|
| **PAT** | Every 90 days | Check `kubectl get eventsource github -o yaml` |
| **GitHub App** | Annual key rotation | Confirm `argocd-repo-server` logs & webhook health |
| **Webhook HMAC** | 180 days | Push test and verify 200 OK in Webhook deliveries |

## Consequences

### Positive

1. **Flexibility**: Multiple authentication modes accommodate different organizational security policies and use cases

2. **Security**: GitHub App mode provides fine-grained permissions and automatic token rotation, reducing credential exposure

3. **Self-service**: Clear documentation enables users to onboard without platform operator intervention

4. **Multi-tenant support**: GitHub App installation tokens are scoped per repository, enabling secure multi-tenant deployments

5. **Standardization**: Consistent approach across all integrations reduces configuration errors and support burden

6. **Auditability**: Structured secret management enables tracking of credential usage and rotation compliance

### Negative

1. **Complexity**: Supporting three authentication modes increases documentation and support requirements

2. **Secret sprawl**: Multiple secrets across namespaces can be difficult to manage and audit

3. **Rotation burden**: Manual rotation processes for PATs and HMAC secrets require operational overhead

4. **Learning curve**: Users must understand which authentication mode is appropriate for their use case

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Credential exposure | Use vault or External Secrets Operator for secret management |
| Expired credentials | Implement monitoring and alerting for expiring credentials |
| Inconsistent practices | Provide clear documentation and PR templates for onboarding |
| Secret sprawl | Use naming conventions and labels for secret organization |
| GitHub App misconfiguration | Validate permissions during installation and provide diagnostics |

## Alternatives Considered

### 1. GitHub App Only

Mandate GitHub App authentication for all users.

**Rejected because**:
- Creates barriers for individual developers and small teams
- Requires organizational GitHub App setup which some users cannot perform
- Doesn't support edge cases like offline repositories or air-gapped environments
- Too restrictive for development and testing workflows

### 2. PAT Only

Use only Personal Access Tokens for all authentication.

**Rejected because**:
- PATs are tied to individual users, creating single points of failure
- No fine-grained permissions comparable to GitHub Apps
- Security concerns with token rotation and storage
- Not suitable for production multi-tenant environments
- Doesn't scale as organization grows

### 3. External Secret Management System

Require all users to use external secret management (Vault, AWS Secrets Manager, etc.).

**Rejected because**:
- Creates dependency on external systems
- Increases complexity for simple use cases
- May not be available in all deployment environments
- Should be optional, not mandatory

### 4. OAuth Flow

Implement OAuth flow for user credential collection.

**Rejected because**:
- Requires building and maintaining OAuth infrastructure
- Creates security and compliance concerns around credential storage
- GitHub Apps provide similar functionality with better security model
- Significantly increases implementation complexity

## References

- [Argo CD — Private Repositories (GitHub App)](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories)
- [Argo CD — Notifications / GitHub Service](https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/github)
- [Argo CD Discussion — Using GitHub App for Repo Access](https://github.com/argoproj/argo-cd/discussions/15641)
- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [GitHub API: Fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

## Notes

Implementation checklist:
- [ ] Docs updated for GitHub App and PAT workflows
- [ ] Portal/PR template collects repo + auth method
- [ ] Vault or External Secrets tested for token sync
- [ ] Argo CD configured for GitHub App authentication
- [ ] Argo Events validated for PAT + webhookSecret modes

> ℹ️ If you are using a different version of Argo CD, consult the documentation matching your installed version.
