
set -x

kubectl exec -n vault vault-0 -- vault policy read argo-stack
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

kubectl get clustersecretstore -o yaml
kubectl get serviceaccount eso-vault-auth -n external-secrets-system -o yaml
kubectl get externalsecret s3-credentials -n wf-poc -o yaml
kubectl logs deploy/external-secrets --tail=100 -n external-secrets-system  | grep 's3-credentials' | tail -1

