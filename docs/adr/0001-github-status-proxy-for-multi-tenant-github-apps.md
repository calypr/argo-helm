# ADR 0001: GitHub Status Proxy for Multi-Tenant GitHub App Integration

## Status

Accepted

## Context

Argo CD Notifications supports posting commit statuses to GitHub via GitHub Apps, but requires a hardcoded `installationID` in the chart values:

```yaml
service.github: |
  appID: <app id>
  installationID: <installation id>
  privateKey: $github-privateKey
```

This approach has several limitations:

1. **Single-tenant only**: The configuration assumes a single GitHub App installation, making it unsuitable for multi-tenant environments where different users/organizations install the app on their repositories.

2. **Manual configuration required**: Operators must manually discover the numeric `installationID` for each GitHub App installation and update Helm values, preventing self-service onboarding.

3. **No dynamic resolution**: When a GitHub App is installed on multiple repositories across different accounts, there's no way to automatically determine which installation to use for each repository.

4. **Operational overhead**: Each new repository requires manual intervention to configure and deploy updated values.

### Use Case

We want to enable:
- A shared Argo CD control plane serving multiple tenants
- A single shared GitHub App that users can install on their repositories
- Automatic commit status posting to the correct repository installation
- Self-service onboarding without operator intervention

## Decision

We will implement a **GitHub Status Proxy** microservice that sits between Argo CD Notifications and GitHub. The proxy will:

1. Accept webhook requests from Argo CD Notifications containing:
   - Repository URL
   - Commit SHA
   - Status state (success, failure, pending, error)
   - Context and description

2. Dynamically resolve the GitHub App installation for each repository by:
   - Parsing owner and repo from the repository URL
   - Creating a GitHub App JWT using the App ID and private key
   - Calling GitHub's API to find the installation ID for that repository
   - Obtaining an installation access token
   - Posting the commit status using the installation token

3. Be deployed as a Kubernetes service within the cluster, accessible only to Argo CD Notifications

4. Be integrated with Argo CD Notifications via webhook service configuration

### Architecture

```
┌─────────────────┐
│   Argo CD       │
│  Notifications  │
└────────┬────────┘
         │ webhook
         │ (repo_url, sha, state, context)
         ▼
┌─────────────────┐
│  GitHub Status  │
│     Proxy       │
│                 │
│ 1. Parse repo   │
│ 2. Get install  │
│ 3. Get token    │
│ 4. Post status  │
└────────┬────────┘
         │ GitHub API
         │ (with installation token)
         ▼
┌─────────────────┐
│     GitHub      │
│   Repositories  │
└─────────────────┘
```

### Implementation Components

1. **Go Microservice** (`github-status-proxy/`):
   - Lightweight HTTP server
   - GitHub App JWT creation
   - Installation lookup and token exchange
   - Commit status posting
   - Comprehensive error handling and logging

2. **Helm Templates** (`helm/argo-stack/templates/`):
   - Deployment and Service for the proxy
   - ConfigMap for Argo CD Notifications
   - Secret reference for GitHub App private key

3. **Values Configuration** (`helm/argo-stack/values.yaml`):
   - `githubStatusProxy.enabled` flag
   - GitHub App ID configuration
   - Private key secret reference

4. **Notifications Templates**:
   - Webhook service definition
   - Templates for sync events (succeeded, failed, running)
   - Templates for deployment events
   - Trigger definitions

## Consequences

### Positive

1. **Self-service onboarding**: Users can install the GitHub App and immediately get commit statuses without operator intervention

2. **Multi-tenant support**: A single Argo CD instance can serve multiple GitHub users/organizations with automatic installation resolution

3. **Simplified configuration**: No need to manually look up and configure installation IDs

4. **Scalable**: The proxy can handle multiple concurrent requests and scale horizontally

5. **Maintainable**: Centralized logic for GitHub App authentication and status posting

6. **Secure**: Private key stored as Kubernetes secret, short-lived installation tokens, in-cluster only access

### Negative

1. **Additional component**: Introduces a new microservice that must be deployed and maintained

2. **Single point of failure**: If the proxy is down, commit statuses won't be posted (mitigated by running multiple replicas)

3. **API rate limits**: Each status post requires multiple GitHub API calls (installation lookup + token exchange + status post), though these are cached per repository

4. **Dependency on GitHub API**: Failures in GitHub's API will prevent status posting

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Proxy service unavailable | Run multiple replicas with liveness/readiness probes |
| GitHub API rate limits | Implement caching for installation IDs and tokens |
| Private key exposure | Mount as read-only secret, restrict service access |
| Invalid repository URLs | Comprehensive input validation and error handling |
| GitHub App not installed | Clear error messages and logging |

## Alternatives Considered

### 1. Multi-installation Configuration in Argo CD

Configure multiple GitHub App installations in Argo CD Notifications, one per tenant.

**Rejected because**:
- Still requires manual configuration for each tenant
- Doesn't scale to many tenants
- Requires updating Argo CD configuration for each new user

### 2. GitHub Personal Access Tokens

Use PATs instead of GitHub Apps.

**Rejected because**:
- PATs are tied to individual users, not suitable for shared infrastructure
- No fine-grained permissions
- Security concerns with token rotation and storage
- Doesn't solve the multi-tenant problem

### 3. Argo CD Plugin/Extension

Implement as an Argo CD plugin or extension.

**Rejected because**:
- More complex integration
- Tighter coupling with Argo CD internals
- Harder to maintain across Argo CD versions
- The webhook approach is simpler and more maintainable

### 4. Lambda/Serverless Function

Deploy as a serverless function (AWS Lambda, Google Cloud Functions).

**Rejected because**:
- Introduces cloud provider dependency
- More complex deployment and configuration
- Harder to test and debug
- In-cluster solution is simpler for Kubernetes environments

## References

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [GitHub API: Commit Status](https://docs.github.com/en/rest/commits/statuses)
- [Argo CD Notifications](https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/)
- [Feature Request Issue](../github-status-proxy-feature-request.md)

## Notes

This ADR addresses the core requirement for multi-tenant GitHub App integration. Future enhancements may include:

- Caching of installation IDs and tokens to reduce API calls
- Support for GitHub Deployments and deployment statuses
- Integration with Argo Workflows for posting build statuses
- Metrics and monitoring dashboards
- Rate limit handling and backoff strategies
