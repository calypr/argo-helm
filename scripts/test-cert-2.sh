set -x

# Check if ingress-nginx sees the TLS secret
kubectl get secret calypr-demo-tls -n argo-stack -o yaml | grep -A1 "tls.crt\|tls.key"

# Check ingress-nginx logs for certificate loading
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50 | grep -i "tls\|certificate\|calypr-demo"

# Access via the actual NodePort (bypasses any port forwarding issues)
curl -vI --resolve calypr-demo.ddns.net:30443:100.22.124.96 https://calypr-demo.ddns.net:30443/workflows

