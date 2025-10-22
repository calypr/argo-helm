import os
import requests
from flask import Flask, request, make_response

FENCE_BASE = os.environ.get("FENCE_BASE", "https://calypr-dev.ohsu.edu/user")
USERINFO_URL = FENCE_BASE.rstrip("/") + "/user"
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "3.0"))
SERVICE_TOKEN = os.environ.get("FENCE_SERVICE_TOKEN", "")

app = Flask(__name__)

def decide_groups(
    doc,
    verb=None,
    group=None,
    version=None,
    resource=None,
    namespace=None,
):
    """
    Map Fence-style authz JSON into coarse-grained groups Argo/ArgoCD can use.
    Backward compatible: extra args are optional.
    If Argo resource context is provided, only grant runner for Argo resources.
    """
    groups = []
    if not doc.get("active"):
        return groups

    authz = doc.get("authz", {})
    # Default policy: grant runner if user can create gen3 workflow tasks
    has_gen3_create = any(
        (item.get("method") in ("create", "*"))
        for item in authz.get("/services/workflow/gen3-workflow", [])
    )

    # If the call includes resource context, scope the decision to Argo resources
    if group == "argoproj.io" and resource in {"workflows", "workflowtemplates"}:
        if has_gen3_create:
            groups.append("argo-runner")
    else:
        # No resource context provided: be permissive with the same rule
        if has_gen3_create:
            groups.append("argo-runner")

    # Everyone active gets viewer
    groups.append("argo-viewer")
    return groups

def fetch_user_doc(auth_header):
    headers = {}
    if auth_header and auth_header.lower().startswith("bearer "):
        headers["Authorization"] = auth_header
    elif SERVICE_TOKEN:
        headers["Authorization"] = "Bearer " + SERVICE_TOKEN
    else:
        return None, "no token"
    
    try:
        r = requests.get(USERINFO_URL, headers=headers, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, f"userinfo status {r.status_code}"
        return r.json(), None
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection error"
    except requests.exceptions.RequestException as e:
        return None, f"request error: {e}"
    except Exception as e:
        return None, f"unexpected error: {e}"

@app.route("/check", methods=["GET"])
def check():
    auth = request.headers.get("Authorization", "")
    doc, err = fetch_user_doc(auth)
    if err or not doc:
        return make_response(f"authz fetch failed: {err}", 401)
    email = doc.get("email") or doc.get("name") or doc.get("username") or "unknown"
    groups = decide_groups(doc)
    if not groups:
        return make_response("forbidden", 403)
    resp = make_response("", 200)
    resp.headers["X-Auth-Request-User"] = email
    resp.headers["X-Auth-Request-Email"] = email
    resp.headers["X-Auth-Request-Groups"] = ",".join(groups)
    resp.headers["X-Allowed"] = "true"
    return resp

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
