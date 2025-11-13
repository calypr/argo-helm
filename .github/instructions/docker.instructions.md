---
description: 'Instructions for writing Dockerfiles and working with containers'
applyTo: '**/Dockerfile, **/Dockerfile.*, **/.dockerignore'
---

# Docker and Containerization Instructions

## General Principles

- Write secure, efficient, and maintainable Dockerfiles
- Optimize for small image sizes and fast build times
- Follow Docker best practices and security guidelines
- Use multi-stage builds when appropriate
- Keep images minimal and focused

## Dockerfile Best Practices

### Base Image Selection

- Use official base images from Docker Hub
- Prefer specific version tags over `latest`
- Choose appropriate base images for your use case:
  - `alpine` for minimal size (use musl libc compatible packages)
  - `slim` variants for balance between size and compatibility
  - Full images when you need all system utilities
- Use multi-stage builds to keep final images small

```dockerfile
# Good: Specific version
FROM python:3.11-slim

# Bad: Using latest
FROM python:latest

# Good: Alpine for minimal size
FROM python:3.11-alpine

# Good: Multi-stage build
FROM python:3.11 AS builder
# Build steps

FROM python:3.11-slim
# Copy artifacts from builder
```

### Image Structure

- Order instructions from least to most frequently changing
- Combine related RUN commands to reduce layers
- Use `.dockerignore` to exclude unnecessary files
- Clean up in the same layer where you create files

```dockerfile
FROM python:3.11-slim

# Set working directory early
WORKDIR /app

# Install system dependencies (changes rarely)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first (changes less often than code)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (changes most frequently)
COPY . .

# Set runtime configuration
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run as non-root user
USER nobody

# Define entrypoint
CMD ["python", "app.py"]
```

### Layer Optimization

- Minimize the number of layers (combine RUN commands)
- Put frequently changing instructions at the end
- Use build cache effectively by ordering instructions properly
- Clean up temporary files in the same RUN instruction

```dockerfile
# Good: Combined into one layer with cleanup
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        build-essential && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc build-essential && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Bad: Multiple layers, no cleanup
RUN apt-get update
RUN apt-get install -y gcc
RUN pip install -r requirements.txt
```

### Multi-stage Builds

- Use multi-stage builds to separate build and runtime environments
- Copy only necessary artifacts to final image
- Keep final image minimal

```dockerfile
# Build stage
FROM python:3.11 AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        build-essential

# Install Python packages
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application
COPY . .

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

USER nobody

CMD ["python", "app.py"]
```

## Security Best Practices

### User Management

- Don't run containers as root
- Create dedicated non-root user if needed
- Use numeric user IDs for better Kubernetes compatibility

```dockerfile
# Option 1: Use nobody user (already exists in base images)
USER nobody

# Option 2: Create a dedicated user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Option 3: Use numeric UID (better for Kubernetes)
USER 1000:1000
```

### Minimize Attack Surface

- Install only necessary packages
- Remove package manager caches
- Use specific package versions
- Scan images for vulnerabilities regularly

```dockerfile
# Install only what's needed, clean up after
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Pin Python package versions
COPY requirements.txt .
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    requests==2.31.0
```

### Secrets and Sensitive Data

- Never include secrets in Docker images
- Use build arguments for build-time configuration (not secrets)
- Use Docker secrets or environment variables for runtime secrets
- Don't commit .env files with secrets

```dockerfile
# Good: Use ARG for build-time values (not secrets)
ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}

# Good: Expect secrets via environment at runtime
ENV API_KEY=""

# Bad: Hardcoded secret
ENV API_KEY="secret-key-12345"
```

## Python-Specific Patterns

### Python Dockerfiles

- Use `PYTHONUNBUFFERED=1` for real-time logging
- Install packages with `--no-cache-dir` to save space
- Use `pip install --user` in multi-stage builds
- Consider using `uv` or `pip-tools` for faster installs

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8080"]
```

### Flask/Web Application Pattern

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Run as non-root
USER nobody

EXPOSE 8080

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8080"]
```

## .dockerignore

- Always include a `.dockerignore` file
- Exclude unnecessary files to speed up builds and reduce context size
- Follow patterns similar to `.gitignore`

```
# .dockerignore
.git
.gitignore
.github
README.md
LICENSE
.venv
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.tox/
dist/
build/
*.egg-info/
.DS_Store
.env
.env.local
*.log
tests/
docs/
examples/
```

## Health Checks

- Include HEALTHCHECK instructions for containerized services
- Implement a health endpoint in your application
- Set appropriate intervals and timeouts

```dockerfile
# Simple health check using curl
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Health check without additional tools
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/healthz').raise_for_status()" || exit 1
```

## Labels and Metadata

- Add labels for better organization and documentation
- Follow OCI annotation conventions
- Include version, build info, and maintainer

```dockerfile
LABEL org.opencontainers.image.title="Argo AuthZ Adapter" \
      org.opencontainers.image.description="Authorization adapter for Argo Workflows" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="Your Team <team@example.com>" \
      org.opencontainers.image.source="https://github.com/calypr/argo-helm" \
      org.opencontainers.image.licenses="Apache-2.0"
```

## Build Arguments

- Use ARG for configurable build-time values
- Provide sensible defaults
- Document arguments in comments

```dockerfile
# Build arguments with defaults
ARG PYTHON_VERSION=3.11
ARG APP_VERSION=latest

FROM python:${PYTHON_VERSION}-slim

# Re-declare after FROM to use in this stage
ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}

LABEL version="${APP_VERSION}"
```

## Entrypoint vs CMD

- Use ENTRYPOINT for executable containers
- Use CMD for default arguments to ENTRYPOINT or standalone commands
- Use JSON array format for proper signal handling

```dockerfile
# Good: ENTRYPOINT + CMD for flexibility
ENTRYPOINT ["python"]
CMD ["app.py"]
# Can override CMD: docker run myimage script.py

# Good: ENTRYPOINT as executable
ENTRYPOINT ["python", "-m", "flask"]
CMD ["run", "--host=0.0.0.0"]

# Good: Simple CMD
CMD ["python", "app.py"]

# Bad: Shell form (doesn't handle signals properly)
CMD python app.py
```

## Working with Alpine

- Install Python packages that need compilation with build dependencies
- Use Alpine's package manager (apk)
- Clean up build dependencies after use

```dockerfile
FROM python:3.11-alpine

WORKDIR /app

# Install build dependencies and runtime dependencies
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev && \
    apk add --no-cache \
        ca-certificates \
        curl

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build dependencies
RUN apk del .build-deps

COPY . .

USER nobody

CMD ["python", "app.py"]
```

## Volume Management

- Use VOLUME for data that should persist or be shared
- Document expected volumes in comments
- Don't include VOLUME for application code

```dockerfile
# Create directory for data
RUN mkdir -p /data && chown appuser:appuser /data

# Declare volume for persistent data
VOLUME ["/data"]

# Document in comment
# Expected volumes:
#   /data - Application data and logs
```

## Common Patterns

### Development vs Production

Create separate Dockerfiles or use build targets:

```dockerfile
# Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .

FROM base AS development
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
COPY . .
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--debug"]

FROM base AS production
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER nobody
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

### Build with make target

```bash
# Build development image
docker build --target development -t myapp:dev .

# Build production image
docker build --target production -t myapp:prod .
```

## Testing Docker Images

- Test images locally before pushing
- Verify non-root user execution
- Check image size
- Scan for vulnerabilities

```bash
# Build image
docker build -t myapp:test .

# Check image size
docker images myapp:test

# Run security scan (example with trivy)
trivy image myapp:test

# Test the container
docker run --rm -p 8080:8080 myapp:test

# Verify non-root
docker run --rm myapp:test id
```

## Common Pitfalls to Avoid

- Don't use `apt-get upgrade` in Dockerfiles (use newer base image instead)
- Don't store secrets in images
- Don't run containers as root
- Don't use `latest` tag for base images in production
- Don't ignore .dockerignore (slows builds and increases context size)
- Don't install unnecessary packages
- Don't create unnecessary layers
- Don't leave package manager caches
- Don't use shell form for ENTRYPOINT/CMD (breaks signal handling)
- Don't copy everything with `COPY . .` too early (breaks layer caching)

## Documentation

- Document build arguments and their defaults
- Document exposed ports and their purpose
- Document required environment variables
- Document expected volumes
- Include example run commands in README
