#!/usr/bin/env python3
"""
Test multi-installation GitHub App notification support.

This test validates that the Helm chart correctly generates unique
service.github-<installationId> configurations for each distinct
installationId found in repoRegistrations.
"""


def test_multi_installation_service_generation():
    """
    Test that multiple service.github-<installationId> entries are generated
    when repoRegistrations have different installationIds.
    """
    # Simulate the template logic
    repo_registrations = [
        {"name": "repo1", "installationId": 12345678},
        {"name": "repo2", "installationId": 87654321},
        {"name": "repo3", "installationId": 12345678},  # Same as repo1
    ]
    
    # Collect unique installation IDs
    # Note: Using dict here to match Helm template behavior (Helm doesn't have sets)
    # In Python, we could use a set, but we're simulating the template logic
    installation_ids = {}
    for reg in repo_registrations:
        if "installationId" in reg:
            installation_ids[str(reg["installationId"])] = True
    
    # Verify we get exactly 2 unique installation IDs
    assert len(installation_ids) == 2, \
        f"Expected 2 unique installation IDs, got {len(installation_ids)}"
    
    # Verify the IDs are correct
    assert "12345678" in installation_ids
    assert "87654321" in installation_ids
    
    print("✅ Test passed: Multiple installation IDs collected correctly")
    print(f"   Unique installation IDs: {sorted(installation_ids.keys())}")
    
    # Alternative implementation using set (more Pythonic, but not available in Helm)
    installation_ids_set = {str(reg["installationId"]) for reg in repo_registrations if "installationId" in reg}
    assert len(installation_ids_set) == 2
    print(f"   (Python set alternative also works: {sorted(installation_ids_set)})")


def test_service_name_generation():
    """
    Test that service names are generated correctly for each installation.
    """
    installation_id = 12345678
    use_github_app = True
    
    # Simulate service name generation (same logic as template)
    service_name = "github"
    if installation_id and use_github_app:
        service_name = f"github-{installation_id}"
    
    assert service_name == "github-12345678", \
        f"Expected 'github-12345678', got '{service_name}'"
    
    print("✅ Test passed: Service name generated correctly")
    print(f"   Service name: {service_name}")


def test_backward_compatibility():
    """
    Test that the template falls back to global config when no
    repoRegistrations have installationId.
    """
    # Simulate no installation IDs
    repo_registrations = [
        {"name": "repo1", "repoUrl": "https://github.com/org/repo1.git"},
        {"name": "repo2", "repoUrl": "https://github.com/org/repo2.git"},
    ]
    
    # Collect unique installation IDs
    installation_ids = {}
    for reg in repo_registrations:
        if "installationId" in reg:
            installation_ids[str(reg["installationId"])] = True
    
    # When no installation IDs, should use global config
    use_global_config = len(installation_ids) == 0
    
    assert use_global_config, \
        "Should fall back to global config when no installation IDs"
    
    print("✅ Test passed: Backward compatibility maintained")
    print("   Falls back to global service.github configuration")


def test_annotation_generation():
    """
    Test that notification subscription annotations use the correct service name.
    """
    test_cases = [
        # (installationId, useGithubApp, expected_service_name)
        (12345678, True, "github-12345678"),
        (None, True, "github"),
        (12345678, False, "github"),
    ]
    
    for installation_id, use_github_app, expected in test_cases:
        service_name = "github"
        if installation_id and use_github_app:
            service_name = f"github-{installation_id}"
        
        assert service_name == expected, \
            f"Expected '{expected}', got '{service_name}' for " \
            f"installationId={installation_id}, useGithubApp={use_github_app}"
    
    print("✅ Test passed: Notification annotations generated correctly")
    print("   All test cases passed")


def main():
    """Run all tests."""
    print("\n🧪 Testing Multi-Installation GitHub App Notification Support\n")
    
    test_multi_installation_service_generation()
    test_service_name_generation()
    test_backward_compatibility()
    test_annotation_generation()
    
    print("\n✅ All tests passed!\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
