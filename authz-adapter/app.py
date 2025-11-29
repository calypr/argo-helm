import os
import requests
from flask import Flask, request, make_response, render_template, send_from_directory

FENCE_BASE = os.environ.get("FENCE_BASE", "https://calypr-dev.ohsu.edu/user")
USERINFO_URL = FENCE_BASE.rstrip("/") + "/user"
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "3.0"))
SERVICE_TOKEN = os.environ.get("FENCE_SERVICE_TOKEN", "")

# Landing page configuration
CONTENT_DIR = os.environ.get("CONTENT_DIR", "/content")
# Allowed markdown file extensions
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
# Priority order for default markdown files
DEFAULT_FILES = ["index.md", "README.md", "readme.md", "INDEX.md"]

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
    Map Fence-style authorization JSON into coarse-grained groups for Argo/ArgoCD.

    Determines which permission groups a user belongs to based on their Fence
    authorization document. Supports resource-scoped decisions when Argo resource
    context is provided.

    Args:
        doc: User authorization document from Fence containing 'active' status and 'authz' data
        verb: Optional Kubernetes verb (e.g., 'create', 'get', 'list')
        group: Optional API group (e.g., 'argoproj.io')
        version: Optional API version (e.g., 'v1alpha1')
        resource: Optional resource type (e.g., 'workflows', 'workflowtemplates')
        namespace: Optional namespace for the resource

    Returns:
        List of group names the user belongs to (e.g., ['argo-runner', 'argo-viewer'])
        Empty list if user is not active

    Examples:
        >>> doc = {"active": True, "authz": {"/services/workflow/gen3-workflow": [{"method": "create"}]}}
        >>> decide_groups(doc)
        ['argo-runner', 'argo-viewer']

        >>> decide_groups(doc, group="argoproj.io", resource="workflows")
        ['argo-runner', 'argo-viewer']

        >>> decide_groups({"active": False})
        []
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
    """
    Fetch user authorization document from Fence userinfo endpoint.

    Validates the provided authorization token by calling the Fence /user endpoint.
    Falls back to using a service token if no user token is provided.

    Args:
        auth_header: Authorization header value (e.g., 'Bearer <token>')

    Returns:
        Tuple of (user_doc, error):
            - user_doc: Dictionary containing user info and authz data, or None on error
            - error: Error message string, or None on success

    Examples:
        >>> doc, err = fetch_user_doc("Bearer valid-token")
        >>> if err:
        ...     print(f"Error: {err}")
        ... else:
        ...     print(doc.get("email"))

    Raises:
        No exceptions are raised; errors are returned in the tuple
    """
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


def get_debugging_vars():
    """
    Retrieve debugging override variables from query parameters or environment.

    Allows setting a fixed email and groups for testing purposes via
    'debug_email' and 'debug_groups' query parameters or
    'DEBUG_EMAIL' and 'DEBUG_GROUPS' environment variables.

    Returns:
        Tuple of (email, groups):
            - email: Debug email string or None
            - groups: List of debug groups or None

    """
    email = None
    groups = None
    if os.environ.get("DEBUG_EMAIL"):
        email = request.args.get("debug_email") or os.environ.get("DEBUG_EMAIL")
        groups_str = request.args.get("debug_groups") or os.environ.get("DEBUG_GROUPS")
        groups = groups_str.split(",") if groups_str else None
    return email, groups


@app.route("/check", methods=["GET"])
def check():
    """
    Authorization check endpoint for nginx auth_request.

    Validates the user's authorization token against Fence and determines their
    permission groups. Sets custom headers for nginx to forward to upstream services.

    Expected Headers:
        Authorization: Bearer token or service token fallback

    Response Headers (on success):
        X-Auth-Request-User: User identifier (email/name/username)
        X-Auth-Request-Email: User email
        X-Auth-Request-Groups: Comma-separated list of groups
        X-Allowed: 'true' to signal authorization success

    Returns:
        HTTP Response:
            - 200: User authorized, headers set
            - 401: Authentication failed (invalid/missing token)
            - 403: User authenticated but not authorized (no groups)

    Examples:
        GET /check
        Authorization: Bearer abc123

        Response: 200 OK
        X-Auth-Request-User: user@example.com
        X-Auth-Request-Groups: argo-runner,argo-viewer
    """
    # Check for debugging overrides via query parameters or environment variables
    email,  groups = get_debugging_vars()
    # no debugging override, do real authz
    if not (email and groups):
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
    """
    Health check endpoint.

    Simple endpoint to verify the service is running and responding.
    Does not check external dependencies like Fence availability.

    Returns:
        Tuple of (response_body, status_code):
            - 200: Service is healthy

    Examples:
        GET /healthz

        Response: 200 OK
        ok
    """
    return "ok", 200


def find_markdown_file():
    """
    Find the best markdown file to display from the content directory.

    Searches for markdown files in the CONTENT_DIR directory, preferring
    files in the DEFAULT_FILES list (index.md, README.md, etc.) in order
    of priority.

    Returns:
        Tuple of (filename, error):
            - filename: Name of the markdown file found, or None if not found
            - error: Error message string, or None on success

    Examples:
        >>> filename, err = find_markdown_file()
        >>> if err:
        ...     print(f"Error: {err}")
        ... else:
        ...     print(f"Found: {filename}")
    """
    if not os.path.isdir(CONTENT_DIR):
        return None, f"Content directory not found: {CONTENT_DIR}"

    # Check for default files in priority order
    for default_file in DEFAULT_FILES:
        filepath = os.path.join(CONTENT_DIR, default_file)
        if os.path.isfile(filepath):
            return default_file, None

    # Fall back to first markdown file found
    try:
        for entry in os.listdir(CONTENT_DIR):
            if os.path.isfile(os.path.join(CONTENT_DIR, entry)):
                ext = os.path.splitext(entry)[1].lower()
                if ext in MARKDOWN_EXTENSIONS:
                    return entry, None
    except OSError as e:
        return None, f"Error reading content directory: {e}"

    return None, "No markdown files found in content directory"


def is_safe_path(base_dir, requested_path):
    """
    Check if a requested path is safely within the base directory.

    Prevents path traversal attacks by ensuring the resolved path
    is within the allowed base directory.

    Args:
        base_dir: The allowed base directory
        requested_path: The path requested by the user

    Returns:
        bool: True if the path is safe, False otherwise
    """
    # Resolve both paths to their absolute, canonical form
    base_resolved = os.path.realpath(base_dir)
    requested_resolved = os.path.realpath(os.path.join(base_dir, requested_path))

    # Check that the resolved path starts with the base directory
    return requested_resolved.startswith(base_resolved + os.sep) or \
           requested_resolved == base_resolved


@app.route("/", methods=["GET"])
def landing_page():
    """
    Landing page endpoint serving markdown content.

    Renders a landing page that displays markdown content from a mounted
    directory. The markdown is rendered client-side using the marked.js library.

    Configuration:
        CONTENT_DIR: Directory containing markdown files (default: /content)

    File Selection Priority:
        1. index.md
        2. README.md
        3. readme.md
        4. INDEX.md
        5. First .md or .markdown file found

    Returns:
        HTML page that renders the markdown content client-side

    Examples:
        GET /

        Response: 200 OK
        HTML page with embedded markdown rendering
    """
    markdown_file, error = find_markdown_file()

    has_content = markdown_file is not None
    content_path = f"/content/{markdown_file}" if has_content else ""
    base_url = "/content"

    return render_template(
        "landing.html",
        title="Welcome",
        has_content=has_content,
        content_path=content_path,
        base_url=base_url,
        error_message=error or ""
    )


@app.route("/content/<path:filename>", methods=["GET"])
def serve_content(filename):
    """
    Serve static files from the content directory.

    Serves files from the CONTENT_DIR directory, with path traversal
    protection to prevent access to files outside the configured directory.

    Args:
        filename: The path to the file within the content directory

    Returns:
        HTTP Response:
            - 200: File contents with appropriate MIME type
            - 404: File not found or path traversal attempt

    Security:
        - Path traversal protection prevents access outside CONTENT_DIR
        - Only serves files within the configured content directory

    Examples:
        GET /content/README.md
        GET /content/images/diagram.png
    """
    # Security: Prevent path traversal
    if not is_safe_path(CONTENT_DIR, filename):
        return make_response("Not found", 404)

    filepath = os.path.join(CONTENT_DIR, filename)
    if not os.path.isfile(filepath):
        return make_response("Not found", 404)

    # Get the directory and filename for send_from_directory
    directory = os.path.dirname(filepath)
    basename = os.path.basename(filepath)

    return send_from_directory(directory, basename)


if __name__ == "__main__":
    """
    Run the Flask development server.

    Starts the authorization adapter service on all interfaces (0.0.0.0)
    on port 8080. This should only be used for development/testing.
    For production, use a WSGI server like gunicorn or uwsgi.

    Environment Variables:
        FENCE_BASE: Base URL for Fence service (default: https://calypr-dev.ohsu.edu/user)
        HTTP_TIMEOUT: Timeout for Fence requests in seconds (default: 3.0)
        FENCE_SERVICE_TOKEN: Fallback service token for authentication
    """
    app.run(host="0.0.0.0", port=8080)
