If your goal is to detect **“one or more pushes to the same pull request branch”** (i.e., new commits added to an open PR), there is exactly **one GitHub event** that represents this reliably:

# ✅ **`pull_request` event with `action: synchronize`**

This event fires **every time** someone pushes new commits to the branch associated with an open PR.

### Why it's the right event

* It batches *any number of git pushes* into a single conceptual signal:
  *“The PR changed; its head SHA is updated.”*
* It is emitted whether:

  * the author pushes one commit
  * multiple commits
  * rebases
  * force-pushes
  * resolves merge conflicts
  * GitHub automatically updates the branch

### What you get

GitHub always sends:

```json
{
  "action": "synchronize",
  "pull_request": {
    "number": 42,
    "head": {
      "ref": "feature-x",
      "sha": "abc123..."
    }
  },
  "installation": { "id": 123456 }
}
```

This is the canonical trigger for GitOps automation that needs to:

* run validation workflows
* run metadata checks
* preview manifests
* lint pipeline configs
* update PR statuses/comments

---

# Optional companion events

Depending on how rich your GitOps automation is, you may also subscribe to these:

### **1. `pull_request` with `opened`**

Triggered when a new PR is created.
Useful for initial workflow runs.

### **2. `pull_request` with `reopened`**

If repos enforce closing PRs on failures, this allows reactivation.

### **3. `push`** (optional)

Only needed if you want:

* behavior on branches **without** a PR
* behavior on default branch (e.g., `main`)
* behavior on tags

For “one or more pushes *to a PR*,” you don't need `push`.

### **4. `issue_comment`** (optional)

If you want your automation to react to `/retest`, `/sync`, `/approve`, etc.

---

# 🚫 Events that do *not* represent PR updates

* `pull_request_review`
* `pull_request_review_comment`
* `check_suite`
* `check_run`

These are *downstream* events, not indicators of new commits.

---

# 🎯 Final Answer

To represent **“one or more pushes to a pull request”**, subscribe to:

```text
pull_request:
  - synchronize      # commits pushed to PR
  - opened           # initial PR creation
  - reopened         # optional
```

And treat **`synchronize`** as the canonical signal for “new code just arrived.”

In “pure” GitOps, you treat **Git as the source of truth**, not as a log sink — so you usually **don’t** write raw workflow logs back into the repo.

Here’s how I’d structure it.

---

### 1. Where the *logs* live

When a push happens to a branch like `main` and your workflow runs (Argo Workflows, Tekton, Actions, etc.):

* **Runtime logs**

  * Stay in the **workflow engine / cluster**:

    * Pod logs in Kubernetes
    * Argo Workflows UI / `argo logs`
  * Optionally streamed/archived to:

    * Object storage (S3/MinIO/GCS)
    * Log aggregation (Loki, ELK, CloudWatch, etc.)

* **Artifacts / result bundles**

  * Stored in an **artifact repository** (S3, GCS, MinIO, Artifactory, etc.).
  * Your workflow can expose a URL back to those artifacts.

👉 **Do not** commit raw logs into the Git repo — it bloats history and breaks the “config only” contract.

---

### 2. Where the *status* goes

For GitOps, status tends to feed back to **two places**:

1. **Git provider (GitHub) – for humans and automations**

   * Use:

     * **Commit status** or **Checks API** on the `main` commit
     * Optional: a short **commit comment** with links to logs/artifacts
   * This gives a simple signal:

     * ✅ success / ❌ failure
     * * URL to detailed logs or report

2. **Cluster GitOps objects – for controllers**

   * Argo CD / Flux will maintain status in:

     * `Application` (Argo CD)
     * `Kustomization` / `HelmRelease` (Flux)
   * These CRDs show *deployment* status (Synced, Healthy, Degraded), not CI logs.

---

### 3. A good pattern in one sentence

> On push to `main`, the workflow writes **logs and artifacts** to an external store, writes a **succinct status** (✅/❌ + link) back to the **commit in GitHub**, and lets **Argo CD/Flux** express the deployment state via their own status fields.

That keeps Git clean, keeps ops logs in the right place, and still gives you a single-click path from the commit to the full workflow history.


