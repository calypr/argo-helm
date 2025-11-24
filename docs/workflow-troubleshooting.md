[Home](index.md) > Testing and Troubleshooting

# ⚙️ Workflow Troubleshooting Guide

**Document Purpose:**  
This guide helps users verify that their Git push successfully triggered a workflow in Argo Workflows, and to troubleshoot common issues in the GitHub → Argo Events → Argo Workflows chain.

**Audience:**  
Data managers and developers using Calypr’s Git-integrated workflow platform to run pipelines (e.g., Nextflow) automatically after code or data updates.

---

## 🧭 Overview

When you push to your Git repository, a webhook (managed by GitHub or Argo Events) should:
1. Deliver an event to **Argo Events**.
2. Trigger a **Sensor**.
3. Submit a **Workflow** in **Argo Workflows**.
4. Run the desired pipeline (e.g., Nextflow) and store results in your assigned S3 bucket.

If any link in that chain breaks, use this guide to isolate and fix it.

---

## ✅ Step 1. Check Webhook Delivery in GitHub

1. Go to your repository → **Settings → Webhooks**.  
2. Click your webhook (e.g., `/events` endpoint).  
3. Check **Recent Deliveries**:
   - **✅ Success:** Status code `200` or `202`  
   - **⚠️ Failure:** Any 4xx/5xx — click “Response” to inspect the error body.

### Common causes
| Error | Meaning | Fix |
|-------|----------|-----|
| `404 Not Found` | EventSource service not reachable | Check ingress host/path and EventSource name. |
| `401 Unauthorized` | HMAC or PAT mismatch | Confirm webhook secret matches K8s Secret in Argo Events. |
| `timeout` | Ingress blocked / DNS issue | Check cluster ingress and firewall rules. |
| `SSL error` | Self-signed certificate | Verify TLS setup or disable webhook SSL verification (temporary). |

---

## ✅ Step 2. Confirm Argo Events Received the Event

Run:
```bash
kubectl -n argo-events get eventsource github -o yaml | yq '.status'
kubectl -n argo-events get sensor run-nextflow-on-push -o yaml | yq '.status'
```

### Logs
```bash
kubectl -n argo-events logs -l eventsource-name=github --tail=100
kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push --tail=100
```

You should see messages like:
```
"processing event"
"triggering workflow"
```

If not:
- Ensure both **EventSource** and **Sensor** have status `Deployed`.
- Restart the EventSource pod:
  ```bash
  kubectl -n argo-events rollout restart deployment github-eventsource
  ```

---

## ✅ Step 3. Verify Workflow Creation

Watch the chain

```bash
# Argo Events (ingest + trigger)
kubectl -n argo-events logs -l eventsource-name=github --tail=200 -f
kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push --tail=200 -f
# Argo Workflows (submission + logs)
argo -n <workflow-namespace> list
argo -n <workflow-namespace> get @latest
argo -n <workflow-namespace> logs @latest --follow
```

Does the Sensor lacked permission to create Workflows in <wf-poc>

Even if logs look "OK", Sensor will log a forbidden when it actually tries to submit. Check:

```bash
# What SA is the sensor pod using?
kubectl -n argo-events get pod -l sensor-name=run-nextflow-on-push -o jsonpath='{.items[0].spec.serviceAccountName}{"\n"}'

# Can that SA create workflows in wf-poc?
kubectl -n wf-poc auth can-i create workflows --as=system:serviceaccount:argo-events:<SENSOR_SA>
```


Check sensor can create workflows.  The Argo Events → Argo Workflows bridge requires two capabilities:

* get workflowtemplates — to read the referenced template.
* create workflows — to instantiate it.

Each of those is namespaced. So even though the Sensor runs in argo-events, it must be authorized in the workflow namespace (wf-poc).


```bash
kubectl -n wf-poc auth can-i get workflowtemplates --as=system:serviceaccount:argo-events:default
kubectl -n wf-poc auth can-i create workflows --as=system:serviceaccount:argo-events:default
```
#### TODO ✅ Option 2 — Better long term: give each Sensor its own ServiceAccount

Instead of using default, you can set a dedicated one in the Sensor manifest:
```yaml
spec:
  template:
    serviceAccountName: sensor-run-nextflow
```

Then grant RBAC to that SA (same Role/RoleBinding as above).
This avoids accidentally over-permitting the default service account.



List workflows in your target namespace (often `argo` or `wf-poc`):
```bash
argo -n argo list
```
Or:
```bash
kubectl -n argo get wf
```

To follow the newest run:
```bash
argo -n argo get @latest
argo -n argo logs @latest --follow
```

> **Tip:** If your Sensor adds commit metadata:
> ```bash
> kubectl -n argo get wf -l git.sha=<COMMIT_SHA> -o wide
> ```

---

## ✅ Step 4. Check Workflow Status

### Common Phases
| Phase | Meaning |
|--------|----------|
| `Running` | Workflow is active. |
| `Succeeded` | Completed successfully. |
| `Failed` | One or more tasks failed. |
| `Error` | Infrastructure or submission issue. |
| `Omitted` | Step skipped by condition. |

### Inspect a workflow
```bash
argo -n argo get <workflow-name>
argo -n argo logs <workflow-name> --follow
```

---

## 🧩 Step 5. If No Workflow Was Created

Check RBAC and template references.

### Verify the Sensor’s permissions
```bash
kubectl -n argo auth can-i create workflows --as=system:serviceaccount:argo-events:<sensor-sa> -n argo
```
If it prints **no**, apply or patch a Role/RoleBinding allowing:
```yaml
rules:
- apiGroups: ["argoproj.io"]
  resources: ["workflows"]
  verbs: ["create"]
```

### Verify the WorkflowTemplate
```bash
kubectl -n argo get workflowtemplate nextflow-hello-template
```
If missing, reapply the workflow template YAML.

---

## ✅ Step 6. Troubleshoot Workflow Failures

```bash
argo -n argo get @latest
argo -n argo logs @latest --follow
```

### Common causes
| Symptom | Likely issue | Fix |
|----------|---------------|----|
| `ImagePullBackOff` | Container image not accessible | Verify image and credentials. |
| `S3 upload failed` | Bad bucket/keys or missing IRSA | Check artifact repository configuration. |
| `Permission denied` | ServiceAccount lacks permissions | Check RoleBinding for workflow executor. |
| `Nextflow missing` | Wrong container or entrypoint | Confirm `entrypoint` and image in WorkflowTemplate. |

---

## 🪣 Step 7. Validate Artifact Storage

Each application can use its own S3 bucket and key prefix for tenant isolation and traceability.

### Per-Repository Artifact Configuration

When an application is configured with per-repository artifacts (`.Values.applications[].artifacts`), the system creates:
1. A **ConfigMap** named `argo-artifacts-<app-name>` in the `argo-workflows` namespace
2. A **WorkflowTemplate** named `<app-name>-template` that references this ConfigMap

#### Check Your Application's Artifact Configuration

List all per-app artifact ConfigMaps:
```bash
kubectl -n argo-workflows get cm -l app.kubernetes.io/component=artifact-repository
```

View the artifact configuration for your specific app:
```bash
kubectl -n argo-workflows get cm argo-artifacts-<app-name> -o yaml
```

Verify the ConfigMap contains:
- `bucket`: Your assigned S3 bucket (e.g., `calypr-nextflow-hello`)
- `keyPrefix`: Workflow output path prefix (e.g., `workflows/`)
- `endpoint`: S3 endpoint URL
- `region`: AWS region
- `credentialsSecret` or `useSDKCreds`: Authentication method

#### Check WorkflowTemplate References

Verify your workflow template references the correct artifact repository:
```bash
kubectl -n wf-poc get workflowtemplate <app-name>-template -o yaml | grep -A3 artifactRepositoryRef
```

Expected output:
```yaml
artifactRepositoryRef:
  configMap: argo-artifacts-<app-name>
  key: artifactRepository
```

#### Verify Credentials

If using static credentials (not recommended for production):
```bash
kubectl -n wf-poc get secret <credentials-secret-name> -o yaml
```

The secret should contain:
- `accessKey`: AWS access key ID
- `secretKey`: AWS secret access key

If using **IRSA (AWS)** or **Workload Identity (GCP)**:
```bash
# Check service account annotation
kubectl -n wf-poc get sa wf-runner -o yaml | grep eks.amazonaws.com/role-arn
```

#### Test S3 Connectivity

List artifacts in your application's S3 location:
```bash
# Using AWS CLI
aws s3 ls s3://<your-app-bucket>/<keyPrefix>/

# Or if using a specific endpoint (MinIO, etc.)
aws s3 ls s3://<your-app-bucket>/<keyPrefix>/ --endpoint-url=<endpoint>
```

#### Common Artifact Issues

| Symptom | Likely Issue | Fix |
|---------|--------------|-----|
| `S3 upload failed: 403 Forbidden` | Invalid credentials or bucket permissions | Verify credentials secret or IRSA role permissions |
| `S3 upload failed: NoSuchBucket` | Bucket doesn't exist | Create the bucket or fix bucket name in ConfigMap |
| `S3 upload failed: connection timeout` | Endpoint unreachable or incorrect | Verify endpoint URL and network connectivity |
| `artifactRepositoryRef not found` | ConfigMap missing | Check if app has `artifacts` config in values.yaml |
| Artifacts in wrong bucket | Using global config instead of per-app | Ensure WorkflowTemplate has `artifactRepositoryRef` |

#### Fallback to Global Artifacts

If your application doesn't have a dedicated artifacts configuration, workflows will use the **global artifact repository** defined in:
```bash
kubectl -n argo-workflows get cm artifact-repositories -o yaml
```

This is controlled by the global `s3.*` values in the Helm chart.

#### Debugging Artifact Upload

To see detailed S3 upload logs, check the workflow pod logs:
```bash
# Find the workflow pod
kubectl -n wf-poc get pods -l workflows.argoproj.io/workflow=<workflow-name>

# View logs
kubectl -n wf-poc logs <pod-name> -c wait
```

Look for messages containing:
- `Saving output artifacts`
- `s3.PutObject`
- `Archive Logs`

### Migration from Global to Per-Repository Artifacts

If you're migrating from global artifacts to per-repository:

1. **Add artifacts config** to your application in values.yaml:
```yaml
applications:
  - name: my-app
    repoURL: https://github.com/org/my-repo.git
    artifacts:
      bucket: my-app-bucket
      keyPrefix: workflows/
      endpoint: https://s3.us-west-2.amazonaws.com
      region: us-west-2
      credentialsSecret: s3-cred-my-app
```

2. **Create the credentials secret** (if using static credentials):
```bash
kubectl create secret generic s3-cred-my-app \
  -n wf-poc \
  --from-literal=accessKey=<KEY> \
  --from-literal=secretKey=<SECRET>
```

3. **Upgrade the Helm release**:
```bash
helm upgrade argo-stack ./helm/argo-stack \
  -n argocd \
  --values my-values.yaml
```

4. **Verify ConfigMap created**:
```bash
kubectl -n argo-workflows get cm argo-artifacts-my-app
```

5. **Update workflows** to use the new template:
```yaml
workflowTemplateRef:
  name: my-app-template  # Instead of generic template
```

---

## ✅ Step 8. Verify in the UI

### Argo Workflows UI
- Visit: `https://<argo-host>/workflows/<namespace>`
- Use the filter by label:
  ```
  git.repo = bwalsh/nextflow-hello-project
  git.sha = <commit-sha>
  ```

### Expected
- The workflow matching your commit appears.
- Status = `Succeeded`.
- Logs and artifacts are accessible.

---

## 🔎 Step 9. Common Debug Commands (cheat sheet)

| Action | Command |
|--------|----------|
| List workflows | `argo -n argo list` |
| Follow logs | `argo -n argo logs @latest --follow` |
| Watch events | `stern -n argo-events 'eventsource|sensor'` |
| Check webhook ingress | `kubectl -n argo-events get ingress` |
| Get sensor status | `kubectl -n argo-events get sensor run-nextflow-on-push -o yaml | yq '.status'` |
| Describe workflow | `kubectl -n argo describe wf @latest` |
| Cleanup test runs | `argo -n argo delete --completed --older 1d` |

---

## 🧠 Optional Enhancements

- **Add labels and parameters** in your Sensor to trace workflows by repo and commit:
  ```yaml
  metadata:
    labels:
      git.repo: "{{ (events.push.body.repository.full_name) }}"
      git.sha:  "{{ (events.push.body.head_commit.id) }}"
      git.ref:  "{{ (events.push.body.ref) }}"
  spec:
    arguments:
      parameters:
        - name: git_revision
          value: "{{ (events.push.body.head_commit.id) }}"
  ```
- **Enable notifications**:
  - GitHub commit status via ArgoCD Notifications
  - Slack/Teams messages via Argo Events trigger

---

## ✅ Quick Validation Test

Run the following smoke test:
```bash
git commit --allow-empty -m "trigger test"
git push
```
Then verify:
1. GitHub webhook → status `200`.
2. `argo-events` logs show event processed.
3. A new workflow appears:
   ```bash
   argo -n argo list
   ```
4. The workflow runs to `Succeeded`.
5. Artifacts appear in your configured S3 bucket and prefix.

---

**Document Version:** 2025-11-04  
**Maintainer:** Platform / Data Workflow Team  
**Next Review:** Q1 2026
