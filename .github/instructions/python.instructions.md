---
description: 'Instructions for Python development following best practices and conventions'
applyTo: '**/*.py, **/requirements*.txt, **/setup.py, **/pyproject.toml'
---

# Python Development Instructions

## General Principles

- Write clear, readable, and maintainable Python code
- Follow PEP 8 style guidelines
- Use Python 3.9+ features and best practices
- Write comprehensive tests for all functionality
- Document code with docstrings and type hints
- Prefer explicit over implicit

## Code Style and Formatting

### PEP 8 Compliance

- Use 4 spaces for indentation (never tabs)
- Limit lines to 88-100 characters (prefer 88 for Black compatibility)
- Use blank lines to separate logical sections
- Follow naming conventions:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
  - `_leading_underscore` for private/internal

### Imports

- Group imports in order: standard library, third-party, local
- Use absolute imports over relative imports
- Sort imports alphabetically within groups
- One import per line for clarity:

```python
# Standard library
import os
import sys
from typing import Dict, List, Optional

# Third-party
import flask
from flask import Flask, request

# Local
from .config import Config
from .utils import helper_function
```

### Type Hints

- Always use type hints for function signatures
- Use `Optional[T]` for values that can be None
- Import types from `typing` module
- Use `-> None` for functions that don't return values

```python
from typing import Dict, List, Optional

def process_data(
    data: List[str],
    config: Optional[Dict[str, str]] = None
) -> Dict[str, int]:
    """Process data and return results."""
    result: Dict[str, int] = {}
    # Implementation
    return result
```

## Documentation

### Docstrings

- Use docstrings for all public modules, classes, and functions
- Follow Google or NumPy style for multi-line docstrings
- Include parameter descriptions and return values
- Document exceptions that can be raised

```python
def validate_token(token: str, fence_base: str) -> Dict[str, any]:
    """
    Validate an authentication token against Fence.
    
    Args:
        token: The authentication token to validate
        fence_base: Base URL for the Fence authentication service
        
    Returns:
        Dictionary containing user information and authorization data
        
    Raises:
        ValueError: If token is empty or invalid format
        requests.HTTPError: If Fence API request fails
    """
    if not token:
        raise ValueError("Token cannot be empty")
    # Implementation
```

### Comments

- Write comments for complex logic, not obvious code
- Keep comments up to date with code changes
- Use `#` for inline comments, prefer docstrings for functions
- Explain "why" not "what" when the code is self-documenting

## Functions and Classes

### Function Design

- Keep functions small and focused (single responsibility)
- Use descriptive function names that indicate purpose
- Limit function parameters (consider using dataclasses for many params)
- Return early to reduce nesting

```python
def decide_groups(user_doc: Dict[str, any]) -> List[str]:
    """Determine user's authorization groups."""
    if not user_doc.get("active"):
        return []
    
    groups = []
    authz = user_doc.get("authz", {})
    
    # Check for admin privileges
    if _is_admin(user_doc):
        groups.extend(["argo-admin", "argo-runner", "argo-viewer"])
        return groups
    
    # Check for runner privileges
    if _has_workflow_access(authz):
        groups.append("argo-runner")
    
    return groups
```

### Classes

- Use classes for stateful objects and related functionality
- Implement `__init__`, `__repr__`, and other dunder methods as needed
- Use properties for computed attributes
- Consider dataclasses for simple data containers

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class WorkflowConfig:
    """Configuration for workflow execution."""
    name: str
    namespace: str
    service_account: Optional[str] = None
    timeout: int = 300
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.timeout < 0:
            raise ValueError("Timeout must be positive")
```

## Error Handling

### Exceptions

- Use specific exception types, not bare `except:`
- Catch exceptions at the appropriate level
- Log errors before re-raising or returning error responses
- Create custom exceptions for domain-specific errors

```python
class AuthorizationError(Exception):
    """Raised when user is not authorized for an action."""
    pass

def check_authorization(user: str, resource: str) -> bool:
    """Check if user can access resource."""
    try:
        result = validate_access(user, resource)
        return result
    except requests.RequestException as e:
        logger.error(f"Authorization check failed: {e}")
        raise AuthorizationError(f"Cannot verify access for {user}") from e
    except Exception as e:
        logger.exception("Unexpected error in authorization check")
        raise
```

### Validation

- Validate inputs early
- Use descriptive error messages
- Consider using libraries like `pydantic` for complex validation

```python
def process_request(data: Dict[str, any]) -> Dict[str, any]:
    """Process incoming request."""
    # Validate required fields
    required_fields = ["user_id", "action", "resource"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    
    # Validate field values
    if not data["user_id"].strip():
        raise ValueError("user_id cannot be empty")
    
    # Process data
    return perform_action(data)
```

## Flask/Web Application Patterns

### Application Structure

- Use application factory pattern for Flask apps
- Separate configuration, routes, and business logic
- Use blueprints for modular organization
- Configure proper logging

```python
from flask import Flask
import logging

def create_app(config: Optional[Dict] = None) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    if config:
        app.config.update(config)
    
    # Register routes
    register_routes(app)
    
    return app
```

### Route Handlers

- Keep route handlers thin (delegate to service layer)
- Validate inputs
- Return appropriate HTTP status codes
- Use consistent response format

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/check", methods=["GET"])
def check_authorization():
    """Check if user is authorized."""
    try:
        # Extract headers
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        # Validate token
        token = auth_header.replace("Bearer ", "")
        user_info = validate_token(token)
        
        # Check authorization
        groups = decide_groups(user_info)
        if not groups:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Success response
        return jsonify({
            "authorized": True,
            "groups": groups
        }), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Authorization check failed")
        return jsonify({"error": "Internal server error"}), 500
```

### Health Checks

- Implement health check endpoints
- Check dependencies (database, external services)
- Return appropriate status codes

```python
@app.route("/healthz", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        # Check if critical services are accessible
        check_external_dependencies()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503
```

## Testing

### Test Structure

- Use `pytest` for testing
- Organize tests to mirror source structure
- Use descriptive test names that explain what is being tested
- Group related tests in classes

```python
import pytest
from app import decide_groups

class TestDecideGroups:
    """Tests for decide_groups function."""
    
    def test_inactive_user_returns_empty_list(self):
        """Inactive users should have no groups."""
        user_doc = {"active": False}
        assert decide_groups(user_doc) == []
    
    def test_admin_user_gets_all_groups(self):
        """Admin users should get all permission groups."""
        user_doc = {
            "active": True,
            "email": "admin@example.com",
            "authz": {}
        }
        groups = decide_groups(user_doc)
        assert "argo-admin" in groups
        assert "argo-runner" in groups
        assert "argo-viewer" in groups
```

### Fixtures

- Use pytest fixtures for common test setup
- Keep fixtures focused and reusable
- Use `conftest.py` for shared fixtures

```python
# conftest.py
import pytest
from app import create_app

@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app({"TESTING": True})
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def sample_user():
    """Sample user document for testing."""
    return {
        "active": True,
        "email": "test@example.com",
        "authz": {
            "/workflows/submit": [{"method": "create"}]
        }
    }
```

### Test Coverage

- Aim for high test coverage (80%+ for critical code)
- Test edge cases and error conditions
- Use `pytest-cov` to measure coverage
- Don't just aim for coverage, ensure meaningful tests

### Mocking

- Use `unittest.mock` or `pytest-mock` for external dependencies
- Mock network calls, file I/O, and external services
- Keep mocks simple and focused

```python
from unittest.mock import Mock, patch
import pytest

def test_token_validation_with_mock():
    """Test token validation with mocked HTTP call."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "active": True,
        "email": "user@example.com"
    }
    
    with patch("requests.get", return_value=mock_response):
        result = validate_token("test-token", "https://fence.example.com")
        assert result["active"] is True
```

## Dependencies and Environment

### Requirements Files

- Use `requirements.txt` for production dependencies
- Use `requirements-dev.txt` for development dependencies
- Pin versions for reproducibility
- Keep dependencies minimal and up to date

```
# requirements.txt
flask==3.0.0
requests==2.31.0

# requirements-dev.txt
pytest==7.4.3
pytest-cov==4.1.0
black==23.12.0
flake8==6.1.0
```

### Virtual Environments

- Always use virtual environments
- Document setup in README
- Consider using `venv`, `virtualenv`, or `uv`

## Logging

### Logger Configuration

- Use Python's `logging` module
- Configure appropriate log levels
- Include context in log messages
- Don't log sensitive information

```python
import logging

logger = logging.getLogger(__name__)

def process_authorization(user_id: str, resource: str) -> bool:
    """Process authorization request."""
    logger.info(f"Checking authorization for user {user_id} on {resource}")
    
    try:
        result = check_access(user_id, resource)
        logger.info(f"Authorization check completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Authorization check failed for {user_id}: {e}")
        raise
```

## Security Considerations

### Input Validation

- Validate all external inputs
- Sanitize data before use
- Use parameterized queries for databases
- Validate file paths to prevent path traversal

### Secrets Management

- Never hardcode secrets
- Use environment variables or secret management systems
- Don't log sensitive data
- Use secure random number generation for tokens

```python
import os
import secrets

def get_api_key() -> str:
    """Get API key from environment."""
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable not set")
    return api_key

def generate_token() -> str:
    """Generate secure random token."""
    return secrets.token_urlsafe(32)
```

## Performance Considerations

### Efficient Code

- Use list comprehensions for simple transformations
- Use generators for large datasets
- Cache expensive computations when appropriate
- Profile before optimizing

```python
# Good: List comprehension
active_users = [u for u in users if u.get("active")]

# Good: Generator for large datasets
def process_large_file(filename: str):
    """Process large file line by line."""
    with open(filename) as f:
        for line in f:
            yield process_line(line)

# Good: Caching with functools
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(n: int) -> int:
    """Cached expensive operation."""
    return sum(i * i for i in range(n))
```

## Common Patterns

### Context Managers

- Use context managers for resource management
- Implement `__enter__` and `__exit__` for custom context managers

```python
from contextlib import contextmanager

@contextmanager
def managed_resource(resource_name: str):
    """Manage resource lifecycle."""
    resource = acquire_resource(resource_name)
    try:
        yield resource
    finally:
        release_resource(resource)

# Usage
with managed_resource("my-resource") as res:
    res.do_something()
```

## Common Pitfalls to Avoid

- Don't use mutable default arguments (`def func(items=[]):`)
- Don't modify lists while iterating over them
- Don't catch `Exception` without logging or re-raising
- Don't use `eval()` or `exec()` with untrusted input
- Don't ignore return values from functions
- Don't use global variables when class attributes would work
- Avoid circular imports (reorganize code structure)

## Code Quality Tools

### Linting and Formatting

- Use `black` for code formatting
- Use `flake8` or `pylint` for linting
- Use `mypy` for type checking
- Configure tools in `pyproject.toml` or setup.cfg

```bash
# Format code
black .

# Check style
flake8 .

# Type checking
mypy app.py
```

### Pre-commit Hooks

- Set up pre-commit hooks for automatic checks
- Run formatters and linters before committing
- Ensure tests pass before pushing
