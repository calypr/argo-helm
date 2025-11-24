# Tenant Onboarding Checklist

## Step 1: Create RepoRegistration
Add a YAML definition to cluster defining namespace, runner template, artifact repo.

## Step 2: Ensure WorkflowTemplates exist
Repository must contain:
workflows/<runner>.yaml

## Step 3: Configure GitHub webhook
POST events to URL:
https://events.<domain>/push

## Step 4: Validate namespace
kubectl get ns wf-<repo>

## Step 5: Push code and trigger workflow
A push should generate a workflow in Argo Workflows UI.
