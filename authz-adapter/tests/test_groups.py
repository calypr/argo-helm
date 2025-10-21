import importlib.util
import pathlib

# Load the adapter module directly so we can call decide_groups
APP_PATH = pathlib.Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("adapter_app", str(APP_PATH))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore

def _doc(active=True, methods=("create",), service="gen3-workflow", path="/services/workflow/gen3-workflow"):
    return {
        "active": active,
        "authz": {
            path: [{"method": m, "service": service} for m in methods]
        },
        "email": "user@example.org"
    }

def test_runner_group_on_create():
    doc = _doc(active=True, methods=("create",))
    groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                               version="v1alpha1", resource="workflows", namespace="wf-poc")
    assert "argo-runner" in groups
    assert "argo-viewer" in groups

def test_no_runner_if_not_authorized():
    doc = _doc(active=True, methods=("read",), service="other", path="/workspace")
    groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                               version="v1alpha1", resource="workflows", namespace="wf-poc")
    assert "argo-runner" not in groups
    assert "argo-viewer" in groups

def test_inactive_user_denied():
    doc = _doc(active=False, methods=("create",))
    groups = mod.decide_groups(doc, verb="CREATE", group="argoproj.io",
                               version="v1alpha1", resource="workflows", namespace="wf-poc")
    assert groups == []
