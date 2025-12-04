# Landing Page

A simple static landing page that renders markdown files.

## Usage

Build the Docker image:

```bash
docker build -t landing-page .
```

Run with a mounted docs directory:

```bash
docker run -p 8080:80 -v /path/to/your/docs:/docs landing-page
```

## Helm Configuration

Configure via `values.yaml`:

```yaml
landingPage:
  enabled: true
  image:
    repository: landing-page
    tag: latest
  title: "Welcome"
  docsPath: "/var/www/docs"  # See "Content Directory" below
```

### Content Directory (`docsPath`)

The `docsPath` is a Kubernetes **hostPath volume** that mounts a directory from the node's filesystem.

**For kind clusters:**

Kind clusters must be configured with `extraMounts` at creation time (mounts cannot be added to running clusters).

1. **Add extraMounts to kind-config.yaml:**
   ```yaml
   kind: Cluster
   apiVersion: kind.x-k8s.io/v1alpha4
   nodes:
     - role: control-plane
       extraMounts:
         - hostPath: /path/on/your/host
           containerPath: /var/www/docs
       extraPortMappings:
         - containerPort: 30080
           hostPort: 80
         - containerPort: 30443
           hostPort: 443
   ```

2. **Recreate the kind cluster with the new config:**
   ```bash
   # Delete existing cluster
   kind delete cluster --name kind
   
   # Create new cluster with mount config
   kind create cluster --config kind-config.yaml
   
   # Re-run setup (load images, install charts)
   make docker-install
   make install
   ```

3. **Set docsPath in values.yaml:**
   ```yaml
   landingPage:
     docsPath: "/var/www/docs"
   ```

4. **Add your markdown content:**
   ```bash
   # On your host machine
   echo "# Welcome" > /path/on/your/host/index.md
   ```

**Content updates:**
- Changes to markdown files are picked up on browser refresh
- No pod restart needed—nginx serves files directly from the mount
- The page fetches and renders markdown via JavaScript on each load

## Features

- Renders `index.md` or `README.md` from the mounted `/docs` directory
- Client-side markdown rendering using marked.js with DOMPurify sanitization
- Minimal, lightweight nginx-based container
- Health check endpoint at `/healthz`
- Security headers (X-Content-Type-Options, X-Frame-Options)

## Security Notes

- JavaScript libraries (marked.js, DOMPurify) are loaded from jsdelivr CDN
- For production deployments, consider adding Subresource Integrity (SRI) hashes
- Only expose dedicated docs directories via the hostPath mount
