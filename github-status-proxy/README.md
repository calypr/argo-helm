# GitHub Status Proxy

A microservice that enables Argo CD to post GitHub commit statuses via a GitHub App **without** requiring a hardcoded `installationID` in chart values.

## Overview

This proxy service sits between Argo CD Notifications and GitHub, automatically resolving the correct GitHub App installation for each repository and posting commit statuses on behalf of Argo CD applications.

### Why?

Argo CD Notifications supports GitHub Apps, but requires manually configuring the `installationID` for each repository. This works for single repositories but breaks down for:

- Multi-tenant clusters where many independent GitHub users want to use the same Argo CD instance
- Self-service onboarding where new users want to connect their repos without operator intervention
- Situations where the GitHub App is installed across multiple accounts and repositories

## How It Works

1. A GitHub user installs the shared GitHub App on their repository
2. An Argo CD Application points at that repo
3. On sync events, Argo CD Notifications sends a webhook to the GitHub Status Proxy with:
   - `repo_url`
   - `sha`
   - `state` (success, failure, pending, error)
   - `context`
   - `target_url`
   - `description`
4. The proxy:
   - Parses owner and repo from the URL
   - Creates a GitHub App JWT
   - Calls `GET /repos/{owner}/{repo}/installation` to find the installation ID
   - Calls `POST /app/installations/{id}/access_tokens` to get an installation token
   - Calls `POST /repos/{owner}/{repo}/statuses/{sha}` to create the commit status

## API

### POST /status

Creates a commit status for a GitHub repository.

**Request Body:**

```json
{
  "repo_url": "https://github.com/owner/repo",
  "sha": "abc123def456",
  "state": "success",
  "context": "argocd/my-app",
  "target_url": "https://argocd.example.com/applications/my-app",
  "description": "Application synced successfully"
}
```

**Fields:**

- `repo_url` (required): GitHub repository URL in any format (HTTPS, SSH, or owner/repo)
- `sha` (required): Git commit SHA
- `state` (required): One of: `success`, `failure`, `pending`, `error`
- `context` (required): Status context identifier (e.g., "argocd/my-app")
- `target_url` (optional): URL to link from the status
- `description` (optional): Human-readable status description

**Response:**

```json
{
  "success": true,
  "message": "Commit status created successfully"
}
```

### GET /healthz

Health check endpoint.

**Response:** `200 OK` with body `OK`

## Configuration

The service is configured via environment variables:

- `GITHUB_APP_ID` (required): GitHub App ID
- `GITHUB_APP_PRIVATE_KEY_PATH` (optional): Path to private key file (default: `/etc/github/private-key.pem`)
- `PORT` (optional): HTTP port to listen on (default: `8080`)

## Building

```bash
# Build the binary
go build -o github-status-proxy .

# Run tests
go test -v ./...

# Build Docker image
docker build -t github-status-proxy:latest .
```

## Deployment

See the parent Helm chart for deployment instructions. The service is deployed as part of the `argo-stack` Helm chart.

Enable it by setting:

```yaml
githubStatusProxy:
  enabled: true
  githubAppId: "123456"
  privateKeySecret:
    name: github-app-private-key
    key: private-key.pem
```

## Testing

Run the unit tests:

```bash
go test -v ./...
```

Run with coverage:

```bash
go test -v -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## Security Considerations

- The GitHub App private key is mounted as a Kubernetes secret
- The service only accepts requests from within the cluster (ClusterIP service)
- All GitHub API calls use short-lived installation tokens
- Failed authentication attempts are logged but do not expose sensitive information

## License

Apache 2.0
