
# 🧑‍💻 Argo Stack Development Guide

This document explains how to use the **Makefile** in this repository to deploy, test, and iterate on the Argo stack locally or in a development Kubernetes cluster.

---

## ⚙️ Prerequisites

Before using the Makefile, ensure you have:

- **kubectl** (≥ v1.25)
- **Helm** (≥ v3.10)
- **make**
- A running **Kubernetes cluster** (e.g. kind, minikube, or EKS)
- Internet connectivity for pulling Argo container images

---

## 🌱 Environment Setup

The Makefile expects three environment variables:

```bash
export GITHUB_PAT=<your-personal-access-token>
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)
export ARGO_HOSTNAME=<your-hostname-or-elb>
````

### 🔑 Variable details

| Variable              | Description                                                                                                                                                                                                                                                   | Example                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **GITHUB_PAT**        | GitHub Personal Access Token used by the Argo Events GitHub EventSource to automatically create a webhook. Must include scopes:<br>Fine-grained → **Webhooks: Read/Write**, **Contents: Read**, **Metadata: Read**<br>Classic → **repo**, **admin:repo_hook** | `github_pat_11AAALVQA0n9Un6...`                     |
| **ARGOCD_SECRET_KEY** | Used by Argo CD server for JWT signing. Generate with `openssl rand -hex 32`.                                                                                                                                                                                 | `439db941bec3bdcf...`                               |
| **ARGO_HOSTNAME**     | The external DNS name or public hostname where the Argo CD and Workflows UIs will be reachable.                                                                                                                                                               | `ec2-34-217-38-185.us-west-2.compute.amazonaws.com` |

You can persist these in your shell profile, or source a local `.env` file before running make commands.

---

## 🧩 Makefile Targets

Common developer targets (run with `make <target>`):

| Target                 | Description                                                                                                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **make install**       | Installs or upgrades the full Argo stack Helm chart (`helm/argo-stack`) into the `argocd` and `argo-events` namespaces. Uses `GITHUB_PAT`, `ARGOCD_SECRET_KEY`, and `ARGO_HOSTNAME`. |
| **make logs**          | Streams logs from Argo CD, Argo Workflows, and Argo Events pods for debugging.                                                                                                       |
| **make port-forward**  | Starts local port-forwards for Argo CD (8080→443) and Argo Workflows (2746).                                                                                                         |
| **make uninstall**     | Removes all Argo stack resources and namespaces.                                                                                                                                     |
| **make stern-install** | Installs the `stern` log-tailing utility on Linux.                                                                                                                                   |

---

## 🌐 Required Network Ports

| Port           | Service                             | Purpose                            |
| -------------- | ----------------------------------- | ---------------------------------- |
| **443 / 8080** | Argo CD server                      | Web UI and API access              |
| **2746**       | Argo Workflows server               | Workflow UI and API                |
| **12000**      | GitHub EventSource                  | GitHub → Argo Events webhook       |
| **80 / 443**   | (Optional) NGINX Ingress controller | Public ingress for external access |

If you’re running on EC2, ensure these ports are open in your instance’s security group.

---

## 🚀 Deploying the Stack

```bash
make install
```

This command wraps:

```bash
helm upgrade --install argo-stack ./helm/argo-stack \
  -n argocd --create-namespace \
  --wait --atomic \
  --set-string events.github.secret.tokenValue="${GITHUB_PAT}" \
  --set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
  --set-string events.github.webhook.ingress.enabled=true \
  --set-string events.github.webhook.ingress.className=nginx \
  --set-string events.github.webhook.ingress.hosts[0]="${ARGO_HOSTNAME}"
```

After deployment:

```bash
kubectl get pods -A | grep argo
```

All Argo pods should be in **Running** state.

---

## 🔓 Getting the Argo CD Admin Password

```bash
ARGOCD_POD=$(kubectl -n argocd get pod -l app.kubernetes.io/name=argocd-server -o name)
kubectl -n argocd exec -it ${ARGOCD_POD} -- argocd admin initial-password
```

Copy the password and log in at:

```
https://<ARGO_HOSTNAME>:8080
```

Username: **admin**
Password: *(value above)*

---

## 🧭 Accessing the UIs

### Option A — Port Forward (local testing)

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443 &
kubectl -n argo port-forward svc/argo-workflows-server 2746:2746 &
```

* **Argo CD UI:** [http://localhost:8080](http://localhost:8080)
* **Argo Workflows UI:** [http://localhost:2746](http://localhost:2746)

### Option B — Ingress (if configured)

* **Argo CD:** `https://argocd.${ARGO_HOSTNAME}`
* **Workflows:** `https://argo.${ARGO_HOSTNAME}`
* **Events Webhook:** `https://${ARGO_HOSTNAME}/events`

---

## 🔁 Testing GitHub Push → Workflow Trigger

1. Ensure the **GitHub EventSource** is running:

   ```bash
   kubectl -n argo-events get eventsource
   kubectl -n argo-events logs -l eventsource-name=github
   ```

2. Verify the webhook exists in your repository:
   **GitHub → Settings → Webhooks**

   You should see an entry pointing to:

   ```
   https://${ARGO_HOSTNAME}/events
   ```

3. Push a commit to your repository’s default branch:

   ```bash
   git commit --allow-empty -m "Trigger Argo workflow"
   git push
   ```

4. Confirm the event reached the cluster:

   ```bash
   kubectl -n argo-events logs -l eventsource-name=github | grep push
   kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push | grep trigger
   ```

5. View the triggered workflow:

   ```bash
   kubectl -n argo get wf
   ```

6. Open the Workflows UI ([http://localhost:2746](http://localhost:2746) or Ingress URL) to visualize execution.

---

## 🧹 Cleanup

```bash
make uninstall
```

This removes all Argo resources and namespaces.

---

## 🧠 Tips

* Render manifests for inspection:

  ```bash
  make template
  ```
* Debug Helm chart values:

  ```bash
  helm get values argo-stack -n argocd -a
  ```
* Tail logs for all Argo components:

  ```bash
  make logs
  ```

---

**End of README**

```

---

