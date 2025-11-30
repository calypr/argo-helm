[Home](index.md) > User Guides

# 👩‍🔬 User Guide — Running Nextflow Workflows from GitHub

This guide explains how to connect your **GitHub repository** to the Argo environment so that every **push** automatically runs a **Nextflow workflow** on the compute cluster.

---

## 🧠 What Happens

1. You push code to GitHub.
2. A GitHub **webhook** notifies the Argo platform.
3. Argo launches a **Nextflow workflow**.
4. You view logs, results, and history through the **Argo Workflows UI**.

```mermaid
sequenceDiagram
    participant GH as GitHub Repo
    participant AE as Argo Events
    participant AW as Argo Workflows
    GH->>AE: Push event (webhook POST)
    AE->>AW: Submit Workflow (Nextflow)
    AW-->>GH: (optional status)
```

## 1. Prepare Your GitHub Repository

Ensure your repository contains:
- A `main.nf` or equivalent Nextflow script.
- Any configuration files (`nextflow.config`, `params.json`, etc.).
- (Optional) a small test dataset.

## 2. Create a Personal Access Token (PAT)

Argo uses this token to create a webhook automatically.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens**
2. Choose **Fine-grained token** (recommended).
3. Select your repository and grant:
   - **Webhooks: Read/Write**
   - **Contents: Read**
   - **Metadata: Read**
4. Copy the generated token (it starts with `github_pat_...`).

Send this token to your Argo admin (securely), or store it locally if you’ll register the webhook manually.


### 🔐 GitHub Personal Access Token Setup

For Argo Events to automatically create and manage webhooks in your GitHub repositories, you need a Personal Access Token (PAT) with the appropriate permissions.

#### Single Repository (Fine-Grained Token)

If you only need to monitor **one repository**, you can use a fine-grained token:

1. Go to [GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token**
3. Configure the token:
   - **Token name:** `argo-events-webhook`
   - **Expiration:** Choose appropriate expiration
   - **Repository access:** Select "Only select repositories" and choose your repository
4. Under **Repository permissions**, enable:
   - **Contents:** Read-only (to access repository metadata)
   - **Metadata:** Read-only (required)
   - **Webhooks:** Read and write (to create/manage webhooks)
5. Click **Generate token** and **copy the token immediately** (you won't be able to see it again)

#### Multiple Repositories (Classic Token - Recommended)

If you need to monitor **multiple repositories** (e.g., both `nextflow-hello-project` and `nextflow-hello-project-2`), you should use a **classic Personal Access Token** because fine-grained tokens are limited to specific repositories:

1. Go to [GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Configure the token:
   - **Note:** `argo-events-multi-repo`
   - **Expiration:** Choose appropriate expiration (e.g., 90 days, 1 year, or no expiration)
4. Select the following scopes:
   - ✅ **`repo`** (Full control of private repositories) - This includes:
     - `repo:status` - Access commit status
     - `repo_deployment` - Access deployment status
     - `public_repo` - Access public repositories
     - `repo:invite` - Access repository invitations
   - ✅ **`admin:repo_hook`** (Full control of repository hooks) - This includes:
     - `write:repo_hook` - Write repository hooks
     - `read:repo_hook` - Read repository hooks
5. Click **Generate token** and **copy the token immediately**

#### Important Notes

- **Never commit your PAT to Git** - Always pass it at deployment time using `--set-string`
- **Store it securely** - Use a password manager or secrets management system
- **Rotate regularly** - Set an expiration date and rotate your token periodically
- **Minimal permissions** - Only grant the scopes necessary for your use case
- **Organization repositories** - If your repositories are in an organization:
  1. After creating the token, click **Configure SSO** next to the token
  2. Authorize the token for your organization
  3. Ensure the organization settings allow PAT access

#### Common Permission Issues

If you see errors like:
```
403 Resource not accessible by personal access token
```

This means:
- The PAT doesn't have access to the repository
- The PAT doesn't have the required scopes (`admin:repo_hook` or `repo`)
- The repository is in an organization and the token isn't authorized for that organization
- The organization has restricted PAT access

**Solution:** Regenerate the token with the correct scopes and organization authorization.

---

## 3. Connect Your Repo to the Argo Platform

If your admin has automated onboarding, they’ll request:
- Your **GitHub repo URL**
- Your **GitHub username or org name**
- Your **token**

They will register the webhook endpoint (for example `https://argo-events.example.com/events`).

If manual setup is needed, go to your **GitHub repo → Settings → Webhooks → Add webhook** and enter:

| Field | Value |
|-------|--------|
| **Payload URL** | `https://<argo-hostname>/events` |
| **Content type** | `application/json` |
| **Secret** | *(value provided by admin, if used)* |
| **Events** | Just the **push** event |

Click **Add webhook** and verify you see a green ✅ next to it.

## 4. Push to Trigger a Workflow

Make a commit in your repo and push it:

```bash
git commit --allow-empty -m "Trigger Nextflow workflow"
git push
```

Argo will automatically start a new run using your latest commit.

## 5. Viewing Your Workflow

### Web UI

Visit: http://<argo-workflows-host>:2746

You’ll see your workflow under the **Workflows** list.

Click the workflow name to view its DAG and live logs.

### Command Line

```bash
argo -n argo list
argo -n argo get @latest
```

To stream logs:
```bash
argo -n argo logs @latest
```

## 6. Retrieving Results

Each workflow runs inside the cluster and writes outputs to object storage.

### Per-Repository Artifact Storage

The Argo platform supports **per-repository S3 buckets** to ensure tenant isolation and traceability. Each GitHub repository can be configured with its own dedicated bucket or bucket prefix:

#### Example Configuration

When your repository is configured with per-repository artifacts, your admin will set up values like:

```yaml
applications:
  - name: nextflow-hello-project
    repoURL: https://github.com/bwalsh/nextflow-hello-project.git
    artifacts:
      bucket: calypr-nextflow-hello
      keyPrefix: workflows/
      endpoint: https://s3.us-west-2.amazonaws.com
      region: us-west-2
      credentialsSecret: s3-cred-nextflow-hello
```

#### Locating Your Workflow Outputs

With per-repository artifacts enabled, your workflow outputs are stored at:

```
s3://<your-repo-bucket>/<keyPrefix>/<workflow-name>/
```

For example:
```
s3://calypr-nextflow-hello/workflows/nextflow-hello-abc123/
```

You can find the exact bucket path in the workflow metadata:
```bash
argo -n argo get @latest -o yaml | grep -A2 artifactRepositoryRef
```

Or view the ConfigMap that defines your repository's artifact storage:
```bash
kubectl -n argo-workflows get configmap argo-artifacts-<your-app-name> -o yaml
```

#### Accessing Your Data

If you have AWS CLI configured with appropriate credentials:

```bash
# List workflow outputs
aws s3 ls s3://calypr-nextflow-hello/workflows/

# Download a specific workflow's outputs
aws s3 sync s3://calypr-nextflow-hello/workflows/nextflow-hello-abc123/ ./local-results/

# View logs
aws s3 cp s3://calypr-nextflow-hello/workflows/nextflow-hello-abc123/main.log -
```

#### Benefits of Per-Repository Artifacts

- **Tenant Isolation**: Each repository's data is kept separate
- **Traceability**: Outputs are linked to the source repository and Git commit
- **Custom Policies**: Apply repository-specific retention, encryption, and replication rules
- **Access Control**: Grant granular S3 bucket permissions per team or project

#### Global vs Per-Repository Artifacts

If your repository doesn't have a dedicated artifacts configuration, it will fall back to the **global S3 bucket** configured by your admin:

```bash
# Global artifact repository
s3://<global-bucket>/<workflow-name>/
```

Consult with your admin to determine which configuration applies to your repository.

If your workflow includes a results collection step, it will post a summary to the Workflows UI under **Artifacts**.

## 7. Inspecting Logs and History

- **Argo Workflows UI → Workflow → Logs tab**  
  View stdout/stderr for each task.

- **CLI:**
  ```bash
  argo -n argo logs @latest --follow
  ```

- **Audit history:**  
  ```bash
  argo -n argo list
  ```

Each workflow corresponds to one Git commit (shown as `git_revision` in parameters).

## 8. Disconnect or Pause Automation

If you want to stop automatic triggering:
1. Delete the webhook from your GitHub repo (**Settings → Webhooks → Delete**)
2. Notify your admin if you want to disable event listening for your repo.

---

## 9. Self-Service Repository Registration

### 🎯 Overview

The **RepoRegistration** feature enables **self-service onboarding** of GitHub repositories to the Argo platform. Instead of asking an administrator to manually configure your repository, you can create a `RepoRegistration` resource that automatically sets up:

- GitHub webhook integration
- Dedicated S3 buckets for artifacts and data
- Vault-backed secret management
- User access controls (admin and read-only users)
- Workflow automation

### 📋 When to Use RepoRegistration

Use the `RepoRegistration` approach when:

✅ You want **automated, self-service** repository onboarding  
✅ Your repository needs **dedicated S3 buckets** for tenant isolation  
✅ You're using **Vault** for centralized secret management  
✅ You need **fine-grained user access control** (admin vs. read-only users)  
✅ You want automatic reconciliation and lifecycle management

### 🏗️ How It Works

```mermaid
sequenceDiagram
    participant User as Developer
    participant K8s as Kubernetes
    participant Controller as Repo Controller
    participant Vault as HashiCorp Vault
    participant ESO as External Secrets Operator
    participant GH as GitHub
    participant Argo as Argo Workflows

    User->>K8s: Create RepoRegistration
    K8s->>Controller: Reconcile new resource
    Controller->>Vault: Fetch S3 credentials
    Controller->>ESO: Create ExternalSecret
    ESO->>Vault: Pull credentials
    ESO->>K8s: Create Kubernetes Secret
    Controller->>GH: Create webhook
    Controller->>Argo: Create WorkflowTemplate
    GH-->>Argo: Push events trigger workflows
```

### 🚀 Creating Your First RepoRegistration

#### Step 1: Prepare Your GitHub Repository

Ensure your repository:
- Contains a Nextflow pipeline (e.g., `main.nf`, `workflow.nf`)
- Has configuration files if needed (`nextflow.config`)
- Is accessible with your GitHub Personal Access Token

#### Step 2: Store Credentials in Vault

Your platform administrator should have created Vault paths for your repository. You'll need:

**GitHub Credentials:**
```bash
vault kv put kv/argo/apps/my-repo/github \
  token="ghp_YourPersonalAccessToken" \
  webhookSecret="random-webhook-secret"
```

**S3 Artifact Bucket Credentials:**
```bash
vault kv put kv/argo/apps/my-repo/s3/artifacts \
  accessKey="AKIAIOSFODNN7EXAMPLE" \
  secretKey="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

**S3 Data Bucket Credentials (if applicable):**
```bash
vault kv put kv/argo/apps/my-repo/s3/data \
  accessKey="AKIAIOSFODNN7EXAMPLE" \
  secretKey="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

#### Step 3: Create a RepoRegistration Resource

Create a file `my-repo-registration.yaml`:

```yaml
apiVersion: platform.calypr.io/v1alpha1
kind: RepoRegistration
metadata:
  name: my-nextflow-repo
  namespace: argo  # Or your designated namespace
spec:
  # Required fields
  repoUrl: https://github.com/myorg/my-nextflow-repo.git
  tenant: myteam
  workflowTemplateRef: nextflow-repo-runner
  githubSecretName: my-repo-github-creds
  
  # Optional: Default branch to track
  defaultBranch: main
  
  # Artifact bucket configuration (optional but recommended)
  artifactBucket:
    hostname: https://s3.us-west-2.amazonaws.com
    bucket: my-team-artifacts
    region: us-west-2
    insecure: false
    pathStyle: false
    # Vault path for S3 credentials
    externalSecretPath: kv/argo/apps/my-repo/s3/artifacts
  
  # Data bucket configuration (optional)
  dataBucket:
    hostname: https://s3.us-west-2.amazonaws.com
    bucket: my-team-data
    region: us-west-2
    insecure: false
    pathStyle: false
    # Vault path for S3 credentials
    externalSecretPath: kv/argo/apps/my-repo/s3/data
  
  # Access control
  adminUsers:
    - admin@example.com
    - lead@example.com
  
  readUsers:
    - viewer@example.com
    - analyst@example.com
  
  # Public visibility (optional)
  isPublic: false
```

#### Step 4: Apply the Configuration

```bash
kubectl apply -f my-repo-registration.yaml
```

#### Step 5: Verify the Registration

```bash
# Check the RepoRegistration status
kubectl get reporegistration my-nextflow-repo -n argo -o yaml

# Look at the status field
kubectl get reporegistration my-nextflow-repo -n argo -o jsonpath='{.status}' | jq
```

Expected status:
```json
{
  "phase": "Ready",
  "message": "Repository successfully registered and webhook configured",
  "lastReconciled": "2025-11-20T01:00:00Z"
}
```

### 📊 Field Reference

#### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `repoUrl` | string | Git repository URL (must end with `.git`) | `https://github.com/org/repo.git` |
| `tenant` | string | Tenant identifier (project/program code) | `myproject` |
| `workflowTemplateRef` | string | Argo WorkflowTemplate to use | `nextflow-repo-runner` |
| `githubSecretName` | string | Name of Kubernetes Secret with GitHub credentials | `my-repo-github-creds` |

#### Optional Fields

##### Artifact Bucket Configuration (`artifactBucket`)

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `hostname` | string | S3 endpoint URL | - |
| `bucket` | string | Bucket name for workflow artifacts | - |
| `region` | string | AWS region or compatible | `us-west-2` |
| `insecure` | boolean | Use HTTP instead of HTTPS | `false` |
| `pathStyle` | boolean | Force path-style requests | `false` |
| `externalSecretPath` | string | Vault KV v2 path for S3 credentials | - |

##### Data Bucket Configuration (`dataBucket`)

Same fields as `artifactBucket`, but for primary data storage.

##### User Access Control

| Field | Type | Description |
|-------|------|-------------|
| `adminUsers` | array[string] | Email addresses with admin access to workflows, logs, and configuration |
| `readUsers` | array[string] | Email addresses with read-only access to workflow logs and outputs |

##### Visibility

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `defaultBranch` | string | Default branch to track | `main` |
| `isPublic` | boolean | Allow public access without Fence login | `false` |

### 🔍 Examples

#### Minimal Configuration

For a basic setup with global S3 bucket (no dedicated buckets):

```yaml
apiVersion: platform.calypr.io/v1alpha1
kind: RepoRegistration
metadata:
  name: simple-repo
  namespace: argo
spec:
  repoUrl: https://github.com/myorg/simple-pipeline.git
  tenant: demo
  workflowTemplateRef: nextflow-repo-runner
  githubSecretName: simple-repo-github
```

#### Full Configuration with MinIO

For local development using MinIO:

```yaml
apiVersion: platform.calypr.io/v1alpha1
kind: RepoRegistration
metadata:
  name: dev-pipeline
  namespace: argo
spec:
  repoUrl: https://github.com/myorg/dev-pipeline.git
  defaultBranch: develop
  tenant: dev-team
  workflowTemplateRef: nextflow-repo-runner
  githubSecretName: dev-pipeline-github
  
  artifactBucket:
    hostname: http://minio.minio-system.svc.cluster.local:9000
    bucket: dev-artifacts
    region: us-east-1
    insecure: true
    pathStyle: true
    externalSecretPath: kv/argo/apps/dev-pipeline/s3/artifacts
  
  dataBucket:
    hostname: http://minio.minio-system.svc.cluster.local:9000
    bucket: dev-data
    region: us-east-1
    insecure: true
    pathStyle: true
    externalSecretPath: kv/argo/apps/dev-pipeline/s3/data
  
  adminUsers:
    - dev@example.com
  
  isPublic: true  # Development environment
```

#### Production Configuration with AWS S3

For production with dedicated AWS S3 buckets:

```yaml
apiVersion: platform.calypr.io/v1alpha1
kind: RepoRegistration
metadata:
  name: production-pipeline
  namespace: argo
spec:
  repoUrl: https://github.com/myorg/production-pipeline.git
  defaultBranch: main
  tenant: prod-team
  workflowTemplateRef: nextflow-repo-runner
  githubSecretName: prod-pipeline-github
  
  artifactBucket:
    hostname: https://s3.us-west-2.amazonaws.com
    bucket: prod-workflow-artifacts
    region: us-west-2
    insecure: false
    pathStyle: false
    externalSecretPath: kv/argo/apps/production-pipeline/s3/artifacts
  
  dataBucket:
    hostname: https://s3.us-west-2.amazonaws.com
    bucket: prod-research-data
    region: us-west-2
    insecure: false
    pathStyle: false
    externalSecretPath: kv/argo/apps/production-pipeline/s3/data
  
  adminUsers:
    - admin@example.com
    - devops@example.com
  
  readUsers:
    - scientist@example.com
    - analyst@example.com
  
  isPublic: false
```

### 🛠️ Troubleshooting

#### Check Registration Status

```bash
# Get detailed status
kubectl describe reporegistration my-repo -n argo

# Check events
kubectl get events -n argo --field-selector involvedObject.name=my-repo
```

#### Common Issues

**❌ Status: Error - "Failed to create webhook"**
- Verify your GitHub PAT has webhook permissions (`admin:repo_hook`)
- Check the GitHub secret exists and contains a valid token
- Ensure the repository URL is correct and accessible

**❌ Status: Error - "Failed to fetch S3 credentials from Vault"**
- Verify the Vault path in `externalSecretPath` is correct
- Check that credentials exist in Vault: `vault kv get <path>`
- Ensure External Secrets Operator is running and has Vault access

**❌ Status: Pending**
- The controller is processing your registration
- Wait a few moments and check again
- If stuck for >2 minutes, check controller logs:
  ```bash
  kubectl logs -n argo-system -l app=repo-registration-controller
  ```

#### Viewing Generated Resources

```bash
# Check ExternalSecrets created for your repo
kubectl get externalsecrets -n argo | grep my-repo

# Check Kubernetes Secrets
kubectl get secrets -n argo | grep my-repo

# View the generated ConfigMaps
kubectl get configmaps -n argo | grep my-repo
```

### 🔐 Security Best Practices

1. **Vault Paths**: Use a consistent naming convention:
   ```
   kv/argo/apps/<repo-name>/github
   kv/argo/apps/<repo-name>/s3/artifacts
   kv/argo/apps/<repo-name>/s3/data
   ```

2. **GitHub Tokens**: Use fine-grained tokens with minimal permissions:
   - Webhooks: Read/Write
   - Contents: Read
   - Metadata: Read

3. **User Emails**: Use verified email addresses that match your Fence/OIDC identity provider

4. **S3 Buckets**: 
   - Use separate buckets for artifacts and data when possible
   - Apply bucket policies to restrict access to specific IAM roles
   - Enable versioning and lifecycle policies

5. **Public Repos**: Set `isPublic: false` unless you specifically need unauthenticated access

---

# 🌟 Using the Calypr GitHub App

Issue tracking:

See #108 #35

This guide covers:

* **What the Calypr GitHub App does**
* **Why a user would install it**
* **How to integrate it into their GitHub account**
* **How it affects their project workflows**

### How to Connect Your GitHub Repository to the Calypr Server

## Overview

The **Calypr GitHub App** allows your project repository on GitHub to stay in sync with the Calypr platform.

By installing this app on your GitHub repository:

* Your **data**, **metadata**, and **workflow configuration files** will be automatically available to the Calypr system.
* Calypr can **detect updates** in your repository and ensure your project environment reflects your latest work.
* You no longer need to manage tokens, SSH keys, or manual permissions—GitHub handles it securely.

This makes collaboration easier, keeps your project reproducible, and ensures the Calypr server always has the most up-to-date version of your files.

---

# 🔧 What the Calypr GitHub App Does

After you install it:

### ✔ 1. **Securely connects your GitHub repository to Calypr**

The app grants Calypr read-only access to your repository. Calypr can download the files it needs, but **cannot modify your code or data**.

### ✔ 2. **Keeps your Calypr environment automatically updated**

Whenever you push new:

* data files
* metadata
* workflow definitions (Nextflow, Argo, CWL, etc.)
* configuration settings

…the Calypr server can see the latest version and use it in your workspace and pipelines.

### ✔ 3. **Simplifies onboarding**

No personal GitHub tokens.
No SSH keys.
No security complexity.
Just a simple installation and you’re done.

### ✔ 4. **Works with private repositories**

Your private data stays private. Only the Calypr system (and only specific components) can access it.

---

# 🧠 Why You Might Need This

You should install the Calypr GitHub App if:

* Your workflow, metadata, or analysis files live in GitHub.
* You want Calypr to run workflows based on the files in your repo.
* You want collaborators or pipelines to always use the current version.
* You want a secure, low-maintenance way to connect GitHub and Calypr.

If you’re using Calypr for **multi-omics**, **analysis pipelines**, or **any project with multiple collaborators**, the GitHub App is the easiest way to keep everything synchronized.

---

# 🛠 How to Install the Calypr GitHub App

Installing takes less than one minute.

### **Step 1 — Open the Installation Page**

Visit:

```
https://github.com/apps/calypr
```

(or the URL provided by your administrator)

### **Step 2 — Select Your Account or Organization**

You will see options such as:

* **Install for my personal GitHub account**
* **Install for an organization**

Choose where your repository lives.

### **Step 3 — Select Repositories**

You have two choices:

### **Option A — Only give access to selected repositories (recommended)**

Choose specific repositories that contain Calypr projects.

### **Option B — Give access to all repositories**

Only use this if:

* Your GitHub account is dedicated to Calypr work
  — or —
* You prefer not to manage per-repo permissions.

### **Step 4 — Confirm Permissions**

The Calypr GitHub App typically requests:

* **Read-only access to code and files**
* **Read-only access to repo metadata (branch names, permissions)**
* (Optional) permission to mark CI/check results, if Calypr is configured to do so

The app **cannot** modify your repository.

### **Step 5 — Finish Installation**

Click **Install**.
That’s it—your repository is now linked.

---

# 🔁 What Happens After Installation?

Once your repository is connected:

### ✔ Calypr immediately gains access

Your project will appear in the Calypr interface (or become available for registration, depending on your setup).

### ✔ Any updates you push to GitHub are seen by Calypr

Examples:

* upload new FASTQ files → they appear in Calypr’s data browser
* update metadata → validators update automatically
* change workflow config → workflow UI shows new settings
* add or edit sample sheets → pipelines re-index as needed

### ✔ No further authentication is required

You don’t need to manage passwords, tokens, or machine access.

---

# 🧪 Verifying the Connection

You can check the connection by:

* Opening the Calypr UI → Projects → *Your Repository*
* Clicking **Refresh**
* Verifying that your latest branch, files, and metadata are shown

If you push a change to GitHub and see it reflected in Calypr within a minute or two, everything is working.

---

# ❓ Troubleshooting

### **I don’t see my repository listed in Calypr.**

Make sure the GitHub App was installed for that specific repository.

### **I installed the app, but Calypr says it cannot access the repo.**

Two common causes:

1. The app was installed in your personal account, but the repo is in an organization.
2. The repo was not selected during installation.

### **I want to remove access.**

You can uninstall the app or change the permitted repositories anytime from:

```
https://github.com/settings/installations
```

---

# 📬 Need Help?

If you run into issues:

* Contact your Calypr platform administrator
* Or open a support ticket through the Calypr help portal

---

### 📚 Additional Resources

- [Vault Integration Guide](./secrets-with-vault.md)
- [Admin Guide - Managing RepoRegistrations](./admin-guide.md)
- [Workflow Troubleshooting](./workflow-troubleshooting.md)
