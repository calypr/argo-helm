[Home](index.md) > [Testing and Troubleshooting](index.md#5-testing-and-troubleshooting)

# 🔧 Argo Stack Troubleshooting Guide

**Document Purpose:**  
This comprehensive guide helps users troubleshoot common issues across the Argo Stack, including GitHub integration, Argo Events, Argo Workflows, and infrastructure components.

**Audience:**  
Data managers, developers, and platform administrators using the Argo Stack for Git-integrated workflow automation.

---

## Table of Contents

- [General Troubleshooting](#general-troubleshooting)
- [Ingress and Connectivity Troubleshooting](#ingress-and-connectivity-troubleshooting)
- [Environment-Specific Ingress Configuration](#environment-specific-ingress-configuration)
  - [AWS EKS Configuration](#aws-eks-configuration)
  - [On-Premises / Bare Metal Configuration](#on-premises--bare-metal-configuration)
- [Workflow Troubleshooting](#workflow-troubleshooting)
- [Argo Events Issues](#argo-events-issues)
- [Secret and Vault Issues](#secret-and-vault-issues)
- [Common Commands Cheat Sheet](#common-commands-cheat-sheet)

---

## General Troubleshooting

### Issue: Argo Events CRDs Not Found

**Error:**
```
argo-workflows-server shows the following error at /event-sources/ 
"Not Found: the server could not find the requested resource (get eventsources.argoproj.io)"
```

**Cause:** The **Argo Events CRDs aren't installed** (or the argo-server RBAC can't read them). `eventsources.argoproj.io` is a CRD from **Argo Events**, not Argo Workflows.

**Solution:**

#### 1. Verify the CRD is missing

```bash
kubectl get crd | grep eventsources
kubectl api-resources | grep -E 'eventsources|sensors|eventbus'
```

If nothing returns, you need Argo Events.

#### 2. Install Argo Events (CRDs + controllers)

Using Helm (recommended):

```bash
# once per cluster
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# create ns
kubectl create ns argo-events || true

# install Argo Events and its CRDs
helm upgrade --install argo-events argo/argo-events \
  -n argo-events \
  --set crds.install=true
```

Or with manifests (if you're not using Helm), apply the Argo Events CRDs and controllers for your version/cluster.

#### 3. Create a basic EventBus (required by Events)

```bash
cat <<'YAML' | kubectl apply -n argo-events -f -
apiVersion: argoproj.io/v1alpha1
kind: EventBus
metadata:
  name: default
spec:
  nats: {}   # default NATS; fine for dev
YAML
```

#### 4. (If needed) RBAC so argo-server can list Events resources

If the CRDs exist but you still get 404 in the UI, give the argo-server's SA read access:

```bash
cat <<'YAML' | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argo-server-argo-events-read
rules:
- apiGroups: ["argoproj.io"]
  resources: ["eventsources", "sensors", "eventbus"]
  verbs: ["get","list","watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argo-server-argo-events-read
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argo-server-argo-events-read
subjects:
- kind: ServiceAccount
  name: argo-stack-argo-workflows-server   # adjust to your SA name
  namespace: default                       # adjust to your namespace
YAML
```

#### 5. Recheck

```bash
kubectl get eventsources -A
# then hit /event-sources again, or port-forward the server and refresh
```

**Summary:** `/event-sources` is an Argo Events view. Install **Argo Events (CRDs + controller + EventBus)** and ensure **RBAC** allows argo-server to read them; the 404 will go away.

---

## Ingress and Connectivity Troubleshooting

### Issue: Connection Refused on Port 443

**Error:**
```
curl: (7) Failed to connect to calypr-demo.ddns.net port 443 after 2 ms: Could not connect to server
```

**Cause:** The NGINX Ingress Controller is not accessible. This can happen for several reasons:
- Ingress Controller is not running
- LoadBalancer service has no external IP
- Firewall/Security Group blocking port 443
- Wrong ingress class configured

**Solution - Step-by-Step Debugging:**

#### 1. Check NGINX Ingress Controller Status

```bash
# Check if ingress-nginx pods are running
kubectl get pods -n ingress-nginx

# Check ingress-nginx service and external IP
kubectl get svc -n ingress-nginx

# Expected output should show EXTERNAL-IP (not <pending>)
# NAME                                 TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)
# ingress-nginx-controller             LoadBalancer   10.100.x.x      <public-ip>     80:30080/TCP,443:30443/TCP
```

If `EXTERNAL-IP` shows `<pending>`, the LoadBalancer hasn't been provisioned:

```bash
# Check events for the service
kubectl describe svc ingress-nginx-controller -n ingress-nginx

# Check cloud provider logs for LoadBalancer issues
```

#### 2. Verify Ingress Controller is Installed

```bash
# Check if ingress-nginx namespace exists
kubectl get ns ingress-nginx

# If not installed, install with:
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace
```

#### 3. Check Ingress Resources

```bash
# List all ingress resources in relevant namespaces
kubectl get ingress -A

# Describe a specific ingress to check configuration
kubectl describe ingress ingress-authz-workflows -n argo-stack
```

Look for:
- Correct host matching your domain
- IngressClass set correctly (usually `nginx`)
- TLS secret exists
- Backend service exists

#### 4. Verify TLS Certificate

```bash
# Check if certificate is ready
kubectl get certificate -n argo-stack

# Check certificate status
kubectl describe certificate calypr-demo-tls -n argo-stack

# Check if TLS secret exists
kubectl get secret calypr-demo-tls -n argo-stack
```

#### 5. Check Ingress Controller Logs

```bash
# View ingress controller logs for errors
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100

# Look for errors related to:
# - Certificate loading
# - Backend connection
# - Configuration reloads
```

#### 6. Verify Network Connectivity

```bash
# Test from inside the cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server.argo-stack:2746/

# Test the ingress controller service directly
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://ingress-nginx-controller.ingress-nginx:80/
```

#### 7. Check Security Groups / Firewalls (Cloud-specific)

**AWS:**
```bash
# Check the LoadBalancer security group allows inbound 443
aws ec2 describe-security-groups --group-ids <sg-id>
```

**GCP:**
```bash
# Check firewall rules
gcloud compute firewall-rules list --filter="name~ingress"
```

**Azure:**
```bash
# Check network security group
az network nsg rule list --resource-group <rg> --nsg-name <nsg-name>
```

### Issue: 404 Not Found on Ingress Paths

**Error:**
```
{"level":"error","ts":...,"msg":"route not found"...}
```

**Cause:** The ingress path doesn't match any backend or the service doesn't exist.

**Solution:**

1. Verify backend service exists:
```bash
kubectl get svc -n argo-stack argo-stack-argo-workflows-server
```

2. Check ingress path configuration matches service expectations
3. Verify the service ports match ingress configuration

### Issue: 503 Service Unavailable

**Error:**
```
HTTP/1.1 503 Service Temporarily Unavailable
```

**Cause:** Backend service has no healthy endpoints.

**Solution:**

```bash
# Check endpoints for the service
kubectl get endpoints argo-stack-argo-workflows-server -n argo-stack

# Check backend pods are running
kubectl get pods -n argo-stack -l app.kubernetes.io/name=argo-workflows-server

# Check pod health
kubectl describe pod <pod-name> -n argo-stack
```

### Issue: authz-adapter External Auth Failure

**Error:**
```
auth-url: http://authz-adapter.security.svc.cluster.local:8080/check failed
```

**Cause:** The authz-adapter service is not responding.

**Solution:**

```bash
# Check authz-adapter is running
kubectl get pods -n security -l app=authz-adapter

# Check authz-adapter service exists
kubectl get svc authz-adapter -n security

# Test authz-adapter from within cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://authz-adapter.security:8080/healthz

# Check authz-adapter logs
kubectl logs -n security -l app=authz-adapter --tail=100
```

### Ingress Debugging Cheat Sheet

| Check | Command |
|-------|---------|
| Ingress controller pods | `kubectl get pods -n ingress-nginx` |
| Ingress controller service | `kubectl get svc -n ingress-nginx` |
| All ingress resources | `kubectl get ingress -A` |
| Ingress details | `kubectl describe ingress <name> -n <ns>` |
| TLS certificates | `kubectl get certificate -A` |
| Certificate status | `kubectl describe certificate <name> -n <ns>` |
| Controller logs | `kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx` |
| authz-adapter status | `kubectl get pods -n security -l app=authz-adapter` |
| Test internal connectivity | `kubectl run debug --image=curlimages/curl --rm -it -- curl -v <url>` |

---

## Environment-Specific Ingress Configuration

This section covers ingress setup and troubleshooting for different deployment environments.

### AWS EKS Configuration

#### Prerequisites for AWS EKS

1. **AWS Load Balancer Controller** (recommended) or use the default in-tree cloud provider
2. **IAM permissions** for creating/managing Elastic Load Balancers
3. **Subnet tags** for automatic subnet discovery

#### Installing NGINX Ingress on AWS EKS

```bash
# Add the ingress-nginx repository
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install with AWS-specific settings
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-scheme"=internet-facing
```

#### AWS-Specific Annotations

For Network Load Balancer (NLB) - recommended for production:
```yaml
service:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    # For internal-only access:
    # service.beta.kubernetes.io/aws-load-balancer-scheme: internal
```

For Application Load Balancer (ALB) - requires AWS Load Balancer Controller:

⚠️ **Note:** When using ALB with the AWS Load Balancer Controller, you configure the Ingress resource (not the Service). The Service should use `ClusterIP` or `NodePort` type.

```yaml
# Ingress annotations for ALB (on the Ingress resource, not Service):
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
```

#### Troubleshooting AWS LoadBalancer Pending

If `EXTERNAL-IP` stays `<pending>`:

1. **Check service events:**
```bash
kubectl describe svc ingress-nginx-controller -n ingress-nginx
```

Look for events like:
- `Error syncing load balancer` - IAM permission issues
- `could not find any suitable subnets` - subnet tagging issues

2. **Verify IAM permissions:**

The node IAM role or service account needs these permissions:
```json
{
  "Effect": "Allow",
  "Action": [
    "elasticloadbalancing:CreateLoadBalancer",
    "elasticloadbalancing:DeleteLoadBalancer",
    "elasticloadbalancing:DescribeLoadBalancers",
    "elasticloadbalancing:ModifyLoadBalancerAttributes",
    "elasticloadbalancing:CreateTargetGroup",
    "elasticloadbalancing:DeleteTargetGroup",
    "elasticloadbalancing:DescribeTargetGroups",
    "elasticloadbalancing:RegisterTargets",
    "elasticloadbalancing:DeregisterTargets",
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeSubnets",
    "ec2:DescribeVpcs",
    "ec2:CreateSecurityGroup",
    "ec2:AuthorizeSecurityGroupIngress"
  ],
  "Resource": "*"
}
```

3. **Check subnet tags:**

Public subnets need this tag for internet-facing LBs:
```
kubernetes.io/role/elb = 1
```

Private subnets need this tag for internal LBs:
```
kubernetes.io/role/internal-elb = 1
```

4. **Verify cluster tag on subnets:**
```
kubernetes.io/cluster/<cluster-name> = shared (or owned)
```

5. **Check AWS Load Balancer Controller (if using ALB):**
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

#### AWS Security Group Configuration

After LoadBalancer is created, verify security group allows traffic:

```bash
# Get the LoadBalancer DNS name
LB_DNS=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo $LB_DNS

# Find associated security group (from AWS Console or CLI)
# Replace the DNS name in the query with your actual LoadBalancer DNS
aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='${LB_DNS}'].SecurityGroups"

# Verify inbound rules allow 80 and 443
aws ec2 describe-security-groups --group-ids <sg-id> --query "SecurityGroups[].IpPermissions"
```

Required inbound rules:
- Port 80 (HTTP) from 0.0.0.0/0 (or your IP range)
- Port 443 (HTTPS) from 0.0.0.0/0 (or your IP range)

---

### On-Premises / Bare Metal Configuration

#### Option 1: MetalLB (Recommended for On-Premises)

MetalLB provides LoadBalancer functionality for bare metal clusters.

**Install MetalLB:**
```bash
# Install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# Wait for MetalLB pods to be ready
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=90s
```

**Configure IP Address Pool:**
```bash
cat <<'YAML' | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.240-192.168.1.250  # Adjust to your available IP range
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
spec:
  ipAddressPools:
  - default-pool
YAML
```

**Then install NGINX Ingress with LoadBalancer:**
```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer
```

#### Option 2: NodePort (Simple, No External Dependencies)

Use NodePort when you don't have a LoadBalancer solution:

```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30080 \
  --set controller.service.nodePorts.https=30443
```

Access via any node IP on the configured ports:
```bash
# Get node IPs
kubectl get nodes -o wide

# Access ingress
curl http://<node-ip>:30080/
curl -k https://<node-ip>:30443/
```

**To use standard ports (80/443)**, set up an external load balancer or reverse proxy (HAProxy, NGINX) pointing to the NodePorts.

#### Option 3: HostNetwork (Direct Node Access)

For single-node clusters or when you need direct port 80/443 access:

```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.hostNetwork=true \
  --set controller.service.type=ClusterIP \
  --set controller.kind=DaemonSet
```

Access directly via node IP on ports 80 and 443.

⚠️ **Note:** Only one ingress controller pod can run per node with hostNetwork.

#### Troubleshooting On-Premises Ingress

1. **MetalLB not assigning IPs:**
```bash
# Check MetalLB speaker pods
kubectl get pods -n metallb-system

# Check MetalLB logs
kubectl logs -n metallb-system -l component=speaker

# Verify IPAddressPool is configured
kubectl get ipaddresspool -n metallb-system
```

2. **NodePort not accessible:**
```bash
# Verify service has NodePort assigned
kubectl get svc ingress-nginx-controller -n ingress-nginx

# Check if port is open on the node
nc -zv <node-ip> 30443

# Check firewall (iptables/firewalld)
sudo iptables -L -n | grep 30443
sudo firewall-cmd --list-ports
```

3. **Network connectivity from external:**
```bash
# Test from external machine
telnet <node-ip> 30443

# Check if traffic reaches the node
sudo tcpdump -i any port 30443
```

4. **Firewall configuration (if using firewalld):**
```bash
# Option 1: Allow only the specific ports you're using (recommended for security)
sudo firewall-cmd --permanent --add-port=30080/tcp  # HTTP NodePort
sudo firewall-cmd --permanent --add-port=30443/tcp  # HTTPS NodePort
sudo firewall-cmd --reload

# Option 2: Allow entire NodePort range (less secure, but convenient for development)
# sudo firewall-cmd --permanent --add-port=30000-32767/tcp
# sudo firewall-cmd --reload
```

---

### Environment Comparison Quick Reference

| Feature | AWS EKS | On-Premises (MetalLB) | On-Premises (NodePort) |
|---------|---------|----------------------|------------------------|
| LoadBalancer type | NLB/ALB | L2/BGP | N/A |
| External IP | Automatic | From IP pool | Node IP + port |
| Standard ports (80/443) | ✅ Yes | ✅ Yes | ❌ No (30000-32767) |
| TLS termination | Ingress or ALB | Ingress | Ingress |
| Health checks | AWS-managed | MetalLB | Manual |
| HA setup | Multi-AZ | Multiple speakers | External LB needed |
| Setup complexity | Medium | Medium | Low |

---

## Workflow Troubleshooting

### 🧭 Overview

When you push to your Git repository, a webhook (managed by GitHub or Argo Events) should:
1. Deliver an event to **Argo Events**
2. Trigger a **Sensor**
3. Submit a **Workflow** in **Argo Workflows**
4. Run the desired pipeline (e.g., Nextflow) and store results in your assigned S3 bucket

If any link in that chain breaks, use this section to isolate and fix it.

---

### ✅ Step 1. Check Webhook Delivery in GitHub

1. Go to your repository → **Settings → Webhooks**
2. Click your webhook (e.g., `/events` endpoint)
3. Check **Recent Deliveries**:
   - **✅ Success:** Status code `200` or `202`  
   - **⚠️ Failure:** Any 4xx/5xx — click "Response" to inspect the error body

#### Common causes

| Error | Meaning | Fix |
|-------|----------|-----|
| `404 Not Found` | EventSource service not reachable | Check ingress host/path and EventSource name |
| `401 Unauthorized` | HMAC or PAT mismatch | Confirm webhook secret matches K8s Secret in Argo Events |
| `timeout` | Ingress blocked / DNS issue | Check cluster ingress and firewall rules |
| `SSL error` | Self-signed certificate | Verify TLS setup or disable webhook SSL verification (temporary) |

---

### ✅ Step 2. Confirm Argo Events Received the Event

Run:
```bash
kubectl -n argo-events get eventsource github -o yaml | yq '.status'
kubectl -n argo-events get sensor run-nextflow-on-push -o yaml | yq '.status'
```

#### Logs
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
- Ensure both **EventSource** and **Sensor** have status `Deployed`
- Restart the EventSource pod:
  ```bash
  kubectl -n argo-events rollout restart deployment github-eventsource
  ```

---

### ✅ Step 3. Verify Workflow Creation

Watch the chain:

```bash
# Argo Events (ingest + trigger)
kubectl -n argo-events logs -l eventsource-name=github --tail=200 -f
kubectl -n argo-events logs -l sensor-name=run-nextflow-on-push --tail=200 -f
# Argo Workflows (submission + logs)
argo -n <workflow-namespace> list
argo -n <workflow-namespace> get @latest
argo -n <workflow-namespace> logs @latest --follow
```

#### Check Sensor Permissions

The Sensor may lack permission to create Workflows in the target namespace:

```bash
# What SA is the sensor pod using?
kubectl -n argo-events get pod -l sensor-name=run-nextflow-on-push -o jsonpath='{.items[0].spec.serviceAccountName}{"\n"}'

# Can that SA create workflows in wf-poc?
kubectl -n wf-poc auth can-i create workflows --as=system:serviceaccount:argo-events:<SENSOR_SA>
```

The Argo Events → Argo Workflows bridge requires two capabilities:

* get workflowtemplates — to read the referenced template
* create workflows — to instantiate it

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

#### List Workflows

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

### ✅ Step 4. Check Workflow Status

#### Common Phases

| Phase | Meaning |
|--------|----------|
| `Running` | Workflow is active |
| `Succeeded` | Completed successfully |
| `Failed` | One or more tasks failed |
| `Error` | Infrastructure or submission issue |
| `Omitted` | Step skipped by condition |

#### Inspect a workflow
```bash
argo -n argo get <workflow-name>
argo -n argo logs <workflow-name> --follow
```

---

### 🧩 Step 5. If No Workflow Was Created

Check RBAC and template references.

#### Verify the Sensor's permissions
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

#### Verify the WorkflowTemplate
```bash
kubectl -n argo get workflowtemplate nextflow-hello-template
```
If missing, reapply the workflow template YAML.

---

### ✅ Step 6. Troubleshoot Workflow Failures

```bash
argo -n argo get @latest
argo -n argo logs @latest --follow
```

#### Common causes

| Symptom | Likely issue | Fix |
|----------|---------------|----|
| `ImagePullBackOff` | Container image not accessible | Verify image and credentials |
| `S3 upload failed` | Bad bucket/keys or missing IRSA | Check artifact repository configuration |
| `Permission denied` | ServiceAccount lacks permissions | Check RoleBinding for workflow executor |
| `Nextflow missing` | Wrong container or entrypoint | Confirm `entrypoint` and image in WorkflowTemplate |

---

### 🪣 Step 7. Validate Artifact Storage

Each application can use its own S3 bucket and key prefix for tenant isolation and traceability.

#### Per-Repository Artifact Configuration

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

#### Migration from Global to Per-Repository Artifacts

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

### ✅ Step 8. Verify in the UI

#### Argo Workflows UI
- Visit: `https://<argo-host>/workflows/<namespace>`
- Use the filter by label:
  ```
  git.repo = bwalsh/nextflow-hello-project
  git.sha = <commit-sha>
  ```

#### Expected
- The workflow matching your commit appears
- Status = `Succeeded`
- Logs and artifacts are accessible

---

## Argo Events Issues

### Issue: EventBus Not Ready

**Error:**
```
argo-events controller-manager: "eventbus not ready"
```

**Cause:** The EventBus resource hasn't been created or isn't healthy.

**Solution:**

1. Check EventBus status:
```bash
kubectl get eventbus -n argo-events
kubectl describe eventbus default -n argo-events
```

2. Create EventBus if missing:
```bash
cat <<'YAML' | kubectl apply -n argo-events -f -
apiVersion: argoproj.io/v1alpha1
kind: EventBus
metadata:
  name: default
spec:
  nats: {}
YAML
```

3. Wait for EventBus to be ready:
```bash
kubectl wait --for=condition=Ready eventbus/default -n argo-events --timeout=120s
```

### Issue: EventSource Service Not Found

**Error:**
```
Error from server (NotFound): services "github-eventsource-svc" not found
```

**Cause:** EventSource deployment hasn't created the service yet, or EventSource is misconfigured.

**Solution:**

1. Check EventSource status:
```bash
kubectl get eventsource -n argo-events
kubectl describe eventsource github-repo-registrations -n argo-events
```

2. Check EventSource pod logs:
```bash
kubectl logs -n argo-events -l eventsource-name=github-repo-registrations
```

3. Verify EventSource has correct service configuration
4. Restart EventSource if needed:
```bash
kubectl delete pod -n argo-events -l eventsource-name=github-repo-registrations
```

### Issue: Sensor Has No Event Dependencies

**Error:**
```
argo-events sensor controller: "no event dependencies found"
```

**Cause:** The Sensor's `dependencies` field is empty or incorrectly configured.

**Solution:**

1. Check Sensor configuration:
```bash
kubectl get sensor run-nextflow-on-push -n argo-events -o yaml
```

2. Ensure `spec.dependencies` lists the correct EventSource events
3. Example fix:
```yaml
spec:
  dependencies:
    - name: repo_push-myrepo
      eventSourceName: github-repo-registrations
      eventName: myrepo
```

---

## Secret and Vault Issues

For detailed Vault troubleshooting, see [Vault Guide - Troubleshooting Section](secrets-with-vault.md#-troubleshooting).

### Quick Checks

1. **ExternalSecret not syncing:**
```bash
kubectl describe externalsecret <name> -n <namespace>
kubectl logs -l app.kubernetes.io/name=external-secrets -n external-secrets-system
```

2. **Vault connectivity:**
```bash
kubectl run -it --rm debug --image=curlimages/curl -- curl -v http://vault.vault.svc.cluster.local:8200/v1/sys/health
```

3. **Check secret exists in Vault:**
```bash
kubectl exec -n vault vault-0 -- vault kv get kv/argo/path/to/secret
```

---

## 🔎 Common Commands Cheat Sheet

| Action | Command |
|--------|----------|
| List workflows | `argo -n argo list` |
| Follow logs | `argo -n argo logs @latest --follow` |
| Watch events | `stern -n argo-events 'eventsource\|sensor'` |
| Check webhook ingress | `kubectl -n argo-events get ingress` |
| Get sensor status | `kubectl -n argo-events get sensor run-nextflow-on-push -o yaml \| yq '.status'` |
| Describe workflow | `kubectl -n argo describe wf @latest` |
| Cleanup test runs | `argo -n argo delete --completed --older 1d` |
| Check ExternalSecrets | `kubectl get externalsecrets -A` |
| View Vault secrets | `kubectl exec -n vault vault-0 -- vault kv list kv/argo` |
| Test RBAC | `kubectl auth can-i create workflows --as=system:serviceaccount:argo-events:default -n argo` |

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
1. GitHub webhook → status `200`
2. `argo-events` logs show event processed
3. A new workflow appears:
   ```bash
   argo -n argo list
   ```
4. The workflow runs to `Succeeded`
5. Artifacts appear in your configured S3 bucket and prefix

---

## 📚 Additional Resources

- [User Guide](user-guide.md)
- [Vault Integration Guide](secrets-with-vault.md)
- [Admin Guide](admin-guide.md)
- [Development Guide](development.md)
- [Testing Guide](testing.md)

---

**Document Version:** 2025-11-24  
**Maintainer:** Platform / Data Workflow Team
