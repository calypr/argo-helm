# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter test-artifacts all

deps:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	helm dependency build helm/argo-stack

lint:
	helm lint helm/argo-stack --values helm/argo-stack/values.yaml

template: deps
	helm template argo-stack helm/argo-stack \
		--values helm/argo-stack/values.yaml \
		--set-string events.github.secret.tokenValue=${GITHUB_PAT} \
		--set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000  \
		--namespace argocd > rendered.yaml

validate:
	kubeconform -strict -ignore-missing-schemas \
	  -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' \
	  -summary rendered.yaml

kind:
	kind delete cluster || true
	kind create cluster

ct: kind deps
	ct lint --config .ct.yaml --debug
	ct install --config .ct.yaml --debug --helm-extra-args "--timeout 15m"

deploy: kind deps
	@test -n "$(GITHUB_PAT)" || (echo "Error: GITHUB_PAT is undefined. Run 'export GITHUB_PAT=...' before installing" && exit 1)
	@test -n "$(ARGOCD_SECRET_KEY)" || (echo "Error: ARGOCD_SECRET_KEY is undefined. Run 'export ARGOCD_SECRET_KEY=...' before installing" && exit 1)
	@test -n "$(ARGO_HOSTNAME)" || (echo "Error: ARGO_HOSTNAME is undefined. Run 'export ARGO_HOSTNAME=...' before installing" && exit 1)
	helm upgrade --install \
		argo-stack ./helm/argo-stack -n argocd --create-namespace \
		--wait --atomic \
		--set-string events.github.secret.tokenValue=${GITHUB_PAT} \
		--set-string argo-cd.configs.secret.extra."server\.secretkey"="${ARGOCD_SECRET_KEY}" \
		--set-string events.github.webhook.ingress.hosts[0]=${ARGO_HOSTNAME} \
		--set-string events.github.webhook.url=http://${ARGO_HOSTNAME}:12000 # --debug #  --values testing-values.yaml 
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
