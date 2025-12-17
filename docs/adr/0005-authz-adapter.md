# ADR: Authorization Adapter Architecture and Deployment

**Status:** Accepted  
**Date:** 2025-01-16  
**Deciders:** Platform Engineering Team  
**Affected Stakeholders:** DevOps, Security, Application Teams

---

## Context

The Argo stack exposes Argo CD, Argo Workflows, and Vault via NGINX Ingress. Kubernetes RBAC protects in-cluster calls, but external HTTP traffic requires centralized authorization that retrieves Gen3 Fence project membership claims, enforces path-based policies, validates bearer tokens, logs every decision, and plugs into NGINX via the `auth_request` flow.

---

## Decision

Adopt **authz-adapter**, a Python/Flask authorization proxy deployed in-cluster. It validates requests against policy files, resolves user identity and project membership through Gen3 Fence, enforces RBAC, integrates with NGINX forward-auth, caches membership lookups, and produces structured audit logs.

---

## Architecture

### High-Level Flow

```
Client → NGINX Ingress (auth_request) → authz-adapter → Fence → allow/deny → protected service
```

### Components

| Component | Description | Location |
|-----------|-------------|----------|
| authz-adapter app | Flask service exposing `/authz-check`, `/health`, `/ready`, `/metrics` | `'authz-adapter/app.py'` |
| Policy bundle | YAML policy definitions mounted as ConfigMap | `'authz-adapter/fixtures/policies/*.yaml'` |
| Helm overlay | Generates Deployment, Service, and ingress wiring | `'helm/argo-stack/overlays/ingress-authz-overlay/templates/*.yaml'` |
| Tests | Pytest suites for unit/integration/load coverage | `'authz-adapter/tests/'` |

---

## Configuration

### Environment Variables

| Variable | Required | Purpose | Default |
|----------|----------|---------|---------|
| `FENCE_URL` | Yes | Gen3 Fence base URL for authorization lookups | — |
| `POLICY_CONFIG_PATH` | No | Policy file path | `/config/policies.yaml` |
| `LOG_LEVEL` | No | Logging level (`INFO`, `DEBUG`) | `INFO` |
| `CACHE_TTL_SECONDS` | No | Membership cache TTL | `300` |
| `AUTHZ_ADAPTER_PORT` | No | Listener port | `8000` |
| `AUTHZ_ADAPTER_HOST` | No | Bind address | `0.0.0.0` |

### Policy Configuration

Policies live in ConfigMaps mounted at `/config/policies.yaml` and describe path globs, required groups, roles, and optional public access flags. See `'authz-adapter/tests/fixtures/policies.yaml'` for canonical structure.

### Helm/Overlay Values

The overlay consumes values beneath `ingress.authz*` and `authzAdapter.*` in your user values file. Instead of embedding manifests, refer to:

- `'helm/argo-stack/overlays/ingress-authz-overlay/templates/authz-adapter.yaml'` (Deployment/Service)
- `'helm/argo-stack/overlays/ingress-authz-overlay/templates/ingress-authz.yaml'` (Ingress annotations)
- `'helm/argo-stack/overlays/ingress-authz-overlay/templates/externalname-services.yaml'` (optional upstreams)
- `'helm/argo-stack/overlays/ingress-authz-overlay/templates/_helpers.tpl'` (labels/ports)

---

## Deployment

1. Enable the overlay via `ingress.authzEnabled=true` and point `ingress.authzAdapterService` at the adapter Service.
2. Provide Gen3 Fence configuration under `authzAdapter.fence`.
3. Apply via `make argo-stack`. The overlay templates listed above render the Kubernetes objects.
4. Validate by inspecting pods (`kubectl get pods -l app=authz-adapter`), logs, and hitting `/authz-check` from an in-cluster debug pod.

---

## Protected Resources

Authorization covers every ingress annotated with the overlay. Default policies ship for:

| Service | Paths | Policy Reference |
|---------|-------|------------------|
| Argo CD | `/api/v1/settings*`, `/api/v1/account*` | `policies.argocd-admin-only` |
| Argo CD | `/api/v1/applications*` | `policies.argocd-teams` |
| Argo Workflows | `/api/v1/workflows*` | `policies.argo-workflows-viewers` |
| Vault | `/v1/sys*` | `policies.vault-admins-only` |
| Landing page | `/`, `/landing` | `policies.public-landing` |

Modify or add rules by editing the ConfigMap backing `POLICY_CONFIG_PATH`.

---

## API Surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/authz-check` | POST | Evaluated by NGINX `auth_request`; returns 200 or 403 with headers describing the caller. |
| `/health` | GET | Liveness probe. |
| `/ready` | GET | Readiness probe, verifies policy load. |
| `/metrics` | GET | Optional Prometheus metrics (requests, cache hits, decision latencies). |

---

## Implementation Notes

### Gen3 Fence Integration

The adapter queries Fence's `/user/user` endpoint (authenticated via the incoming bearer token) to retrieve the authorization document. This JSON response contains:

- `active` – Boolean indicating whether the user account is enabled.
- `authz` – Nested dictionary mapping resource paths (e.g., `/services/workflow/gen3-workflow`) to lists of authorization entries, each specifying `service`, `method` (e.g., `create`, `*`).

The adapter extracts this document, caches it for `CACHE_TTL_SECONDS`, and passes it to `decide_groups` for group mapping.

### Fence Authorization Mapping (`decide_groups`)

The `decide_groups` helper in `'authz-adapter/app.py'` translates Fence authorization JSON into the coarse-grained groups expected by Argo CD and Argo Workflows:

1. **Activation gate** – Inactive users (`doc["active"]` is falsey) short-circuit to `[]`, preventing any authorization headers from being issued.

2. **Capability detection** – The function inspects `doc["authz"]["/services/workflow/gen3-workflow"]` and grants the `argo-runner` group when any entry advertises `method: create` or `*`. This aligns with Argo Workflows' requirement that workflow submitters possess create privileges.

3. **Resource scoping** – If the incoming Kubernetes admission context includes `group=argoproj.io` and `resource` in `{workflows, workflowtemplates}`, the same capability check is applied but scoped only to that specific Argo namespace.

4. **Baseline viewing** – Every active caller receives the `argo-viewer` group, matching Argo CD/Workflows' expectation that authenticated principals can at least list resources unless stronger constraints are applied upstream.

This mapping ensures Fence's fine-grained project-level permissions collapse gracefully into Argo's simpler role model while preserving the principle of least privilege.

### Policy Enforcement

- `load_policies()` parses YAML on demand and is guarded for empty datasets.
- Authorization logic walks policies in order, matches path prefixes, honors public routes, validates required groups (now sourced from Fence), and denies by default.
- JSON responses carry error codes (`missing_token`, `insufficient_groups`, `no_matching_policy`) for observability.

---

## Ingress Header Contract

On successful authorization, the adapter injects these headers for consumption by downstream services:

- **`X-Auth-Request-User`** – Required by the Argo CD ingress SSO flow so the API server can associate the session with the authenticated principal (see [Argo CD Ingress Authentication](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/#ingress-authentication)).

- **`X-Auth-Request-Email`** – Consumed by the Argo Workflows server when `--auth-mode sso` is enabled to render the user identity in the UI and audit logs (see [Argo Workflows SSO Auth Mode](https://argo-workflows.readthedocs.io/en/stable/argo-server-auth-mode/#sso)).

- **`X-Auth-Request-Groups`** – Used by both Argo CD RBAC (`policy.csv`) and Argo Workflows RBAC to map callers to roles; documented in the [Argo CD RBAC Guide](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/).

- **`X-Allowed`** – Mirrors the `auth_request` contract described in the [Argo Workflows Ingress Example](https://argo-workflows.readthedocs.io/en/stable/argo-server-auth-mode/#ingress); Argo respects the NGINX allow/deny decision before proxying to the UI/API.

---

## Testing

Pytest suites cover:
- Request lifecycle with mocked Fence responses
- `decide_groups` logic across various Fence authorization payloads
- Integration with synthetic ingress headers
- Cache performance and TTL behavior

Run with `pytest -v` or `pytest --cov=app`. HTML coverage reports are emitted under `'authz-adapter/htmlcov/'`.

---

## Security Considerations

1. Store Fence endpoint URLs and any service credentials in Kubernetes Secrets; mount through environment variables only.
2. Rotate credentials via `kubectl apply` updates and `kubectl rollout restart` to flush cached memberships.
3. Keep cache TTL short enough to respect real-time project membership revocations in Fence.
4. Enforce HTTPS from clients to ingress; intra-cluster traffic can optionally adopt mTLS via service mesh.
5. Monitor Fence API quotas; caching plus per-route rate limits mitigate exhaustion.
6. Validate that bearer tokens sent to Fence are scoped appropriately and never logged in plaintext.

---

## Operations

- **Update Fence URL:** edit the Secret/ConfigMap, restart the Deployment, verify logs show successful `/user/user` calls.
- **Update policies:** edit the ConfigMap, restart to reload (or add file watchers).
- **Clear cache:** restart pods to flush in-memory authorization lookups.
- **Monitor:** tail adapter logs, scrape `/metrics`, and alert on elevated 403 rates or Fence API errors.

---

## Trade-offs & Future Work

| Choice | Benefit | Future Option |
|--------|---------|---------------|
| Python/Flask | Rapid iteration, rich ecosystem | Potential Go rewrite for lower latency |
| In-memory cache | Simple, fast | External cache (Redis) for multi-replica consistency |
| Fence-only identity | Aligns with Gen3 ecosystem | Add OIDC or LDAP backends for hybrid environments |
| NGINX forward-auth | Minimal ingress changes | Evaluate service mesh policies or Envoy ext-authz |

---

## References

- NGINX `auth_request`: https://nginx.org/en/docs/http/ngx_http_auth_request_module.html  
- Gen3 Fence User API: https://github.com/uc-cdis/fence  
- Argo CD Ingress Authentication: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/#ingress-authentication  
- Argo CD RBAC: https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/  
- Argo Workflows SSO Auth: https://argo-workflows.readthedocs.io/en/stable/argo-server-auth-mode/#sso  
- Flask docs: https://flask.palletsprojects.com/  
- Adapter codebase: `'authz-adapter/app.py'`  
- Overlay templates: `'helm/argo-stack/overlays/ingress-authz-overlay/templates/'`