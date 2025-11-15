# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter test-artifacts all vault-dev vault-seed vault-cleanup vault-status

S3_ENABLED           ?= true
S3_ACCESS_KEY_ID     ?=
S3_SECRET_ACCESS_KEY ?=
S3_BUCKET            ?=

# Vault configuration for local development
VAULT_ADDR           ?= http://127.0.0.1:8200
VAULT_TOKEN          ?= root
VAULT_DEV_CONTAINER  ?= vault-dev


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

ct: check-vars kind deps
	ct lint --config .ct.yaml --debug
	ct install --config .ct.yaml --debug --helm-extra-args "--timeout 15m"

deploy: check-vars kind bump-limits deps
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
		--set-string s3.region=${S3_REGION} \
		--set-string s3.hostname=${S3_HOSTNAME}
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

test-artifacts:
	./test-per-app-artifacts.sh

password:
	kubectl get secret argocd-initial-admin-secret \
          -o jsonpath="{.data.password}"  -n argocd | base64 -d; echo  #  -n argocd 

login:
	argocd login localhost:8080 --skip-test-tls --insecure --name admin --password `kubectl get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"  -n argocd | base64 -d`

all: lint template validate kind ct adapter test-artifacts

# ============================================================================
# Vault Development Targets
# ============================================================================

vault-dev:
	@echo "🔐 Starting Vault dev server..."
	@if docker ps -a --format '{{.Names}}' | grep -q "^$(VAULT_DEV_CONTAINER)$$"; then \
		echo "⚠️  Vault container already exists. Removing..."; \
		docker rm -f $(VAULT_DEV_CONTAINER) 2>/dev/null || true; \
	fi
	@docker run -d --name $(VAULT_DEV_CONTAINER) \
		--cap-add=IPC_LOCK \
		-p 8200:8200 \
		-e VAULT_DEV_ROOT_TOKEN_ID=$(VAULT_TOKEN) \
		-e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
		hashicorp/vault:latest
	@echo "⏳ Waiting for Vault to be ready..."
	@sleep 3
	@echo "✅ Vault dev server running at $(VAULT_ADDR)"
	@echo "   Root token: $(VAULT_TOKEN)"

vault-status:
	@echo "🔍 Checking Vault status..."
	@docker exec $(VAULT_DEV_CONTAINER) vault status 2>/dev/null || echo "❌ Vault not running. Run 'make vault-dev' first."

vault-seed:
	@echo "🌱 Seeding Vault with test secrets..."
	@echo "➡️  Enabling KV v2 secrets engine..."
	@docker exec $(VAULT_DEV_CONTAINER) vault secrets enable -version=2 -path=kv kv 2>/dev/null || echo "   (KV already enabled)"
	@echo "➡️  Creating secrets for Argo CD..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/argocd/admin \
		password="admin123456" \
		bcryptHash='$$2a$$10$$rRyBkqjtRlpvrut4WyTp0eSx5qbHJUh.O7Ql0kp.VeGAHu8xfKKVi'
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/argocd/oidc \
		clientSecret="test-oidc-secret-argocd"
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/argocd/server \
		secretKey="$$(openssl rand -hex 32)"
	@echo "➡️  Creating secrets for Argo Workflows..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/workflows/artifacts \
		accessKey="minioadmin" \
		secretKey="minioadmin"
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/workflows/oidc \
		clientSecret="test-oidc-secret-workflows"
	@echo "➡️  Creating secrets for authz-adapter..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/authz \
		clientSecret="test-oidc-secret-authz"
	@echo "➡️  Creating secrets for GitHub Events..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/events/github \
		token="ghp_test_token_replace_with_real_one"
	@echo "➡️  Creating per-app S3 credentials..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/apps/nextflow-hello/s3 \
		accessKey="app1-access-key" \
		secretKey="app1-secret-key"
	@docker exec $(VAULT_DEV_CONTAINER) vault kv put kv/argo/apps/nextflow-hello-2/s3 \
		accessKey="app2-access-key" \
		secretKey="app2-secret-key"
	@echo "➡️  Enabling Kubernetes auth method..."
	@docker exec $(VAULT_DEV_CONTAINER) vault auth enable kubernetes 2>/dev/null || echo "   (Kubernetes auth already enabled)"
	@echo "✅ Vault seeded with test data"
	@echo ""
	@echo "📋 Available secrets:"
	@echo "   kv/argo/argocd/admin        - Argo CD admin credentials"
	@echo "   kv/argo/argocd/oidc         - Argo CD OIDC client secret"
	@echo "   kv/argo/argocd/server       - Argo CD server secret key"
	@echo "   kv/argo/workflows/artifacts - Workflow artifact storage credentials"
	@echo "   kv/argo/workflows/oidc      - Workflow OIDC client secret"
	@echo "   kv/argo/authz               - AuthZ adapter OIDC secret"
	@echo "   kv/argo/events/github       - GitHub webhook token"
	@echo "   kv/argo/apps/*/s3           - Per-app S3 credentials"

vault-list:
	@echo "📋 Listing all secrets in Vault..."
	@docker exec $(VAULT_DEV_CONTAINER) vault kv list -format=json kv/argo 2>/dev/null || echo "❌ No secrets found or Vault not running"

vault-get:
	@if [ -z "$(PATH)" ]; then \
		echo "❌ Usage: make vault-get PATH=kv/argo/argocd/admin"; \
		exit 1; \
	fi
	@docker exec $(VAULT_DEV_CONTAINER) vault kv get -format=json $(PATH)

vault-cleanup:
	@echo "🧹 Cleaning up Vault dev server..."
	@docker rm -f $(VAULT_DEV_CONTAINER) 2>/dev/null || true
	@echo "✅ Vault dev server removed"

vault-shell:
	@echo "🐚 Opening shell in Vault container..."
	@docker exec -it $(VAULT_DEV_CONTAINER) /bin/sh
