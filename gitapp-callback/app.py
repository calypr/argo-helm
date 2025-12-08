#!/usr/bin/env python3
"""
GitHub App Post-Installation Callback Service

This service handles the post-installation redirect from GitHub after a user
installs or updates the GitHub App. It provides a web form for users to
configure repository registration settings.

The service:
1. Receives installation_id from GitHub's redirect
2. Displays a registration form
3. Collects RepoRegistration configuration
4. Validates and saves the configuration
"""

import os
import re
import sqlite3
import json
from pathlib import Path
from flask import Flask, request, render_template, jsonify, redirect, url_for
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Configuration
GITHUB_APP_NAME = os.environ.get("GITHUB_APP_NAME", "calypr-workflows")

# Default to /tmp in development/test, /var/registrations in production
DEFAULT_DB_PATH = "/tmp/registrations.sqlite" if os.environ.get("FLASK_ENV") == "development" or os.environ.get("TESTING") else "/var/registrations/registrations.sqlite"
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)


def init_db():
    """
    Initialize the SQLite database.
    
    Creates the registrations table if it doesn't exist.
    Table schema:
        - installation_id: TEXT PRIMARY KEY
        - data: TEXT (JSON serialized RepoRegistration)
        - created_at: TIMESTAMP
        - updated_at: TIMESTAMP
    """
    # Ensure directory exists
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            installation_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def get_registration(installation_id):
    """
    Get a registration from the database.
    
    Args:
        installation_id: The GitHub installation ID
        
    Returns:
        dict: The registration data or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT data FROM registrations WHERE installation_id = ?",
        (installation_id,)
    )
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None


def save_registration(installation_id, registration_data):
    """
    Save or update a registration in the database.
    
    Args:
        installation_id: The GitHub installation ID
        registration_data: The RepoRegistration configuration dict
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    data_json = json.dumps(registration_data)
    
    cursor.execute("""
        INSERT INTO registrations (installation_id, data, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(installation_id) 
        DO UPDATE SET 
            data = excluded.data,
            updated_at = CURRENT_TIMESTAMP
    """, (installation_id, data_json))
    
    conn.commit()
    conn.close()
    logger.info(f"Registration saved for installation_id={installation_id}")


# Initialize database on startup
init_db()


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Health check endpoint.

    Returns:
        Tuple of (response_body, status_code):
            - 200: Service is healthy
    """
    return "ok", 200


@app.route("/registrations", methods=["GET"])
def registrations_form():
    """
    GitHub App post-installation callback endpoint.

    This endpoint is called by GitHub after a user installs or updates
    the GitHub App. It displays a form to collect repository registration
    configuration.

    Query Parameters:
        installation_id: GitHub installation ID (required)
        setup_action: 'install' or 'update' (optional)

    Returns:
        HTML form for repository registration configuration
    """
    installation_id = request.args.get("installation_id")
    setup_action = request.args.get("setup_action", "install")

    if not installation_id:
        logger.warning("Missing installation_id in callback")
        return (
            render_template(
                "error.html",
                error_message="Missing installation_id. Please reinstall the GitHub App.",
                github_app_name=GITHUB_APP_NAME,
            ),
            400,
        )

    # Sanitize values for logging (only alphanumeric and basic chars)
    safe_installation_id = "".join(
        c for c in (installation_id or "")[:50] if c.isalnum() or c in "-_"
    )
    safe_setup_action = "".join(c for c in (setup_action or "")[:20] if c.isalnum() or c in "-_")
    logger.info(
        f"Registration form requested: installation_id={safe_installation_id}, "
        f"action={safe_setup_action}"
    )

    # Check if registration exists
    existing_registration = get_registration(installation_id)
    
    # Handle install action
    if setup_action == "install":
        if existing_registration:
            # Installation already exists, warn user and redirect to update
            logger.warning(
                f"Installation {safe_installation_id} already exists, redirecting to update"
            )
            return render_template(
                "error.html",
                error_message=(
                    f"Installation {installation_id} is already registered. "
                    "Redirecting you to update the existing registration..."
                ),
                redirect_url=url_for(
                    "registrations_form",
                    installation_id=installation_id,
                    setup_action="update"
                ),
                github_app_name=GITHUB_APP_NAME,
            )
    
    # Handle update action
    elif setup_action == "update":
        if not existing_registration:
            # No existing registration for update
            logger.error(
                f"Installation {safe_installation_id} not found for update"
            )
            return (
                render_template(
                    "error.html",
                    error_message=(
                        f"Installation {installation_id} not found. "
                        "Please install the GitHub App first."
                    ),
                    github_app_name=GITHUB_APP_NAME,
                ),
                404,
            )

    # Load existing data for update mode
    initial_data = existing_registration if setup_action == "update" else None

    return render_template(
        "registration_form.html",
        installation_id=installation_id,
        setup_action=setup_action,
        initial_data=initial_data,
        github_app_name=GITHUB_APP_NAME,
    )


@app.route("/registrations", methods=["POST"])
def registrations_submit():
    """
    Handle repository registration form submission.

    Validates the submitted form data and saves the repository registration
    configuration.

    Form Fields:
        installation_id: GitHub installation ID (required)
        defaultBranch: Default branch name (default: main)
        dataBucket_*: Data bucket configuration fields (optional)
        artifactBucket_*: Artifact bucket configuration fields (optional)
        adminUsers: Comma-separated list of admin email addresses (required)
        readUsers: Comma-separated list of read-only email addresses (optional)

    Returns:
        JSON response with success/error status or redirect to success page
    """
    try:
        # Extract form data
        installation_id = request.form.get("installation_id", "").strip()
        default_branch = request.form.get("defaultBranch", "main").strip()
        admin_users_raw = request.form.get("adminUsers", "").strip()
        read_users_raw = request.form.get("readUsers", "").strip()

        # Validate required fields
        if not installation_id:
            return jsonify({"success": False, "error": "installation_id is required"}), 400

        if not admin_users_raw:
            return (
                jsonify({"success": False, "error": "At least one admin user email is required"}),
                400,
            )

        # Parse email lists
        admin_users = [email.strip() for email in admin_users_raw.split(",") if email.strip()]
        read_users = (
            [email.strip() for email in read_users_raw.split(",") if email.strip()]
            if read_users_raw
            else []
        )

        # Validate admin users
        if not admin_users:
            return (
                jsonify({"success": False, "error": "At least one admin user email is required"}),
                400,
            )

        # Basic email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        for email in admin_users + read_users:
            if not re.match(email_pattern, email):
                return jsonify({"success": False, "error": f"Invalid email address: {email}"}), 400

        # Parse bucket configurations
        def parse_bucket_config(prefix):
            """Parse S3 bucket configuration from form data."""
            bucket_name = request.form.get(f"{prefix}_bucket", "").strip()
            if not bucket_name:
                return None

            access_key = request.form.get(f"{prefix}_accessKey", "").strip()
            secret_key = request.form.get(f"{prefix}_secretKey", "").strip()

            # If bucket is set, accessKey and secretKey must exist
            if not access_key or not secret_key:
                raise ValueError(
                    f"{prefix.replace('_', ' ').title()} requires both access key and secret key"
                )

            is_aws = request.form.get(f"{prefix}_is_aws") == "on"

            config = {
                "bucket": bucket_name,
                "accessKey": access_key,
                "secretKey": secret_key,
                "is_aws": is_aws,
            }

            # If not AWS, hostname, region, and pathStyle should be complete
            if not is_aws:
                hostname = request.form.get(f"{prefix}_hostname", "").strip()
                region = request.form.get(f"{prefix}_region", "").strip()
                path_style = request.form.get(f"{prefix}_pathStyle") == "on"

                if not hostname or not region:
                    raise ValueError(
                        f"{prefix.replace('_', ' ').title()} (non-AWS) requires hostname and region"
                    )

                if not hostname.startswith("https://"):
                    raise ValueError(
                        f"{prefix.replace('_', ' ').title()} hostname must start with https://"
                    )

                config["hostname"] = hostname
                config["region"] = region
                config["pathStyle"] = path_style

            return config

        try:
            data_bucket = parse_bucket_config("dataBucket")
            artifact_bucket = parse_bucket_config("artifactBucket")
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # Create registration configuration
        registration_config = {
            "installation_id": installation_id,
            "defaultBranch": default_branch,
            "dataBucket": data_bucket,
            "artifactBucket": artifact_bucket,
            "adminUsers": admin_users,
            "readUsers": read_users,
        }

        logger.info(f"Repository registration submitted: installation_id={installation_id}")

        # Save configuration to database
        save_registration(installation_id, registration_config)

        # Return success response
        if request.headers.get("Accept") == "application/json":
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Repository registration completed successfully",
                        "config": registration_config,
                    }
                ),
                200,
            )
        else:
            # Redirect to success page
            return render_template(
                "success.html", github_app_name=GITHUB_APP_NAME, config=registration_config
            )

    except Exception as e:
        logger.exception("Error processing registration submission")
        return jsonify({"success": False, "error": f"Internal server error: {str(e)}"}), 500


if __name__ == "__main__":
    """
    Run the Flask development server.

    Environment Variables:
        SECRET_KEY: Flask secret key for session management
        GITHUB_APP_NAME: Name of the GitHub App (default: calypr-workflows)
    """
    app.run(host="0.0.0.0", port=8080, debug=True)
