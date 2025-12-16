[Home](index.md) > [Testing and Troubleshooting](index.md#5-testing-and-troubleshooting)

# 🔍 Troubleshooting Guide

This guide helps diagnose and resolve common issues when deploying and running the Argo stack with GitHub App integration.

---

## 🧪 Pre-Installation Diagnostics

### Check Environment Variables

Before deployment, validate all required variables are set:

```bash
make check-vars
```

This validates:
- S3 configuration (if enabled)
- GitHub App credentials (App ID, Client ID, Private Key path, Installation ID)
- ArgoCD secret key
- Argo hostname

**Expected output:**
```
✅ Environment validation passed.
✅ All GITHUBHAPP environment variables are set.
```

**Common errors:**

| Error | Solution |
|-------|----------|
| `S3_ACCESS_KEY_ID must be set` | Export S3 credentials: `export S3_ACCESS_KEY_ID=minioadmin` |
| `ARGOCD_SECRET_KEY is undefined` | Generate: `export ARGOCD_SECRET_KEY=$(openssl rand -hex 32)` |
| `ARGO_HOSTNAME is undefined` | Export domain: `export ARGO_HOSTNAME=argo.example.com` |
| `GITHUBHAPP_APP_ID is undefined` | Get from GitHub App settings and export |
| `GITHUBHAPP_INSTALLATION_ID is undefined` | Install GitHub App on org, capture ID from callback |
| `GITHUBHAPP_PRIVATE_KEY_FILE_PATH file not found` | Download private key from GitHub App settings, verify path |

### Verify Cluster and Tools

```bash
# Check cluster connectivity
kubectl cluster-info

# Verify required tools
command -v helm && echo "✅ helm installed"
command -v kubectl && echo "✅ kubectl installed"
command -v kind && echo "✅ kind installed"
```

---

## 🏗️ Installation Troubleshooting

### Kind Cluster Issues

**Problem:** Kind cluster creation fails

**Solution:**
```bash
# Check if Docker is running
docker ps

# Check existing kind clusters
kind get clusters

# Delete and recreate
kind delete cluster
make kind bump-limits
```

**Problem:** System limits too low

**Solution:**
```bash
# Apply system limit increases
make bump-limits

# Verify limits
make show-limits
```

### Dependency Installation Issues

**Problem:** `helm repo add` fails

**Solution:**
```bash
# Clear helm cache and retry
helm repo list
helm repo remove argo || true
helm repo remove external-secrets || true
helm repo remove minio || true
helm repo remove hashicorp || true

# Rebuild dependencies
make deps
```

**Problem:** CRD installation fails

**Solution:**
```bash
# Check if CRDs are installed
kubectl get crd | grep external-secrets

# Reinstall External Secrets Operator
make eso-cleanup
make eso-install
```

---

## 🔐 Vault Troubleshooting

### Vault Installation Issues

**Problem:** Vault pod stuck in pending state

**Solution:**
```bash
# Check pod status
kubectl describe pod -n vault vault-0

# Check node resources
kubectl top nodes

# Restart Vault
make vault-cleanup
make vault-dev
```

**Problem:** Cannot reach Vault from cluster

**Solution:**
```bash
# Verify Vault service exists
kubectl get svc -n vault

# Check Vault pod is running
kubectl get pods -n vault

# Test connectivity from a pod
kubectl run -it --rm debug --image=alpine --restart=Never -- \
  wget -O- http://vault.vault.svc.cluster.local:8200/v1/sys/health
```

### Vault Secret Management Issues

**Problem:** `make vault-seed` fails

**Solution:**
```bash
# Check Vault status
make vault-status

# View Vault logs
kubectl logs -n vault vault-0 -f

# Verify Vault is initialized
kubectl exec -n vault vault-0 -- vault status

# Re-seed if needed
make vault-cleanup
make vault-dev
make vault-auth
make vault-seed
```

**Problem:** Secret not found in Vault

**Solution:**
```bash
# List all secrets
make vault-list

# Get a specific secret
make vault-get VPATH=kv/argo/argocd/admin

# Check ExternalSecret for errors
kubectl describe externalsecret argocd-secret -n argocd

# View Vault policy
kubectl exec -n vault vault-0 -- vault policy read argo-stack
```

**Problem:** GitHub App private key not syncing to Vault

**Solution:**
```bash
# Verify file exists and is readable
test -f "${GITHUBHAPP_PRIVATE_KEY_FILE_PATH}" && echo "✅ File exists"
head -1 "${GITHUBHAPP_PRIVATE_KEY_FILE_PATH}"  # Should show "-----BEGIN RSA PRIVATE KEY-----"

# Manually seed the key
cat "${GITHUBHAPP_PRIVATE_KEY_FILE_PATH}" | kubectl exec -i -n vault vault-0 -- \
  vault kv put "${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}" privateKey=-

# Verify it was stored
kubectl exec -n vault vault-0 -- vault kv get "${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}"
```

---

## 🔑 External Secrets Operator Troubleshooting

### ESO Installation Issues

**Problem:** External Secrets Operator pods not running

**Solution:**
```bash
# Check pod status
kubectl get pods -n external-secrets-system

# Check logs
kubectl logs -n external-secrets-system -l app.kubernetes.io/name=external-secrets

# Verify CRDs are installed
kubectl get crd | grep external-secrets

# Reinstall if needed
make eso-cleanup
make eso-install
```

**Problem:** Webhook validation failures

**Solution:**
```bash
# Check webhook configuration
kubectl get validatingwebhookconfigurations

# View webhook CA certificate
kubectl get validatingwebhookconfigurations externalsecret-validate -o yaml | \
  grep -A5 clientConfig

# Restart ESO webhook
kubectl rollout restart deployment -n external-secrets-system external-secrets-webhook
```

### ExternalSecret Sync Issues

**Problem:** ExternalSecret stuck in "pending" state

**Solution:**
```bash
# Check ExternalSecret status
kubectl describe externalsecret argocd-secret -n argocd

# View full status details
kubectl get externalsecret argocd-secret -n argocd -o yaml | tail -20

# Check ESO logs for errors
kubectl logs -n external-secrets-system -l app.kubernetes.io/name=external-secrets -f --all-containers=true

# Verify SecretStore configuration
kubectl get secretstore -n argocd -o yaml
```

**Problem:** SecretStore connection fails

**Solution:**
```bash
# Verify Vault is accessible from ESO pod
kubectl exec -n external-secrets-system \
  $(kubectl get pod -n external-secrets-system -l app.kubernetes.io/name=external-secrets -o jsonpath='{.items[0].metadata.name}') -- \
  curl -k https://vault.vault.svc.cluster.local:8200/v1/sys/health

# Check Vault Kubernetes auth configuration
kubectl exec -n vault vault-0 -- vault auth list

# Verify Kubernetes auth is configured
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

# Check Vault policy for argo-stack role
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/role/argo-stack
```

**Problem:** Kubernetes secret not created after ExternalSecret syncs

**Solution:**
```bash
# Check if Kubernetes secret exists
kubectl get secret argocd-secret -n argocd

# Check if ExternalSecret is marked as Ready
kubectl get externalsecret -n argocd -o wide

# View recent events
kubectl describe externalsecret argocd-secret -n argocd | grep -A5 Events

# Check if ESO has permission to create secrets
kubectl get rolebindings -n argocd | grep external-secrets
```

---

## 🏗️ Argo CD Troubleshooting

### ArgoCD Installation Issues

**Problem:** ArgoCD pods not running

**Solution:**
```bash
# Check pod status
kubectl get pods -n argocd

# View pod descriptions for pending/failed pods
kubectl describe pod -n argocd <pod-name>

# Check resource requests vs available resources
kubectl top nodes
kubectl describe node

# Check logs
kubectl logs -n argocd deployment/argocd-server -f
```

**Problem:** ArgoCD server certificate errors

**Solution:**
```bash
# Verify TLS secret exists
kubectl get secret -n argocd | grep tls

# Check certificate validity
kubectl get secret argocd-server-tls -n argocd -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

# Recreate TLS secret if needed
kubectl delete secret argocd-server-tls -n argocd
# Then rerun make argo-stack
```

### ArgoCD Configuration Issues

**Problem:** ArgoCD password reset needed

**Solution:**
```bash
# Get default admin password
make password

# Login to ArgoCD CLI
make login

# Or manually reset password
kubectl exec -n argocd argocd-server-<pod-id> -- argocd account update-password \
  --account admin \
  --new-password <new-password>
```

**Problem:** Application status shows "OutOfSync"

**Solution:**
```bash
# Check Application status
kubectl describe application my-nextflow-project -n argocd

# Check RepoRegistration status
kubectl describe reporegistration my-nextflow-project -n argocd

# View Application controller logs
kubectl logs -n argocd deployment/argocd-application-controller -f --tail=100

# Force sync
kubectl patch application my-nextflow-project -n argocd --type merge \
  -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=true"]}}}'
```

**Problem:** Cannot access ArgoCD UI

**Solution:**
```bash
# Port forward to ArgoCD
kubectl port-forward -n argocd svc/argocd-server 8080:443 &

# Visit https://localhost:8080 (accept self-signed certificate)

# Check ingress configuration
kubectl get ingress -n argocd

# Test ingress connectivity
curl -k https://${ARGO_HOSTNAME}

# Check NGINX ingress logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx -f
```

---

## 🔔 Argo Events Troubleshooting

### EventSource Issues

**Problem:** EventSource shows "no need to create webhooks"

**Solution:**
```bash
# Check EventSource status
kubectl describe eventsource github -n argo-events

# Check EventSource logs
kubectl logs -n argo-events deployment/github-events-eventsource -f

# Verify GitHub secret exists in Vault
kubectl exec -n vault vault-0 -- vault kv get kv/argo/events/github

# Verify Kubernetes secret was created
kubectl get secret -n argo-events | grep github

# Re-trigger ExternalSecret sync
kubectl annotate externalsecret github-secret -n argo-events \
  force-sync="$(date +%s%N)" --overwrite
```

**Problem:** Webhook URL configuration issues

**Solution:**
```bash
# Check EventSource webhook configuration
kubectl get eventsource github -n argo-events -o yaml | grep -A5 webhook

# Verify ARGO_HOSTNAME is correct
echo $ARGO_HOSTNAME

# Check GitHub webhook settings
# Navigate to: GitHub Repo → Settings → Webhooks

# Manually verify webhook endpoint
curl -k https://${ARGO_HOSTNAME}/events

# Check NGINX ingress for /events route
kubectl describe ingress -n argo-events
```

### Sensor Issues

**Problem:** Sensor not triggering on webhook events

**Solution:**
```bash
# Check Sensor status
kubectl describe sensor push-sensor -n argo-events

# View recent Sensor logs
kubectl logs -n argo-events deployment/github-events-sensor -f --tail=50

# Check EventSource is ready
kubectl get eventsource -n argo-events

# Verify webhook event format matches Sensor filter
# Check GitHub webhook deliveries: Repo → Settings → Webhooks → Recent Deliveries

# Test manually by creating a Workflow
kubectl create -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: test-
  namespace: argo-workflows
spec:
  entrypoint: main
  templates:
  - name: main
    container:
      image: alpine
      command: [echo]
      args: ["test"]
EOF
```

**Problem:** Webhook deliveries failing in GitHub

**Solution:**
```bash
# Check GitHub webhook logs
# Navigate to: GitHub Repo → Settings → Webhooks → Recent Deliveries

# Verify webhook URL is accessible
curl -k https://${ARGO_HOSTNAME}/events -X POST

# Check EventSource pod logs for parsing errors
kubectl logs -n argo-events -l app=github-events-eventsource -f

# Verify firewall/network allows GitHub webhook IPs
# GitHub webhook IPs: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses
```

---

## 🚀 Argo Workflows Troubleshooting

### Workflow Submission Issues

**Problem:** Workflow submission fails with permission denied

**Solution:**
```bash
# Check service account permissions
kubectl describe serviceaccount argo-events-sa -n argo-events

# Verify RBAC role exists
kubectl describe role argo-events-workflow-submit -n argo-events

# Check role binding
kubectl describe rolebinding argo-events-workflow-submit -n argo-events

# Apply RBAC if missing
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: argo-events-workflow-submit
  namespace: argo-events
rules:
  - apiGroups: ["argoproj.io"]
    resources: ["workflows", "workflowtemplates"]
    verbs: ["get", "list", "watch", "create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: argo-events-workflow-submit
  namespace: argo-events
subjects:
  - kind: ServiceAccount
    name: argo-events-sa
    namespace: argo-events
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: argo-events-workflow-submit
EOF
```

### Workflow Execution Issues

**Problem:** Workflow pending indefinitely

**Solution:**
```bash
# Check workflow status
kubectl describe workflow <workflow-name> -n argo-workflows

# Check pod status
kubectl get pods -n argo-workflows | grep <workflow-name>

# View workflow pod logs
kubectl logs -n argo-workflows <workflow-name>-<node-id> -f

# Check resource constraints
kubectl top nodes
kubectl describe node

# Check if WorkflowTemplate exists
kubectl get workflowtemplate -n argo-workflows
```

**Problem:** Workflow fails with artifact errors

**Solution:**
```bash
# Check S3 configuration in workflow
kubectl get workflow <workflow-name> -n argo-workflows -o yaml | grep -A10 artifactRepositories

# Verify artifact bucket is accessible
kubectl run s3-test --rm -it --image=amazon/aws-cli --restart=Never -- \
  s3 ls s3://argo-artifacts --endpoint-url http://minio.minio-system.svc.cluster.local:9000

# Check S3 credentials secret
kubectl get secret -n argo-workflows -l app=argo-workflows

# View MinIO logs
kubectl logs -n minio-system -l app=minio -f
```

**Problem:** Container image not found

**Solution:**
```bash
# Check image availability in kind cluster
kind load docker-image <image>:<tag> --name kind

# Verify image exists in cluster
docker exec -it kind-control-plane crictl images | grep <image>

# Check workflow image pull policy
kubectl get workflow <workflow-name> -n argo-workflows -o yaml | grep -A3 "image:"
```

---

## 🪣 MinIO / S3 Troubleshooting

### MinIO Installation Issues

**Problem:** MinIO pod not running

**Solution:**
```bash
# Check MinIO pods
kubectl get pods -n minio-system

# Check MinIO service
kubectl get svc -n minio-system

# View MinIO logs
kubectl logs -n minio-system -l app=minio -f

# Check PVC if persistent storage enabled
kubectl get pvc -n minio-system
```

### Artifact Storage Issues

**Problem:** Cannot access MinIO bucket

**Solution:**
```bash
# List MinIO contents
make minio-ls

# Create bucket if missing
kubectl run minio-mc --rm -i --restart=Never --image=minio/mc --command -- \
  sh -c "mc alias set myminio http://minio.minio-system.svc.cluster.local:9000 minioadmin minioadmin && \
  mc mb myminio/argo-artifacts --ignore-existing"

# Test S3 credentials
kubectl run s3-test --rm -it --image=amazon/aws-cli --restart=Never -- \
  s3 ls s3://argo-artifacts \
  --endpoint-url http://minio.minio-system.svc.cluster.local:9000 \
  --region us-east-1
```

**Problem:** Artifact upload fails

**Solution:**
```bash
# Check MinIO service connectivity
kubectl run connectivity-test --rm -it --image=alpine --restart=Never -- \
  wget -O- http://minio.minio-system.svc.cluster.local:9000/minio/health/live

# Verify S3 endpoint URL in workflow
kubectl get workflow <workflow-name> -n argo-workflows -o yaml | grep -B5 -A5 endpoint

# Check MinIO pod resource usage
kubectl top pod -n minio-system -l app=minio
```

---

## 🌐 Network and Ingress Troubleshooting

### Ingress Issues

**Problem:** Cannot reach services via ingress

**Solution:**
```bash
# Check ingress resources
kubectl get ingress -n argocd
kubectl get ingress -n argo-events

# Describe ingress to check configuration
kubectl describe ingress -n argocd

# Check NGINX ingress controller
kubectl get pods -n ingress-nginx

# View NGINX logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx -f

# Test NGINX directly
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80 &
curl http://localhost:8080/events -H "Host: ${ARGO_HOSTNAME}"
```

**Problem:** TLS certificate errors

**Solution:**
```bash
# Verify TLS secret exists
kubectl get secret -n ingress-nginx | grep tls

# Check certificate details
kubectl get secret calypr-demo-tls -n ingress-nginx -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

# Test HTTPS endpoint
curl -k https://${ARGO_HOSTNAME}

# Check ingress TLS configuration
kubectl get ingress -n argocd -o yaml | grep -A10 tls
```

### DNS Resolution Issues

**Problem:** Domain name not resolving

**Solution:**
```bash
# For kind local development
# Add to /etc/hosts (macOS/Linux):
echo "127.0.0.1 ${ARGO_HOSTNAME}" | sudo tee -a /etc/hosts

# For production, ensure DNS records point to ingress IP
kubectl get ingress -n argocd -o wide
nslookup ${ARGO_HOSTNAME}
```

---

## 📊 GitHub App Troubleshooting

### GitHub App Installation Issues

**Problem:** GitHub App not appearing in organization

**Solution:**
```bash
# Verify GitHub App exists
# Visit: GitHub Settings → Developer settings → GitHub Apps

# Check if installation was successful
# URL: https://github.com/settings/installations

# Capture installation ID from callback URL
# Or view in organization settings → GitHub Apps → Installed
```

**Problem:** `GITHUBHAPP_INSTALLATION_ID` undefined

**Solution:**
```bash
# Install GitHub App on organization
# Visit: https://github.com/apps/<your-app-name>/installations/new

# After installation, capture ID from URL or settings
export GITHUBHAPP_INSTALLATION_ID=<captured-id>

# Verify it's set
echo $GITHUBHAPP_INSTALLATION_ID
```

### GitHub App Webhook Issues

**Problem:** Webhook not firing

**Solution:**
```bash
# Check GitHub webhook deliveries
# Navigate to: GitHub Repo → Settings → Webhooks → Recent Deliveries

# Verify EventSource webhook configuration
kubectl get eventsource github -n argo-events -o yaml | grep -A5 webhook

# Test webhook endpoint manually
curl -X POST \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: $(uuidgen)" \
  -d '{"ref":"refs/heads/main"}' \
  https://${ARGO_HOSTNAME}/events

# Check EventSource logs
kubectl logs -n argo-events -l app=github-events-eventsource -f
```

**Problem:** Private key not accessible to EventSource

**Solution:**
```bash
# Verify private key in Vault
kubectl exec -n vault vault-0 -- vault kv get "${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}"

# Verify Kubernetes secret created
kubectl get secret -n argo-events github-app-private-key -o yaml

# Check secret has correct data
kubectl get secret -n argo-events github-app-private-key -o jsonpath='{.data.privateKey}' | base64 -d | head -1

# Check EventSource references correct secret
kubectl get eventsource github -n argo-events -o yaml | grep -A3 "auth:"
```

---

## 🧹 Cleanup and Reset

### Partial Cleanup

```bash
# Remove only specific components
make vault-cleanup        # Remove Vault
make eso-cleanup          # Remove External Secrets Operator
make minio-cleanup        # Remove MinIO
make argo-stack clean     # Remove Argo stack charts
```

### Full Reset

```bash
# Delete entire kind cluster
kind delete cluster --name kind

# Verify cluster is gone
kind get clusters
```

### Clean Specific Namespaces

```bash
# Delete all workflows in namespace
kubectl delete workflow --all -n argo-workflows

# Delete all applications
kubectl delete application --all -n argocd

# Delete namespace
kubectl delete namespace wf-poc
```

---

## 📋 Health Check Commands

### Quick Status Check

```bash
#!/bin/bash
# Quick health check for Argo stack

echo "🔍 Argo Stack Health Check"
echo ""

echo "Cluster connectivity:"
kubectl cluster-info >/dev/null 2>&1 && echo "✅ Cluster OK" || echo "❌ Cluster unreachable"

echo ""
echo "Component status:"
kubectl get pods -n argocd -q >/dev/null 2>&1 && echo "✅ ArgoCD running" || echo "❌ ArgoCD not found"
kubectl get pods -n argo-workflows -q >/dev/null 2>&1 && echo "✅ Argo Workflows running" || echo "❌ Argo Workflows not found"
kubectl get pods -n argo-events -q >/dev/null 2>&1 && echo "✅ Argo Events running" || echo "❌ Argo Events not found"
kubectl get pods -n vault -q >/dev/null 2>&1 && echo "✅ Vault running" || echo "❌ Vault not found"
kubectl get pods -n minio-system -q >/dev/null 2>&1 && echo "✅ MinIO running" || echo "❌ MinIO not found"
kubectl get pods -n external-secrets-system -q >/dev/null 2>&1 && echo "✅ ESO running" || echo "❌ ESO not found"

echo ""
echo "Secrets status:"
kubectl get externalsecret -n argocd --no-headers 2>/dev/null | wc -l | xargs echo "ExternalSecrets in argocd:"
kubectl get externalsecret -n argo-events --no-headers 2>/dev/null | wc -l | xargs echo "ExternalSecrets in argo-events:"

echo ""
echo "✅ Health check complete"
```

---

## 🆘 Getting Help

### Collect Diagnostic Information

```bash
# Create diagnostic bundle
mkdir -p argo-diagnostics

# Cluster info
kubectl version > argo-diagnostics/k8s-version.txt
kubectl get nodes > argo-diagnostics/nodes.txt
kubectl top nodes > argo-diagnostics/node-resources.txt 2>&1

# Pod status
kubectl get pods --all-namespaces > argo-diagnostics/pods.txt

# Events
kubectl get events --all-namespaces > argo-diagnostics/events.txt

# Logs
for ns in argocd argo-workflows argo-events vault minio-system external-secrets-system; do
    mkdir -p "argo-diagnostics/$ns"
    kubectl logs -n "$ns" --all-containers=true --timestamps=true > "argo-diagnostics/$ns/logs.txt" 2>&1
done

# Create archive
tar -czf argo-diagnostics.tar.gz argo-diagnostics/
echo "Diagnostics saved to argo-diagnostics.tar.gz"
```

### Verify Configuration

```bash
# Check all environment variables
echo "ARGO_HOSTNAME: $ARGO_HOSTNAME"
echo "S3_ENABLED: $S3_ENABLED"
echo "GITHUBHAPP_APP_ID: $GITHUBHAPP_APP_ID"
echo "GITHUBHAPP_INSTALLATION_ID: $GITHUBHAPP_INSTALLATION_ID"
echo "GITHUBHAPP_PRIVATE_KEY_FILE_PATH: $GITHUBHAPP_PRIVATE_KEY_FILE_PATH"
echo "GITHUBHAPP_PRIVATE_KEY_VAULT_PATH: $GITHUBHAPP_PRIVATE_KEY_VAULT_PATH"

# Verify files exist
test -f "${GITHUBHAPP_PRIVATE_KEY_FILE_PATH}" && echo "✅ Private key file exists" || echo "❌ Private key file missing"
```

---

## 📚 Related Documentation

- [Argo CD Troubleshooting](https://argo-cd.readthedocs.io/en/stable/operator-manual/troubleshooting/)
- [Argo Workflows Troubleshooting](https://argoproj.github.io/argo-workflows/troubleshooting/)
- [Argo Events Troubleshooting](https://argoproj.github.io/argo-events/troubleshooting/)
- [External Secrets Operator Debugging](https://external-secrets.io/latest/troubleshooting/)
- [HashiCorp Vault Troubleshooting](https://www.vaultproject.io/docs/concepts/integrated-storage/autopilot#troubleshooting-outages)
- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug-application-cluster/)

---

## ✅ Common Solutions Summary

| Issue | Likely Cause | Quick Fix |
|-------|--------------|-----------|
| Pods not scheduling | Resource limits | `make bump-limits` |
| ExternalSecrets pending | Vault not ready | `make vault-dev` then `make vault-seed` |
| Webhook not firing | EventSource misconfigured | Check GitHub webhook deliveries, verify `ARGO_HOSTNAME` |
| Workflow fails | Missing S3/credentials | Check ExternalSecret status, verify Vault secrets |
| Cannot access UI | Ingress misconfigured | Verify TLS secret, check NGINX ingress logs |
| Installation timeout | Network/resource issues | Check node resources: `kubectl top nodes` |
| GitOps sync failing | Missing manifest repo | Verify ArgoCD Application configuration |

---

## 🆘 Emergency Reset

If everything seems broken, try this reset sequence:

```bash
# 1. Stop port-forwards
killall kubectl 2>/dev/null || true

# 2. Delete cluster
kind delete cluster --name kind

# 3. Clear Makefile artifacts
rm -f rendered.yaml

# 4. Start fresh
make init
make argo-stack
```

Then validate:
```bash
make check-vars
make password
kubectl -n argocd port-forward svc/argocd-server 8080:443 &
# Visit https://localhost:8080 with admin password
```
