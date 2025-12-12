# (File moved to docs/adr/0003-githubapp-secrets.md; delete this file.)
---
## 🧾 PAT Mode (Fine-Grained Token)

User creates a token with minimal scopes (`Webhooks RW`, `Contents R`, `Metadata R`), shares it securely (vault or one-time link), and the platform stores it:

```bash
kubectl -n argo-events create secret generic github-secret   --from-literal=token=$GITHUB_PAT
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

---

## 🔄 Manual Webhook (Shared HMAC)

User generates:
```bash
openssl rand -hex 20
```
Adds to GitHub webhook “Secret”.  
Platform mirrors it:
```bash
kubectl -n argo-events create secret generic github-webhook-secret   --from-literal=token=<same-string>
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

---

## 🔁 Rotation and Validation

| Type | Rotation | Verification |
|------|-----------|--------------|
| **PAT** | Every 90 days | Check `kubectl get eventsource github -o yaml` |
| **GitHub App** | Annual key rotation | Confirm `argocd-repo-server` logs & webhook health |
| **Webhook HMAC** | 180 days | Push test and verify 200 OK in Webhook deliveries |

---

## ✅ Acceptance Criteria

- [ ] Docs updated for GitHub App and PAT workflows  
- [ ] Portal/PR template collects repo + auth method  
- [ ] Vault or External Secrets tested for token sync  
- [ ] Argo CD configured for GitHub App authentication  
- [ ] Argo Events validated for PAT + webhookSecret modes  

---

**References**
- 🔗 [Argo CD — Private Repositories (GitHub App)](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories)  
- 🔗 [Argo CD — Notifications / GitHub Service](https://argo-cd.readthedocs.io/en/release-2.5/operator-manual/notifications/services/github)  
- 🔗 [Argo CD Discussion — Using GitHub App for Repo Access](https://github.com/argoproj/argo-cd/discussions/15641)
