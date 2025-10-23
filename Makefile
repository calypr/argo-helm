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

deploy: kind 
	helm template argo-stack helm/argo-stack \
          --values testing-values.yaml \
          --namespace argocd > rendered.yaml
	helm upgrade --install argo-stack ./helm/argo-stack
	kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
	echo waiting for pods
	sleep 10
	kubectl wait --for=condition=Ready pod   -l app.kubernetes.io/name=argocd-server   --timeout=120s -n argocd
	echo starting port forwards
	kubectl -n default port-forward svc/argo-stack-argo-workflows-server 2746:2746 --address=0.0.0.0 &
	kubectl port-forward svc/argocd-server -n argocd 8080:443 --address=0.0.0.0 &
	echo UIs available of port 2746 and port 8080

adapter:
	cd authz-adapter && python3 -m pip install -r requirements.txt pytest && pytest -q

password:
	kubectl -n argocd get secret argocd-initial-admin-secret \
          -o jsonpath="{.data.password}" | base64 -d; echo

all: lint template validate kind ct adapter
