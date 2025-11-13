# 🚀 Quick Start Guide

Choose your deployment path:

## 🏠 Local Development (5 minutes)

Perfect for testing and development with automatic MinIO deployment inside the cluster.

```bash
# Set required environment variables
export GITHUB_PAT=<your-github-token>
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)
export ARGO_HOSTNAME=<your-hostname>

# Deploy everything (Kind cluster + MinIO + Argo Stack)
make deploy

# Ports are automatically forwarded:
# - Argo Workflows: http://localhost:2746
# - Argo CD:        http://localhost:8080
# - GitHub Events:  http://localhost:12000
```

**Get ArgoCD password:**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

**Access MinIO Console (optional):**
```bash
kubectl port-forward svc/minio -n minio-system 9001:9001
# Open http://localhost:9001 (minioadmin/minioadmin)
```

**When done:**
```bash
kind delete cluster  # Remove the entire cluster
```

---

## 🌐 Production Deployment (15 minutes)

For production deployments with your own repositories and S3 storage.

### Step 1: Create Your Values File

```bash
cat > my-values.yaml <<'EOF'
# S3 Configuration
s3:
  enabled: true
  hostname: "s3.us-west-2.amazonaws.com"
  bucket: "my-argo-artifacts"
  region: "us-west-2"
  accessKey: "YOUR_ACCESS_KEY"
  secretKey: "YOUR_SECRET_KEY"

# Your Applications (REQUIRED)
applications:
  - name: my-workflow-app
    project: default
    repoURL: https://github.com/YOUR_ORG/YOUR_REPO.git  # ⚠️  Replace this
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
EOF
```

**Important:** Replace `YOUR_ORG/YOUR_REPO` with your actual repository!

### Step 2: Deploy

```bash
export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)

helm upgrade --install argo-stack ./helm/argo-stack \
  --namespace argocd --create-namespace \
  --values my-values.yaml \
  --set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
  --wait --timeout 10m
```

### Step 3: Access

```bash
kubectl -n argo-workflows port-forward svc/argo-stack-argo-workflows-server 2746:2746 &
kubectl -n argocd port-forward svc/argo-stack-argocd-server 8080:443 &
```

---

## 📚 More Information

- **Full documentation:** [README.md](README.md)
- **Development guide:** [docs/development.md](docs/development.md)
- **Configuration examples:** [examples/](examples/)
- **Per-repo artifacts:** [examples/per-repo-artifacts-values.yaml](examples/per-repo-artifacts-values.yaml)
- **User repo example:** [examples/user-repos-example.yaml](examples/user-repos-example.yaml)

---

## ❓ Common Questions

**Q: Can I deploy without any applications?**  
A: Yes! The chart will deploy Argo Workflows and Argo CD without any applications. You can add applications later through the Argo CD UI or by updating your values.

**Q: Where do I put my GitHub repository URLs?**  
A: Create a values file (like `my-values.yaml`) with your repositories in the `applications` array. Never commit credentials or private repo URLs to version control.

**Q: How do I use MinIO with Kubernetes in Kind/Minikube?**  
A: Use `make deploy` which automatically sets up MinIO inside the cluster. See [docs/development.md](docs/development.md#local-minio-for-development) for details.

**Q: What about GitHub Events/webhooks?**  
A: Configure the `events.github.repositories` section in your values file. See [examples/user-repos-example.yaml](examples/user-repos-example.yaml) for an example.

---

## 🆘 Getting Help

- **Check logs:** `kubectl logs -n argo-workflows -l app.kubernetes.io/name=argo-workflows-server`
- **MinIO logs:** `kubectl logs -n minio-system -l app=minio`
- **Issues:** [GitHub Issues](https://github.com/calypr/argo-helm/issues)
