# Landing Page Service

A standalone Flask service that serves a customizable landing page with markdown content from a mounted directory. The markdown is rendered client-side using marked.js with DOMPurify for XSS protection.

## Features

- **Markdown Rendering**: Client-side rendering using marked.js with GitHub-flavored markdown support
- **Dark Mode Support**: Automatic theme switching based on system preferences
- **File Priority**: Automatic selection of `index.md` → `README.md` → `readme.md` → first `.md` file
- **Security**: 
  - DOMPurify sanitization to prevent XSS attacks
  - Path traversal protection using pathlib
  - Read-only content mount
- **Static Asset Support**: Serve images and other files referenced in markdown

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run the service
python app.py

# Run tests
pytest tests/ -v
```

### Docker

```bash
# Build the image
docker build -t landing-page:latest .

# Run with a content directory
docker run -p 8080:8080 -v /path/to/content:/content:ro landing-page:latest
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CONTENT_DIR` | `/content` | Directory containing markdown files |

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/` | GET | Landing page with rendered markdown |
| `/content/<path>` | GET | Serve static files from content directory |
| `/healthz` | GET | Health check endpoint |

## Content Directory Structure

```
/content/
├── index.md          # Primary landing page content
├── README.md         # Fallback if index.md doesn't exist
├── images/
│   └── logo.png      # Referenced as ![](images/logo.png)
└── docs/
    └── guide.md      # Can be linked from main content
```

## Helm Chart Integration

The service is deployed via the argo-stack Helm chart:

```yaml
landingPage:
  enabled: true
  image:
    repository: landing-page
    tag: latest
  replicas: 1
  contentDir: "/content"
  # Volume source (choose one):
  configMap: "landing-page-content"      # From ConfigMap
  # persistentVolumeClaim: "landing-pvc" # From PVC
  # hostPath: "/host/path"               # From host (dev only)
```

### Example ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: landing-page-content
data:
  index.md: |
    # Welcome to Our Platform
    
    This is the landing page for our Argo Workflows deployment.
    
    ## Quick Links
    
    - [Workflows](/workflows)
    - [Applications](/applications)
    - [Documentation](/docs)
```

## Development

```bash
# Install dev dependencies
make install

# Run tests
make test

# Run linter
make lint

# Format code
make format

# Build Docker image
make build
```

## License

Apache 2.0
