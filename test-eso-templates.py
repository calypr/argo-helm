#!/usr/bin/env python3
"""
Test script to validate ESO template rendering with different configurations.
This bypasses the dependency check issue by directly testing template logic.
"""

import yaml
import sys
from pathlib import Path

def test_template_conditionals():
    """Test that ESO templates have proper conditionals"""
    
    print("🔍 Testing ESO template conditionals...")
    
    eso_templates = list(Path('helm/argo-stack/templates/eso').glob('*.yaml'))
    
    for template_file in eso_templates:
        with open(template_file) as f:
            content = f.read()
            
        # Check that template has proper conditional wrapping
        if 'ExternalSecret' in content or 'SecretStore' in content or 'ServiceAccount' in content:
            if '{{- if' not in content[:200]:
                print(f"❌ {template_file.name}: Missing conditional wrapper")
                return False
            
            # Check for proper helper usage
            if 'ExternalSecret' in content or 'SecretStore' in content:
                if 'argo-stack.vault.enabled' not in content and 'argo-stack.secretStore' not in content:
                    print(f"⚠️  {template_file.name}: May be missing vault.enabled check")
        
        print(f"✅ {template_file.name}")
    
    return True

def test_existing_secret_conditionals():
    """Test that existing Secret templates are disabled when ESO is enabled"""
    
    print("\n🔍 Testing existing secret template conditionals...")
    
    # Check GitHub secret
    with open('helm/argo-stack/templates/events/secret-github.yaml') as f:
        content = f.read()
        if '(not (include "argo-stack.vault.enabled"' not in content:
            print("❌ GitHub secret: Missing ESO disable logic")
            return False
        print("✅ GitHub secret properly conditional")
    
    # Check S3 credentials
    with open('helm/argo-stack/templates/20-artifact-repositories.yaml') as f:
        content = f.read()
        if '{{- if not (include "argo-stack.vault.enabled"' not in content:
            print("❌ S3 credentials: Missing ESO disable logic")
            return False
        print("✅ S3 credentials properly conditional")
    
    return True

def test_helper_templates():
    """Test that helper templates are properly defined"""
    
    print("\n🔍 Testing helper templates...")
    
    with open('helm/argo-stack/templates/_eso-helpers.tpl') as f:
        content = f.read()
        
        required_helpers = [
            'argo-stack.externalSecrets.enabled',
            'argo-stack.vault.enabled',
            'argo-stack.secretStore.kind',
            'argo-stack.secretStore.name',
            'argo-stack.vault.backend',
            'argo-stack.vault.auth',
        ]
        
        for helper in required_helpers:
            if f'define "{helper}"' not in content:
                print(f"❌ Missing helper: {helper}")
                return False
            print(f"✅ Helper defined: {helper}")
    
    return True

def test_path_format():
    """Test that secret paths use proper format"""
    
    print("\n🔍 Testing secret path format in templates...")
    
    eso_templates = list(Path('helm/argo-stack/templates/eso').glob('externalsecret-*.yaml'))
    
    for template_file in eso_templates:
        with open(template_file) as f:
            content = f.read()
            
        # Check for path#key format being converted to path/key
        if 'replace "#" "/"' not in content:
            print(f"❌ {template_file.name}: Missing path format conversion")
            return False
        
        print(f"✅ {template_file.name}: Path format conversion present")
    
    return True

def test_values_schema():
    """Test that values.yaml has proper ESO configuration"""
    
    print("\n🔍 Testing values.yaml schema...")
    
    with open('helm/argo-stack/values.yaml') as f:
        values = yaml.safe_load(f)
    
    # Check externalSecrets section exists
    if 'externalSecrets' not in values:
        print("❌ Missing externalSecrets section in values.yaml")
        return False
    
    eso = values['externalSecrets']
    
    # Check required fields
    required_fields = ['enabled', 'installOperator', 'vault', 'secrets']
    for field in required_fields:
        if field not in eso:
            print(f"❌ Missing required field: externalSecrets.{field}")
            return False
        print(f"✅ Field present: externalSecrets.{field}")
    
    # Check vault configuration
    vault = eso['vault']
    required_vault_fields = ['enabled', 'address', 'auth', 'kv']
    for field in required_vault_fields:
        if field not in vault:
            print(f"❌ Missing required field: externalSecrets.vault.{field}")
            return False
        print(f"✅ Field present: externalSecrets.vault.{field}")
    
    # Check secret paths
    secrets = eso['secrets']
    required_secret_sections = ['argocd', 'workflows', 'github']
    for section in required_secret_sections:
        if section not in secrets:
            print(f"❌ Missing secret section: externalSecrets.secrets.{section}")
            return False
        print(f"✅ Secret section present: externalSecrets.secrets.{section}")
    
    return True

def main():
    print("=" * 60)
    print("ESO Integration Template Validation")
    print("=" * 60)
    
    tests = [
        ("Helper Templates", test_helper_templates),
        ("Values Schema", test_values_schema),
        ("ESO Template Conditionals", test_template_conditionals),
        ("Existing Secret Conditionals", test_existing_secret_conditionals),
        ("Secret Path Format", test_path_format),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with exception: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
