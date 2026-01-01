# GitHub App Callback Service

A Flask-based web service that handles post-installation callbacks from GitHub Apps, providing a user-friendly form for repository registration configuration.

## Overview

When a user installs a GitHub App, GitHub redirects them to a configured "Post-installation redirect URL". This service receives that callback and guides users through configuring their repository settings for Argo Workflows.

## Features

- **GitHub App Integration**: Handles post-installation callbacks with `installation_id` parameter
- **User-Friendly Form**: Clean, modern UI following calypr-public.ohsu.edu design patterns
- **Repository Configuration**: Collects all required RepoRegistration fields:
  - Default branch (defaults to `main`)
  - Data bucket (optional)
  - Artifact bucket (optional)
  - Admin users (required, comma-separated emails)
  - Read-only users (optional, comma-separated emails)
  - Installation ID (from GitHub callback)
- **Validation**: Email validation and required field checks
- **Modern UI**: Left navigation, rounded cards, slate-gray text, blue primary buttons

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   make install-dev
   ```

2. **Run the development server:**
   ```bash
   make run
   ```

3. **Access the service:**
   - Health check: http://localhost:8080/healthz
   - Registration form: http://localhost:8080/registrations?installation_id=12345678

### Docker

1. **Build the image:**
   ```bash
   make docker-build
   ```

2. **Run the container:**
   ```bash
   make docker-run
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for session management | `dev-secret-key-change-in-production` |
| `GITHUB_APP_NAME` | Name of your GitHub App | `calypr-workflows` |

## API Endpoints

### `GET /healthz`

Health check endpoint.

**Response:**
- `200 OK`: Service is healthy

### `GET /registrations`

Display registration form.

**Query Parameters:**
- `installation_id` (required): GitHub installation ID
- `setup_action` (optional): `install` or `update`

**Response:**
- `200 OK`: Registration form HTML
- `400 Bad Request`: Missing installation_id

### `POST /registrations`

Submit registration configuration.

**Form Data:**
- `installation_id` (required): GitHub installation ID
- `defaultBranch` (optional): Default branch name (default: `main`)
- `dataBucket` (optional): S3 bucket for data
- `artifactBucket` (optional): S3 bucket for artifacts
- `adminUsers` (required): Comma-separated admin email addresses
- `readUsers` (optional): Comma-separated read-only email addresses

**Response:**
- `200 OK`: Success page or JSON response
- `400 Bad Request`: Validation errors

## User Flow

1. User installs GitHub App or updates repository access
2. GitHub redirects to: `https://your-domain.com/registrations?installation_id=12345678&setup_action=install`
3. User sees registration form with installation ID pre-filled
4. User fills in:
   - Default branch (pre-filled with "main")
   - Storage buckets (optional)
   - Admin users (required)
   - Read-only users (optional)
5. User submits form
6. Service validates input
7. Success page displays configuration summary

## Design

The UI follows the calypr-public.ohsu.edu visual theme:

- **Left Navigation**: Fixed sidebar with dark background (#1e293b)
- **Main Content**: Light background (#f5f7fa) with centered container
- **Cards**: White rounded cards with subtle shadow
- **Typography**: Slate-gray text (#475569) for body, dark text for headings
- **Buttons**: Blue primary buttons (#3b82f6), gray secondary buttons
- **Form Elements**: Clean inputs with blue focus states

## Development

### Project Structure

```
gitapp-callback/
├── app.py                 # Flask application
├── templates/
│   ├── registration_form.html  # Main registration form
│   ├── success.html           # Success page
│   └── error.html             # Error page
├── static/                # Static assets (empty for now)
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── Dockerfile            # Container image definition
├── Makefile              # Build and development tasks
└── README.md             # This file
```

### Testing

Run tests with:
```bash
make test
```

### Linting

Check code style:
```bash
make lint
```

Format code:
```bash
make format
```

## Deployment

### Docker

The service is containerized and can be deployed to any Docker-compatible environment:

```bash
docker build -t gitapp-callback:latest .
docker run -p 8080:8080 \
  -e SECRET_KEY=your-secret-key \
  -e GITHUB_APP_NAME=your-app-name \
  gitapp-callback:latest
```

### Kubernetes

Create a Deployment and Service in your cluster. Example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitapp-callback
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: gitapp-callback
        image: gitapp-callback:latest
        ports:
        - containerPort: 8080
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: gitapp-callback-secrets
              key: secret-key
---
apiVersion: v1
kind: Service
metadata:
  name: gitapp-callback
spec:
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: gitapp-callback
```

## References
https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-user-authorization-callback-url


### GitHub App Configuration

1. Go to your GitHub App settings
2. Set "Post-installation redirect URL" to: `https://your-domain.com/registrations`
3. GitHub will append `?installation_id=XXX&setup_action=install` automatically

## Overview
### initialize app
```mermaid
graph TD
    Start["🚀 App Startup"] --> InitDB["Initialize SQLite Database"]
    InitDB --> CreateTable["Create registrations table<br/>installation_id, data, timestamps"]
    CreateTable --> EnsureRepo["ensure_repo_registration"]

    EnsureRepo --> CheckRepo{REPO_REGISTRATION<br/>configured?}
    CheckRepo -->|No| SkipRepo["⊘ Skip registrations checkout"]
    CheckRepo -->|Yes| SetupGit["Configure git credentials<br/>GIT_CREDENTIALS_FILE"]
    SetupGit --> ConfigHelper["git config --global<br/>credential.helper store"]
    ConfigHelper --> CheckPath{REGISTRATIONS_PATH<br/>exists?}

    CheckPath -->|No| CloneRepo["Clone registrations repo<br/>git clone REPO_REGISTRATION"]
    CloneRepo --> ReadyApp["✓ App Ready"]

    CheckPath -->|Yes| CheckGit{.git directory<br/>exists?}
    CheckGit -->|Yes| FetchOrigin["Fetch and update repo<br/>git fetch origin --prune"]
    FetchOrigin --> GetBranch["Get default branch<br/>git symbolic-ref refs/remotes/origin/HEAD"]
    GetBranch --> Checkout["git checkout default_branch"]
    Checkout --> Reset["git reset --hard<br/>origin/default_branch"]
    Reset --> ReadyApp

    CheckGit -->|No| CheckEmpty{Directory<br/>not empty?}
    CheckEmpty -->|Yes| WarnEmpty["⚠️ Warn: skip if dir not empty"]
    CheckEmpty -->|No| ReadyApp

    SkipRepo --> ReadyApp
    WarnEmpty --> ReadyApp

    ReadyApp --> InitComplete["✓ Initialization Complete<br/>Ready for HTTP requests"]

    style Start fill:#e1f5ff
    style ReadyApp fill:#c8e6c9
    style InitComplete fill:#c8e6c9,stroke:#4caf50,stroke-width:2px

```

### Get registration flow
```mermaid
graph TD
    GetReq["GET /registrations"] --> ExtractParams["Extract installation_id<br/>and setup_action params"]
    ExtractParams --> ValInstallID{installation_id<br/>present?}

    ValInstallID -->|No| Err400A["❌ Return 400<br/>Missing installation_id"]
    ValInstallID -->|Yes| ValInteger{installation_id<br/>is integer?}

    ValInteger -->|No| Err400B["❌ Return 400<br/>Invalid format"]
    ValInteger -->|Yes| FetchRepos["Fetch repositories from<br/>GitHub API<br/>get_installation_repositories"]
    FetchRepos --> ValFetch{Fetch<br/>success?}

    ValFetch -->|No| Err500A["❌ Return 500<br/>GitHub API error"]
    ValFetch -->|Yes| ValAction{setup_action<br/>valid?}

    ValAction -->|No| Err400C["❌ Return 400<br/>Invalid setup_action"]
    ValAction -->|Yes| CheckAction{setup_action<br/>== install?}

    CheckAction -->|Yes| CheckExists{Registration<br/>exists?}
    CheckExists -->|Yes| Redirect["⤴️ Redirect to update<br/>with setup_action=update"]
    CheckExists -->|No| DisplayForm["✓ Display registration form<br/>initial_data = null"]

    CheckAction -->|No| CheckExistsUpdate{Registration<br/>exists?}
    CheckExistsUpdate -->|No| Err404["❌ Return 404<br/>Not found for update"]
    CheckExistsUpdate -->|Yes| LoadForm["✓ Load existing data<br/>from database<br/>and display form"]

    Redirect --> Done["Return HTML response"]
    DisplayForm --> Done
    LoadForm --> Done
    Err400A --> Done
    Err400B --> Done
    Err400C --> Done
    Err500A --> Done
    Err404 --> Done

    style GetReq fill:#e1f5ff
    style DisplayForm fill:#fff9c4
    style LoadForm fill:#fff9c4
    style Done fill:#c8e6c9
    style Err400A fill:#ffccbc
    style Err400B fill:#ffccbc
    style Err400C fill:#ffccbc
    style Err500A fill:#ffccbc
    style Err404 fill:#ffccbc

```

### Validate registration
```mermaid
graph TD
    PostReq["POST /registrations"] --> ExtractForm["Extract form data<br/>installation_id, defaultBranch,<br/>admin/readUsers, buckets"]
    ExtractForm --> ValInstall{installation_id<br/>present?}

    ValInstall -->|No| FormErr400A["❌ Return 400"]
    ValInstall -->|Yes| ValAdmin{Admin users<br/>present?}

    ValAdmin -->|No| FormErr400B["❌ Return 400"]
    ValAdmin -->|Yes| ParseEmails["Parse email lists<br/>admin_users, read_users"]
    ParseEmails --> ValEmails{All emails<br/>valid format?}

    ValEmails -->|No| FormErr400C["❌ Return 400<br/>Invalid email"]
    ValEmails -->|Yes| ParseBuckets["Parse S3 bucket configs<br/>dataBucket & artifactBucket"]
    ParseBuckets --> ValBuckets{Bucket config<br/>valid?}

    ValBuckets -->|No| FormErr400D["❌ Return 400<br/>Invalid bucket config"]
    ValBuckets -->|Yes| CreateConfig["Create registration_config dict"]
    CreateConfig --> FetchReposForm["Fetch repositories<br/>from GitHub API"]
    FetchReposForm --> ValFetchForm{Fetch<br/>success?}

    ValFetchForm -->|No| FormErr500A["❌ Return 500"]
    ValFetchForm -->|Yes| CheckReposExist{Repositories<br/>found?}

    CheckReposExist -->|No| FormErr500B["❌ Return 500<br/>No repos found"]
    CheckReposExist -->|Yes| SaveDB["save_registration"]
    
```


### Upsert registration flow
```mermaid
graph TD
    PostReq["POST /registrations"] --> ExtractForm["Extract form data<br/>installation_id, defaultBranch,<br/>admin/readUsers, buckets"]
    ExtractForm --> ValAll{validate all form fields}

    ValAll -->|No| FormErr400A["❌ Return 400"]
    ValAll -->|Yes| SaveDB

    SaveDB --> RemoveBuckets["Remove buckets from config<br/>del dataBucket, artifactBucket"]
    RemoveBuckets --> CheckVault{VAULT_ADDR &<br/>VAULT_TOKEN set?}

    CheckVault -->|Yes| SaveDataVault["Save dataBucket to Vault<br/>argo/apps/owner/repo/dataBucket"]
    SaveDataVault --> SaveArtifactVault["Save artifactBucket to Vault<br/>argo/apps/owner/repo/artifactBucket"]
    SaveArtifactVault --> ValVaultSave{Save<br/>success?}

    CheckVault -->|No| SkipVault["⊘ Skip Vault save"]
    ValVaultSave -->|No| FormErr500C["❌ Return 500<br/>Vault save failed"]
    ValVaultSave -->|Yes| InsertDB
    SkipVault --> InsertDB["INSERT/UPDATE registrations<br/>table in SQLite<br/>ON CONFLICT DO UPDATE"]

    InsertDB --> CreatePR["create_registration_pull_request"]
    CreatePR --> EnsureRepoPR["ensure_repo_registration"]
    EnsureRepoPR --> FetchOriginPR["git fetch origin --prune"]
    FetchOriginPR --> GetDefaultBranch["Get default branch<br/>from origin/HEAD"]
    GetDefaultBranch --> CreateBranch["Create feature branch<br/>chore/create-owner-repo<br/>or chore/update-owner-repo"]
    CreateBranch --> CreateFile["Create registration file<br/>registrations/owner/repo_name.yaml"]
    CreateFile --> WritePayload["Write JSON payload<br/>{installation_id, registration_config}"]
    WritePayload --> GitAdd["git add file"]
    GitAdd --> GitCommit["git commit --allow-empty<br/>-m branch_name"]
    GitCommit --> GitPush["git push -u origin branch"]
    GitPush --> ValPush{Push<br/>success?}

    ValPush -->|No| PRErr["❌ Git command returned FAILED"]
    ValPush -->|Yes| CreateGHPR["Create GitHub PR via API<br/>POST /repos/owner/repo/pulls"]
    CreateGHPR --> ValPRCreate{PR created<br/>success?}

    ValPRCreate -->|No| CheckExistingPR{PR already<br/>exists?}
    CheckExistingPR -->|Yes| GetExistingPR["Get existing PR"]
    CheckExistingPR -->|No| PRErr500["❌ Return 500<br/>PR creation failed"]

    ValPRCreate -->|Yes| AddReviewer["Add co-pilot<br/>as PR reviewer"]
    GetExistingPR --> AddReviewer
    AddReviewer --> ValReviewer{Reviewer<br/>added?}

    ValReviewer -->|Yes| SuccessResp["✓ Return success<br/>JSON or HTML page<br/>with registration_config"]
    ValReviewer -->|No| PRErr500

    PRErr --> PRErrorResp["⚠️ Return 500<br/>Registration saved but<br/>git/PR creation failed"]
    PRErr500 --> PRErrorResp

    FormErr400A --> FormErrResp["❌ Return 400"]
    FormErr400B --> FormErrResp
    FormErr400C --> FormErrResp
    FormErr400D --> FormErrResp
    FormErr500A --> FormErrResp
    FormErr500B --> FormErrResp
    FormErr500C --> FormErrResp

    PRErrorResp --> Done["Return response"]
    FormErrResp --> Done
    SuccessResp --> Done

    style PostReq fill:#e1f5ff
    style SaveDB fill:#e1f5ff,stroke:#f57c00,stroke-width:2px
    style CreatePR fill:#e1f5ff,stroke:#f57c00,stroke-width:2px
    style SuccessResp fill:#c8e6c9
    style PRErrorResp fill:#fff9c4
    style FormErrResp fill:#ffccbc

```


## Future Enhancements

- [ ] refactor tests to use pytest fixtures/mocks
- [ ] Persist configuration to Kubernetes CRD (RepoRegistration)
- [ ] Integrate with GitHub API to fetch repository details
- [ ] Validate installation_id with GitHub API
- [ ] Add authentication/authorization
- [ ] Support for updating existing registrations
- [ ] Webhook configuration interface
- [ ] Repository list view

## License

Apache 2.0
