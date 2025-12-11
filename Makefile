# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter github-status-proxy test-artifacts all minio minio-ls help
.PHONY: build-proxy-binary build-proxy-image load-proxy-image deploy-proxy
.PHONY: deps lint template validate kind ct adapter test-artifacts test-secrets test-artifact-repository-ref all minio minio-ls minio-status minio-cleanup vault-dev vault-seed vault-cleanup vault-status eso-install eso-status eso-cleanup vault-seed-github-app

# S3/MinIO configuration - defaults to in-cluster MinIO
S3_ENABLED           ?= true
S3_ACCESS_KEY_ID     ?= minioadmin
S3_SECRET_ACCESS_KEY ?= minioadmin
S3_BUCKET            ?= argo-artifacts
S3_REGION            ?= us-east-1
S3_HOSTNAME          ?= minio.minio-system.svc.cluster.local:9000

# GitHub Status Proxy image configuration
PROXY_IMAGE          ?= ghcr.io/calypr/github-status-proxy
PROXY_TAG            ?= latest
PROXY_IMAGE_FULL     := $(PROXY_IMAGE):$(PROXY_TAG)
# Vault configuration for local development (in-cluster deployment)
VAULT_TOKEN          ?= root

# Ingress configuration - must be set for production deployments
# ARGO_HOSTNAME: (REQUIRED) The domain name for your Argo services (e.g., argo.example.com)
#                Must be set as environment variable: export ARGO_HOSTNAME=your-domain.com
# TLS_SECRET_NAME: Name of the TLS secret for SSL certificates
# EXTERNAL_IP: External IP address for ingress (leave empty to skip external IP assignment)
TLS_SECRET_NAME      ?= calypr-demo-tls
PUBLIC_IP            ?=
LANDING_PAGE_IMAGE_TAG ?= v3

# GitHub App configuration (optional)
# Set these to seed the GitHub App private key into Vault
# GITHUBAPP_PRIVATE_KEY_FILE_PATH ?=
GITHUBAPP_PRIVATE_KEY_VAULT_PATH ?= kv/argo/argocd/github-app


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
	@test -n "$(ARGO_HOSTNAME)" || (echo "Error: ARGO_HOSTNAME is undefined. Run 'export ARGO_HOSTNAME=...' before installing" && exit 1)
	@test -n "$(GITHUBHAPP_APP_ID)" || (echo "Error: GITHUBHAPP_APP_ID is undefined. Run 'export GITHUBHAPP_APP_ID=...' before installing" && exit 1)
	@test -n "$(GITHUBHAPP_CLIENT_ID)" || (echo "Error: GITHUBHAPP_CLIENT_ID is undefined. Run 'export GITHUBHAPP_CLIENT_ID=...' before installing" && exit 1)
	@test -n "$(GITHUBHAPP_PRIVATE_KEY_SECRET_NAME)" || (echo "Error: GITHUBHAPP_PRIVATE_KEY_SECRET_NAME is undefined. Run 'export GITHUBHAPP_PRIVATE_KEY_SECRET_NAME=...' before installing" && exit 1) 
	@test -f "$(GITHUBHAPP_PRIVATE_KEY_FILE_PATH)" || (echo "Error: GITHUBHAPP_PRIVATE_KEY_FILE_PATH file '$(GITHUBHAPP_PRIVATE_KEY_FILE_PATH)' not found. Create the file before installing" && exit 1)
	@test -n "$(GITHUBHAPP_PRIVATE_KEY_VAULT_PATH)" || (echo "Error: GITHUBHAPP_PRIVATE_KEY_VAULT_PATH is undefined. Run 'export GITHUBHAPP_PRIVATE_KEY_VAULT_PATH=...' before installing" && exit 1)
	@test -n "$(GITHUBHAPP_INSTALLATION_ID)" || (echo "Error: GITHUBHAPP_INSTALLATION_ID is undefined. Run 'export GITHUBHAPP_INSTALLATION_ID=...' before installing" && exit 1)
	@echo "✅ All GITHUBHAPP environment variables are set."


deps:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo add external-secrets https://charts.external-secrets.io
	helm repo update
	helm dependency build helm/argo-stack

lint:
	helm lint helm/argo-stack --values helm/argo-stack/values.yaml

template: check-vars deps
	S3_HOSTNAME=${S3_HOSTNAME} S3_BUCKET=${S3_BUCKET} S3_REGION=${S3_REGION} \
	envsubst < my-values.yaml | \
	helm template argo-stack helm/argo-stack \
		--debug \
		--set-string events.github.secret.tokenValue=${GITHUB_PAT} \
		--set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}/registrations \
		--set-string s3.enabled=${S3_ENABLED} \
		--set-string s3.accessKeyId=${S3_ACCESS_KEY_ID} \
		--set-string s3.secretAccessKey=${S3_SECRET_ACCESS_KEY} \
		--set-string s3.bucket=${S3_BUCKET} \
		--set-string githubApp.enabled=true \
		--set-string githubApp.appId="${GITHUBHAPP_APP_ID}" \
		--set-string githubApp.installationId="${GITHUBHAPP_INSTALLATION_ID}" \
		--set-string githubApp.privateKeySecretName="${GITHUBHAPP_PRIVATE_KEY_SECRET_NAME}" \
		--set-string githubApp.privateKeyVaultPath="${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}" \
		--set-string landingPage.image.tag="${LANDING_PAGE_IMAGE_TAG}" \
		--set githubStatusProxy.image="${PROXY_IMAGE_FULL}" \
		--set githubStatusProxy.githubAppId="${GITHUBHAPP_APP_ID}" \
		--set githubStatusProxy.privateKeySecret.name="${GITHUBHAPP_PRIVATE_KEY_SECRET_NAME}" \
		--set githubStatusProxy.privateKeySecret.key=privateKey \
		-f - \
		-f helm/argo-stack/admin-values.yaml \
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
	envsubst < kind-config.yaml | kind create cluster --config -

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

init: check-vars kind bump-limits eso-install vault-dev vault-seed deps minio vault-auth 

argo-stack:
	S3_HOSTNAME=${S3_HOSTNAME} S3_BUCKET=${S3_BUCKET} S3_REGION=${S3_REGION} \
	envsubst < my-values.yaml | helm upgrade --install \
		argo-stack ./helm/argo-stack -n argocd --create-namespace \
		--wait --atomic --timeout 10m0s \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=https://${ARGO_HOSTNAME}/events\
		--set-string s3.enabled=${S3_ENABLED} \
		--set-string s3.bucket=${S3_BUCKET} \
		--set-string s3.pathStyle=true \
		--set-string s3.insecure=true \
		--set-string s3.region=${S3_REGION} \
		--set-string s3.hostname=${S3_HOSTNAME} \
		--set-string ingress.argoWorkflows.host=${ARGO_HOSTNAME} \
		--set-string ingress.argocd.host=${ARGO_HOSTNAME} \
		--set-string ingress.gitappCallback.enabled=true \
		--set-string ingress.gitappCallback.host=${ARGO_HOSTNAME} \
		--set-string githubApp.enabled=true \
		--set-string githubApp.appId="${GITHUBHAPP_APP_ID}" \
		--set-string githubApp.installationId="${GITHUBHAPP_INSTALLATION_ID}" \
		--set-string githubApp.privateKeySecretName="${GITHUBHAPP_PRIVATE_KEY_SECRET_NAME}" \
		--set-string githubApp.privateKeyVaultPath="${GITHUBHAPP_PRIVATE_KEY_VAULT_PATH}" \
		--set-string landingPage.image.tag="${LANDING_PAGE_IMAGE_TAG}" \
		--set githubStatusProxy.enabled=false \
		--set githubStatusProxy.image="${PROXY_IMAGE_FULL}" \
		--set githubStatusProxy.githubAppId="${GITHUBHAPP_APP_ID}" \
		--set githubStatusProxy.privateKeySecret.name="${GITHUBHAPP_PRIVATE_KEY_SECRET_NAME}" \
		--set githubStatusProxy.privateKeySecret.key=privateKey \
		-f helm/argo-stack/admin-values.yaml \
		-f -

deploy: init docker-install argo-stack ports
ports:	
	# manual certificate
	# If the secret already exists, delete it first:
	kubectl delete secret calypr-demo-tls -n argo-stack || true
	# Create the TLS secret from your certificate files
	sudo cp /etc/letsencrypt/live/calypr-demo.ddns.net/fullchain.pem /tmp/
	sudo cp /etc/letsencrypt/live/calypr-demo.ddns.net/privkey.pem /tmp/
	sudo chmod 644 /tmp/fullchain.pem /tmp/privkey.pem
	kubectl create secret tls ${TLS_SECRET_NAME}  -n default        --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n argocd         --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n argo-workflows --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n argo-events    --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n argo-stack     --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n calypr-api     --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	kubectl create secret tls ${TLS_SECRET_NAME}  -n calypr-tenants --cert=/tmp/fullchain.pem --key=/tmp/privkey.pem || true
	sudo rm /tmp/fullchain.pem /tmp/privkey.pem
	# install ingress
	helm upgrade --install ingress-authz-overlay \
	  helm/argo-stack/overlays/ingress-authz-overlay \
	  --namespace argo-stack \
	  --set ingressAuthzOverlay.host=${ARGO_HOSTNAME}
	# start nginx
	helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
	helm repo update
	helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  	-n ingress-nginx --create-namespace \
  	--set controller.service.type=NodePort \
	--set controller.extraArgs.default-ssl-certificate=default/${TLS_SECRET_NAME} \
	--set controller.watchIngressWithoutClass=true \
	-f helm/argo-stack/overlays/ingress-authz-overlay/values-ingress-nginx.yaml
	# Solution - Use NodePort instead of LoadBalancer in kind
	kubectl patch svc ingress-nginx-controller -n ingress-nginx -p '{"spec":{"type":"NodePort","ports":[{"port":80,"nodePort":30080},{"port":443,"nodePort":30443}]}}'

adapter:
	cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q

github-status-proxy:
	cd github-status-proxy && go test -v ./...

# Build the GitHub Status Proxy binary
build-proxy-binary:
	@echo "🔨 Building GitHub Status Proxy binary..."
	cd github-status-proxy && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -installsuffix cgo -o github-status-proxy .
	@echo "✅ Binary built: github-status-proxy/github-status-proxy"

# Build the GitHub Status Proxy Docker image
build-proxy-image: build-proxy-binary
	@echo "🐳 Building GitHub Status Proxy Docker image..."
	docker build -t $(PROXY_IMAGE_FULL) github-status-proxy/
	@echo "✅ Image built: $(PROXY_IMAGE_FULL)"

# Load the proxy image into kind cluster
load-proxy-image: build-proxy-image
	@echo "📦 Loading GitHub Status Proxy image into kind cluster..."
	@kind load docker-image $(PROXY_IMAGE_FULL) || (echo "❌ Failed to load image. Is kind cluster running?" && exit 1)
	@echo "✅ Image loaded into kind cluster"

# Deploy GitHub Status Proxy to the cluster
deploy-proxy: load-proxy-image
	@echo "🚀 Deploying GitHub Status Proxy..."
	@echo "📝 Creating secret for GitHub App credentials..."
	@kubectl create secret generic github-app-private-key \
		--from-file=private-key.pem=$(GITHUBHAPP_PRIVATE_KEY_FILE_PATH) \
		-n argocd --dry-run=client -o yaml | kubectl apply -f -
	@echo "📝 Deploying GitHub Status Proxy with Helm..."
	helm upgrade --install argo-stack ./helm/argo-stack \
		-n argocd --create-namespace \
		--set githubStatusProxy.enabled=true \
		--set githubStatusProxy.image=$(PROXY_IMAGE_FULL) \
		--set githubStatusProxy.githubAppId=$(GITHUBHAPP_APP_ID) \
		--set githubStatusProxy.privateKeySecret.name=github-app-private-key \
		--set githubStatusProxy.privateKeySecret.key=private-key.pem \
		--wait
	@echo "✅ GitHub Status Proxy deployed successfully"
	@echo "   Check status: kubectl get pods -n argocd -l app=github-status-proxy"
	@echo "   View logs: kubectl logs -n argocd -l app=github-status-proxy"

test-artifacts:
	./test-per-app-artifacts.sh

test-artifact-repository-ref:
	@echo "🧪 Testing Artifact Repository Ref Feature (Issue #82)"
	./test-artifact-repository-ref.sh

test-secrets:
	@echo "🔐 Validating ExternalSecrets exist and are valid..."
	@echo ""
	@echo "📋 Checking ArgoCD ExternalSecrets in namespace: argocd"
	@kubectl get externalsecret argocd-secret -n argocd -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ argocd-secret not found"
	@kubectl get externalsecret argocd-initial-admin-secret -n argocd -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ argocd-initial-admin-secret not found"
	@echo ""
	@echo "📋 Checking GitHub ExternalSecrets in namespace: argo-events"
	@kubectl get externalsecret github-secret-nextflow-hello -n argo-events -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ github-secret-nextflow-hello not found"
	# @kubectl get externalsecret github-secret-genomics -n argo-events -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ github-secret-genomics not found"
	# @kubectl get externalsecret github-secret-internal-dev -n argo-events -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ github-secret-internal-dev not found"
	@echo ""
	@echo "📋 Checking S3 ExternalSecrets in tenant namespaces"
	@kubectl get externalsecret s3-credentials-nextflow-hello-project -n wf-bwalsh-nextflow-hello-project -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ s3-credentials-nextflow-hello-project not found in wf-bwalsh-nextflow-hello-project"
	# @kubectl get externalsecret s3-credentials-genomics-variant-calling -n wf-genomics-lab-variant-calling-pipeline -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ s3-credentials-genomics-variant-calling not found in wf-genomics-lab-variant-calling-pipeline"
	# @kubectl get externalsecret s3-data-credentials-genomics-variant-calling -n wf-genomics-lab-variant-calling-pipeline -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ s3-data-credentials-genomics-variant-calling not found in wf-genomics-lab-variant-calling-pipeline"
	# @kubectl get externalsecret s3-credentials-local-dev-workflows -n wf-internal-dev-workflows -o jsonpath='{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}' || echo "❌ s3-credentials-local-dev-workflows not found in wf-internal-dev-workflows"
	@echo ""
	@echo "📊 Summary of all ExternalSecrets:"
	@echo "Namespace: argocd"
	@kubectl get externalsecret -n argocd -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SYNCED:.status.conditions[?(@.type=="Ready")].lastTransitionTime' 2>/dev/null || echo "  No ExternalSecrets found"
	@echo ""
	@echo "Namespace: argo-events"
	@kubectl get externalsecret -n argo-events -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SYNCED:.status.conditions[?(@.type=="Ready")].lastTransitionTime' 2>/dev/null || echo "  No ExternalSecrets found"
	@echo ""
	@echo "Namespace: wf-bwalsh-nextflow-hello-project"
	@kubectl get externalsecret -n wf-bwalsh-nextflow-hello-project -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SYNCED:.status.conditions[?(@.type=="Ready")].lastTransitionTime' 2>/dev/null || echo "  No ExternalSecrets found"
	# @echo ""
	# @echo "Namespace: wf-genomics-lab-variant-calling-pipeline"
	# @kubectl get externalsecret -n wf-genomics-lab-variant-calling-pipeline -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SYNCED:.status.conditions[?(@.type=="Ready")].lastTransitionTime' 2>/dev/null || echo "  No ExternalSecrets found"
	# @echo ""
	# @echo "Namespace: wf-internal-dev-workflows"
	# @kubectl get externalsecret -n wf-internal-dev-workflows -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SYNCED:.status.conditions[?(@.type=="Ready")].lastTransitionTime' 2>/dev/null || echo "  No ExternalSecrets found"
	# @echo ""
	@echo "✅ ExternalSecret validation complete"

password:
	kubectl get secret argocd-initial-admin-secret \
          -o jsonpath="{.data.password}"  -n argocd | base64 -d; echo  #  -n argocd 

login:
	argocd login localhost:8080 --skip-test-tls --insecure --name admin --password `kubectl get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"  -n argocd | base64 -d`

all: lint template validate kind ct adapter github-status-proxy test-artifacts

# Display help information
help:
	@echo "📋 Argo Stack Makefile Targets"
	@echo ""
	@echo "🔧 Setup & Dependencies:"
	@echo "  deps              - Add Helm repositories and build dependencies"
	@echo "  kind              - Create a new kind cluster"
	@echo "  bump-limits       - Raise system limits in kind nodes"
	@echo "  minio             - Install MinIO for artifact storage"
	@echo ""
	@echo "🏗️  Build & Test:"
	@echo "  lint              - Lint Helm charts"
	@echo "  template          - Render Helm templates"
	@echo "  validate          - Validate rendered templates with kubeconform"
	@echo "  adapter           - Run authz-adapter tests"
	@echo "  github-status-proxy - Run github-status-proxy tests"
	@echo "  test-artifacts    - Test artifact configurations"
	@echo ""
	@echo "🐳 GitHub Status Proxy (Docker):"
	@echo "  build-proxy-image - Build the GitHub Status Proxy Docker image"
	@echo "  load-proxy-image  - Build and load image into kind cluster"
	@echo "  deploy-proxy      - Build, load, and deploy proxy to cluster"
	@echo "                      Requires: GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_FILE"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  deploy            - Full deployment to kind cluster"
	@echo "  ct                - Run chart-testing lint and install"
	@echo ""
	@echo "🔍 Utilities:"
	@echo "  password          - Get ArgoCD admin password"
	@echo "  login             - Login to ArgoCD CLI"
	@echo "  minio-ls          - List files in MinIO bucket"
	@echo "  show-limits       - Show current system limits"
	@echo ""
	@echo "📦 Variables:"
	@echo "  PROXY_IMAGE       - Docker image name (default: ghcr.io/calypr/github-status-proxy)"
	@echo "  PROXY_TAG         - Docker image tag (default: latest)"
	@echo "  GITHUB_APP_ID     - GitHub App ID for deployment"
	@echo "  GITHUB_APP_PRIVATE_KEY_FILE - Path to GitHub App private key PEM file"
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

vault-seed: vault-seed-etc vault-seed-github-app

vault-seed-github-app:
	@echo "➡️  Creating secrets for github app ..."
	cat "$(GITHUBHAPP_PRIVATE_KEY_FILE_PATH)" | kubectl exec -i -n vault vault-0 -- vault kv put $(GITHUBAPP_PRIVATE_KEY_VAULT_PATH) privateKey=-; \
	
vault-seed-etc:
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
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/bwalsh/nextflow-hello-project/s3 \
		accessKey="minioadmin" \
		secretKey="minioadmin"
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/bwalsh/nextflow-hello-2/s3 \
		accessKey="app2-access-key" \
		secretKey="app2-secret-key"
	@echo "➡️  Seeding Vault with secrets from my-values.yaml repoRegistrations..."
	@# nextflow-hello-project GitHub credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/bwalsh/nextflow-hello-project/github \
		token="$(GITHUB_PAT)"
	@# nextflow-hello-project S3 artifact credentials
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/bwalsh/nextflow-hello-project/s3/artifacts \
		AWS_ACCESS_KEY_ID="minioadmin" \
		AWS_SECRET_ACCESS_KEY="minioadmin"
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
	@echo "   kv/argo/apps/bwalsh/nextflow-hello-project/github      - nextflow-hello-project GitHub token"
	@echo "   kv/argo/apps/bwalsh/nextflow-hello-project/s3/artifacts - nextflow-hello-project S3 credentials"
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
	@printf '%s\n%s\n' 'path "kv/data/argo/*" {' '  capabilities = ["read"]' '}' \
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
	@echo "⏳ Waiting for webhook CA certificate to be generated..."
	@MAX_WAIT=60; \
	ELAPSED=0; \
	while [ $$ELAPSED -lt $$MAX_WAIT ]; do \
		if kubectl get validatingwebhookconfiguration externalsecret-validate -o jsonpath='{.webhooks[0].clientConfig.caBundle}' 2>/dev/null | grep -q "."; then \
			echo "✅ Webhook CA certificate is ready"; \
			break; \
		fi; \
		sleep 2; \
		ELAPSED=$$((ELAPSED + 2)); \
	done; \
	if [ $$ELAPSED -ge $$MAX_WAIT ]; then \
		echo "⚠️  Webhook CA certificate not ready after $${MAX_WAIT}s, but continuing..."; \
	fi
	@echo "✅ External Secrets Operator installed successfully"

eso-status:
	@echo "🔍 Checking External Secrets Operator status..."
	@kubectl get pods -n external-secrets-system -l app.kubernetes.io/name=external-secrets 2>/dev/null || echo "❌ ESO not running. Run 'make eso-install' first."

eso-cleanup:
	@echo "🧹 Cleaning up External Secrets Operator..."
	@helm uninstall external-secrets -n external-secrets-system 2>/dev/null || true
	@kubectl delete namespace external-secrets-system 2>/dev/null || true
	@echo "✅ External Secrets Operator removed"

docker-runner:
	docker build -t nextflow-runner:latest -f nextflow-runner/Dockerfile .
	kind load docker-image nextflow-runner:latest --name kind
	docker exec -it kind-control-plane crictl images | grep nextflow-runner
	@echo "✅ loaded docker nextflow-runner"

docker-authz:
	cd authz-adapter ; docker build -t authz-adapter:v0.0.1 -f Dockerfile .
	kind load docker-image authz-adapter:v0.0.1 --name kind
	docker exec -it kind-control-plane crictl images | grep authz-adapter
	@echo "✅ loaded docker authz-adapter"

docker-landing-page:
	cd landing-page ; docker build --no-cache  -t landing-page:${LANDING_PAGE_IMAGE_TAG} -f Dockerfile .
	kind load docker-image landing-page:${LANDING_PAGE_IMAGE_TAG} --name kind
	docker exec -it kind-control-plane crictl images | grep landing-page
	@echo "✅ loaded docker landing-page"

docker-gitapp-callback:
	cd gitapp-callback ; docker build -t gitapp-callback:v1.0.0 -f Dockerfile .
	kind load docker-image gitapp-callback:v1.0.0 --name kind
	docker exec -it kind-control-plane crictl images | grep gitapp-callback
	@echo "✅ loaded docker gitapp-callback"

docker-install: docker-runner docker-authz docker-landing-page docker-gitapp-callback load-proxy-image

