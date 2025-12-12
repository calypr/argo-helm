# 🔒 Define Secure Handling of GitHub Secrets for Self-Service Onboarding

## 🧭 Context

As we expand self-service onboarding for Git → Argo Workflows, users need a clear, standardized method to **communicate secrets** (GitHub App credentials, PATs, or Webhook HMACs) to the platform.

Secrets enable:
- Creation of GitHub Webhooks for workflow triggers.
- Authentication of Argo CD to private repositories.
- Verification of event payloads received by Argo Events.

This issue documents **how users should provide secrets securely**, which authentication modes are supported, and references to **Argo CD’s official GitHub App documentation**.

---

## 🔑 Supported Authentication Modes

| Mode | Description | Who provides the secret | Best for |
|------|--------------|--------------------------|-----------|
| **GitHub App** | GitHub App installed on user’s repository; Argo CD/Argo Events uses installation tokens. | Platform (user only approves installation). | Secure, multi-tenant environments |
| **PAT (Personal Access Token)** | Fine-grained GitHub PAT with limited scopes (webhook + contents + metadata). | User provides securely via vault or one-time link. | Simpler dev/testing |
| **Manual Webhook (HMAC)** | Shared secret string configured in GitHub Webhook + Argo Events Secret. | Shared between user and platform. | External or offline repos |

---

## 🧠 GitHub App Mode (Preferred)

### 1. User Action
- Install the organization’s **GitHub App** on their repository.
- Confirm the App has permissions for:
  - `Contents: Read`
  - `Metadata: Read`
  - `Webhooks: Read/Write` (if Argo manages hooks automatically)

### 2. Platform Configuration
Argo CD uses a GitHub App to access repositories instead of a PAT.

Reference:
- **Argo CD Docs → Private Repositories (GitHub App section)**  
  🔗 https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories  
- **Argo CD Docs → Notifications / GitHub Service**  
  🔗 https://argo-cd.readthedocs.io/en/release-2.5/operator-manual/notifications/services/github  
- **Community Discussion → GitHub App Integration Example**  
  🔗 https://github.com/argoproj/argo-cd/discussions/15641

Example Secret manifest:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-app-creds
  namespace: argocd
stringData:
  appID: "123456"
  installationID: "987654"
  privateKey: |
    -----BEGIN RSA PRIVATE KEY-----
    ...
    -----END RSA PRIVATE KEY-----
```

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
