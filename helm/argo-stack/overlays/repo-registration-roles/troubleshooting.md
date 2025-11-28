# Troubleshooting repo-registration-roles

This guide helps you debug issues when tenants do not see the expected Argo CD
applications or workflows, or when group-based permissions are not enforced as
expected.

---

## 1. Verify `repoRegistrations` values

1. Check that `repoRegistrations` is present in the values file passed to this chart:
   ```bash
   grep -A10 '^repoRegistrations:' my-values.yaml
   ```
2. Confirm each entry has a valid `repoUrl` of the form:
   ```text
   https://github.com/<org>/<repo>.git
   ```
3. Render the chart locally and inspect the generated RBAC:
   ```bash
   helm template repo-registration-roles ./helm/repo-registration-roles -f my-values.yaml > rendered.yaml
   ```

Look for:

- `ConfigMap argocd-rbac-cm` with `policy.csv` lines for your tenant.
- `Role` / `RoleBinding` resources in the expected namespace `wf-<org>-<repo>`.

---

## 2. Check Argo CD RBAC mapping

1. Confirm the `argocd-rbac-cm` in the cluster matches what you expect:
   ```bash
   kubectl get configmap argocd-rbac-cm -n argocd -o yaml
   ```
2. Inspect `data.policy.csv` and verify:
   - There is a `role:wf-admin` line and a `g, <adminGroup>, role:wf-admin`.
   - For each `repoUrl`, there are `role:wf-<org>-<repo>-writer` and
     `role:wf-<org>-<repo>-reader` lines.
3. Log in to Argo CD (through the ingress / auth proxy) and run:
   ```bash
   argocd account get-user-info
   ```
   You should see the `groups` list include:
   - `wf-<org>-<repo>-writers` or `wf-<org>-<repo>-readers`
   - `wf-admins` for global admins (if configured).

4. Validate effective permissions:
   ```bash
   argocd account can-i get applications '<projectName>/<appName>'
   argocd account can-i sync applications '<projectName>/<appName>'
   ```

Expected:

- Writers: `get` = allowed, `sync` = allowed.
- Readers: `get` = allowed, `sync` = denied.

---

## 3. Verify workflow namespace RBAC

1. Compute the workflow namespace:
   ```text
   wf-<org>-<repo>
   ```
   For `repoUrl: https://github.com/bwalsh/nextflow-hello-project.git`:
   - `org = bwalsh`
   - `repo = nextflow-hello-project`
   - `namespace = wf-bwalsh-nextflow-hello-project`
2. Confirm Roles and RoleBindings exist:
   ```bash
   kubectl get role,rolebinding -n wf-bwalsh-nextflow-hello-project
   ```
3. Use `kubectl auth can-i` with impersonated groups:
   ```bash
   NS=wf-bwalsh-nextflow-hello-project

   kubectl auth can-i list workflows.argoproj.io      --as-group=wf-bwalsh-nextflow-hello-project-writers      -n "$NS"

   kubectl auth can-i create workflows.argoproj.io      --as-group=wf-bwalsh-nextflow-hello-project-readers      -n "$NS"
   ```

Expected:

- Writers: `list/create` = **yes**.
- Readers: `list` = **yes**, `create` = **no**.

If the checks fail, inspect the corresponding `Role` and `RoleBinding` definitions
in `rendered.yaml` and in the live cluster.

---

## 4. Validate X-Auth-Request-Groups end-to-end

1. **authz-adapter output**

   - Increase logging or add a debug endpoint in `authz-adapter` to print:
     - User email (`sub` / `preferred_username` / `email`).
     - Derived groups, e.g. `wf-<org>-<repo>-writers`.

   Ensure that for a given user:

   - Members of `adminUsers` in `repoRegistrations[]` get:
     - `wf-<org>-<repo>-writers` (and optionally `wf-admins`).
   - Members of `readUsers` get:
     - `wf-<org>-<repo>-readers`.

2. **Ingress (NGINX) headers**

   - Check the ingress configuration to confirm `auth_request` and header
     propagation:
     ```bash
     kubectl get ingress -A -o yaml | grep -A5 'auth-request'
     ```
   - Use a temporary echo service behind the same ingress to inspect headers:
     ```bash
     curl -k -H "Host: <your-host>" https://<your-host>/debug/headers
     ```
     Look for:
     ```text
     X-Auth-Request-User: ...
     X-Auth-Request-Groups: wf-<org>-<repo>-writers, wf-admins
     ```

3. **Argo CD sees the groups**

   - From the user’s environment, run:
     ```bash
     argocd account get-user-info
     ```
     Confirm the `Groups` section contains the `wf-*` groups from above.

   If the groups appear at the ingress echo service but **not** in Argo CD,
   check:

   - Whether a proxy or extra layer is stripping the headers.
   - Whether TLS termination is happening in a place that changes headers.

---

## 5. Common mistakes

- **Wrong repoUrl format**

  If `repoUrl` is not `https://github.com/<org>/<repo>.git`, the Helm templates
  may derive incorrect `<org>` / `<repo>` segments, leading to mismatched group
  names and namespaces.

- **Namespaces not created**

  This chart does not create namespaces. Make sure `wf-<org>-<repo>` exists and
  is managed by your base Argo stack or another chart.

- **Argo CD Application name mismatch**

  The chart assumes the Application name and Project name are both `<org>-<repo>`.
  If you use a different naming convention, you must adjust the RBAC templates
  accordingly.

- **authz-adapter not configured to emit wf-* groups**

  The overlay cannot work unless `X-Auth-Request-Groups` includes values like
  `wf-<org>-<repo>-writers` and `wf-<org>-<repo>-readers`. Make sure your
  authz-adapter derives those consistently from `repoRegistrations` and/or IdP
  group memberships.

If you have verified all of the above and things still do not behave as
expected, rerun `helm template` and carefully compare the rendered RBAC
resources against what is actually running in the cluster.
