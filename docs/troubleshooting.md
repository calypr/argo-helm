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

### Issue: Connection Refused but Internal Services Work

**Symptoms:**
Internal cluster connectivity works perfectly, but external access fails:

```bash
# ✅ Internal service access works:
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server.argo-workflows:2746/
# Returns 200 OK with HTML content

# ✅ ExternalName proxy also works:
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server-proxy.argo-stack:2746/
# Returns 200 OK

# ❌ But external access fails:
curl https://calypr-demo.ddns.net/workflows
# curl: (7) Failed to connect to calypr-demo.ddns.net port 443 after 2 ms: Could not connect to server
```

**Cause:** This "Connection refused" error at the network level means the **ingress-nginx controller's LoadBalancer service** is not exposing ports to the external network. This is distinct from a 404 error (which would mean the ingress is reachable but routing is misconfigured).

Common causes:
- LoadBalancer service is pending (no external IP provisioned)
- NodePort is not exposed in firewall/security groups
- DNS is not pointing to the correct IP
- Cloud provider LoadBalancer controller is not configured

**Solution - Step-by-Step Diagnosis:**

#### 1. Check the ingress-nginx LoadBalancer Service

```bash
# Check the service type and external IP
kubectl get svc -n ingress-nginx

# Expected output for LoadBalancer type:
# NAME                       TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)
# ingress-nginx-controller   LoadBalancer   10.100.x.x      <public-ip>     80:30080/TCP,443:30443/TCP

# Expected output for NodePort type:
# NAME                       TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)
# ingress-nginx-controller   NodePort       10.100.x.x      <none>          80:30080/TCP,443:30443/TCP
```

#### 2. If EXTERNAL-IP is `<pending>`

This means the cloud LoadBalancer hasn't been provisioned:

```bash
# Check service events for errors
kubectl describe svc ingress-nginx-controller -n ingress-nginx

# Common causes:
# - AWS Load Balancer Controller not installed (EKS)
# - Insufficient IAM permissions for LB creation
# - Subnet/VPC configuration issues
# - Quota exceeded for load balancers
```

**For AWS EKS:** See [Troubleshooting AWS LoadBalancer Pending](#troubleshooting-aws-loadbalancer-pending) for detailed AWS-specific steps including IAM permissions, subnet tagging, and AWS Load Balancer Controller setup.

Quick check:
```bash
# Check if AWS Load Balancer Controller is installed
kubectl get deployment -n kube-system aws-load-balancer-controller

# If not installed, the Kubernetes service will stay in <pending>
```

**For bare metal / on-premises clusters:**

LoadBalancer type won't work without a load balancer controller. Options:
- Use MetalLB: https://metallb.universe.tf/
- Switch to NodePort and configure external LB manually
- Use HostPort on specific nodes

#### 3. If using NodePort, check external access

```bash
# Get the NodePort for port 443
kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.spec.ports[?(@.port==443)].nodePort}'
# Example output: 30443

# Get node external IP
kubectl get nodes -o wide
# Note the EXTERNAL-IP of your nodes

# Verify firewall allows traffic on the NodePort
# Then test: curl https://<node-external-ip>:<nodeport>/
```

#### 4. Verify DNS Resolution

```bash
# Check that your domain resolves to the correct IP
nslookup calypr-demo.ddns.net

# This should return the LoadBalancer external IP or Node external IP
# If it returns an incorrect IP, update your DNS
```

#### 5. Test Direct Access to the LoadBalancer IP

```bash
# Get the LoadBalancer IP
LB_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "LoadBalancer IP: $LB_IP"

# If AWS NLB (uses hostname instead of IP):
LB_HOSTNAME=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "LoadBalancer Hostname: $LB_HOSTNAME"

# Test direct access
curl -v -k https://$LB_IP/workflows

# If this works but your domain doesn't, the issue is DNS
```

#### 6. AWS-Specific: Check Security Groups

See [AWS Security Group Configuration](#aws-security-group-configuration) for detailed security group verification.

The LoadBalancer security group must allow:
- Inbound 443 from 0.0.0.0/0 (or your IP range)
- Inbound 80 from 0.0.0.0/0 (for HTTP-01 ACME challenges)

#### 7. Verify ingress-nginx Controller is Healthy

```bash
# Check pods are running
kubectl get pods -n ingress-nginx

# Check controller logs for errors
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50

# Look for:
# - "successfully synced" messages (good)
# - Error loading certificate (TLS issue)
# - Backend connection errors
```

#### 8. kind Cluster Specific Issues

If you're using **kind** (Kubernetes IN Docker), the networking works differently:

**Problem:** MetalLB's external IP only exists inside the Docker network, not accessible from your host machine.

**Solution for kind:**

1. **Access via localhost** using the port mappings defined in your kind config:
```bash
# If you configured extraPortMappings for ports 80/443
curl -k https://localhost/workflows

# Update /etc/hosts to use localhost for your domain
echo "127.0.0.1 calypr-demo.ddns.net" | sudo tee -a /etc/hosts
curl -k https://calypr-demo.ddns.net/workflows
```

2. **Use NodePort instead of LoadBalancer** with kind:
```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  kubeProxyMode: "iptables"
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080  # NodePort for HTTP
    hostPort: 80
  - containerPort: 30443  # NodePort for HTTPS
    hostPort: 443
```

Then patch the ingress-nginx service:
```bash
kubectl patch svc ingress-nginx-controller -n ingress-nginx -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":80,"nodePort":30080},{"name":"https","port":443,"nodePort":30443}]}}'
```

3. **Check iptables rules inside the kind container** (not on host):
```bash
# Rules exist inside the kind node container, not on the host
docker exec -it kind-control-plane bash

# Inside the container
iptables-save | grep KUBE-SERVICES
iptables-save | grep ingress-nginx
```

4. **Let's Encrypt certificates won't work in kind** - use self-signed certs instead:

kind clusters aren't accessible from the internet, so Let's Encrypt HTTP-01 challenges will fail. You'll see "Kubernetes Ingress Controller Fake Certificate" in your browser.

**Solution - Use self-signed certificates for kind:**

```bash
# Create a self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=calypr-demo.ddns.net/O=calypr-demo"

# Create the TLS secret
kubectl create secret tls calypr-demo-tls \
  -n argo-stack \
  --cert=tls.crt \
  --key=tls.key

# Delete the Certificate resource (stop cert-manager from managing it)
kubectl delete certificate calypr-demo-tls -n argo-stack

# Remove cert-manager annotation from ingress
kubectl annotate ingress ingress-authz-workflows -n argo-stack cert-manager.io/cluster-issuer-
```

Your browser will show a security warning (expected for self-signed certs), but you can proceed.

---

### Issue: kube-proxy Not Creating iptables/nftables Rules

**Symptoms:**
- NodePort connections fail (Connection refused)
- Testing `curl localhost:<nodeport>` fails
- No KUBE-* chains in iptables/nftables output

**Cause:** kube-proxy is configured for iptables mode but the system uses nftables, and no rules are being created.

**Diagnosis:**

1. **Check if kube-proxy rules exist:**
```bash
# On systems using iptables-nft backend
sudo nft list ruleset | grep KUBE-SERVICES

# On systems using iptables-legacy
sudo iptables-save | grep KUBE-SERVICES

# If you get "incompatible, use 'nft' tool" error:
# Your system uses nftables but you're trying to use iptables commands
```

2. **Verify which iptables backend is active:**
```bash
sudo update-alternatives --display iptables
# Look for: link currently points to /usr/sbin/iptables-nft
```

3. **Check kube-proxy configuration:**
```bash
kubectl get cm kube-proxy -n kube-system -o yaml | grep "mode:"
# Should show: mode: iptables or mode: nft
```

**Solution:**

**For kind clusters:**
- kube-proxy runs inside the kind container
- Check rules from inside: `docker exec -it kind-control-plane iptables-save`
- The host's iptables/nftables are separate from the kind node's

**For bare metal/VM clusters with nftables:**

If your system uses iptables-nft and kube-proxy shows "Using iptables Proxier" but creates no rules:

1. **Verify kube-proxy mode in ConfigMap:**
```bash
kubectl edit cm kube-proxy -n kube-system
```

Ensure `mode: iptables` is set (it should work with iptables-nft).

2. **Restart kube-proxy:**
```bash
kubectl delete pod -n kube-system -l k8s-app=kube-proxy
```

3. **Verify rules are created:**
```bash
# Wait 30 seconds, then check
sudo nft list ruleset | grep KUBE-SERVICES
```

4. **If still no rules, check kube-proxy logs:**
```bash
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=100
# Look for errors about iptables/nftables initialization
```

---

### Issue: Let's Encrypt Certificate Not Issuing (Fake Certificate Shown)

**Symptoms:**
- Browser shows "Kubernetes Ingress Controller Fake Certificate"
- Certificate status shows `Ready: False` with reason `DoesNotExist`
- CertificateRequest or Challenge resources stuck in pending state

**Diagnosis:**

1. **Check Certificate status:**
```bash
kubectl describe certificate calypr-demo-tls -n argo-stack

# Look for conditions showing why it's not ready
# Common reasons: DoesNotExist, Pending, Failed
```

2. **Check CertificateRequest:**
```bash
kubectl get certificaterequest -n argo-stack
kubectl describe certificaterequest <name> -n argo-stack

# Check for failure reasons
```

3. **Check ACME Challenge (for Let's Encrypt):**
```bash
kubectl get challenges -A
kubectl describe challenge <name> -n argo-stack

# Look for HTTP-01 or DNS-01 challenge status
```

4. **Check cert-manager logs:**
```bash
kubectl logs -n cert-manager -l app=cert-manager --tail=100
kubectl logs -n cert-manager -l app=webhook --tail=100
```

**Common Causes and Solutions:**

#### Cause 1: Domain Not Accessible from Internet (kind/local clusters)

**For kind or local development clusters**, Let's Encrypt cannot reach your domain to verify ownership via HTTP-01 challenge.

**Solution:** Use self-signed certificates (see [kind Cluster Specific Issues](#8-kind-cluster-specific-issues) section).

#### Cause 2: HTTP-01 Challenge Fails - Port 80 Not Reachable

Let's Encrypt needs to reach `http://your-domain/.well-known/acme-challenge/` on port 80.

**Check:**
```bash
# Verify ingress responds on port 80
curl -v http://calypr-demo.ddns.net/.well-known/acme-challenge/test

# Check if port 80 is open in firewall/security groups
# AWS: Check security group allows inbound port 80 from 0.0.0.0/0
# On-prem: Check firewall allows port 80 from Let's Encrypt IPs
```

**Solution:**
```bash
# Ensure LoadBalancer/NodePort exposes port 80
kubectl get svc ingress-nginx-controller -n ingress-nginx

# Should show: 80:xxxxx/TCP in PORT(S) column
```

#### Cause 3: Use DNS-01 Challenge for kind/Local Clusters

**For kind clusters or when using dynamic DNS providers like No-IP.com**, HTTP-01 challenges won't work because:
- kind clusters aren't publicly accessible from the internet
- Dynamic DNS IPs may not route directly to your cluster

**Solution: Use DNS-01 challenge with webhook solver**

cert-manager doesn't have native No-IP.com support, but you can use the generic **webhook solver with custom scripts** or **acme-dns**:

**Option A: Use acme-dns (Recommended for No-IP.com)**

1. **Set up acme-dns server** (one-time setup):
```bash
# Deploy acme-dns in your cluster
kubectl apply -f https://raw.githubusercontent.com/joohoi/acme-dns/master/k8s/acme-dns-deployment.yaml

# Or use the public acme-dns service at auth.acme-dns.io
```

2. **Install cert-manager acme-dns webhook**:
```bash
helm repo add cert-manager-webhook-acme-dns https://k8s-at-home.github.io/charts
helm install acme-dns-webhook cert-manager-webhook-acme-dns/cert-manager-webhook-acme-dns \
  -n cert-manager
```

3. **Register your domain with acme-dns** (follow prompts):
```bash
curl -X POST https://auth.acme-dns.io/register
# Returns: {"username":"xxx","password":"xxx","fulldomain":"xxx.auth.acme-dns.io","subdomain":"xxx"}
```

4. **Add CNAME record in No-IP.com**:
```
_acme-challenge.calypr-demo.ddns.net CNAME <fulldomain from above>
```

5. **Create ClusterIssuer with acme-dns**:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - dns01:
        acmeDNS:
          host: https://auth.acme-dns.io
          accountSecretRef:
            name: acme-dns-credentials
            key: acmedns.json
```

6. **Create the credentials secret**:
```bash
cat > acmedns.json <<EOF
{
  "calypr-demo.ddns.net": {
    "username": "<from registration>",
    "password": "<from registration>",
    "fulldomain": "<from registration>",
    "subdomain": "<from registration>",
    "allowfrom": []
  }
}
EOF

kubectl create secret generic acme-dns-credentials \
  -n cert-manager \
  --from-file=acmedns.json
```

**Option B: Manual DNS-01 (Not recommended - use acme-dns instead)**

Manual verification requires adding TXT records to No-IP.com each time a certificate renews. This is not practical for automated renewals.

If you still want manual control, you'll need to:
1. Create a Certificate with manual approval
2. Check the Challenge resource for the required TXT record
3. Add the TXT record `_acme-challenge.calypr-demo.ddns.net` to No-IP.com
4. Wait for validation

For automated renewals, use Option A (acme-dns) instead.

#### Debugging DNS-01 Challenge Flow

If you've configured DNS-01 challenges but still see self-signed certificates, follow these debugging steps:

**Step 1: Verify ClusterIssuer Configuration**

```bash
# Check ClusterIssuer exists and is ready
kubectl get clusterissuer
kubectl describe clusterissuer letsencrypt-prod

# Look for status: Ready: True
# If not ready, check the status conditions for error messages
```

**Step 2: Check Certificate Resource Status**

```bash
# Check certificate status
kubectl get certificate -n argo-stack
kubectl describe certificate calypr-demo-tls -n argo-stack

# Look for:
# - Ready: False (certificate not issued)
# - Status conditions showing the reason (e.g., "Issuing", "NotReady")
# - Last transition time (stuck?)
```

**Step 3: Inspect CertificateRequest**

```bash
# List certificate requests
kubectl get certificaterequest -n argo-stack

# Describe the most recent one
kubectl describe certificaterequest -n argo-stack | head -50

# Look for:
# - Approved: True
# - Ready: False
# - Status message indicating DNS-01 challenge state
```

**Step 4: Check Challenge Resources (DNS-01 specific)**

```bash
# List all challenges
kubectl get challenges -A

# Describe the challenge
kubectl describe challenge <challenge-name> -n argo-stack

# Look for:
# - Type: DNS-01
# - State: pending, valid, invalid, or errored
# - Reason field with specific error messages
# - Presented: True (DNS record was created)
```

**Step 5: Verify acme-dns Credentials Secret**

If using acme-dns:

```bash
# Check secret exists
kubectl get secret acme-dns-credentials -n cert-manager

# Verify the secret has the correct key
kubectl get secret acme-dns-credentials -n cert-manager -o jsonpath='{.data.acmedns\.json}' | base64 -d | jq .

# Should return JSON with your domain configuration:
# {
#   "calypr-demo.ddns.net": {
#     "username": "...",
#     "password": "...",
#     "fulldomain": "xxx.auth.acme-dns.io",
#     "subdomain": "xxx",
#     "allowfrom": []
#   }
# }
```

**Step 6: Verify CNAME Record**

```bash
# Check if CNAME record exists for _acme-challenge subdomain
nslookup -type=CNAME _acme-challenge.calypr-demo.ddns.net

# Or use dig
dig _acme-challenge.calypr-demo.ddns.net CNAME +short

# Should return something like: xxx.auth.acme-dns.io
```

If the CNAME is missing, add it to your DNS provider (e.g., No-IP.com):
```
_acme-challenge.calypr-demo.ddns.net CNAME <fulldomain from acme-dns registration>
```

**Step 7: Check acme-dns TXT Record**

```bash
# Get the fulldomain from your secret
FULLDOMAIN=$(kubectl get secret acme-dns-credentials -n cert-manager -o jsonpath='{.data.acmedns\.json}' | base64 -d | jq -r '."calypr-demo.ddns.net".fulldomain')

echo "Full domain: $FULLDOMAIN"

# Check if TXT record is created on acme-dns
dig @auth.acme-dns.io $FULLDOMAIN TXT +short

# During a challenge, you should see a TXT record with the validation token
```

**Step 8: Check cert-manager Logs**

```bash
# cert-manager controller logs (handles Certificate resources)
kubectl logs -n cert-manager -l app=cert-manager --tail=100 --follow

# cert-manager webhook logs (handles DNS-01 challenge creation)
kubectl logs -n cert-manager -l app=webhook --tail=100

# Look for:
# - "DNS record created" or "DNS propagation check"
# - acme-dns API call logs
# - Authentication errors
# - "challenge not ready" or timeout messages
```

**Step 9: Verify acme-dns Webhook (if installed)**

If you installed the acme-dns webhook:

```bash
# Check webhook pod is running
kubectl get pods -n cert-manager | grep acme-dns

# Check webhook logs
kubectl logs -n cert-manager -l app.kubernetes.io/name=cert-manager-webhook-acme-dns --tail=50

# Test webhook connectivity to acme-dns server
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v https://auth.acme-dns.io/health
```

**Step 10: Manual Challenge Validation**

Test if Let's Encrypt can validate your DNS-01 challenge:

```bash
# Get the challenge token from the Challenge resource
kubectl get challenge -n argo-stack -o yaml

# Look for spec.key (the validation token)
# The TXT record should be: _acme-challenge.calypr-demo.ddns.net -> CNAME -> fulldomain.auth.acme-dns.io

# Verify Let's Encrypt can resolve it
dig _acme-challenge.calypr-demo.ddns.net TXT +short

# This should resolve through the CNAME to the acme-dns TXT record
```

**Step 11: Force Certificate Reissue**

After fixing configuration issues:

```bash
# Delete failed challenges and certificate requests
kubectl delete challenges -n argo-stack --all
kubectl delete certificaterequest -n argo-stack --all

# Optionally delete the certificate to trigger fresh issuance
kubectl delete certificate calypr-demo-tls -n argo-stack

# cert-manager will automatically recreate them
# Watch the new challenge
kubectl get challenges -n argo-stack -w
```

**Common DNS-01 Issues and Solutions:**

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "DNS record not yet propagated" | CNAME not configured or DNS cache | See detailed fix below |
| Challenge stuck in "pending" | CNAME not configured | Add `_acme-challenge.your-domain CNAME fulldomain.auth.acme-dns.io` |
| "invalid credentials" | Wrong acme-dns credentials | Re-register with acme-dns and update secret |
| "DNS record not found" | CNAME propagation delay | Wait 5-10 minutes for DNS propagation |
| "acme-dns: unauthorized" | Incorrect username/password | Verify credentials in secret match registration |
| Challenge "invalid" after 60s | DNS propagation too slow | Use longer `--dns01-self-check-period` flag on cert-manager |
| Certificate stays "Issuing" | Previous challenge failed | Delete old challenges: `kubectl delete challenges -A` |

**Detailed Fix for "DNS record not yet propagated" Error:**

If you see this error in cert-manager logs:
```
"propagation check failed" err="DNS record for \"calypr-demo.ddns.net\" not yet propagated"
```

This means cert-manager is checking for the TXT record but can't find it. Follow these steps:

**1. Verify the CNAME Record Exists:**

```bash
# Check if CNAME exists
dig _acme-challenge.calypr-demo.ddns.net CNAME +short

# Should return: xxx.auth.acme-dns.io
# If empty, the CNAME is missing - add it to your DNS provider
```

**2. Check DNS Resolution Path:**

```bash
# Follow the full resolution chain
dig _acme-challenge.calypr-demo.ddns.net TXT +trace

# This should show:
# 1. Query to root servers
# 2. Query to .net servers
# 3. Query to ddns.net servers (No-IP.com)
# 4. CNAME pointing to auth.acme-dns.io
# 5. TXT record on auth.acme-dns.io
```

**3. Verify acme-dns Has Created the TXT Record:**

```bash
# Get the fulldomain from your acme-dns credentials
FULLDOMAIN=$(kubectl get secret acme-dns-credentials -n cert-manager \
  -o jsonpath='{.data.acmedns\.json}' | base64 -d | \
  jq -r '."calypr-demo.ddns.net".fulldomain')

echo "Checking TXT record on: $FULLDOMAIN"

# Query acme-dns directly
dig @auth.acme-dns.io $FULLDOMAIN TXT +short

# Should return a TXT record like: "abc123def456..."
# If empty, acme-dns hasn't created the record yet
```

**4. Check cert-manager's View:**

cert-manager uses specific DNS resolvers. Check what it sees:

```bash
# Get the cert-manager pod name
CERT_MGR_POD=$(kubectl get pods -n cert-manager -l app=cert-manager -o jsonpath='{.items[0].metadata.name}')

# Check DNS resolution from cert-manager's perspective
kubectl exec -n cert-manager $CERT_MGR_POD -- nslookup -type=TXT _acme-challenge.calypr-demo.ddns.net

# If this fails but your local dig works, cert-manager is using different DNS servers
```

**5. Wait for DNS Propagation:**

DNS changes can take time to propagate:

```bash
# Watch the challenge status
kubectl get challenges -n argo-stack -w

# cert-manager retries every 60 seconds by default
# Wait up to 10 minutes for DNS propagation
```

**6. Check for DNS Caching Issues:**

```bash
# Flush local DNS cache (on your machine, not cluster)
# Linux:
sudo systemd-resolve --flush-caches

# macOS:
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Then retest
dig _acme-challenge.calypr-demo.ddns.net TXT +short
```

**7. Verify CNAME Configuration in No-IP.com:**

Log into your No-IP.com account and verify:

1. Go to **Dynamic DNS** → **Hostnames**
2. Click **Modify** on `calypr-demo.ddns.net`
3. Check if there's a **DNS Records** or **Advanced** section
4. Add CNAME record:
   - **Subdomain**: `_acme-challenge`
   - **Record Type**: CNAME
   - **Target**: `<fulldomain>.auth.acme-dns.io` (from your acme-dns registration)

**8. If CNAME is Correct but Still Failing:**

The issue might be cert-manager's DNS resolver configuration:

```bash
# Check cert-manager deployment for custom DNS settings
kubectl get deployment -n cert-manager cert-manager -o yaml | grep -A 5 dnsPolicy

# If using ClusterFirst (default), it uses cluster DNS (CoreDNS/kube-dns)
# Try using public DNS resolvers by adding flags to cert-manager:
kubectl set env deployment/cert-manager -n cert-manager \
  --containers=cert-manager \
  DNS01_RECURSIVE_NAMESERVERS=8.8.8.8:53,1.1.1.1:53
```

**9. Increase DNS Propagation Check Period:**

If your DNS propagates slowly:

```bash
# Edit cert-manager deployment to increase check period
kubectl edit deployment cert-manager -n cert-manager

# Add to container args:
# - --dns01-recursive-nameservers-only=true
# - --dns01-self-check-period=10m

# Or use kubectl set:
kubectl patch deployment cert-manager -n cert-manager --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--dns01-self-check-period=10m"}]'
```

**10. Verify acme-dns API Accessibility:**

```bash
# Test from within the cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v https://auth.acme-dns.io/health

# Should return: {"ok":true}

# If this fails, check network policies or firewall rules blocking acme-dns
```

**11. Check acme-dns Registration:**

Verify your acme-dns registration is correct:

```bash
# View the credentials
kubectl get secret acme-dns-credentials -n cert-manager \
  -o jsonpath='{.data.acmedns\.json}' | base64 -d | jq .

# Test the credentials directly
curl -X POST https://auth.acme-dns.io/update \
  -H "X-Api-User: <username from above>" \
  -H "X-Api-Key: <password from above>" \
  -d '{"subdomain":"<subdomain from above>","txt":"test123"}'

# Should return: {"txt":"test123"}
```

**12. Monitor cert-manager Logs in Real-Time:**

```bash
# Watch cert-manager process the DNS-01 challenge
kubectl logs -n cert-manager -l app=cert-manager --tail=100 -f | grep -i "dns\|propagation\|challenge"

# Look for:
# - "Calling DNS01 Update" (acme-dns API call)
# - "Waiting for DNS-01 propagation" (checking DNS)
# - "DNS record propagated" (success!)
# - Specific error messages
```

After fixing the issue, the challenge should transition from "pending" to "valid", and cert-manager will issue the certificate.

**Using Staging for DNS-01 Testing:**

To avoid Let's Encrypt rate limits while debugging:

```bash
# Create staging ClusterIssuer with DNS-01
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
    - dns01:
        acmeDNS:
          host: https://auth.acme-dns.io
          accountSecretRef:
            name: acme-dns-credentials
            key: acmedns.json
EOF

# Update ingress to use staging
kubectl annotate ingress ingress-authz-workflows -n argo-stack \
  cert-manager.io/cluster-issuer=letsencrypt-staging --overwrite

# Delete certificate to trigger reissuance
kubectl delete certificate calypr-demo-tls -n argo-stack
```

Once DNS-01 works with staging, switch back to production.

---

#### Cause 4: ClusterIssuer Not Ready (HTTP-01)

```bash
kubectl get clusterissuer
kubectl describe clusterissuer letsencrypt-prod

# Check status shows Ready: True
```

If ClusterIssuer doesn't exist or isn't ready:
```bash
# Create ClusterIssuer for HTTP-01 (production clusters only)
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

#### Cause 5: Rate Limiting from Let's Encrypt

If testing repeatedly, you may hit Let's Encrypt rate limits (5 failures per hour, 50 certs per domain per week).

**Solution:** Use letsencrypt-staging for testing:
```bash
# Switch to staging issuer in your ingress annotation
kubectl annotate ingress ingress-authz-workflows -n argo-stack \
  cert-manager.io/cluster-issuer=letsencrypt-staging --overwrite

# Delete existing certificate to retry
kubectl delete certificate calypr-demo-tls -n argo-stack
```

Staging certificates won't be trusted by browsers but allow testing without hitting rate limits.

#### Cause 6: DNS Not Pointing to LoadBalancer IP

```bash
# Verify DNS resolves to your LoadBalancer IP
nslookup calypr-demo.ddns.net

# Should return your LoadBalancer's external IP
LB_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Expected IP: $LB_IP"
```

If DNS is wrong, update your DNS provider to point to the LoadBalancer IP.

**Force certificate reissue after fixing DNS:**
```bash
kubectl delete certificaterequest -n argo-stack --all
kubectl delete challenges -n argo-stack --all
# cert-manager will automatically create new ones
```

---

### Installing a Manual Certificate

If you've obtained a certificate manually (e.g., using `certbot` directly) and want to use it instead of cert-manager automation, follow these steps.

**Scenario:** You have a Let's Encrypt certificate stored locally or on a server:
```
Certificate is saved at: /etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem
```

#### Step 1: Create TLS Secret from Certificate Files

```bash
# Create the TLS secret from your certificate files
kubectl create secret tls calypr-demo-tls \
  -n argo-stack \
  --cert=/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem \
  --key=/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem

# If the secret already exists, delete it first:
kubectl delete secret calypr-demo-tls -n argo-stack

# Then recreate it
kubectl create secret tls calypr-demo-tls \
  -n argo-stack \
  --cert=/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem \
  --key=/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem
```

**For certificates on a remote server:**

```bash
# Copy certificate files from remote server
scp user@server:/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem ./fullchain.pem
scp user@server:/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem ./privkey.pem

# Create secret from local files
kubectl create secret tls calypr-demo-tls \
  -n argo-stack \
  --cert=./fullchain.pem \
  --key=./privkey.pem

# Clean up local copies
rm ./fullchain.pem ./privkey.pem
```

#### Step 2: Stop cert-manager from Managing the Certificate

To prevent cert-manager from overwriting your manual certificate:

```bash
# Remove cert-manager annotation from all ingress resources
kubectl annotate ingress ingress-authz-workflows -n argo-stack \
  cert-manager.io/cluster-issuer-

kubectl annotate ingress ingress-authz-applications -n argo-stack \
  cert-manager.io/cluster-issuer-

kubectl annotate ingress ingress-authz-registrations -n argo-stack \
  cert-manager.io/cluster-issuer-

# Or remove from all ingress resources at once
kubectl get ingress -n argo-stack -o name | xargs -I {} \
  kubectl annotate {} cert-manager.io/cluster-issuer-

# Delete the Certificate resource (prevents cert-manager from managing it)
kubectl delete certificate calypr-demo-tls -n argo-stack
```

#### Step 3: Verify Certificate Installation

```bash
# Check the TLS secret exists
kubectl get secret calypr-demo-tls -n argo-stack

# Verify certificate details
kubectl get secret calypr-demo-tls -n argo-stack -o jsonpath='{.data.tls\.crt}' | \
  base64 -d | openssl x509 -noout -text | grep -A2 "Validity\|Subject:"

# Test HTTPS connection
curl -vI https://calypr-demo.ddns.net/workflows 2>&1 | grep "subject:\|issuer:\|expire"
```

#### Step 4: Update Multiple Namespaces (if needed)

If you have ingress resources in multiple namespaces using the same certificate:

```bash
# Create the same secret in other namespaces
kubectl create secret tls calypr-demo-tls \
  -n calypr-api \
  --cert=/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem \
  --key=/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem

kubectl create secret tls calypr-demo-tls \
  -n calypr-tenants \
  --cert=/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem \
  --key=/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem
```

#### Important Notes

**Certificate Expiration:**
- Let's Encrypt certificates are valid for **90 days**
- You must manually renew before expiration
- Set a calendar reminder for 30 days before expiration

**Check expiration date:**
```bash
kubectl get secret calypr-demo-tls -n argo-stack -o jsonpath='{.data.tls\.crt}' | \
  base64 -d | openssl x509 -noout -enddate
```

**Manual Renewal Process:**

When the certificate is about to expire:

```bash
# 1. Renew on the server where you originally obtained it
certbot renew

# 2. Update the Kubernetes secret
kubectl create secret tls calypr-demo-tls \
  -n argo-stack \
  --cert=/etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem \
  --key=/etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Restart ingress controller to pick up new certificate (optional)
kubectl rollout restart deployment ingress-nginx-controller -n ingress-nginx
```

#### Re-enabling Automated cert-manager Management

If you later fix your DNS-01 or HTTP-01 setup and want to return to automated certificate management:

```bash
# 1. Delete the manual secret
kubectl delete secret calypr-demo-tls -n argo-stack

# 2. Re-add the cert-manager annotation to your ingress
kubectl annotate ingress ingress-authz-workflows -n argo-stack \
  cert-manager.io/cluster-issuer=letsencrypt-prod

# 3. cert-manager will automatically create a new Certificate resource
# and obtain a certificate from Let's Encrypt

# 4. Verify certificate is being issued
kubectl get certificate -n argo-stack
kubectl describe certificate calypr-demo-tls -n argo-stack
```

#### Alternative: Using cert-manager with Manual Certificates

If you want cert-manager to manage the Certificate resource but provide your own cert:

```bash
# Create a Certificate resource pointing to an existing secret
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: calypr-demo-tls
  namespace: argo-stack
spec:
  secretName: calypr-demo-tls
  # Don't specify issuerRef - this tells cert-manager to just manage the secret
  # without trying to obtain a new certificate
  dnsNames:
    - calypr-demo.ddns.net
EOF
```

---

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
kubectl run -it --rm debug --image=curlimages/curl --restart=Never --   curl -v http://argo-stack-argo-workflows-server.argo-workflows:2746/

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
kubectl get svc -n argo-workflows argo-stack-argo-workflows-server
```

2. Check ingress path configuration matches service expectations
3. Verify the service ports match ingress configuration

### Issue: 404 Due to Cross-Namespace Service Routing

**Error:**
NGINX ingress returns 404 for all paths (`/workflows`, `/applications`, `/registrations`) even though the backend pods are running and responding correctly when accessed directly within the cluster.

**Symptoms:**
```bash
# Direct service access works:
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server.argo-workflows:2746/
# Returns expected HTML

# But ingress returns 404:
curl https://calypr-demo.ddns.net/workflows
# Returns 404 Not Found
```

**Cause:** Kubernetes Ingress resources can **only route to services in the same namespace** as the Ingress. If your ingress is in `argo-stack` namespace but the actual service is in `argo-workflows` namespace, NGINX cannot route to it directly.

Common cross-namespace scenarios:
- Ingress in `argo-stack` → Service in `argo-workflows` (Argo Workflows Server)
- Ingress in `argo-stack` → Service in `argocd` (Argo CD Server)
- Ingress in `argo-stack` → Service in `argo-events` (EventSource Service)

**Solution - Use ExternalName Services:**

The `ingress-authz-overlay` chart supports cross-namespace routing via ExternalName services. Configure each route with both `namespace` (where ingress lives) and `serviceNamespace` (where service actually exists):

```yaml
# helm/argo-stack/overlays/ingress-authz-overlay/values.yaml
ingressAuthzOverlay:
  routes:
    workflows:
      namespace: argo-stack           # Where the ingress is created
      serviceNamespace: argo-workflows # Where the actual service exists
      service: argo-stack-argo-workflows-server
      port: 2746
    applications:
      namespace: argo-stack
      serviceNamespace: argocd        # ArgoCD server is in argocd namespace
      service: argo-stack-argocd-server
      port: 8080
    registrations:
      namespace: argo-stack
      serviceNamespace: argo-events   # EventSource is in argo-events namespace
      service: github-repo-registrations-eventsource-svc
      port: 12000
```

When `serviceNamespace` differs from `namespace`, the chart automatically creates:
1. **ExternalName Service** (e.g., `argo-stack-argo-workflows-server-proxy`) in the ingress namespace
2. This service acts as a DNS proxy pointing to the actual service FQDN
3. The ingress routes to the proxy service, which forwards to the actual service

**Verify ExternalName Services:**
```bash
# Check ExternalName services were created
kubectl get svc -n argo-stack -l app.kubernetes.io/component=externalname-proxy

# Verify ExternalName targets
kubectl get svc argo-stack-argo-workflows-server-proxy -n argo-stack -o yaml | grep externalName
# Should show: externalName: argo-stack-argo-workflows-server.argo-workflows.svc.cluster.local
```

**Redeploy the overlay:**
```bash
helm upgrade --install ingress-authz-overlay \
  helm/argo-stack/overlays/ingress-authz-overlay \
  --namespace argo-stack
```

**Debug cross-namespace routing:**
```bash
# 1. Verify direct service access works
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server.argo-workflows:2746/

# 2. Verify ExternalName proxy service resolves correctly
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://argo-stack-argo-workflows-server-proxy.argo-stack:2746/

# 3. Check ingress configuration
kubectl describe ingress ingress-authz-workflows -n argo-stack | grep -A5 "backend"
```

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
