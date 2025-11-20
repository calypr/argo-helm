{{/*
External Secrets Operator helper templates
*/}}

{{/*
Check if External Secrets is enabled
*/}}
{{- define "argo-stack.externalSecrets.enabled" -}}
{{- .Values.externalSecrets.enabled -}}
{{- end -}}

{{/*
Check if Vault is enabled
*/}}
{{- define "argo-stack.vault.enabled" -}}
{{- and .Values.externalSecrets.enabled .Values.externalSecrets.vault.enabled -}}
{{- end -}}

{{/*
Get the SecretStore kind (SecretStore or ClusterSecretStore)
*/}}
{{- define "argo-stack.secretStore.kind" -}}
{{- if eq .Values.externalSecrets.vault.scope "cluster" -}}
ClusterSecretStore
{{- else -}}
SecretStore
{{- end -}}
{{- end -}}

{{/*
Get the SecretStore name
*/}}
{{- define "argo-stack.secretStore.name" -}}
{{- printf "%s-vault" .Release.Name -}}
{{- end -}}

{{/*
Get the SecretStore namespace (only for SecretStore, not ClusterSecretStore)
*/}}
{{- define "argo-stack.secretStore.namespace" -}}
{{- if ne .Values.externalSecrets.vault.scope "cluster" -}}
{{- .Values.externalSecrets.vault.namespace | default .Values.namespaces.argocd -}}
{{- end -}}
{{- end -}}

{{/*
Generate Vault backend configuration
*/}}
{{- define "argo-stack.vault.backend" -}}
server: {{ .Values.externalSecrets.vault.address | quote }}
path: {{ .Values.externalSecrets.vault.kv.defaultPathPrefix | quote }}
version: {{ .Values.externalSecrets.vault.kv.engineVersion | quote }}
{{- if .Values.externalSecrets.vault.caBundleSecretName }}
caBundle: {{ .Values.externalSecrets.vault.caBundleSecretKey | quote }}
caProvider:
  type: Secret
  name: {{ .Values.externalSecrets.vault.caBundleSecretName | quote }}
  key: {{ .Values.externalSecrets.vault.caBundleSecretKey | quote }}
{{- end }}
{{- end -}}

{{/*
Generate Vault auth configuration
*/}}
{{- define "argo-stack.vault.auth" -}}
{{- if eq .Values.externalSecrets.vault.auth.method "kubernetes" }}
kubernetes:
  mountPath: {{ .Values.externalSecrets.vault.auth.mount | quote }}
  role: {{ .Values.externalSecrets.vault.auth.role | quote }}
  serviceAccountRef:
    name: {{ .Values.externalSecrets.vault.auth.serviceAccountName | quote }}
    namespace: "external-secrets-system"
{{- else if eq .Values.externalSecrets.vault.auth.method "jwt" }}
jwt:
  path: {{ .Values.externalSecrets.vault.auth.mount | quote }}
  role: {{ .Values.externalSecrets.vault.auth.role | quote }}
  secretRef:
    name: {{ .Values.externalSecrets.vault.auth.serviceAccountName | quote }}
    key: "token"
{{- else if eq .Values.externalSecrets.vault.auth.method "approle" }}
appRole:
  path: {{ .Values.externalSecrets.vault.auth.mount | quote }}
  roleId: {{ .Values.externalSecrets.vault.auth.approle.roleId | quote }}
  secretRef:
    name: {{ .Values.externalSecrets.vault.auth.approle.secretRef.name | quote }}
    key: {{ .Values.externalSecrets.vault.auth.approle.secretRef.key | quote }}
{{- end }}
{{- end -}}

{{/*
Generate namespace name from repoRegistration using wf-<org>-<repo> pattern
Expects a repoRegistration object with a repoUrl field
Example: https://github.com/bwalsh/nextflow-hello-project.git -> wf-bwalsh-nextflow-hello-project
*/}}
{{- define "argo-stack.repoRegistration.namespace" -}}
{{- $repoUrl := .repoUrl -}}
{{- $cleaned := trimSuffix ".git" $repoUrl -}}
{{- $cleaned = trimPrefix "https://" $cleaned -}}
{{- $cleaned = trimPrefix "http://" $cleaned -}}
{{- $cleaned = trimPrefix "github.com/" $cleaned -}}
{{- $parts := splitList "/" $cleaned -}}
{{- if ge (len $parts) 2 -}}
{{- printf "wf-%s-%s" (index $parts 0) (index $parts 1) -}}
{{- else -}}
{{- printf "wf-%s" .name -}}
{{- end -}}
{{- end -}}
