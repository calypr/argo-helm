set -x

# Check what IP the domain resolves to
nslookup calypr-demo.ddns.net
dig calypr-demo.ddns.net +short

# Get your ingress controller's external IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# should not be in hosts file
grep calypr-demo /etc/hosts

# check cert
curl https://calypr-demo.ddns.net/tenants/login || true


