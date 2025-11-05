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

Typical outputs:
- `s3://<your-bucket>/<workflow-name>/results/`
- or a project-specific bucket managed by your admin.

You can find the bucket path in the workflow metadata:
```bash
argo -n argo get @latest -o yaml | grep -A2 artifactRepositoryRef
```

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
