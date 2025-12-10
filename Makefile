# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter github-status-proxy test-artifacts all minio minio-ls help
.PHONY: build-proxy-binary build-proxy-image load-proxy-image deploy-proxy

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
	helm repo update
	helm dependency build helm/argo-stack

lint:
	helm lint helm/argo-stack --values helm/argo-stack/values.yaml

template: check-vars deps 
	helm template argo-stack helm/argo-stack \
		--debug \
		--values helm/argo-stack/values.yaml \
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

ct: check-vars kind deps
	ct lint --config .ct.yaml --debug
	ct install --config .ct.yaml --debug --helm-extra-args "--timeout 15m"

deploy: check-vars kind bump-limits deps minio
	helm upgrade --install \
		argo-stack ./helm/argo-stack -n argocd --create-namespace \
		--wait --atomic \
		--set-string events.github.secret.tokenValue=${GITHUB_PAT} \
		--set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000 \
		--set-string s3.enabled=${S3_ENABLED} \
		--set-string s3.accessKeyId=${S3_ACCESS_KEY_ID} \
		--set-string s3.secretAccessKey=${S3_SECRET_ACCESS_KEY} \
		--set-string s3.bucket=${S3_BUCKET} \
		--set-string s3.pathStyle=true \
		--set-string s3.insecure=true \
		--set-string s3.region=${S3_REGION} \
		--set-string s3.hostname=${S3_HOSTNAME} \
		-f my-values.yaml
	echo waiting for pods
	sleep 10
	kubectl wait --for=condition=Ready pod   -l app.kubernetes.io/name=argocd-server   --timeout=120s -n argocd
	echo starting port forwards
	kubectl port-forward svc/argo-stack-argo-workflows-server 2746:2746 --address=0.0.0.0 -n argo-workflows &
	kubectl port-forward svc/argo-stack-argocd-server         8080:443  --address=0.0.0.0 -n argocd &
	kubectl port-forward svc/github-eventsource-svc 12000:12000             --address=0.0.0.0 -n argo-events &
	echo UIs available on port 2746 and port 8080, event exposed on 12000

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
	@if [ -z "$(GITHUB_APP_ID)" ]; then \
		echo "❌ ERROR: GITHUB_APP_ID must be set. Run 'export GITHUB_APP_ID=...' before deploying"; \
		exit 1; \
	fi
	@if [ ! -f "$(GITHUB_APP_PRIVATE_KEY_FILE)" ]; then \
		echo "❌ ERROR: GITHUB_APP_PRIVATE_KEY_FILE must point to a valid PEM file"; \
		echo "   Example: export GITHUB_APP_PRIVATE_KEY_FILE=/path/to/private-key.pem"; \
		exit 1; \
	fi
	@echo "📝 Creating secret for GitHub App credentials..."
	@kubectl create secret generic github-app-private-key \
		--from-file=private-key.pem=$(GITHUB_APP_PRIVATE_KEY_FILE) \
		-n argocd --dry-run=client -o yaml | kubectl apply -f -
	@echo "📝 Deploying GitHub Status Proxy with Helm..."
	helm upgrade --install argo-stack ./helm/argo-stack \
		-n argocd --create-namespace \
		--set githubStatusProxy.enabled=true \
		--set githubStatusProxy.image=$(PROXY_IMAGE_FULL) \
		--set githubStatusProxy.githubAppId=$(GITHUB_APP_ID) \
		--set githubStatusProxy.privateKeySecret.name=github-app-private-key \
		--set githubStatusProxy.privateKeySecret.key=private-key.pem \
		--wait
	@echo "✅ GitHub Status Proxy deployed successfully"
	@echo "   Check status: kubectl get pods -n argocd -l app=github-status-proxy"
	@echo "   View logs: kubectl logs -n argocd -l app=github-status-proxy"

test-artifacts:
	./test-per-app-artifacts.sh

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
