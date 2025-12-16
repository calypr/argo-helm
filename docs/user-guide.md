[Home](index.md) > User Guides

# 👩‍🔬 Connect Your GitHub Repo to Calypr and Run Workflows

This simplified guide shows how to:
1) Install the **Calypr GitHub App** on your repository.
2) Understand what happens when you push to **main** (workflow runs, app updates, portal refreshes).
3) Check status and troubleshoot.

---

## Overview

The **Calypr GitHub App** allows your project repository on GitHub to stay in sync with the Calypr platform.

By installing this app on your GitHub repository:

* Your **data**, **metadata**, and **workflow configuration files** will be automatically available to the Calypr system.
* Calypr can **detect updates** in your repository and ensure your project environment reflects your latest work.
* You no longer need to manage tokens, SSH keys, or manual permissions—GitHub handles it securely.

This makes collaboration easier, keeps your project reproducible, and ensures the Calypr server always has the most up-to-date version of your files.

---


## 1) 🔐 Install the Calypr GitHub App on your repo

**Takes ~1 minute.**

1. Open: `https://github.com/apps/calypr`
2. Click **Install**.
3. Choose where to install:
   - **Personal account** or **Organization**
4. Choose repositories:
   - **Recommended:** Select **only the repo(s)** you want Calypr to manage.
5. Confirm permissions (read-only access to code/metadata; write commit status).  [...](#githubapp)
6. Complete registration screen: [...](#registration)
  - User access controls (admin and read-only users)
  - Optional dedicated S3 buckets for artifacts and data


> To change or remove access later: https://github.com/settings/installations

---

## 2) ✅ Push to main: what happens

When you push to **main**:
- ✅ **Workflow runs:** The Nextflow/Argo workflow is triggered automatically.
- ✅ **Application updates (if applicable):** If your repo defines an app, Calypr deploys the new version.
- ✅ **Portal updates:** The Calypr portal reflects the latest files, configs, and metadata.
- ✅ **Git commit status update:** [...](#commitstatus)

---

## 3) 👀 Verify it’s working

### See your data in the Portal

- In the Calypr portal, open your project/repo and **Refresh** — you should see the latest commit/branch.
- In Argo Workflows UI, confirm a new workflow run started after your push.
- If your app is deployed, check the app’s status/version in the portal.

### See your workflow results

#### Locating Your Workflow Logs and History

Your workflow outputs are stored at:

```
s3://<your-repo-bucket>/<keyPrefix>/<workflow-name>/
```

For example:
```
s3://calypr-nextflow-hello/workflows/nextflow-hello-abc123/
```

---

## 4) 🪲 Troubleshooting

- **Repo not visible in Calypr:** Ensure the app was installed for that repo (and for the correct org).
- **No workflow on push:** Confirm you pushed to **main** and the workflow definition exists in the repo.
- **Access errors:** Re-open `https://github.com/settings/installations` and verify the repo is selected.

---

## 5) ℹ️ Need help?

- Contact your Calypr platform admin.
- Or file a support ticket via the Calypr help portal.


### 📚 Additional Resources

- [Vault Integration Guide](./secrets-with-vault.md)
- [Admin Guide - Managing RepoRegistrations](./admin-guide.md)
- [Workflow Troubleshooting](./workflow-troubleshooting.md)

## 6) Examples

---
### GitHubApp
<img width="574" height="638" alt="image" src="https://github.com/user-attachments/assets/0bc96e93-8c12-41fb-8f09-8750cbc8784c" />

---
### Registration
<img width="537" height="512" alt="image" src="https://github.com/user-attachments/assets/0d9c16a6-6c0d-4e6c-8b81-5792d8f0c38b" />

---
### CommitStatus
<img width="583" height="471" alt="image" src="https://github.com/user-attachments/assets/b1344b7e-5edf-4066-965c-43b041960d3a" />
