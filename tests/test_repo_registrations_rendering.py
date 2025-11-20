#!/usr/bin/env python3
"""
Test script to validate Helm template rendering with repoRegistrations.

This test validates that the Helm chart correctly generates all expected
resources from the repoRegistrations configuration in my-values.yaml:
- ArgoCD Applications
- ExternalSecrets for GitHub and S3 credentials
- Artifact Repository ConfigMaps
- EventSource for GitHub webhooks
"""

import subprocess
import yaml
import os
import sys
from pathlib import Path
from typing import List, Dict, Any


class TestRepoRegistrationsRendering:
    """Test suite for repoRegistrations template rendering."""
    
    @classmethod
    def setup_class(cls):
        """Set up test environment and render templates."""
        cls.repo_root = Path(__file__).parent.parent
        cls.chart_dir = cls.repo_root / "helm" / "argo-stack"
        cls.values_file = cls.repo_root / "my-values.yaml"
        cls.rendered_output = None
        
        # Set required environment variables
        os.environ.setdefault('GITHUB_PAT', 'dummy-github-pat-token')
        os.environ.setdefault('ARGOCD_SECRET_KEY', 'dummy-argocd-secret-key-12345678')
        os.environ.setdefault('ARGO_HOSTNAME', 'localhost')
        os.environ.setdefault('GITHUB_USERNAME', 'dummy-user')
        os.environ.setdefault('GITHUB_TOKEN', 'dummy-token')
        os.environ.setdefault('S3_ENABLED', 'true')
        os.environ.setdefault('S3_BUCKET', 'test-bucket')
        os.environ.setdefault('S3_REGION', 'us-west-2')
        os.environ.setdefault('S3_HOSTNAME', 's3.us-west-2.amazonaws.com')
        os.environ.setdefault('S3_ACCESS_KEY_ID', 'dummy-access-key')
        os.environ.setdefault('S3_SECRET_ACCESS_KEY', 'dummy-secret-key')
        
        # Render the template
        cls._render_template()
    
    @classmethod
    def _render_template(cls):
        """Run helm template and capture output."""
        print("\n🔧 Rendering Helm templates...")
        
        cmd = [
            'helm', 'template', 'argo-stack', str(cls.chart_dir),
            '--values', str(cls.values_file),
            '--set-string', f'events.github.secret.tokenValue={os.environ["GITHUB_PAT"]}',
            '--set-string', f'argo-cd.configs.secret.extra.server\\.secretkey={os.environ["ARGOCD_SECRET_KEY"]}',
            '--set-string', f'events.github.webhook.ingress.hosts[0]={os.environ["ARGO_HOSTNAME"]}',
            '--set-string', f'events.github.webhook.url=http://{os.environ["ARGO_HOSTNAME"]}:12000',
            '--set-string', f's3.enabled={os.environ["S3_ENABLED"]}',
            '--set-string', f's3.accessKeyId={os.environ["S3_ACCESS_KEY_ID"]}',
            '--set-string', f's3.secretAccessKey={os.environ["S3_SECRET_ACCESS_KEY"]}',
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cls.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            cls.rendered_output = result.stdout
            print("✅ Templates rendered successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to render templates: {e.stderr}")
            raise
    
    @classmethod
    def _parse_yaml_documents(cls) -> List[Dict[str, Any]]:
        """Parse the rendered YAML into separate documents."""
        if not cls.rendered_output:
            return []
        
        documents = []
        for doc in yaml.safe_load_all(cls.rendered_output):
            if doc:  # Skip empty documents
                documents.append(doc)
        return documents
    
    @classmethod
    def _filter_by_kind(cls, kind: str) -> List[Dict[str, Any]]:
        """Filter documents by Kubernetes kind."""
        docs = cls._parse_yaml_documents()
        return [doc for doc in docs if doc.get('kind') == kind]
    
    @classmethod
    def _filter_by_label(cls, documents: List[Dict[str, Any]], label_key: str, label_value: str) -> List[Dict[str, Any]]:
        """Filter documents by a specific label."""
        return [
            doc for doc in documents
            if doc.get('metadata', {}).get('labels', {}).get(label_key) == label_value
        ]
    
    def test_argocd_applications_count(self):
        """Test that exactly 3 ArgoCD Applications are generated."""
        print("\n🧪 Testing ArgoCD Applications count...")
        
        applications = self._filter_by_kind('Application')
        repo_reg_apps = self._filter_by_label(applications, 'source', 'repo-registration')
        
        expected_count = 3
        actual_count = len(repo_reg_apps)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} ArgoCD Applications from repoRegistrations, "
            f"but found {actual_count}"
        )
        print(f"✅ Found {actual_count} ArgoCD Applications")
    
    def test_argocd_applications_names(self):
        """Test that ArgoCD Applications have correct names."""
        print("\n🧪 Testing ArgoCD Applications names...")
        
        applications = self._filter_by_kind('Application')
        repo_reg_apps = self._filter_by_label(applications, 'source', 'repo-registration')
        
        expected_names = {
            'nextflow-hello-project',
            'genomics-variant-calling',
            'local-dev-workflows'
        }
        
        actual_names = {app['metadata']['name'] for app in repo_reg_apps}
        
        assert actual_names == expected_names, (
            f"Expected Applications {expected_names}, but found {actual_names}"
        )
        print(f"✅ Applications have correct names: {actual_names}")
    
    def test_external_secrets_count(self):
        """Test that exactly 7 ExternalSecrets are generated."""
        print("\n🧪 Testing ExternalSecrets count...")
        
        external_secrets = self._filter_by_kind('ExternalSecret')
        repo_reg_secrets = self._filter_by_label(external_secrets, 'source', 'repo-registration')
        
        expected_count = 7  # 3 GitHub + 4 S3 (3 artifact + 1 data bucket)
        actual_count = len(repo_reg_secrets)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} ExternalSecrets from repoRegistrations, "
            f"but found {actual_count}"
        )
        print(f"✅ Found {actual_count} ExternalSecrets")
    
    def test_external_secrets_github_credentials(self):
        """Test that 3 GitHub credential ExternalSecrets are generated."""
        print("\n🧪 Testing GitHub credential ExternalSecrets...")
        
        external_secrets = self._filter_by_kind('ExternalSecret')
        repo_reg_secrets = self._filter_by_label(external_secrets, 'source', 'repo-registration')
        github_secrets = self._filter_by_label(repo_reg_secrets, 'secret-type', 'github-credentials')
        
        expected_count = 3
        actual_count = len(github_secrets)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} GitHub credential ExternalSecrets, "
            f"but found {actual_count}"
        )
        
        expected_names = {
            'github-secret-nextflow-hello',
            'github-secret-genomics',
            'github-secret-internal-dev'
        }
        actual_names = {secret['metadata']['name'] for secret in github_secrets}
        
        assert actual_names == expected_names, (
            f"Expected GitHub secrets {expected_names}, but found {actual_names}"
        )
        print(f"✅ Found {actual_count} GitHub credential ExternalSecrets with correct names")
    
    def test_external_secrets_s3_credentials(self):
        """Test that 4 S3 credential ExternalSecrets are generated."""
        print("\n🧪 Testing S3 credential ExternalSecrets...")
        
        external_secrets = self._filter_by_kind('ExternalSecret')
        repo_reg_secrets = self._filter_by_label(external_secrets, 'source', 'repo-registration')
        
        # Filter for both s3-credentials and s3-data-credentials types
        s3_secrets = [
            secret for secret in repo_reg_secrets
            if secret.get('metadata', {}).get('labels', {}).get('secret-type', '').startswith('s3-')
        ]
        
        expected_count = 4  # 3 artifact buckets + 1 data bucket
        actual_count = len(s3_secrets)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} S3 credential ExternalSecrets, "
            f"but found {actual_count}"
        )
        
        expected_names = {
            's3-credentials-nextflow-hello-project',
            's3-credentials-genomics-variant-calling',
            's3-data-credentials-genomics-variant-calling',  # data bucket
            's3-credentials-local-dev-workflows'
        }
        actual_names = {secret['metadata']['name'] for secret in s3_secrets}
        
        assert actual_names == expected_names, (
            f"Expected S3 secrets {expected_names}, but found {actual_names}"
        )
        print(f"✅ Found {actual_count} S3 credential ExternalSecrets with correct names")
    
    def test_artifact_repository_configmaps_count(self):
        """Test that exactly 3 Artifact Repository ConfigMaps are generated."""
        print("\n🧪 Testing Artifact Repository ConfigMaps count...")
        
        configmaps = self._filter_by_kind('ConfigMap')
        repo_reg_cms = self._filter_by_label(configmaps, 'source', 'repo-registration')
        
        expected_count = 3
        actual_count = len(repo_reg_cms)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} Artifact Repository ConfigMaps from repoRegistrations, "
            f"but found {actual_count}"
        )
        print(f"✅ Found {actual_count} Artifact Repository ConfigMaps")
    
    def test_artifact_repository_configmaps_s3_config(self):
        """Test that Artifact Repository ConfigMaps have correct S3 configurations."""
        print("\n🧪 Testing Artifact Repository ConfigMaps S3 configurations...")
        
        configmaps = self._filter_by_kind('ConfigMap')
        repo_reg_cms = self._filter_by_label(configmaps, 'source', 'repo-registration')
        
        # Test nextflow-hello-project ConfigMap
        nextflow_cm = next(
            (cm for cm in repo_reg_cms if cm['metadata']['name'] == 'argo-artifacts-nextflow-hello-project'),
            None
        )
        assert nextflow_cm is not None, "ConfigMap for nextflow-hello-project not found"
        
        artifact_repo = yaml.safe_load(nextflow_cm['data']['artifactRepository'])
        assert artifact_repo['s3']['bucket'] == 'research-team-1-artifacts', "Incorrect bucket"
        assert artifact_repo['s3']['keyPrefix'] == 'workflows/', "Incorrect keyPrefix"
        assert artifact_repo['s3']['endpoint'] == 'https://s3.us-west-2.amazonaws.com', "Incorrect endpoint"
        assert artifact_repo['s3']['region'] == 'us-west-2', "Incorrect region"
        assert artifact_repo['s3']['insecure'] == False, "Incorrect insecure flag"
        assert 'pathStyle' not in artifact_repo['s3'] or artifact_repo['s3'].get('pathStyle') == False, "Incorrect pathStyle"
        
        print("✅ nextflow-hello-project ConfigMap has correct S3 config")
        
        # Test genomics-variant-calling ConfigMap
        genomics_cm = next(
            (cm for cm in repo_reg_cms if cm['metadata']['name'] == 'argo-artifacts-genomics-variant-calling'),
            None
        )
        assert genomics_cm is not None, "ConfigMap for genomics-variant-calling not found"
        
        artifact_repo = yaml.safe_load(genomics_cm['data']['artifactRepository'])
        assert artifact_repo['s3']['bucket'] == 'genomics-workflow-artifacts', "Incorrect bucket"
        
        print("✅ genomics-variant-calling ConfigMap has correct S3 config")
        
        # Test local-dev-workflows ConfigMap (MinIO with pathStyle)
        local_dev_cm = next(
            (cm for cm in repo_reg_cms if cm['metadata']['name'] == 'argo-artifacts-local-dev-workflows'),
            None
        )
        assert local_dev_cm is not None, "ConfigMap for local-dev-workflows not found"
        
        artifact_repo = yaml.safe_load(local_dev_cm['data']['artifactRepository'])
        assert artifact_repo['s3']['bucket'] == 'dev-workflow-artifacts', "Incorrect bucket"
        assert artifact_repo['s3']['endpoint'] == 'https://minio.storage.local:9000', "Incorrect endpoint"
        assert artifact_repo['s3']['insecure'] == True, "Incorrect insecure flag"
        assert artifact_repo['s3']['pathStyle'] == True, "pathStyle should be True for MinIO"
        
        print("✅ local-dev-workflows ConfigMap has correct S3 config (MinIO)")
    
    def test_eventsource_count(self):
        """Test that exactly 1 EventSource is generated."""
        print("\n🧪 Testing EventSource count...")
        
        eventsources = self._filter_by_kind('EventSource')
        repo_reg_eventsources = self._filter_by_label(eventsources, 'source', 'repo-registration')
        
        expected_count = 1
        actual_count = len(repo_reg_eventsources)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} EventSource from repoRegistrations, "
            f"but found {actual_count}"
        )
        print(f"✅ Found {actual_count} EventSource")
    
    def test_eventsource_webhook_configurations(self):
        """Test that EventSource has all 3 repository webhook configurations."""
        print("\n🧪 Testing EventSource webhook configurations...")
        
        eventsources = self._filter_by_kind('EventSource')
        repo_reg_eventsources = self._filter_by_label(eventsources, 'source', 'repo-registration')
        
        assert len(repo_reg_eventsources) > 0, "No EventSource found"
        
        eventsource = repo_reg_eventsources[0]
        github_config = eventsource['spec']['github']

        # Validate that all three webhooks are present
        # Each webhook key is expected to be in the format:
        # repo_push_<repo-name-with-dashes-replaced-by-underscores>
        expected_events = {
            'repo_push_nextflow-hello-project',
            'repo_push_genomics-variant-calling',
            'repo_push_local-dev-workflows'
        }

        actual_events = set(github_config.keys())
        
        assert actual_events == expected_events, (
            f"Expected webhook events {expected_events}, but found {actual_events}"
        )
        
        # Validate nextflow-hello webhook
        nextflow_webhook = github_config['repo_push_nextflow-hello-project']
        assert nextflow_webhook['owner'] == 'bwalsh', "Incorrect owner for nextflow-hello"
        assert nextflow_webhook['repository'] == 'nextflow-hello-project', "Incorrect repository for nextflow-hello"
        assert 'push' in nextflow_webhook['events'], "Missing push event for nextflow-hello"
        assert nextflow_webhook['active'] == True, "Webhook should be active for nextflow-hello"
        
        print("✅ nextflow-hello-project webhook configured correctly")
        
        # Validate genomics webhook
        genomics_webhook = github_config['repo_push_genomics-variant-calling']
        assert genomics_webhook['owner'] == 'genomics-lab', "Incorrect owner for genomics"
        assert genomics_webhook['repository'] == 'variant-calling-pipeline', "Incorrect repository for genomics"
        
        print("✅ 'genomics-variant-calling' webhook configured correctly")
        
        # Validate local-dev webhook
        local_dev_webhook = github_config['repo_push_local-dev-workflows']
        assert local_dev_webhook['owner'] == 'internal', "Incorrect owner for local-dev"
        assert local_dev_webhook['repository'] == 'dev-workflows', "Incorrect repository for local-dev"
        
        print("✅ local-dev-workflows webhook configured correctly")

    def test_tenant_namespaces_created(self):
        """Test that per-tenant namespaces are created with correct naming pattern."""
        print("\n🧪 Testing tenant namespace creation...")
        
        namespaces = self._filter_by_kind('Namespace')
        tenant_namespaces = self._filter_by_label(namespaces, 'calypr.io/workflow-tenant', 'true')
        
        expected_count = 3
        actual_count = len(tenant_namespaces)
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} tenant namespaces, but found {actual_count}"
        )
        
        # Verify namespace naming pattern: wf-<org>-<repo>
        expected_namespaces = {
            'wf-bwalsh-nextflow-hello-project',
            'wf-genomics-lab-variant-calling-pipeline',
            'wf-internal-dev-workflows'
        }
        
        actual_namespaces = {ns['metadata']['name'] for ns in tenant_namespaces}
        
        assert actual_namespaces == expected_namespaces, (
            f"Expected namespaces {expected_namespaces}, but found {actual_namespaces}"
        )
        
        print(f"✅ Found {actual_count} tenant namespaces with correct naming pattern")

    def test_legacy_wf_poc_namespace_not_used(self):
        """Test that legacy wf-poc namespace is NOT used in tenant resources."""
        print("\n🧪 Testing that legacy wf-poc namespace is NOT used...")
        
        # Check ExternalSecrets
        external_secrets = self._filter_by_kind('ExternalSecret')
        repo_reg_secrets = self._filter_by_label(external_secrets, 'source', 'repo-registration')
        
        for secret in repo_reg_secrets:
            namespace = secret['metadata']['namespace']
            assert namespace != 'wf-poc', (
                f"ExternalSecret '{secret['metadata']['name']}' should not use legacy 'wf-poc' namespace, "
                f"but found namespace: {namespace}"
            )
        
        # Check that ArgoCD Applications point to tenant namespaces
        applications = self._filter_by_kind('Application')
        repo_reg_apps = self._filter_by_label(applications, 'source', 'repo-registration')
        
        for app in repo_reg_apps:
            dest_namespace = app['spec']['destination']['namespace']
            assert dest_namespace != 'wf-poc', (
                f"ArgoCD Application '{app['metadata']['name']}' should not deploy to legacy 'wf-poc' namespace, "
                f"but found namespace: {dest_namespace}"
            )
        
        print("✅ No tenant resources use legacy wf-poc namespace")

    def test_tenant_namespaces_have_correct_labels(self):
        """Test that tenant namespaces have required labels."""
        print("\n🧪 Testing tenant namespace labels...")
        
        namespaces = self._filter_by_kind('Namespace')
        tenant_namespaces = self._filter_by_label(namespaces, 'calypr.io/workflow-tenant', 'true')
        
        for ns in tenant_namespaces:
            labels = ns['metadata']['labels']
            
            # Check required labels
            assert 'calypr.io/workflow-tenant' in labels, f"Missing 'calypr.io/workflow-tenant' label in namespace {ns['metadata']['name']}"
            assert labels['calypr.io/workflow-tenant'] == 'true', f"Incorrect value for 'calypr.io/workflow-tenant' in {ns['metadata']['name']}"
            
            assert 'source' in labels, f"Missing 'source' label in namespace {ns['metadata']['name']}"
            assert labels['source'] == 'repo-registration', f"Incorrect 'source' label in {ns['metadata']['name']}"
            
            assert 'app.kubernetes.io/part-of' in labels, f"Missing 'app.kubernetes.io/part-of' label in namespace {ns['metadata']['name']}"
            assert labels['app.kubernetes.io/part-of'] == 'argo-stack', f"Incorrect 'app.kubernetes.io/part-of' in {ns['metadata']['name']}"
        
        print("✅ All tenant namespaces have correct labels")

    def test_tenant_rbac_resources_created(self):
        """Test that RBAC resources are created in each tenant namespace."""
        print("\n🧪 Testing tenant RBAC resources...")
        
        # Get all ServiceAccounts, Roles, and RoleBindings from tenant namespaces
        service_accounts = self._filter_by_kind('ServiceAccount')
        roles = self._filter_by_kind('Role')
        role_bindings = self._filter_by_kind('RoleBinding')
        
        # Filter for repo-registration resources
        tenant_sas = self._filter_by_label(service_accounts, 'source', 'repo-registration')
        tenant_roles = self._filter_by_label(roles, 'source', 'repo-registration')
        tenant_rbs = self._filter_by_label(role_bindings, 'source', 'repo-registration')
        
        # Expected: 1 SA per tenant (3 tenants)
        expected_sa_count = 3
        assert len(tenant_sas) == expected_sa_count, (
            f"Expected {expected_sa_count} ServiceAccounts for tenants, but found {len(tenant_sas)}"
        )
        
        # Expected: 2 Roles per tenant (workflow-executor, sensor-workflow-creator) = 6 total
        expected_role_count = 6
        assert len(tenant_roles) == expected_role_count, (
            f"Expected {expected_role_count} Roles for tenants, but found {len(tenant_roles)}"
        )
        
        # Expected: 2 RoleBindings per tenant = 6 total
        expected_rb_count = 6
        assert len(tenant_rbs) == expected_rb_count, (
            f"Expected {expected_rb_count} RoleBindings for tenants, but found {len(tenant_rbs)}"
        )
        
        # Verify ServiceAccount names
        for sa in tenant_sas:
            assert sa['metadata']['name'] == 'workflow-runner', (
                f"ServiceAccount should be named 'workflow-runner', but found {sa['metadata']['name']}"
            )
        
        print(f"✅ Found {len(tenant_sas)} ServiceAccounts, {len(tenant_roles)} Roles, and {len(tenant_rbs)} RoleBindings for tenants")


def main():
    """Run all tests and report results."""
    import pytest
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes'
    ])
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
