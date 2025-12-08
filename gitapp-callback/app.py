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
from flask import Flask, request, render_template, jsonify
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

    return render_template(
        "registration_form.html",
        installation_id=installation_id,
        setup_action=setup_action,
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

        logger.info(f"Repository registration submitted: {registration_config}")

        # TODO: Save configuration to Kubernetes CRD or storage
        # For now, we'll just log it and return success

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
