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
