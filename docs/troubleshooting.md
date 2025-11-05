> [!CAUTION]
> Error:
> ```
> argo-workflows-server shows the following error at /event-sources/ 
> """ Not Found: the server could not find the requested resource (get eventsources.argoproj.io) """
> ```

That error means the **Argo Events CRDs aren’t installed** (or the argo-server RBAC can’t read them). `eventsources.argoproj.io` is a CRD from **Argo Events**, not Argo Workflows. Fix it like this:

# 1. Verify the CRD is missing

```bash
kubectl get crd | grep eventsources
kubectl api-resources | grep -E 'eventsources|sensors|eventbus'
```

If nothing returns, you need Argo Events.

### 2) Install Argo Events (CRDs + controllers)

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

Or with manifests (if you’re not using Helm), apply the Argo Events CRDs and controllers for your version/cluster.

### 3) Create a basic EventBus (required by Events)

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

### 4) (If needed) RBAC so argo-server can list Events resources

If the CRDs exist but you still get 404 in the UI, give the argo-server’s SA read access:

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

### 5) Recheck

```bash
kubectl get eventsources -A
# then hit /event-sources again, or port-forward the server and refresh
```

**Summary:** `/event-sources` is an Argo Events view. Install **Argo Events (CRDs + controller + EventBus)** and ensure **RBAC** allows argo-server to read them; the 404 will go away.

