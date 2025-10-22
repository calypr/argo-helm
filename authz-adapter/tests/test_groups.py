"""Tests for authorization group decision logic."""

import pytest
import importlib.util
import pathlib

# Load the adapter module directly so we can call decide_groups
APP_PATH = pathlib.Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("adapter_app", str(APP_PATH))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore


def _doc(active=True, methods=("create",), service="gen3-workflow", path="/services/workflow/gen3-workflow", email="user@example.org"):
    """Helper to create test user documents."""
    return {
        "active": active,
        "authz": {
            path: [{"method": m, "service": service} for m in methods]
        },
        "email": email
    }


class TestDecideGroups:
    """Test the decide_groups function with various scenarios."""

    @pytest.mark.unit
    def test_runner_group_on_create(self):
        """Test that users with create permissions get argo-runner and argo-viewer groups."""
        doc = _doc(active=True, methods=("create",))
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_runner_group_on_wildcard(self):
        """Test that users with wildcard permissions get argo-runner group."""
        doc = _doc(active=True, methods=("*",))
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_no_runner_if_not_authorized(self):
        """Test that users without create permissions don't get argo-runner group."""
        doc = _doc(active=True, methods=("read",), service="other", path="/workspace")
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_inactive_user_denied(self):
        """Test that inactive users get no groups."""
        doc = _doc(active=False, methods=("create",))
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert groups == []

    @pytest.mark.unit
    def test_no_resource_context_permissive(self):
        """Test authorization without resource context is permissive."""
        doc = _doc(active=True, methods=("create",))
        groups = mod.decide_groups(doc)
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_non_argo_group_ignored(self):
        """Test that non-argoproj.io groups are handled permissively."""
        doc = _doc(active=True, methods=("create",))
        groups = mod.decide_groups(doc, verb="CREATE", group="apps",
                                   version="v1", resource="deployments", namespace="default")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_non_workflow_resource_ignored(self):
        """Test that non-workflow resources are handled permissively."""
        doc = _doc(active=True, methods=("create",))
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="applications", namespace="argocd")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_workflowtemplate_resource_scoped(self):
        """Test that workflowtemplates are properly scoped."""
        doc = _doc(active=True, methods=("create",))
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflowtemplates", namespace="wf-poc")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_multiple_permissions(self):
        """Test user with multiple permission types."""
        doc = {
            "active": True,
            "authz": {
                "/services/workflow/gen3-workflow": [
                    {"method": "create", "service": "gen3-workflow"},
                    {"method": "read", "service": "gen3-workflow"},
                    {"method": "update", "service": "gen3-workflow"}
                ]
            },
            "email": "user@example.org"
        }
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_empty_authz(self):
        """Test user with empty authz section."""
        doc = {
            "active": True,
            "authz": {},
            "email": "user@example.org"
        }
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_missing_authz(self):
        """Test user with missing authz section."""
        doc = {
            "active": True,
            "email": "user@example.org"
        }
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_case_sensitivity(self):
        """Test that method comparison is case-sensitive."""
        doc = _doc(active=True, methods=("CREATE",))  # uppercase
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups  # should not match uppercase CREATE
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_different_service_path(self):
        """Test authorization with different service paths."""
        doc = _doc(active=True, methods=("create",), path="/services/workflow/different-service")
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups
        assert "argo-viewer" in groups

    @pytest.mark.unit
    def test_partial_path_match(self):
        """Test that partial path matches don't grant permissions."""
        doc = _doc(active=True, methods=("create",), path="/services/workflow")
        groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                                   version="v1alpha1", resource="workflows", namespace="wf-poc")
        assert "argo-runner" not in groups
        assert "argo-viewer" in groups
