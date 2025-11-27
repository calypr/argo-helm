#!/usr/bin/env python3
"""
Test script to validate Helm template rendering for GitHub App authentication.

This test validates that the Helm chart correctly generates:
- ExternalSecret for GitHub App credentials (when using Vault)
- Kubernetes Secret for GitHub App repo-creds (when not using External Secrets)
"""

import subprocess
import yaml
import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any


class TestGitHubAppRendering:
    """Test suite for GitHub App template rendering."""
    
    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.repo_root = Path(__file__).parent.parent
        cls.chart_dir = cls.repo_root / "helm" / "argo-stack"
        cls.chart_yaml = cls.chart_dir / "Chart.yaml"
        cls.chart_yaml_backup = cls.chart_dir / "Chart.yaml.backup"
        
    @classmethod
    def _disable_dependencies(cls):
        """Temporarily disable chart dependencies for testing."""
        shutil.copy(cls.chart_yaml, cls.chart_yaml_backup)
        
        with open(cls.chart_yaml, 'r') as f:
            content = f.read()
        
        # Comment out dependencies
        lines = content.split('\n')
        new_lines = []
        in_dependencies = False
        for line in lines:
            if line.strip().startswith('dependencies:'):
                in_dependencies = True
                new_lines.append('# ' + line)
            elif in_dependencies and (line.startswith('  -') or line.startswith('    ')):
                new_lines.append('# ' + line)
            else:
                if in_dependencies and not line.strip().startswith('#') and line.strip():
                    in_dependencies = False
                new_lines.append(line)
        
        with open(cls.chart_yaml, 'w') as f:
            f.write('\n'.join(new_lines))
    
    @classmethod
    def _restore_chart_yaml(cls):
        """Restore original Chart.yaml."""
        if cls.chart_yaml_backup.exists():
            shutil.move(cls.chart_yaml_backup, cls.chart_yaml)
    
    def _render_template(self, set_values: List[str], show_only: str = None) -> str:
        """Run helm template with specified values and return output."""
        self._disable_dependencies()
        
        try:
            cmd = [
                'helm', 'template', 'argo-stack', str(self.chart_dir),
                '--values', str(self.chart_dir / 'values.yaml'),
            ]
            
            for val in set_values:
                cmd.extend(['--set', val])
            
            if show_only:
                cmd.extend(['--show-only', show_only])
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                # Don't check=True because empty templates return non-zero
            )
            # If the template is not found (empty output case), return empty string
            if result.returncode != 0:
                if "could not find template" in result.stderr:
                    return ""
                print(f"Helm template failed: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            return result.stdout
        finally:
            self._restore_chart_yaml()
    
    def _parse_yaml_documents(self, yaml_content: str) -> List[Dict[str, Any]]:
        """Parse YAML content into separate documents."""
        if not yaml_content:
            return []
        
        documents = []
        for doc in yaml.safe_load_all(yaml_content):
            if doc:
                documents.append(doc)
        return documents

    def test_github_app_disabled_by_default(self):
        """Test that GitHub App resources are not created when disabled."""
        print("\n🧪 Testing GitHub App is disabled by default...")
        
        output = self._render_template(
            set_values=[],
            show_only='templates/eso/externalsecret-github-app.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 0, "ExternalSecret should not be created when githubApp.enabled=false"
        
        output = self._render_template(
            set_values=[],
            show_only='templates/argocd/github-app-repo-creds.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 0, "Secret should not be created when githubApp.enabled=false"
        
        print("✅ GitHub App resources not created when disabled")

    def test_github_app_externalsecret_created(self):
        """Test that ExternalSecret is created when GitHub App is enabled with ESO."""
        print("\n🧪 Testing GitHub App ExternalSecret creation...")
        
        output = self._render_template(
            set_values=[
                'githubApp.enabled=true',
                'githubApp.appId=123456',
                'githubApp.installationId=12345678',
                'githubApp.repoCreds.url=https://github.com/test-org',
                'externalSecrets.enabled=true',
                'githubApp.privateKey.externalSecrets.enabled=true',
            ],
            show_only='templates/eso/externalsecret-github-app.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 1, f"Expected 1 ExternalSecret, got {len(docs)}"
        
        es = docs[0]
        assert es['kind'] == 'ExternalSecret', "Expected ExternalSecret kind"
        assert es['metadata']['name'] == 'argocd-github-app-repo-creds', "Incorrect secret name"
        assert es['metadata']['namespace'] == 'argocd', "Incorrect namespace"
        assert es['metadata']['labels']['secret-type'] == 'github-app', "Missing github-app label"
        
        # Verify data mappings
        data = es['spec']['data']
        assert len(data) == 3, "Expected 3 data mappings (appId, installationId, privateKey)"
        
        secret_keys = [d['secretKey'] for d in data]
        assert 'appId' in secret_keys, "Missing appId mapping"
        assert 'installationId' in secret_keys, "Missing installationId mapping"
        assert 'privateKey' in secret_keys, "Missing privateKey mapping"
        
        # Verify template creates correct secret data
        template = es['spec']['target']['template']
        assert template['data']['url'] == 'https://github.com/test-org', "Incorrect URL in template"
        assert template['data']['type'] == 'git', "Incorrect type in template"
        assert 'githubAppID' in template['data'], "Missing githubAppID in template"
        assert 'githubAppInstallationID' in template['data'], "Missing githubAppInstallationID in template"
        assert 'githubAppPrivateKey' in template['data'], "Missing githubAppPrivateKey in template"
        
        print("✅ GitHub App ExternalSecret created correctly")

    def test_github_app_secret_created_without_eso(self):
        """Test that Secret is created when GitHub App is enabled without ESO."""
        print("\n🧪 Testing GitHub App Secret creation (without ESO)...")
        
        output = self._render_template(
            set_values=[
                'githubApp.enabled=true',
                'githubApp.appId=123456',
                'githubApp.installationId=12345678',
                'githubApp.repoCreds.url=https://github.com/test-org',
                'externalSecrets.enabled=false',
            ],
            show_only='templates/argocd/github-app-repo-creds.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 1, f"Expected 1 Secret, got {len(docs)}"
        
        secret = docs[0]
        assert secret['kind'] == 'Secret', "Expected Secret kind"
        assert secret['metadata']['name'] == 'argocd-github-app-repo-creds', "Incorrect secret name"
        assert secret['metadata']['namespace'] == 'argocd', "Incorrect namespace"
        
        # Verify labels
        labels = secret['metadata']['labels']
        assert labels['argocd.argoproj.io/secret-type'] == 'repo-creds', "Missing repo-creds label"
        
        # Verify stringData
        string_data = secret['stringData']
        assert string_data['url'] == 'https://github.com/test-org', "Incorrect URL"
        assert string_data['type'] == 'git', "Incorrect type"
        assert string_data['githubAppID'] == '123456', "Incorrect appId"
        assert string_data['githubAppInstallationID'] == '12345678', "Incorrect installationId"
        
        print("✅ GitHub App Secret created correctly (without ESO)")

    def test_github_app_no_duplicate_secrets(self):
        """Test that Secret is NOT created when ExternalSecret is being used."""
        print("\n🧪 Testing no duplicate secrets when using ESO...")
        
        output = self._render_template(
            set_values=[
                'githubApp.enabled=true',
                'githubApp.appId=123456',
                'githubApp.installationId=12345678',
                'githubApp.repoCreds.url=https://github.com/test-org',
                'externalSecrets.enabled=true',
                'githubApp.privateKey.externalSecrets.enabled=true',
            ],
            show_only='templates/argocd/github-app-repo-creds.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 0, "Secret should not be created when using ExternalSecret"
        
        print("✅ No duplicate secrets when using ESO")

    def test_github_app_custom_secret_name(self):
        """Test that custom secret name is used correctly."""
        print("\n🧪 Testing custom secret name...")
        
        output = self._render_template(
            set_values=[
                'githubApp.enabled=true',
                'githubApp.appId=123456',
                'githubApp.installationId=12345678',
                'githubApp.repoCreds.url=https://github.com/test-org',
                'githubApp.repoCreds.secretName=custom-github-app-secret',
                'externalSecrets.enabled=true',
                'githubApp.privateKey.externalSecrets.enabled=true',
            ],
            show_only='templates/eso/externalsecret-github-app.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 1, f"Expected 1 ExternalSecret, got {len(docs)}"
        
        es = docs[0]
        assert es['metadata']['name'] == 'custom-github-app-secret', "Custom secret name not used"
        assert es['spec']['target']['name'] == 'custom-github-app-secret', "Custom target name not used"
        
        print("✅ Custom secret name applied correctly")

    def test_github_app_custom_vault_path(self):
        """Test that custom Vault path is used correctly."""
        print("\n🧪 Testing custom Vault path...")
        
        output = self._render_template(
            set_values=[
                'githubApp.enabled=true',
                'githubApp.appId=123456',
                'githubApp.installationId=12345678',
                'githubApp.repoCreds.url=https://github.com/test-org',
                'githubApp.privateKey.externalSecrets.path=custom/path/github-app',
                'externalSecrets.enabled=true',
                'githubApp.privateKey.externalSecrets.enabled=true',
            ],
            show_only='templates/eso/externalsecret-github-app.yaml'
        )
        
        docs = self._parse_yaml_documents(output)
        assert len(docs) == 1, f"Expected 1 ExternalSecret, got {len(docs)}"
        
        es = docs[0]
        data = es['spec']['data']
        
        for item in data:
            assert 'custom/path/github-app' in item['remoteRef']['key'], \
                f"Custom Vault path not used in {item['secretKey']}"
        
        print("✅ Custom Vault path applied correctly")


def main():
    """Run all tests and report results."""
    import pytest
    
    exit_code = pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes'
    ])
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
