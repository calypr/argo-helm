#!/usr/bin/env python3
"""
Test script to validate that Vault has been seeded with all required secrets
for repoRegistrations from my-values.yaml.

This test verifies that the vault-seed Makefile target has correctly created
all necessary secrets that ExternalSecrets will reference.
"""

import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Set


class TestVaultSeeding:
    """Test suite for Vault secret seeding based on repoRegistrations."""
    
    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.repo_root = Path(__file__).parent.parent
        cls.values_file = cls.repo_root / "my-values.yaml"
        cls.vault_prefix = "kv/argo/apps"
        
        # Load repoRegistrations from my-values.yaml
        cls.repo_registrations = cls._load_repo_registrations()
    
    @classmethod
    def _load_repo_registrations(cls) -> List[Dict[str, Any]]:
        """Load repoRegistrations from my-values.yaml."""
        with open(cls.values_file, 'r') as f:
            values = yaml.safe_load(f)
        
        return values.get('repoRegistrations', [])
    
    @classmethod
    def _vault_exec(cls, cmd: str) -> str:
        """Execute a command in the Vault pod."""
        full_cmd = [
            'kubectl', 'exec', '-n', 'vault', 'vault-0', '--',
            'sh', '-c', cmd
        ]
        
        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"❌ Vault command failed: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            print("❌ Vault command timed out")
            raise
    
    @classmethod
    def _vault_key_exists(cls, path: str) -> bool:
        """Check if a Vault key exists."""
        try:
            cls._vault_exec(f'vault kv get -format=json {path}')
            return True
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def _vault_get_secret(cls, path: str) -> Dict[str, Any]:
        """Get a secret from Vault and return the data."""
        try:
            output = cls._vault_exec(f'vault kv get -format=json {path}')
            secret = json.loads(output)
            return secret.get('data', {}).get('data', {})
        except subprocess.CalledProcessError:
            return {}
    
    @classmethod
    def _extract_vault_paths(cls) -> Dict[str, Set[str]]:
        """Extract all expected Vault paths from repoRegistrations."""
        paths = {
            'github': set(),
            's3_artifact': set(),
            's3_data': set()
        }
        
        for reg in cls.repo_registrations:
            # GitHub secret paths
            if reg.get('githubSecretPath'):
                github_path = f"kv/{reg['githubSecretPath']}"
                paths['github'].add(github_path)
            
            # S3 artifact bucket paths
            if reg.get('artifactBucket', {}).get('externalSecretPath'):
                s3_path = f"kv/{reg['artifactBucket']['externalSecretPath']}"
                paths['s3_artifact'].add(s3_path)
            
            # S3 data bucket paths
            if reg.get('dataBucket', {}).get('externalSecretPath'):
                s3_path = f"kv/{reg['dataBucket']['externalSecretPath']}"
                paths['s3_data'].add(s3_path)
        
        return paths
    
    def test_vault_is_accessible(self):
        """Test that Vault is running and accessible."""
        print("\n🧪 Testing Vault accessibility...")
        
        try:
            status = self._vault_exec('vault status -format=json')
            status_data = json.loads(status)
            
            assert status_data.get('initialized') == True, "Vault is not initialized"
            assert status_data.get('sealed') == False, "Vault is sealed"
            
            print("✅ Vault is accessible and unsealed")
        except Exception as e:
            raise AssertionError(f"Vault is not accessible: {e}")
    
    def test_kv_engine_enabled(self):
        """Test that KV v2 secrets engine is enabled."""
        print("\n🧪 Testing KV secrets engine...")
        
        try:
            mounts = self._vault_exec('vault secrets list -format=json')
            mounts_data = json.loads(mounts)
            
            assert 'kv/' in mounts_data, "KV secrets engine not mounted at kv/"
            assert mounts_data['kv/']['type'] == 'kv', "KV mount is not of type kv"
            assert mounts_data['kv/']['options'].get('version') == '2', "KV engine is not version 2"
            
            print("✅ KV v2 secrets engine is enabled at kv/")
        except Exception as e:
            raise AssertionError(f"KV engine check failed: {e}")
    
    def test_github_secrets_exist(self):
        """Test that all GitHub credential secrets exist in Vault."""
        print("\n🧪 Testing GitHub credential secrets...")
        
        paths = self._extract_vault_paths()
        github_paths = paths['github']
        
        assert len(github_paths) > 0, "No GitHub secret paths found in repoRegistrations"
        
        missing_paths = []
        invalid_secrets = []
        
        for path in github_paths:
            if not self._vault_key_exists(path):
                missing_paths.append(path)
            else:
                # Verify secret has the required 'token' key
                secret_data = self._vault_get_secret(path)
                if 'token' not in secret_data:
                    invalid_secrets.append((path, "missing 'token' key"))
        
        assert len(missing_paths) == 0, (
            f"Missing GitHub secrets in Vault:\n" + 
            "\n".join(f"  - {path}" for path in missing_paths)
        )
        
        assert len(invalid_secrets) == 0, (
            f"Invalid GitHub secrets (missing required keys):\n" + 
            "\n".join(f"  - {path}: {reason}" for path, reason in invalid_secrets)
        )
        
        print(f"✅ Found {len(github_paths)} GitHub credential secrets:")
        for path in sorted(github_paths):
            print(f"   ✓ {path}")
    
    def test_s3_artifact_secrets_exist(self):
        """Test that all S3 artifact bucket credential secrets exist in Vault."""
        print("\n🧪 Testing S3 artifact bucket credential secrets...")
        
        paths = self._extract_vault_paths()
        s3_paths = paths['s3_artifact']
        
        assert len(s3_paths) > 0, "No S3 artifact secret paths found in repoRegistrations"
        
        missing_paths = []
        invalid_secrets = []
        
        for path in s3_paths:
            if not self._vault_key_exists(path):
                missing_paths.append(path)
            else:
                # Verify secret has required AWS credential keys
                secret_data = self._vault_get_secret(path)
                required_keys = {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'}
                missing_keys = required_keys - set(secret_data.keys())
                
                if missing_keys:
                    invalid_secrets.append((path, f"missing keys: {missing_keys}"))
        
        assert len(missing_paths) == 0, (
            f"Missing S3 artifact secrets in Vault:\n" + 
            "\n".join(f"  - {path}" for path in missing_paths)
        )
        
        assert len(invalid_secrets) == 0, (
            f"Invalid S3 artifact secrets (missing required keys):\n" + 
            "\n".join(f"  - {path}: {reason}" for path, reason in invalid_secrets)
        )
        
        print(f"✅ Found {len(s3_paths)} S3 artifact credential secrets:")
        for path in sorted(s3_paths):
            print(f"   ✓ {path}")
    
    def test_s3_data_secrets_exist(self):
        """Test that all S3 data bucket credential secrets exist in Vault."""
        print("\n🧪 Testing S3 data bucket credential secrets...")
        
        paths = self._extract_vault_paths()
        s3_data_paths = paths['s3_data']
        
        if len(s3_data_paths) == 0:
            print("ℹ️  No S3 data bucket secrets required (skipping)")
            return
        
        missing_paths = []
        invalid_secrets = []
        
        for path in s3_data_paths:
            if not self._vault_key_exists(path):
                missing_paths.append(path)
            else:
                # Verify secret has required AWS credential keys
                secret_data = self._vault_get_secret(path)
                required_keys = {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'}
                missing_keys = required_keys - set(secret_data.keys())
                
                if missing_keys:
                    invalid_secrets.append((path, f"missing keys: {missing_keys}"))
        
        assert len(missing_paths) == 0, (
            f"Missing S3 data bucket secrets in Vault:\n" + 
            "\n".join(f"  - {path}" for path in missing_paths)
        )
        
        assert len(invalid_secrets) == 0, (
            f"Invalid S3 data bucket secrets (missing required keys):\n" + 
            "\n".join(f"  - {path}: {reason}" for path, reason in invalid_secrets)
        )
        
        print(f"✅ Found {len(s3_data_paths)} S3 data bucket credential secrets:")
        for path in sorted(s3_data_paths):
            print(f"   ✓ {path}")
    
    def test_all_repo_registrations_have_required_secrets(self):
        """Test that each repoRegistration has all its required secrets in Vault."""
        print("\n🧪 Testing that each repoRegistration has all required secrets...")
        
        missing_by_repo = {}
        
        for reg in self.repo_registrations:
            repo_name = reg['name']
            missing_secrets = []
            
            # Check GitHub secret
            if reg.get('githubSecretPath'):
                github_path = f"kv/{reg['githubSecretPath']}"
                if not self._vault_key_exists(github_path):
                    missing_secrets.append(('github', github_path))
            
            # Check S3 artifact secret
            if reg.get('artifactBucket', {}).get('externalSecretPath'):
                s3_path = f"kv/{reg['artifactBucket']['externalSecretPath']}"
                if not self._vault_key_exists(s3_path):
                    missing_secrets.append(('s3_artifact', s3_path))
            
            # Check S3 data secret (if configured)
            if reg.get('dataBucket', {}).get('externalSecretPath'):
                s3_data_path = f"kv/{reg['dataBucket']['externalSecretPath']}"
                if not self._vault_key_exists(s3_data_path):
                    missing_secrets.append(('s3_data', s3_data_path))
            
            if missing_secrets:
                missing_by_repo[repo_name] = missing_secrets
        
        if missing_by_repo:
            error_msg = "Some repoRegistrations are missing required secrets:\n"
            for repo_name, missing in missing_by_repo.items():
                error_msg += f"\n  {repo_name}:\n"
                for secret_type, path in missing:
                    error_msg += f"    - {secret_type}: {path}\n"
            
            raise AssertionError(error_msg)
        
        print(f"✅ All {len(self.repo_registrations)} repoRegistrations have their required secrets")
    
    def test_vault_paths_match_externalsecret_templates(self):
        """Test that vault paths are formatted correctly for ExternalSecret templates."""
        print("\n🧪 Testing Vault path format compatibility with ExternalSecret templates...")
        
        paths = self._extract_vault_paths()
        all_paths = set()
        all_paths.update(paths['github'])
        all_paths.update(paths['s3_artifact'])
        all_paths.update(paths['s3_data'])
        
        # ExternalSecret templates expect paths in format: kv/<path>
        # where <path> is what's in externalSecretPath/githubSecretPath
        for path in all_paths:
            assert path.startswith('kv/'), f"Path {path} doesn't start with kv/"
            assert path.startswith('kv/argo/apps/'), (
                f"Path {path} doesn't follow expected pattern kv/argo/apps/..."
            )
        
        print(f"✅ All {len(all_paths)} Vault paths follow the correct format")


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
    import sys
    sys.exit(main())
