\
#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 [--teardown|-t]
  Install (default) or teardown the Argo stack (Argo Workflows, Argo CD, authz-adapter, RBAC, S3 artifacts).
USAGE
}

TEARDOWN=false
if [[ "${1:-}" == "--teardown" || "${1:-}" == "-t" ]]; then
  TEARDOWN=true
fi

: "${WF_NS:=wf-poc}"
: "${ARGO_NS:=argo}"
: "${ARGOCD_NS:=argocd}"
: "${SEC_NS:=security}"
: "${ARGO_HELM_CHART_VERSION:=}"
: "${ARGO_AUTH_MODE:=server}"

# On-prem S3 params
: "${ARTIFACT_S3_HOSTNAME:=}"
: "${ARTIFACT_REGION:=us-west-2}"
: "${ARTIFACT_INSECURE:=false}"
: "${ARTIFACT_PATH_STYLE:=true}"
: "${ARTIFACT_BUCKET:=}"
: "${AWS_ACCESS_KEY_ID:=}"
: "${AWS_SECRET_ACCESS_KEY:=}"

: "${AUTHZ_ADAPTER_IMAGE:=ghcr.io/yourorg/authz-adapter:latest}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "FATAL: '$1' not found"; exit 1; }; }
need kubectl
need helm

if $TEARDOWN; then
  echo ">> Teardown starting"
  set +e
  helm -n "${ARGO_NS}" uninstall argo >/dev/null 2>&1
  # Argo CD installed via upstream manifest; delete it
  kubectl -n "${ARGOCD_NS}" delete -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml >/dev/null 2>&1
  kubectl -n "${SEC_NS}" delete deploy/authz-adapter svc/authz-adapter >/dev/null 2>&1
  kubectl -n "${ARGO_NS}" delete cm artifact-repositories >/dev/null 2>&1
  kubectl -n "${WF_NS}" delete sa/nextflow-launcher role/nextflow-executor rolebinding/nextflow-executor-binding secret/s3-credentials >/dev/null 2>&1
  # Optional: delete namespaces (comment out if shared)
  # kubectl delete ns "${ARGO_NS}" "${ARGOCD_NS}" "${WF_NS}" "${SEC_NS}"
  echo ">> Teardown complete"
  exit 0
fi

echo ">> Creating namespaces (ok if exist)"
kubectl get ns "${ARGO_NS}" >/dev/null 2>&1 || kubectl create ns "${ARGO_NS}"
kubectl get ns "${ARGOCD_NS}" >/dev/null 2>&1 || kubectl create ns "${ARGOCD_NS}"
kubectl get ns "${WF_NS}" >/dev/null 2>&1 || kubectl create ns "${WF_NS}"
kubectl get ns "${SEC_NS}" >/dev/null 2>&1 || kubectl create ns "${SEC_NS}"

echo ">> Helm repo add/update"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null
helm repo update >/dev/null

echo ">> Install/upgrade Argo Workflows"
WF_ARGS=(--install argo argo/argo-workflows -n "${ARGO_NS}")
[[ -n "${ARGO_HELM_CHART_VERSION}" ]] && WF_ARGS+=(--version "${ARGO_HELM_CHART_VERSION}")
helm upgrade "${WF_ARGS[@]}" \
  --set server.enabled=true \
  --set "server.extraArgs[0]=--auth-mode=${ARGO_AUTH_MODE}"
kubectl -n "${ARGO_NS}" rollout status deploy/argo-workflows-server
kubectl -n "${ARGO_NS}" rollout status deploy/argo-workflows-workflow-controller

echo ">> Install/upgrade Argo CD"
kubectl -n "${ARGOCD_NS}" apply -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n "${ARGOCD_NS}" rollout status deploy/argocd-server

echo ">> Tenant SA + RBAC"
kubectl apply -f - <<YAML
apiVersion: v1
kind: ServiceAccount
metadata:
  name: nextflow-launcher
  namespace: ${WF_NS}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: nextflow-executor
  namespace: ${WF_NS}
rules:
  - apiGroups: ["", "batch"]
    resources: ["pods","pods/log","pods/status","jobs"]
    verbs: ["create","get","list","watch","delete","patch","update"]
  - apiGroups: ["argoproj.io"]
    resources:
      - workflows
      - workflowtemplates
      - cronworkflows
      - workflowtaskresults
      - workflowtasksets
      - workfloweventbindings
    verbs: ["create","get","list","watch","delete","patch","update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: nextflow-executor-binding
  namespace: ${WF_NS}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: nextflow-executor
subjects:
  - kind: ServiceAccount
    name: nextflow-launcher
    namespace: ${WF_NS}
YAML

if [[ -n "${AWS_ACCESS_KEY_ID}" && -n "${AWS_SECRET_ACCESS_KEY}" && -n "${ARTIFACT_BUCKET}" && -n "${ARTIFACT_S3_HOSTNAME}" ]]; then
  echo ">> Configure S3 artifact repo"
  kubectl -n "${WF_NS}" apply -f - <<YAML
apiVersion: v1
kind: Secret
metadata: { name: s3-credentials }
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "${AWS_ACCESS_KEY_ID}"
  AWS_SECRET_ACCESS_KEY: "${AWS_SECRET_ACCESS_KEY}"
YAML
  kubectl -n "${ARGO_NS}" apply -f - <<YAML
apiVersion: v1
kind: ConfigMap
metadata:
  name: artifact-repositories
data:
  default-v1: |
    archiveLogs: true
    s3:
      bucket: ${ARTIFACT_BUCKET}
      endpoint: ${ARTIFACT_S3_HOSTNAME}
      region: ${ARTIFACT_REGION}
      insecure: ${ARTIFACT_INSECURE}
      accessKeySecret:
        name: s3-credentials
        key: AWS_ACCESS_KEY_ID
      secretKeySecret:
        name: s3-credentials
        key: AWS_SECRET_ACCESS_KEY
      useSDKCreds: false
      pathStyle: ${ARTIFACT_PATH_STYLE}
YAML
  kubectl -n "${ARGO_NS}" rollout restart deploy/argo-workflows-workflow-controller
  kubectl -n "${ARGO_NS}" rollout status  deploy/argo-workflows-workflow-controller
else
  echo ">> Skipping artifact repo (set ARTIFACT_S3_HOSTNAME, ARTIFACT_BUCKET, AWS_ACCESS_KEY_ID/SECRET)"
fi

echo ">> Deploy authz-adapter"
kubectl -n "${SEC_NS}" apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: authz-adapter
spec:
  replicas: 2
  selector:
    matchLabels: { app: authz-adapter }
  template:
    metadata:
      labels: { app: authz-adapter }
    spec:
      containers:
      - name: adapter
        image: ${AUTHZ_ADAPTER_IMAGE}
        imagePullPolicy: IfNotPresent
        env:
        - name: FENCE_BASE
          value: "https://calypr-dev.ohsu.edu/user"
        ports: [{ containerPort: 8080 }]
        readinessProbe:
          httpGet: { path: /healthz, port: 8080 }
        livenessProbe:
          httpGet: { path: /healthz, port: 8080 }
---
apiVersion: v1
kind: Service
metadata:
  name: authz-adapter
spec:
  selector: { app: authz-adapter }
  ports:
  - name: http
    port: 8080
    targetPort: 8080
YAML

echo "== ✅ Install complete =="
echo "Argo Workflows UI: kubectl -n ${ARGO_NS} port-forward svc/argo-workflows-server 2746:2746"
echo "Argo CD UI:        kubectl -n ${ARGOCD_NS} port-forward svc/argocd-server 8080:80"
echo "Teardown:          $0 --teardown"
