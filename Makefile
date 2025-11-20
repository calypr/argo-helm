# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter test-artifacts all minio minio-ls minio-status minio-cleanup vault-dev vault-seed vault-cleanup vault-status eso-install eso-status eso-cleanup

# S3/MinIO configuration - defaults to in-cluster MinIO
S3_ENABLED           ?= true
S3_ACCESS_KEY_ID     ?= minioadmin
S3_SECRET_ACCESS_KEY ?= minioadmin
S3_BUCKET            ?= argo-artifacts
S3_REGION            ?= us-east-1
S3_HOSTNAME          ?= minio.minio-system.svc.cluster.local:9000

# Vault configuration for local development (in-cluster deployment)
VAULT_TOKEN          ?= root


check-vars:
	@echo "🔍 Checking required environment variables..."
	@test -n "$(S3_ENABLED)" || (echo "❌ ERROR: S3_ENABLED must be set (true/false)" && exit 1)
	@if [ "$(S3_ENABLED)" = "true" ]; then \
		test -n "$(S3_ACCESS_KEY_ID)" || (echo "❌ ERROR: S3_ACCESS_KEY_ID must be set" && exit 1); \
		test -n "$(S3_SECRET_ACCESS_KEY)" || (echo "❌ ERROR: S3_SECRET_ACCESS_KEY must be set" && exit 1); \
		test -n "$(S3_BUCKET)" || (echo "❌ ERROR: S3_BUCKET must be set" && exit 1); \
	fi
	@echo "✅ Environment validation passed."
	@test -n "$(GITHUB_PAT)" || (echo "Error: GITHUB_PAT is undefined. Run 'export GITHUB_PAT=...' before installing" && exit 1)
        @test -n "$(ARGOCD_SECRET_KEY)" || (echo "Error: ARGOCD_SECRET_KEY is undefined. Run 'export ARGOCD_SECRET_KEY=...' before installing" && exit 1)
        @test -n "$(ARGO_HOSTNAME)" || (echo "Error: ARGO_HOSTNAME is undefined. Run 'export ARGO_HOSTNAME=...' before installing" && exit 1)

	@echo "✅ Environment validation passed."


deps:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo add external-secrets https://charts.external-secrets.io
	helm repo update
	helm dependency build helm/argo-stack

lint:
	helm lint helm/argo-stack --values helm/argo-stack/values.yaml

template: check-vars deps 
	helm template argo-stack helm/argo-stack \
		--debug \
		--values my-values.yaml \
		--set-string events.github.secret.tokenValue=${GITHUB_PAT} \
		--set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000  \
		--set-string s3.enabled=${S3_ENABLED} \
                --set-string s3.accessKeyId=${S3_ACCESS_KEY_ID} \
                --set-string s3.secretAccessKey=${S3_SECRET_ACCESS_KEY} \
                --set-string s3.bucket=${S3_BUCKET} \
		--namespace argocd > rendered.yaml

validate:
	kubeconform -strict -ignore-missing-schemas \
	  -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' \
	  -summary rendered.yaml

bump-limits:
	@echo "🔧 Raising inotify and file descriptor limits in Kind nodes..."
	@NODE=$$(kind get nodes | head -n1); \
	if [ -z "$$NODE" ]; then \
		echo "❌ No kind node found. Is your cluster running?"; \
		exit 1; \
	fi; \
	echo "➡️  Applying sysctl updates on $$NODE"; \
	docker exec "$$NODE" sysctl -w fs.inotify.max_user_watches=1048576; \
	docker exec "$$NODE" sysctl -w fs.inotify.max_user_instances=1024; \
	docker exec "$$NODE" sysctl -w fs.file-max=2097152; \
	echo "✅ Limits updated on $$NODE"

show-limits:
	@NODE=$$(kind get nodes | head -n1); \
	if [ -z "$$NODE" ]; then \
		echo "❌ No kind node found."; \
		exit 1; \
	fi; \
	echo "🔍 Checking limits on $$NODE"; \
	docker exec "$$NODE" sh -c 'sysctl fs.inotify.max_user_watches fs.inotify.max_user_instances fs.file-max'



kind:
	kind delete cluster || true
	kind create cluster

minio:
	@echo "🗄️ Installing MinIO in cluster..."
	helm repo add minio https://charts.min.io/ || true
	helm repo update
	helm upgrade --install minio minio/minio \
		--namespace minio-system --create-namespace \
		--set rootUser=minioadmin \
		--set rootPassword=minioadmin \
		--set persistence.enabled=false \
		--set mode=standalone \
		--set resources.requests.memory=512Mi \
		--set resources.requests.cpu=250m \
		--set resources.limits.memory=1Gi \
		--set resources.limits.cpu=500m \
		--wait
	@echo "✅ MinIO installed successfully"
	@echo "⏳ Waiting for MinIO service to be ready..."
	@sleep 10
	@echo "📦 Creating default bucket: argo-artifacts"
	@kubectl run minio-mc-setup --rm -i --restart=Never --image=minio/mc --command -- \
		sh -c "until mc alias set myminio http://minio.minio-system.svc.cluster.local:9000 minioadmin minioadmin; do echo 'Waiting for MinIO...'; sleep 2; done && \
		mc mb myminio/argo-artifacts --ignore-existing && \
		echo 'Bucket argo-artifacts created successfully'" 2>&1 || echo "⚠️  Bucket creation skipped (may already exist)"
	@echo "   Endpoint: minio.minio-system.svc.cluster.local:9000"
	@echo "   Access Key: minioadmin"
	@echo "   Secret Key: minioadmin"
	@echo "   Bucket: argo-artifacts"

minio-ls:
	@echo "📂 Listing files in minio/argo-artifacts bucket..."
	@kubectl run minio-mc-ls --rm -i --restart=Never --image=minio/mc --command -- \
		sh -c "mc alias set myminio http://minio.minio-system.svc.cluster.local:9000 minioadmin minioadmin && \
		mc ls --recursive myminio/argo-artifacts" 2>&1 || echo "⚠️  Failed to list bucket contents"

minio-cleanup:
	@echo "🧹 Cleaning up MinIO..."
	@helm uninstall minio -n minio-system 2>/dev/null || true
	@kubectl delete namespace minio-system 2>/dev/null || true
	@echo "✅ MinIO removed"

minio-shell:
	@echo "🐚 Opening shell in MinIO pod..."
	@kubectl exec -it -n minio-system $$(kubectl get pod -n minio-system -l app=minio -o jsonpath='{.items[0].metadata.name}') -- /bin/sh

ct: check-vars kind deps
	ct lint --config .ct.yaml --debug
	ct install --config .ct.yaml --debug --helm-extra-args "--timeout 15m"

argo-stack: check-vars kind bump-limits eso-install vault-dev vault-seed deps minio vault-auth 
	helm upgrade --install \
		argo-stack ./helm/argo-stack -n argocd --create-namespace \
		--wait --atomic \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000 \
		--set-string s3.enabled=${S3_ENABLED} \
		--set-string s3.bucket=${S3_BUCKET} \
		--set-string s3.pathStyle=true \
		--set-string s3.insecure=true \
		--set-string s3.region=${S3_REGION} \
		--set-string s3.hostname=${S3_HOSTNAME} \
		-f my-values.yaml
	echo waiting for pods
	sleep 10

deploy: argo-stack
	kubectl wait --for=condition=Ready pod   -l app.kubernetes.io/name=argocd-server   --timeout=120s -n argocd
	echo starting port forwards
	kubectl port-forward svc/argo-stack-argo-workflows-server 2746:2746 --address=0.0.0.0 -n argo-workflows &
	kubectl port-forward svc/argo-stack-argocd-server         8080:443  --address=0.0.0.0 -n argocd &
	kubectl port-forward svc/github-eventsource-svc 12000:12000             --address=0.0.0.0 -n argo-events &
	echo UIs available on port 2746 and port 8080, event exposed on 12000

adapter:
	cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q

test-artifacts:
	./test-per-app-artifacts.sh

password:
	kubectl get secret argocd-initial-admin-secret \
          -o jsonpath="{.data.password}"  -n argocd | base64 -d; echo  #  -n argocd 

login:
	argocd login localhost:8080 --skip-test-tls --insecure --name admin --password `kubectl get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"  -n argocd | base64 -d`

all: lint template validate kind ct adapter test-artifacts

# ============================================================================
# Vault Development Targets (Helm-based in-cluster deployment)
# ============================================================================

vault-dev:
	@echo "🔐 Installing Vault dev server in Kubernetes cluster..."
	@helm repo add hashicorp https://helm.releases.hashicorp.com 2>/dev/null || true
	@helm repo update hashicorp
	@kubectl create namespace vault 2>/dev/null || true
	@helm upgrade --install vault hashicorp/vault \
		--namespace vault \
		--set server.dev.enabled=true \
		--set server.dev.devRootToken=$(VAULT_TOKEN) \
		--set injector.enabled=false \
		--set ui.enabled=true \
		--set server.dataStorage.enabled=false \
		--wait --timeout 2m
	@echo "⏳ Waiting for Vault to be ready..."
	@kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=vault -n vault --timeout=120s
	@echo "✅ Vault dev server running in cluster"
	@echo "   Namespace: vault"
	@echo "   Service: vault.vault.svc.cluster.local:8200"
	@echo "   Root token: $(VAULT_TOKEN)"
	@echo ""
	@echo "💡 To access Vault UI, run: kubectl port-forward -n vault svc/vault 8200:8200"

vault-status:
	@echo "🔍 Checking Vault status..."
	@kubectl exec -n vault vault-0 -- vault status 2>/dev/null || echo "❌ Vault not running. Run 'make vault-dev' first."

vault-seed:
	@echo "🌱 Seeding Vault with test secrets..."
	@echo "➡️  Enabling KV v2 secrets engine..."
	@kubectl exec -n vault vault-0 -- vault secrets enable -version=2 -path=kv kv 2>/dev/null || echo "   (KV already enabled)"
	@echo "➡️  Creating secrets for Argo CD..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/argocd/admin \
		password="admin123456" \
		bcryptHash='$$2a$$10$$rRyBkqjtRlpvrut4WyTp0eSx5qbHJUh.O7Ql0kp.VeGAHu8xfKKVi'
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/argocd/oidc \
		clientSecret="test-oidc-secret-argocd"
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/argocd/server \
		secretKey="$$(openssl rand -hex 32)"
	@echo "➡️  Creating secrets for Argo Workflows..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/workflows/artifacts \
		accessKey="minioadmin" \
		secretKey="minioadmin"
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/workflows/oidc \
		clientSecret="test-oidc-secret-workflows"
	@echo "➡️  Creating secrets for authz-adapter..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/authz \
		clientSecret="test-oidc-secret-authz"
	@echo "➡️  Creating secrets for GitHub Events..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/events/github \
		token="$(GITHUB_PAT)" 
	@echo "➡️  Creating per-app S3 credentials..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello/s3 \
		accessKey="app1-access-key" \
		secretKey="app1-secret-key"
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello-2/s3 \
		accessKey="app2-access-key" \
		secretKey="app2-secret-key"
	@echo "➡️  Seeding Vault with secrets from my-values.yaml repoRegistrations..."
	@# nextflow-hello-project GitHub credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello-project/github \
		token="$(GITHUB_PAT)"
	@# nextflow-hello-project S3 artifact credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello-project/s3/artifacts \
		AWS_ACCESS_KEY_ID="nextflow-hello-artifacts-key" \
		AWS_SECRET_ACCESS_KEY="nextflow-hello-artifacts-secret"
	@# genomics-variant-calling GitHub credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/genomics/github \
		token="$(GITHUB_PAT)"
	@# genomics-variant-calling S3 artifact credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/genomics/s3/artifacts \
		AWS_ACCESS_KEY_ID="genomics-artifacts-key" \
		AWS_SECRET_ACCESS_KEY="genomics-artifacts-secret"
	@# genomics-variant-calling S3 data bucket credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/genomics/s3/data \
		AWS_ACCESS_KEY_ID="genomics-data-key" \
		AWS_SECRET_ACCESS_KEY="genomics-data-secret"
	@# local-dev-workflows GitHub credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/internal-dev/github \
		token="$(GITHUB_PAT)"
	@# local-dev-workflows MinIO credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/internal-dev/minio \
		AWS_ACCESS_KEY_ID="minioadmin" \
		AWS_SECRET_ACCESS_KEY="minioadmin"
	@echo "➡️  Enabling Kubernetes auth method..."
	@kubectl exec -n vault vault-0 -- vault auth enable kubernetes 2>/dev/null || echo "   (Kubernetes auth already enabled)"
	@echo "➡️  Configuring Kubernetes auth..."
	@kubectl exec -n vault vault-0 -- sh -c 'vault write auth/kubernetes/config \
		kubernetes_host="https://$$KUBERNETES_PORT_443_TCP_ADDR:443"' 2>/dev/null || echo "   (Kubernetes auth already configured)"
	@echo "✅ Vault seeded with test data"
	@echo ""
	@echo "📋 Available secrets:"
	@echo "   kv/argo/argocd/admin                            - Argo CD admin credentials"
	@echo "   kv/argo/argocd/oidc                             - Argo CD OIDC client secret"
	@echo "   kv/argo/argocd/server                           - Argo CD server secret key"
	@echo "   kv/argo/workflows/artifacts                     - Workflow artifact storage credentials"
	@echo "   kv/argo/workflows/oidc                          - Workflow OIDC client secret"
	@echo "   kv/argo/authz                                   - AuthZ adapter OIDC secret"
	@echo "   kv/argo/events/github                           - GitHub webhook token"
	@echo "   kv/argo/apps/*/s3                               - Per-app S3 credentials (legacy)"
	@echo "   kv/argo/apps/nextflow-hello-project/github      - nextflow-hello-project GitHub token"
	@echo "   kv/argo/apps/nextflow-hello-project/s3/artifacts - nextflow-hello-project S3 credentials"
	@echo "   kv/argo/apps/genomics/github                    - genomics-variant-calling GitHub token"
	@echo "   kv/argo/apps/genomics/s3/artifacts              - genomics-variant-calling S3 artifact credentials"
	@echo "   kv/argo/apps/genomics/s3/data                   - genomics-variant-calling S3 data credentials"
	@echo "   kv/argo/apps/internal-dev/github                - local-dev-workflows GitHub token"
	@echo "   kv/argo/apps/internal-dev/minio                 - local-dev-workflows MinIO credentials"

vault-list:
	@echo "📋 Listing all secrets in Vault..."
	@kubectl exec -n vault vault-0 -- vault kv list -format=json kv/argo 2>/dev/null || echo "❌ No secrets found or Vault not running"

vault-get:
	@if [ -z "$(VPATH)" ]; then \
		echo "❌ Usage: make vault-get VPATH=kv/argo/argocd/admin"; \
		exit 1; \
	fi
	@kubectl exec -n vault vault-0 -- vault kv get -format=json $(VPATH)

vault-cleanup:
	@echo "🧹 Cleaning up Vault dev server..."
	@helm uninstall vault -n vault 2>/dev/null || true
	@kubectl delete namespace vault 2>/dev/null || true
	@echo "✅ Vault dev server removed"

vault-auth:
	@echo "🧹 Binding ServiceAccount to Vault dev server..."
	@printf '%s\n' 'path "kv/data/argo/*" {' '  capabilities = ["read"]' '}' \
	  | kubectl exec -i -n vault vault-0 -- vault policy write argo-stack -
	@kubectl exec -n vault vault-0 -- vault write auth/kubernetes/role/argo-stack \
                bound_service_account_names=eso-vault-auth \
                bound_service_account_namespaces=external-secrets-system \
                policies=argo-stack \
                ttl=1h
	@kubectl exec -n vault vault-0 -- vault read auth/kubernetes/role/argo-stack
	@echo "✅ Service account to Vault dev server added"
vault-shell:
	@echo "🐚 Opening shell in Vault pod..."
	@kubectl exec -it -n vault vault-0 -- /bin/sh

# ============================================================================
# External Secrets Operator Installation
# ============================================================================

eso-install:
	@echo "🔐 Installing External Secrets Operator..."
	@helm repo add external-secrets https://charts.external-secrets.io 2>/dev/null || true
	@helm repo update external-secrets
	@helm upgrade --install external-secrets external-secrets/external-secrets \
		--namespace external-secrets-system --create-namespace \
		--set installCRDs=true \
		--wait --timeout 3m
	@echo "⏳ Waiting for External Secrets Operator to be ready..."
	@kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=external-secrets -n external-secrets-system --timeout=120s
	@echo "⏳ Waiting for CRDs to be established..."
	@kubectl wait --for condition=established --timeout=60s crd/externalsecrets.external-secrets.io
	@kubectl wait --for condition=established --timeout=60s crd/secretstores.external-secrets.io
	@kubectl wait --for condition=established --timeout=60s crd/clustersecretstores.external-secrets.io
	@echo "✅ External Secrets Operator installed successfully"

eso-status:
	@echo "🔍 Checking External Secrets Operator status..."
	@kubectl get pods -n external-secrets-system -l app.kubernetes.io/name=external-secrets 2>/dev/null || echo "❌ ESO not running. Run 'make eso-install' first."

eso-cleanup:
	@echo "🧹 Cleaning up External Secrets Operator..."
	@helm uninstall external-secrets -n external-secrets-system 2>/dev/null || true
	@kubectl delete namespace external-secrets-system 2>/dev/null || true
	@echo "✅ External Secrets Operator removed"

