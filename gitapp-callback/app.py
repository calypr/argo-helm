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
import subprocess
from pathlib import Path
from flask import Flask, request, render_template, jsonify, redirect, url_for
import logging
import jwt
import time
import requests
from typing import List, Dict, Optional, Tuple
import hvac


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Configuration
GITHUB_APP_NAME = os.environ.get("GITHUB_APP_NAME")
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH")
GITHUB_PAT = os.environ.get("GITHUB_PAT")
REPO_REGISTRATION = os.environ.get("REPO_REGISTRATION")
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")
GIT_CREDENTIALS_FILE = os.environ.get("GIT_CREDENTIALS_FILE")



# Default to /tmp in development/test, /var/registrations in production
DEFAULT_DB_PATH = "/tmp/registrations.sqlite" if os.environ.get("FLASK_ENV") == "development" or os.environ.get("TESTING") else "/var/registrations/registrations.sqlite"
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)
# get current directory
REPO_ROOT = Path(__file__).resolve().parents[0]
REGISTRATIONS_PATH = Path("registrations")


def run_git_command(args: List[str], repo_dir: Path) -> str:
    """
    Run a git command and return stdout.

    Args:
        args: List of git arguments (without the leading 'git')
        repo_dir: Working directory to run git in
        use_auth: Whether to attach the PAT to git HTTP requests
    """
    cmd = ["git"]
    cmd.extend(args)
    try:
        logging.info(" ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(
                "Git command failed: %s\nReturn code: %s\nStdout: %s\nStderr: %s\ncwd: %s",
            " ".join(cmd),
            e.returncode,
            e.stdout,
            e.stderr,
            repo_dir,
        )
        return "FAILED"    
    
    return result.stdout.strip()


def parse_repo_owner_name(repo_url: str) -> Tuple[str, str]:
    """
    Parse a GitHub repository URL into owner and repo name.
    """
    if repo_url.startswith("git@"):
        path = repo_url.split(":", 1)[1]
    elif "github.com/" in repo_url:
        path = repo_url.split("github.com/", 1)[1]
    else:
        path = repo_url
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    owner, repo = path.split("/", 1)
    return owner, repo


def ensure_repo_registration() -> None:
    """
    Ensure the REPO_REGISTRATION repository is checked out.
    """
    if not REPO_REGISTRATION:
        logger.info("REPO_REGISTRATION not set; skipping registrations checkout.")
        return
    if not GITHUB_PAT:
        raise ValueError("GITHUB_PAT environment variable not set")

    logger.info(f"Setting git credential.helper to {GIT_CREDENTIALS_FILE}")
    result = run_git_command(["config", "--global", "credential.helper", f'store --file={GIT_CREDENTIALS_FILE}'], REPO_ROOT) 
    logger.info(f"result from setting git credential.helper {result}")

    if not (REPO_ROOT / ".git").exists():
        if not REGISTRATIONS_PATH.exists():
            logger.info("Cloning registrations repository without submodule.")
            run_git_command(
                ["clone", REPO_REGISTRATION, str(REGISTRATIONS_PATH)],
                REPO_ROOT,
            )
            return
        if (REGISTRATIONS_PATH / ".git").exists():
            logger.info("Updating registrations repository checkout.")
            run_git_command(
                ["fetch", "origin", "--prune"],
                REGISTRATIONS_PATH,
            )
            default_branch = get_default_branch(REGISTRATIONS_PATH)
            run_git_command(["checkout", default_branch], REGISTRATIONS_PATH)
            run_git_command(
                ["reset", "--hard", f"origin/{default_branch}"],
                REGISTRATIONS_PATH,
            )
            return
        if any(REGISTRATIONS_PATH.iterdir()):
            logger.warning(
                "Registrations path exists and is not a git repo; skipping checkout."
            )
        return

    gitmodules_path = REPO_ROOT / ".gitmodules"
    submodule_declared = False
    if gitmodules_path.exists():
        submodule_declared = f"path = {REGISTRATIONS_PATH.name}" in gitmodules_path.read_text()

    if not submodule_declared:
        if REGISTRATIONS_PATH.exists() and any(REGISTRATIONS_PATH.iterdir()):
            logger.warning(
                "Registrations path exists and is not a submodule; skipping submodule add."
            )
            return
        logger.info("Adding registrations repository as a git submodule.")
        run_git_command(
            ["submodule", "add", REPO_REGISTRATION, REGISTRATIONS_PATH.name],
            REPO_ROOT,
        )
    else:
        logger.info("Updating registrations git submodule.")
        run_git_command(
            ["submodule", "update", "--init", "--recursive", REGISTRATIONS_PATH.name],
            REPO_ROOT,
        )


def get_default_branch(repo_dir: Path) -> str:
    """
    Determine the default branch for a repo, falling back to main.
    """
    try:
        ref = run_git_command(
            ["symbolic-ref", "refs/remotes/origin/HEAD"],
            repo_dir,
        )
        return ref.split("/")[-1]
    except subprocess.CalledProcessError:
        return "main"


def create_registration_pull_request(
    installation_id: str, registration_config: Dict[str, any], repositories: List[Dict[str, any]]
) -> None:
    """
    Create or update a RepoRegistration file and open a PR in the registrations repo.
    """
    if not REPO_REGISTRATION:
        logger.info("REPO_REGISTRATION not set; skipping registration PR creation.")
        return
    if not GITHUB_PAT:
        raise ValueError("GITHUB_PAT environment variable not set")
    if not repositories:
        raise ValueError("No repositories available to generate registration file.")

    ensure_repo_registration()

    if len(repositories) > 1:
        logging.warning("Multiple repositories found for installation; using the first one.")

    full_name = repositories[0]["full_name"]
    owner, repo_name = full_name.split("/")

    registration_repo_owner, registration_repo_name = parse_repo_owner_name(REPO_REGISTRATION)

    registration_file = REGISTRATIONS_PATH / owner / f"{repo_name}.yaml"
    branch_action = "update" if registration_file.exists() else "create"
    branch_name = f"chore/{branch_action}-{owner}-{repo_name}"

    run_git_command(["fetch", "origin", "--prune"], REGISTRATIONS_PATH)
    default_branch = get_default_branch(REGISTRATIONS_PATH)
    run_git_command(
        ["checkout", "-B", branch_name, f"origin/{default_branch}"],
        REGISTRATIONS_PATH,
    )

    registration_file.parent.mkdir(parents=True, exist_ok=True)
    registration_payload = {
        "installation_id": installation_id,
        "registration_config": registration_config,
    }
    registration_file.write_text(
        json.dumps(registration_payload, indent=2, sort_keys=True) + "\n"
    )

    run_git_command(
        ["add", str(registration_file.relative_to(REGISTRATIONS_PATH))],
        REGISTRATIONS_PATH,
    )
    run_git_command(
        ["commit", "--allow-empty", "-m", branch_name],
        REGISTRATIONS_PATH,
    )

    run_git_command(["push", "-u", "origin", branch_name], REGISTRATIONS_PATH)

    pr_body = (
        f"Automated repo registration for `{owner}/{repo_name}`.\n\n"
        f"Installation ID: `{installation_id}`."
    )
    pr_url = f"https://api.github.com/repos/{registration_repo_owner}/{registration_repo_name}/pulls"
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(
        pr_url,
        headers=headers,
        json={
            "title": branch_name,
            "head": branch_name,
            "base": default_branch,
            "body": pr_body,
        },
    )

    if response.status_code == 422:
        existing_response = requests.get(
            pr_url,
            headers=headers,
            params={"state": "open", "head": f"{registration_repo_owner}:{branch_name}"},
        )
        existing_response.raise_for_status()
        pulls = existing_response.json()
        if pulls:
            pr_number = pulls[0]["number"]
        else:
            response.raise_for_status()
    else:
        response.raise_for_status()
        pr_number = response.json()["number"]

    reviewers_url = (
        f"https://api.github.com/repos/{registration_repo_owner}/"
        f"{registration_repo_name}/pulls/{pr_number}/requested_reviewers"
    )
    reviewers_response = requests.post(
        reviewers_url,
        headers=headers,
        json={"reviewers": ["co-pilot"]},
    )
    reviewers_response.raise_for_status()


def get_github_app_jwt() -> str:
    """
    Generate a JWT for GitHub App authentication.

    Returns:
        JWT token string for authenticating as the GitHub App

    Raises:
        ValueError: If GITHUB_APP_ID is not set
        FileNotFoundError: If private key file doesn't exist
    """
    if not GITHUB_APP_ID:
        raise ValueError("GITHUB_APP_ID environment variable not set")

    # Read private key
    with open(GITHUB_PRIVATE_KEY_PATH, 'rb') as key_file:
        private_key = key_file.read()

    # Create JWT payload
    payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,  # 10 minutes
        'iss': GITHUB_APP_ID
    }

    # Generate JWT
    token = jwt.encode(payload, private_key, algorithm='RS256')
    return token


def get_installation_access_token(installation_id: str) -> str:
    """
    Get an installation access token for API calls.

    Args:
        installation_id: GitHub installation ID

    Returns:
        Access token for the installation

    Raises:
        requests.HTTPError: If GitHub API request fails
    """
    jwt_token = get_github_app_jwt()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    response = requests.post(url, headers=headers)
    response.raise_for_status()

    return response.json()['token']


def get_installation_repositories(installation_id: str) -> List[Dict[str, any]]:
    """
    Retrieve repositories for a GitHub App installation.

    Args:
        installation_id: GitHub installation ID

    Returns:
        List of repository dictionaries with keys like:
        - 'id': Repository ID
        - 'name': Repository name
        - 'full_name': Owner/repo format
        - 'private': Boolean for private/public
        - 'html_url': Repository URL

    Raises:
        requests.HTTPError: If GitHub API request fails
    """
    access_token = get_installation_access_token(installation_id)

    url = "https://api.github.com/installation/repositories"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    repositories = []
    page = 1

    while True:
        response = requests.get(
            url,
            headers=headers,
            params={"per_page": 100, "page": page}
        )
        response.raise_for_status()

        data = response.json()
        repositories.extend(data.get('repositories', []))

        # Check if there are more pages
        if len(data.get('repositories', [])) < 100:
            break
        page += 1

    return repositories


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


def get_registration(installation_id, repositories=None):
    """
    Get a registration from the database.
    
    Args:
        installation_id: The GitHub installation ID
        repositories: Optional list of repositories associated with the installation
        
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
        registration_data = json.loads(row[0])

        if repositories and VAULT_ADDR and VAULT_TOKEN:
            if len(repositories) > 1:
                logging.warning("Multiple repositories found for installation; using the first one.")

            full_name = repositories[0]['full_name']
            owner, repo_name = full_name.split('/')
            data_vault_path = f"argo/apps/{owner}/{repo_name}/dataBucket"
            artifact_vault_path = f"argo/apps/{owner}/{repo_name}/artifactBucket"
            try:
                client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
                data_bucket_response = client.secrets.kv.v2.read_secret_version(
                    path=data_vault_path,
                    mount_point="kv"
                )
                artifact_bucket_response = client.secrets.kv.v2.read_secret_version(
                    path=artifact_vault_path,
                    mount_point="kv"
                )
                if data_bucket_response:
                    created_time = (
                        data_bucket_response
                        .get("data", {})
                        .get("metadata", {})
                        .get("created_time")
                    )
                    if created_time:
                        registration_data["dataBucketCreatedTime"] = created_time
                if artifact_bucket_response:
                    created_time = (
                        artifact_bucket_response
                        .get("data", {})
                        .get("metadata", {})
                        .get("created_time")
                    )
                    if created_time:
                        registration_data["artifactBucketCreatedTime"] = created_time
            except Exception as e:
                logger.warning(f"Failed to retrieve bucket configurations from Vault: {e}")

        return registration_data
    
    return None


def save_registration(installation_id, registration_data, repositories=None):
    """
    Save or update a registration in the database.
    
    Args:
        installation_id: The GitHub installation ID
        registration_data: The RepoRegistration configuration dict
        repositories: Optional list of repositories associated with the installation
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    data_bucket = registration_data.get("dataBucket", None)
    artifact_bucket = registration_data.get("artifactBucket", None)
    if "dataBucket" in registration_data:
        del registration_data["dataBucket"]
    if "artifactBucket" in registration_data:
        del registration_data["artifactBucket"]

    # Save bucket configurations to Vault
    if repositories:
        if len(repositories) > 1:
            logging.warning("Multiple repositories found for installation; using the first one.")

        full_name = repositories[0]['full_name']
        owner, repo_name = full_name.split('/')
        try:
            client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)

            if data_bucket:
                data_vault_path = f"argo/apps/{owner}/{repo_name}/dataBucket"
                client.secrets.kv.v2.create_or_update_secret(
                    path=data_vault_path,
                    secret=data_bucket,
                    mount_point="kv"
                )
                logger.info(f"Saved dataBucket to Vault at {data_vault_path}")

            if artifact_bucket:
                artifact_vault_path = f"argo/apps/{owner}/{repo_name}/artifactBucket"
                client.secrets.kv.v2.create_or_update_secret(
                    path=artifact_vault_path,
                    secret=artifact_bucket,
                    mount_point="kv"
                )
                logger.info(f"Saved artifactBucket to Vault at {artifact_vault_path}")

        except Exception as e:
            logger.error(f"Failed to save bucket configurations to Vault: {e}")
            raise

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


# Initialize module and database on startup
ensure_repo_registration()
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
        installation_id: GitHub installation ID (required, must be integer)
        setup_action: 'install' or 'update' (optional, defaults to 'install')

    Returns:
        HTML form for repository registration configuration
    """
    installation_id = request.args.get("installation_id")
    setup_action = request.args.get("setup_action", "install")

    # retrieve the repository this installation is for
    # installation_id is required


    # Validate installation_id is present
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
    
    # Validate installation_id is an integer
    try:
        int(installation_id)
    except ValueError:
        logger.warning(f"Invalid installation_id (not an integer): {installation_id[:50]}")
        return (
            render_template(
                "error.html",
                error_message=f"Invalid installation_id '{installation_id}'. Must be an integer.",
                github_app_name=GITHUB_APP_NAME,
            ),
            400,
        )

    # Retrieve repositories for this installation
    try:
        repositories = get_installation_repositories(installation_id)
        logger.info(f"Retrieved {len(repositories)} repositories for installation {installation_id}")
    except requests.HTTPError as e:
        logger.error(f"Failed to retrieve repositories: {e}")
        return (
            render_template(
                "error.html",
                error_message="Failed to retrieve repository information from GitHub. Please try again.",
                github_app_name=GITHUB_APP_NAME,
            ),
            500,
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving repositories")
        return (
            render_template(
                "error.html",
                error_message="An unexpected error occurred. Please try again.",
                github_app_name=GITHUB_APP_NAME,
            ),
            500,
        )

    # Validate setup_action is valid
    if setup_action not in ["install", "update"]:
        logger.warning(f"Invalid setup_action: {setup_action[:50]}")
        return (
            render_template(
                "error.html",
                error_message=f"Invalid setup_action '{setup_action}'. Must be 'install' or 'update'.",
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
    existing_registration = get_registration(installation_id, repositories)
    
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
    def registration_pr_error(message: str):
        if request.headers.get("Accept") == "application/json":
            return jsonify({"success": False, "error": message}), 500
        return (
            render_template(
                "error.html",
                error_message=message,
                github_app_name=GITHUB_APP_NAME,
            ),
            500,
        )

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

        # Retrieve repositories for this installation
        try:
            repositories = get_installation_repositories(installation_id)
            logger.info(f"Retrieved {len(repositories)} repositories for installation {installation_id}")
        except requests.HTTPError as e:
            logger.error(f"Failed to retrieve repositories: {e}")
            return (
                render_template(
                    "error.html",
                    error_message="Failed to retrieve repository information from GitHub. Please try again.",
                    github_app_name=GITHUB_APP_NAME,
                ),
                500,
            )
        except Exception as e:
            logger.exception("Unexpected error retrieving repositories")
            return (
                render_template(
                    "error.html",
                    error_message="An unexpected error occurred. Please try again.",
                    github_app_name=GITHUB_APP_NAME,
                ),
                500,
            )

        if not repositories or len(repositories) == 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No repositories found for this installation",
                    }
                ),
                500,
            )

        logger.info(f"Repository registration submitted: installation_id={installation_id} repositories={repositories}")

        # Save configuration to database
        save_registration(installation_id, registration_config, repositories)

        try:
            create_registration_pull_request(
                installation_id, registration_config, repositories
            )
        except Exception:
            logger.exception("Failed to create registration pull request")
            return registration_pr_error(
                "Registration saved, but failed to create a pull request in the "
                "registrations repository."
            )

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
