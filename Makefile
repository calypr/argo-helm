# Convenience targets for local testing
.PHONY: deps lint template validate kind ct adapter all

deps:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	helm dependency build helm/argo-stack

lint:
	helm lint helm/argo-stack --values helm/argo-stack/values.yaml

template: deps
	helm template argo-stack helm/argo-stack \
	  --values helm/argo-stack/values.yaml \
	  --namespace argocd > rendered.yaml

validate:
	kubeconform -strict -ignore-missing-schemas \
	  -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' \
	  -summary rendered.yaml

kind:
	kind delete cluster || true
	kind create cluster

ct: deps
	ct lint --config .ct.yaml --debug
	ct install --config .ct.yaml --debug --helm-extra-args "--timeout 15m"

adapter:
	cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q

all: lint template validate kind ct adapter
