Basically want the **same pattern** you just built for Argo CD Apps, but driven by **Argo Workflows** instead of Applications:

1. Workflow finishes (Succeeded / Failed).
2. Argo Workflows Notifications fires `workflow-succeeded` / `workflow-failed`.
3. Notification is a **webhook** to `github-status-proxy`.
4. `github-status-proxy` posts the result to GitHub (commit status / deployment / check).

Sketch follows...

---

## 1. Turn on Argo Workflows Notifications (if not already)

Argo Workflows has its own notifications engine via a ConfigMap called `workflow-notifications-cm` (name can be customized but that’s the default for the examples).

You want something like this in the **same namespace as your workflows** (maybe `wf-bwalsh-nextflow-hello-project` or a shared `workflows` ns):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-notifications-cm
  namespace: <your-namespace>   # replace with your workflow namespace
data:
  # Service: webhook to github-status-proxy
  service.webhook.github-status-proxy: |
    url: http://github-status-proxy.argocd.svc.cluster.local/workflow
    headers:
      X-Argo-Notifications-Token: $github-status-proxy-token
    insecureSkipVerify: false

  # Template for "workflow-succeeded"
  template.workflow-succeeded: |
    message: |
      Workflow {{.workflow.metadata.name}} has succeeded.
    webhook:
      github-status-proxy:
        method: POST
        body: |
          {
            "kind": "workflow",
            "event": "workflow-succeeded",
            "workflowName": "{{.workflow.metadata.name}}",
            "namespace": "{{.workflow.metadata.namespace}}",
            "phase": "{{.workflow.status.phase}}",
            "startedAt": "{{.workflow.status.startedAt}}",
            "finishedAt": "{{.workflow.status.finishedAt}}",
            "labels": {{ toJson .workflow.metadata.labels }},
            "annotations": {{ toJson .workflow.metadata.annotations }},
            "status": {{ toJson .workflow.status }}
          }

  # Template for "workflow-failed"
  template.workflow-failed: |
    message: |
      Workflow {{.workflow.metadata.name}} has failed.
    webhook:
      github-status-proxy:
        method: POST
        body: |
          {
            "kind": "workflow",
            "event": "workflow-failed",
            "workflowName": "{{.workflow.metadata.name}}",
            "namespace": "{{.workflow.metadata.namespace}}",
            "phase": "{{.workflow.status.phase}}",
            "startedAt": "{{.workflow.status.startedAt}}",
            "finishedAt": "{{.workflow.status.finishedAt}}",
            "labels": {{ toJson .workflow.metadata.labels }},
            "annotations": {{ toJson .workflow.metadata.annotations }},
            "status": {{ toJson .workflow.status }}
          }

  # Trigger for succeeded
  trigger.on-workflow-succeeded: |
    - description: Notify when workflow has succeeded
      when: workflow.status.phase == 'Succeeded'
      oncePer: workflow.metadata.uid
      send:
        - workflow-succeeded

  # Trigger for failed
  trigger.on-workflow-failed: |
    - description: Notify when workflow has failed
      when: workflow.status.phase in ['Failed', 'Error']
      oncePer: workflow.metadata.uid
      send:
        - workflow-failed
```

Then in **`workflow-notifications-secret`** in the same namespace:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: workflow-notifications-secret
  namespace: wf-bwalsh-nextflow-hello-project
stringData:
  github-status-proxy-token: "same-secret-as-argocd-side-or-different"
```

> The structure is very similar to Argo CD notifications: `service.webhook.<name>`, `template.*`, `trigger.*`.

---

## 2. Opt individual workflows into those triggers

For each **Workflow** or **WorkflowTemplate** that should talk to GitHub, add annotations that subscribe to those triggers.

Example Workflow:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  namespace: wf-bwalsh-nextflow-hello-project
  generateName: nextflow-run-
  annotations:
    workflows.argoproj.io/notifications: |
      - trigger: on-workflow-succeeded
        service: github-status-proxy
      - trigger: on-workflow-failed
        service: github-status-proxy
  labels:
    # add GitHub-related info so proxy can route
    repo-url: https://github.com/bwalsh/nextflow-hello-project.git
    tenant: research-team-1
    git-sha: abcd1234
spec:
  # ...
```

Key bits:

* `workflows.argoproj.io/notifications` is where Workflows subscribes to triggers.
* `service: github-status-proxy` matches the `<name>` part of `service.webhook.github-status-proxy`.
* Labels like `repo-url` / `tenant` give the proxy enough info to find the right GitHub App / RepoRegistration.

---

## 3. Extend `github-status-proxy` to handle workflow events

Right now your proxy probably has an `/status` handler aimed at Argo CD App events. For workflows, add a `/workflow` handler.

Very rough sketch:

```go
type WorkflowEvent struct {
  Kind        string            `json:"kind"`        // "workflow"
  Event       string            `json:"event"`       // "workflow-succeeded" | "workflow-failed"
  Workflow    string            `json:"workflowName"`
  Namespace   string            `json:"namespace"`
  Phase       string            `json:"phase"`
  StartedAt   string            `json:"startedAt"`
  FinishedAt  string            `json:"finishedAt"`
  Labels      map[string]string `json:"labels"`
  Annotations map[string]string `json:"annotations"`
  Status      any               `json:"status"`      // or a concrete struct if you care
}

func (s *Server) handleWorkflow(w http.ResponseWriter, r *http.Request) {
  if !s.authenticate(r) {
    http.Error(w, "unauthorized", http.StatusUnauthorized)
    return
  }

  var evt WorkflowEvent
  if err := json.NewDecoder(r.Body).Decode(&evt); err != nil {
    http.Error(w, "bad payload", http.StatusBadRequest)
    return
  }

  log.Printf("Workflow event: %s %s/%s phase=%s",
    evt.Event, evt.Namespace, evt.Workflow, evt.Phase)

  // Figure out repoURL and/or tenant from labels/annotations
  repoURL := evt.Labels["repo-url"]
  tenant := evt.Labels["tenant"]

  if repoURL == "" {
    // maybe fall back to annotation
    repoURL = evt.Annotations["repo-url"]
  }

  if repoURL == "" {
    http.Error(w, "missing repo-url label/annotation", http.StatusBadRequest)
    return
  }

  // Resolve GitHub App / installation, same way you already do for app events.
  // You can either:
  //   - parse owner/repo from repoURL directly (what you’re already doing), or
  //   - use RepoRegistration lookup if you want installation_id from there.
  owner, repo := parseRepoURL(repoURL)

  // Example: map workflow event → commit status state + description
  state := "pending"
  description := "Workflow is running"
  switch evt.Event {
  case "workflow-succeeded":
    state = "success"
    description = "Workflow succeeded"
  case "workflow-failed":
    state = "failure"
    description = "Workflow failed"
  }

  // You'll also need to know which commit SHA to update.
  // You can pass that in the payload (e.g. label/annotation "git-sha") or derive it via RepoRegistration.
  sha := evt.Labels["git-sha"]

  if sha == "" {
    // fallback: maybe from annotations or from evt.Status (if you store it there)
  }

  if sha == "" {
    http.Error(w, "missing git-sha", http.StatusBadRequest)
    return
  }

  // Use your existing GitHub App machinery:
  //   - get installation ID (either from /installation API or from RepoRegistration)
  //   - mint token
  //   - post commit status
  if err := s.postCommitStatus(owner, repo, sha, state, description); err != nil {
    log.Printf("Failed to post commit status for workflow: %v", err)
    http.Error(w, "github error", http.StatusBadGateway)
    return
  }

  w.WriteHeader(http.StatusOK)
}
```

And wire it into your mux:

```go
http.HandleFunc("/workflow", s.handleWorkflow)
```

---

## 4. Getting the Git commit SHA into the workflow

To send a meaningful GitHub status, you need the **commit SHA** that the workflow is executing.

Options:

1. **Pass it via Argo Events Sensor**

   * If GitHub webhook → Argo Events → Workflow, you usually already have the SHA.
   * Sensor can set the SHA as a label/annotation on the Workflow:

     ```yaml
     metadata:
       labels:
         git-sha: "{{ .github.body.after }}"
     ```

2. **Include it in `Workflow.spec.arguments` and copy into metadata** via a Template or a workflow-controller sidecar.

3. **Lookup via RepoRegistration** if you have enough info, but simple is: pass SHA from the trigger.

As long as `github-status-proxy` gets `repo-url` + `git-sha` + `tenant`, it can:

* Determine the correct GitHub App / installation.
* Post a status that says “Workflow succeeded/failed” on that commit.

---

## 5. Naming: `workflow-succeeded` / `workflow-failed`

You already saw where those strings live:

* In **`event`** field of the payload you send from the template.
* In how you branch behavior inside `github-status-proxy`.

So your mental map is:

* Argo Workflows Trigger name: `on-workflow-succeeded`.
* Template name: `workflow-succeeded`.
* Payload `event` field: `"workflow-succeeded"`.
* Proxy: `switch evt.Event { case "workflow-succeeded": ... }`.

---
