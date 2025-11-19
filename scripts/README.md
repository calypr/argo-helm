# scripts/ README

Overview
- Small collection of debugging helpers for troubleshooting Vault + External Secrets (ExternalSecrets operator) integrations used by this repo.
- Each script runs a few kubectl / vault commands to surface common problems (policies, auth config, ClusterSecretStore / ExternalSecret objects, service account, and external-secrets logs).

Files
- debug-git-secret.sh
  - Purpose: Debug a GitHub-related ExternalSecret / External-Secrets flow.
  - Actions:
    - Prints commands (set -x)
    - Reads Vault policy `argo-stack`
    - Reads Vault Kubernetes auth config
    - Prints ClusterSecretStore(s)
    - Prints serviceaccount `eso-vault-auth` in namespace `external-secrets-system`
    - Prints ExternalSecret `github-secret` in namespace `argo-events`
    - Tails External-Secrets controller logs and shows the most recent github-related line
- debug-s3-secret.sh
  - Purpose: Debug an S3 credentials ExternalSecret flow.
  - Actions:
    - Same basic checks as debug-git-secret.sh
    - Shows ExternalSecret `s3-credentials` in namespace `wf-poc`
    - Tails External-Secrets controller logs filtering for `s3-credentials`

Prerequisites
- kubectl configured to talk to the target cluster and with permission to:
  - exec into the Vault pod
  - get/list ClusterSecretStore, serviceaccount, externalsecret
  - view logs for the external-secrets controller
- vault binary available in the Vault pod's image (scripts exec into the pod and run `vault ...`)
- Pod names, namespaces, and ExternalSecret names used by the scripts must match your cluster (see notes below)

Usage
1. Make executable (if needed)
   chmod +x scripts/*.sh

2. Run a script:
   ./scripts/debug-git-secret.sh

Notes / Configuration
- Hardcoded values in the scripts:
  - Vault namespace: `vault` and pod name `vault-0`
  - External Secrets controller namespace: `external-secrets-system`
  - ServiceAccount: `eso-vault-auth`
  - ExternalSecret names / namespaces:
    - `github-secret` in `argo-events` (debug-git-secret.sh)
    - `s3-credentials` in `wf-poc` (debug-s3-secret.sh)
- If your cluster uses different names, edit the scripts or create wrapper scripts that export environment variables and replace hardcoded values.
- The scripts use set -x to print commands before executing them so you can see exactly what's being run.

Security / Safety
- These scripts exec into the Vault pod and run `vault` commands; they will expose command output to your terminal. Do not run on untrusted or production clusters without understanding the effects.
- They only perform read/list/log operations; they do not create or delete resources.

Troubleshooting
- If `kubectl exec` fails, verify the Vault pod name and namespace and that your kubeconfig is correct.
- If the `vault` binary is missing in the pod, run the `vault` commands from a machine that has Vault CLI access or adjust the scripts to use the Vault HTTP API.
- If logs are empty or do not include the expected lines, increase the `--tail` count or remove the `grep`/`tail` pipeline while debugging.

Contributing
- Minor fixes or additional helper scripts are welcome. Keep scripts idempotent, readable, and document any new hardcoded names or assumptions.

