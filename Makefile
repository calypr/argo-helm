# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter test-artifacts all vault-dev vault-seed vault-cleanup vault-status

S3_ENABLED           ?= true
S3_ACCESS_KEY_ID     ?=
S3_SECRET_ACCESS_KEY ?=
S3_BUCKET            ?=

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
		token="ghp_test_token_replace_with_real_one"
	@echo "➡️  Creating per-app S3 credentials..."
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello/s3 \
		accessKey="app1-access-key" \
		secretKey="app1-secret-key"
	@kubectl exec -n vault vault-0 -- vault kv put kv/argo/apps/nextflow-hello-2/s3 \
		accessKey="app2-access-key" \
		secretKey="app2-secret-key"
	@echo "➡️  Enabling Kubernetes auth method..."
	@kubectl exec -n vault vault-0 -- vault auth enable kubernetes 2>/dev/null || echo "   (Kubernetes auth already enabled)"
	@echo "➡️  Configuring Kubernetes auth..."
	@kubectl exec -n vault vault-0 -- sh -c 'vault write auth/kubernetes/config \
		kubernetes_host="https://$$KUBERNETES_PORT_443_TCP_ADDR:443"' 2>/dev/null || echo "   (Kubernetes auth already configured)"
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

vault-shell:
	@echo "🐚 Opening shell in Vault pod..."
	@kubectl exec -it -n vault vault-0 -- /bin/sh
