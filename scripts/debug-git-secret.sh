
set -x

kubectl exec -n vault vault-0 -- vault policy read argo-stack
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

kubectl get clustersecretstore -o yaml
kubectl get serviceaccount eso-vault-auth -n external-secrets-system -o yaml
kubectl get externalsecret github-secret  -n argo-events -o yaml
kubectl logs deploy/external-secrets --tail=100 -n external-secrets-system  | grep github | tail -1

