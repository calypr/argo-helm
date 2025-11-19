
# **Engineering Note: Debugging Vault + External Secrets Operator Integration**

**Date:** 2025-11-19
**Authors:** Engineering Team
**Context:** Integration of **HashiCorp Vault**, **External Secrets Operator (ESO)**, **ClusterSecretStore**, and multiple Kubernetes namespaces within the `argo-stack` Helm chart.

---

## **1. Overview**

During development of the `argo-stack` Helm chart, we integrated:

* **Vault (KV v2)** for centralized secret management
* **External Secrets Operator (ESO)** for syncing secrets into Kubernetes
* **ClusterSecretStore** for cross-namespace access to Vault
* Multiple workloads (Argo CD, Argo Workflows, Argo Events) each running in **separate namespaces**

The debugging work surfaced several important details and pitfalls when combining all four systems. This note captures root causes, solutions, and recommended patterns.

---

# **2. Root Causes Identified**

## **2.1. Namespace Mismatch for ServiceAccount**

ESO uses a Kubernetes **ServiceAccount** to authenticate to Vault via the Kubernetes Auth engine.

ESO logs repeatedly showed:

```
cannot request Kubernetes service account token for service account "eso-vault-auth":
ServiceAccount "eso-vault-auth" not found
```

Root cause:

* The **ClusterSecretStore** specified:

  ```yaml
  serviceAccountRef:
    name: eso-vault-auth
  ```
* But **the ServiceAccount was deployed in a different namespace** than ESO assumed
  (first `argocd`, then moved to `external-secrets-system`).

Fix:

```yaml
serviceAccountRef:
  name: eso-vault-auth
  namespace: external-secrets-system
```

---

## **2.2. Vault Role Bound to Wrong Namespace**

Vault roles must bind explicitly to the namespace where the ServiceAccount lives.

Incorrect:

```bash
vault write auth/kubernetes/role/argo-stack \
  bound_service_account_names=eso-vault-auth \
  bound_service_account_namespaces=argocd
```

Correct:

```bash
vault write auth/kubernetes/role/argo-stack \
  bound_service_account_names=eso-vault-auth \
  bound_service_account_namespaces=external-secrets-system
```

If the namespace does not match exactly, Vault returns:

```
invalid role name
permission denied
```

---

## **2.3. Incorrect Vault Policy Path for KV v2**

Vault KV v2 stores secrets under:

* Write path: `kv/argo/...`
* Read API path: `kv/data/argo/...`

ESO must be allowed to read via the *internal data path*.

Correct policy:

```hcl
path "kv/data/argo/*" {
  capabilities = ["read"]
}
```

Missing this results in 403 errors:

```
Error making API request
Code: 403
permission denied
```

---

## **2.4. ExternalSecret Key Paths Did Not Match Vault Secret Paths**

The most subtle discovery:

ESO uses:

```
remoteRef.key: <path-within-KV>
remoteRef.property: <field within the secret>
```

With `version: v2`, the resulting API call is:

```
GET /v1/<mount>/data/<remoteRef.key>
```

We found two common mistakes:

### ❌ Encoding the field name into the key

Example:

```yaml
key: workflows/artifacts/accessKey
```

ESO interpreted this as the *secret name*, not the field.

Vault error:

```
Secret does not exist
```

### ✔ Correct pattern:

```
key: argo/workflows/artifacts
property: accessKey
```

---

## **2.5. ClusterSecretStore “path” Determines Prefix**

ClusterSecretStore:

```yaml
path: kv
```

ESO constructs:

```
kv/data/<remoteRef.key>
```

If `path: kv/argo`, then:

```
kv/argo/data/<remoteRef.key>
```

We validated that the final working configuration is:

* `path: kv`
* ExternalSecrets reference `argo/...` keys

---

# **3. Working Model (Canonical Pattern)**

This is the mental model that works reliably for Vault + ESO + KV v2.

### **Vault Mount**

```
secrets enable -path=kv -version=2 kv
```

### **Vault Secret Example**

```
kv/argo/workflows/artifacts
```

Actual stored structure:

```json
{
  "accessKey": "...",
  "secretKey": "..."
}
```

### **Vault Policy**

```hcl
path "kv/data/argo/*" {
  capabilities = ["read"]
}
```

### **ClusterSecretStore**

```yaml
spec:
  provider:
    vault:
      server: http://vault.vault.svc.cluster.local:8200
      path: kv
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: argo-stack
          serviceAccountRef:
            name: eso-vault-auth
            namespace: external-secrets-system
```

### **ExternalSecret (Correct Form)**

```yaml
- secretKey: AWS_ACCESS_KEY_ID
  remoteRef:
    key: argo/workflows/artifacts
    property: accessKey
```

---

# **4. Summary of Key Lessons**

### ✔ ESO authenticates using **its own** ServiceAccount

This SA must live in the namespace where the operator runs (`external-secrets-system`).

### ✔ Vault roles must bind to the exact namespace

Otherwise Vault returns “invalid role” or “permission denied.”

### ✔ KV v2 requires policies against `kv/data/...`

Not the human path `kv/...`.

### ✔ ESO’s `remoteRef.key` refers to the **secret**, not the field**

Use `remoteRef.property` for fields.

### ✔ Prefix handling matters (`path: kv` vs `path: kv/argo`)

Be consistent across Vault, ClusterSecretStore, and ExternalSecret.

---

# **5. Recommendations for the Helm Chart**

We should encode a few defaults:

1. **ClusterSecretStore should always specify ServiceAccount namespace**
2. **Chart should publish a README explaining KV v2 path conventions**
3. **All ExternalSecret definitions should use the correct key/property form**
4. **A Vault self-check target should validate:**

   * role exists
   * SA binding matches
   * policy is applied
   * test secret is readable with a JWT

---

# **6. Final Working Example (End-to-End)**

### `vault-auth` Makefile target:

```bash
printf '%s\n' 'path "kv/data/argo/*" {' '  capabilities = ["read"]' '}' \
  | kubectl exec -i -n vault vault-0 -- vault policy write argo-stack -

kubectl exec -n vault vault-0 -- vault write auth/kubernetes/role/argo-stack \
  bound_service_account_names=eso-vault-auth \
  bound_service_account_namespaces=external-secrets-system \
  policies=argo-stack \
  ttl=1h
```

### ExternalSecret for S3 credentials:

```yaml
data:
  - secretKey: AWS_ACCESS_KEY_ID
    remoteRef:
      key: argo/workflows/artifacts
      property: accessKey
  - secretKey: AWS_SECRET_ACCESS_KEY
    remoteRef:
      key: argo/workflows/artifacts
      property: secretKey
```

Everything now syncs cleanly.

---
