# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter test-artifacts all minio

# S3/MinIO configuration - defaults to in-cluster MinIO
S3_ENABLED           ?= true
S3_ACCESS_KEY_ID     ?= minioadmin
S3_SECRET_ACCESS_KEY ?= minioadmin
S3_BUCKET            ?= argo-artifacts
S3_REGION            ?= us-east-1
S3_HOSTNAME          ?= minio.minio-system.svc.cluster.local:9000


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

test-artifacts:
	./test-per-app-artifacts.sh

password:
	kubectl get secret argocd-initial-admin-secret \
          -o jsonpath="{.data.password}"  -n argocd | base64 -d; echo  #  -n argocd 

login:
	argocd login localhost:8080 --skip-test-tls --insecure --name admin --password `kubectl get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"  -n argocd | base64 -d`

all: lint template validate kind ct adapter test-artifacts
