{{/*
Expand the name of the chart.
*/}}
{{- define "ingress-authz-overlay.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ingress-authz-overlay.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ingress-authz-overlay.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ingress-authz-overlay.labels" -}}
helm.sh/chart: {{ include "ingress-authz-overlay.chart" . }}
{{ include "ingress-authz-overlay.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ingress-authz-overlay.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ingress-authz-overlay.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the auth-url for NGINX ingress external auth.
*/}}
{{- define "ingress-authz-overlay.authUrl" -}}
{{- $adapter := .Values.ingressAuthzOverlay.authzAdapter -}}
http://{{ $adapter.serviceName }}.{{ $adapter.namespace }}.svc.cluster.local:{{ $adapter.port }}{{ $adapter.path }}
{{- end }}

{{/*
Create common ingress annotations for NGINX external auth.
*/}}
{{- define "ingress-authz-overlay.authAnnotations" -}}
nginx.ingress.kubernetes.io/auth-url: {{ include "ingress-authz-overlay.authUrl" . | quote }}
nginx.ingress.kubernetes.io/auth-method: "GET"
nginx.ingress.kubernetes.io/auth-signin: {{ .Values.ingressAuthzOverlay.authzAdapter.signinUrl | quote }}
nginx.ingress.kubernetes.io/auth-response-headers: {{ .Values.ingressAuthzOverlay.authzAdapter.responseHeaders | quote }}
nginx.ingress.kubernetes.io/auth-snippet: |
  proxy_set_header Authorization $http_authorization;
  proxy_set_header X-Original-URI $request_uri;
  proxy_set_header X-Original-Method $request_method;
  proxy_set_header X-Forwarded-Host $host;
{{- end }}

{{/*
Create TLS configuration for ingress.
*/}}
{{- define "ingress-authz-overlay.tlsConfig" -}}
{{- if .Values.ingressAuthzOverlay.tls.enabled }}
tls:
  - hosts:
      - {{ .Values.ingressAuthzOverlay.host | quote }}
    secretName: {{ .Values.ingressAuthzOverlay.tls.secretName | quote }}
{{- end }}
{{- end }}

{{/*
Create the ingress name for a route.
*/}}
{{- define "ingress-authz-overlay.ingressName" -}}
{{- $routeName := .routeName -}}
ingress-authz-{{ $routeName }}
{{- end }}
