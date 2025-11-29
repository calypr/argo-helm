"""
Landing Page Service

A standalone service that serves a customizable landing page with markdown
content from a mounted directory. Supports client-side markdown rendering
with proper security controls.
"""

import os
from pathlib import Path
from flask import Flask, request, make_response, render_template, send_from_directory

# Landing page configuration
CONTENT_DIR = os.environ.get("CONTENT_DIR", "/content")
# Allowed markdown file extensions
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
# Priority order for default markdown files
DEFAULT_FILES = ["index.md", "README.md", "readme.md", "INDEX.md"]

app = Flask(__name__)


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
    try:
        # Resolve both paths to their absolute, canonical form
        base_path = Path(base_dir).resolve()
        requested_full = Path(base_dir).joinpath(requested_path).resolve()

        # Check that the resolved path is within the base directory
        # Using is_relative_to() for robust cross-platform path checking
        return requested_full.is_relative_to(base_path)
    except (ValueError, OSError):
        return False


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
    # Security: Prevent path traversal using robust pathlib-based check
    if not is_safe_path(CONTENT_DIR, filename):
        return make_response("Not found", 404)

    # Use send_from_directory with trusted CONTENT_DIR as base
    # Let Flask handle the file existence check and serving
    # The filename may include subdirectory paths (e.g., "images/logo.png")
    try:
        return send_from_directory(CONTENT_DIR, filename)
    except FileNotFoundError:
        return make_response("Not found", 404)


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Health check endpoint.

    Simple endpoint to verify the service is running and responding.

    Returns:
        Tuple of (response_body, status_code):
            - 200: Service is healthy

    Examples:
        GET /healthz

        Response: 200 OK
        ok
    """
    return "ok", 200


if __name__ == "__main__":
    """
    Run the Flask development server.

    Starts the landing page service on all interfaces (0.0.0.0)
    on port 8080. This should only be used for development/testing.
    For production, use a WSGI server like gunicorn or uwsgi.

    Environment Variables:
        CONTENT_DIR: Directory containing markdown content (default: /content)
    """
    app.run(host="0.0.0.0", port=8080)
