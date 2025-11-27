# Multi-Tenant RBAC Design for Calypr + Argo CD + Argo Workflows

## 1. Unified Access Control Matrix

### Group → Permissions Overview

| Group                         | Argo CD Role             | Argo CD Permissions                                      | K8s Role(s)                              | K8s Permissions |
|------------------------------|--------------------------|-----------------------------------------------------------|-------------------------------------------|----------------|
| calypr-demo-repo-readers     | role:demo-repo-read      | Read-only for project + apps                             | wf-demo-repo-reader                       | List/get Workflows, Pods, Logs |
| calypr-demo-repo-writers     | role:demo-repo-write     | Sync, update, manage app                                 | wf-demo-repo-writer                       | CRUD Workflows |
| calypr-platform-admins       | role:admin               | Full Argo CD admin                                        | cluster-admin (ClusterRoleBinding)        | Full cluster |

---

## 2. RBAC Config Examples

### 2.1 Argo CD RBAC (argocd-rbac-cm)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.csv: |
    p, role:admin, *, *, *, allow

    p, role:demo-repo-read, applications, get, demo-repo/*, allow
    p, role:demo-repo-read, applications, sync-status, demo-repo/*, allow
    p, role:demo-repo-read, projects, get, demo-repo, allow

    p, role:demo-repo-write, applications, get, demo-repo/*, allow
    p, role:demo-repo-write, applications, sync, demo-repo/*, allow
    p, role:demo-repo-write, applications, override, demo-repo/*, allow
    p, role:demo-repo-write, applications, update, demo-repo/*, allow
    p, role:demo-repo-write, applications, delete, demo-repo/*, allow

    g, calypr-demo-repo-readers, role:demo-repo-read
    g, calypr-demo-repo-writers, role:demo-repo-write
    g, calypr-platform-admins, role:admin

  policy.default: role:readonly
```

---

### 2.2 AppProject

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: demo-repo
spec:
  sourceRepos:
    - https://github.com/calypr/demo-repo.git
  destinations:
    - namespace: wf-demo-repo
      server: https://kubernetes.default.svc
  namespaceResourceWhitelist:
    - group: argoproj.io
      kind: Workflow
    - group: argoproj.io
      kind: WorkflowTemplate
    - group: argoproj.io
      kind: CronWorkflow
```

---

### 2.3 K8s RBAC for Argo Workflows

#### Reader Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: wf-demo-repo-reader
  namespace: wf-demo-repo
rules:
  - apiGroups: ["argoproj.io"]
    resources: ["workflows", "workflowtemplates", "cronworkflows"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
```

#### Writer Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: wf-demo-repo-writer
  namespace: wf-demo-repo
rules:
  - apiGroups: ["argoproj.io"]
    resources: ["workflows"]
    verbs: ["create", "update", "patch", "delete", "list", "get"]
  - apiGroups: ["argoproj.io"]
    resources: ["workflowtemplates"]
    verbs: ["get", "list", "watch", "create"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
```

#### Admin Binding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: calypr-admin
subjects:
  - kind: Group
    name: calypr-platform-admins
roleRef:
  kind: ClusterRole
  name: cluster-admin
```

---

## 3. Debugging Guide

### Step 1: Verify Group Claims at Auth Layer

```
curl -I https://your-host/debug/headers
```

Look for:

```
X-Auth-Request-User: alice
X-Auth-Request-Groups: calypr-demo-repo-writers,calypr-platform-admins
```

---

### Step 2: Verify Argo CD Sees the Groups

```
argocd account get-user-info
```

Expected:

```json
{
  "username": "alice",
  "groups": ["calypr-demo-repo-writers"]
}
```

---

### Step 3: Verify Kubernetes RBAC

#### Reader Test

```
kubectl auth can-i list workflows.argoproj.io   --as=alice   --as-group=calypr-demo-repo-readers   -n wf-demo-repo
```

#### Writer Test

```
kubectl auth can-i create workflows.argoproj.io   --as=alice   --as-group=calypr-demo-repo-writers   -n wf-demo-repo
```

#### Admin Test

```
kubectl auth can-i '*' '*'   --as=alice   --as-group=calypr-platform-admins
```

---

### Step 4: Functional Checks

Readers:

- Can view app & workflows  
- Cannot sync or create workflows  

Writers:

- Can sync apps  
- Can create/manage workflows in their namespace  

Admins:

- Full access cluster-wide  

