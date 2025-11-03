
## 📜 How `argo-helm` addresses [requirements](https://github.com/calypr/argo-helm/issues/5)

* **Orchestrator & server-side execution (UC-1, UC-6–UC-9):**
  Install **Argo Workflows** and **Argo CD** via the community Helm charts. This gives you DAGs, steps, retries, artifacts, logs/UIDs, and API/CLI to start runs (jobs) with parameters. You model `tiff_offsets`, `file_transfer`, and custom pipelines as (Cluster)WorkflowTemplates and submit Runs programmatically. ([GitHub][1])

* **Submission API surface (UC-1):**
  Argo Workflows’ server API (exposed by the chart) accepts workflow submissions with input params; Argo CD can also be used to declaratively drive workflow launches (e.g., an Application that renders a `Workflow` CR). **`argo-helm` installs these components;** your Calypr API would call them. ([GitHub][1])

* **Policy-driven plans / default workflows (UC-2):**
  Not a native Argo feature, but you can approximate with **Argo CD ApplicationSets** and Helm values overlays, or read a “policy pack” ConfigMap and render different workflow templates based on file type. Argo CD **supports multiple sources** (chart & values from different repos) from **v2.6+**, which helps you separate policy packs from workflow charts. ([Argo CD][2])

* **Observability: job/run status & logs (UC-3, AT-4):**
  Workflows UI and API expose per-run state, timelines, and **log tailing**; Argo CD shows resource health/sync for GitOps-driven launches. All of this is what the charts install and expose. ([GitHub][1])

* **Gating publication on required jobs (UC-4, AT-5/AT-6):**
  **Not enforced by Argo itself.** Recommended pattern: Calypr API checks Argo run states (via label selectors/annotations per input) before allowing publication. Argo provides the **ground truth of run states and artifacts**; your API enforces the 412/428 logic. (Deploying Argo via `argo-helm` is the enabling step.) ([GitHub][1])

* **Background publication updates (UC-5, AT-7):**
  Model as a separate “update-publication” workflow that runs asynchronously; trigger via your API or GitOps commit. Argo handles the run; your API versions the publication. Installed via the charts. ([GitHub][1])

* **Custom workflow registration & invocation (UC-8, AT-PS9):**
  Use **WorkflowTemplate/ClusterWorkflowTemplate** to register `custom:<name>@<version>`; invoke by reference with params. Managed and deployed with Helm/Argo CD. ([GitHub][1])

* **Retries, partial success, idempotency (UC-9, AT-9):**
  Use `retryStrategy` and step-level exit handlers. Your API tracks Job/Run IDs and retries failed ones only. Provided by Argo Workflows, installed by the chart. ([GitHub][1])

* **AuthN/Z & multi-tenant isolation (UC-10, AT-10):**
  Achieve **namespace-scoped isolation** with Kubernetes RBAC; Argo CD integrates OIDC SSO and repo credentials. The Argo CD Helm chart is the standard way to deploy these features. ([artifacthub.io][3])

* **Ingress/UI exposure & cluster bootstrap:**
  The official charts are the supported install path. You can expose **Argo CD** and **Argo Workflows** UIs via Ingress or port-forwarding; this is the common setup shown in docs and chart pages. ([Argo CD][2])

* **Values/overlays & “policy pack” repos:**
  Since **Argo CD v2.6**, you can keep **charts in one repo and values in another**, which maps well to your “policy pack” versioning and environment overlays. ([Argo CD][2])

# What `argo-helm` does **not** do (and how to fill the gaps)

* **Pre-submission “Jobs Suite” client (Section 2, UC-PS1–PS10):**
  That client-side toolkit (signing, SBOM, offline runs) is out of scope for `argo-helm`. You’d ship it as a separate CLI and have it submit evidence or artifacts. Argo just runs the workflows you define. ([GitHub][1])

* **Publication gating logic:**
  Needs to live in Calypr’s API/service. Argo supplies run results; your service enforces `requiredWorkflows` before allowing publication. ([GitHub][1])

* **DRS/Indexd updates:**
  Implement as workflow steps (containers) or post-run webhooks in your API; Argo executes them, but the contract to Indexd/DRS is your code. ([GitHub][1])


