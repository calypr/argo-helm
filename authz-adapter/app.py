import os
import requests
from flask import Flask, request, make_response

FENCE_BASE = os.environ.get("FENCE_BASE", "https://calypr-dev.ohsu.edu/user")
USERINFO_URL = FENCE_BASE.rstrip("/") + "/user"
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "3.0"))
SERVICE_TOKEN = os.environ.get("FENCE_SERVICE_TOKEN", "")

app = Flask(__name__)

def decide_groups(doc):
    groups = []
    if not doc.get("active"):
        return groups
    authz = doc.get("authz", {})
    gw = authz.get("/services/workflow/gen3-workflow", [])
    if any(x.get("method") in ["create", "*"] for x in gw):
        groups.append("argo-runner")
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
    r = requests.get(USERINFO_URL, headers=headers, timeout=TIMEOUT)
    if r.status_code != 200:
        return None, f"userinfo status {r.status_code}"
    return r.json(), None

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
