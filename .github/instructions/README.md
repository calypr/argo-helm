# GitHub Copilot Instructions

This directory contains instruction files that help GitHub Copilot provide better, more contextual assistance when working with this repository. These files follow the [GitHub Copilot coding agent best practices](https://gh.io/copilot-coding-agent-tips).

## Overview

Each instruction file provides guidelines, conventions, and best practices for specific technologies or file types used in this repository. GitHub Copilot uses these instructions to understand the project's coding standards and provide more accurate suggestions.

## Instruction Files

### Core Technologies

- **[helm-kubernetes.instructions.md](helm-kubernetes.instructions.md)** - Comprehensive guide for Helm chart development and Kubernetes manifest creation
  - Applies to: `**/*.yaml`, `**/*.yml`, `**/Chart.yaml`, `**/values.yaml`, `**/templates/**`
  - Covers: Helm best practices, chart structure, template development, RBAC, Argo-specific patterns

- **[python.instructions.md](python.instructions.md)** - General Python development guidelines
  - Applies to: `**/*.py`, `**/requirements*.txt`, `**/setup.py`, `**/pyproject.toml`
  - Covers: PEP 8 compliance, type hints, testing, Flask patterns, error handling

- **[bash.instructions.md](bash.instructions.md)** - Bash scripting and Makefile best practices
  - Applies to: `**/*.sh`, `**/Makefile`
  - Covers: Script structure, error handling, Kubernetes patterns, security, testing

- **[docker.instructions.md](docker.instructions.md)** - Docker and containerization guidelines
  - Applies to: `**/Dockerfile`, `**/Dockerfile.*`, `**/.dockerignore`
  - Covers: Multi-stage builds, security, optimization, health checks, Alpine patterns

### Specialized Technologies

- **[go.instructions.md](go.instructions.md)** - Go development following idiomatic practices
  - Applies to: `**/*.go`, `**/go.mod`, `**/go.sum`
  - Covers: Idiomatic Go, naming conventions, error handling, concurrency

- **[python-mcp-server.instructions.md](python-mcp-server.instructions.md)** - Model Context Protocol (MCP) server development
  - Applies to: `**/*.py`, `**/pyproject.toml`, `**/requirements.txt`
  - Covers: FastMCP patterns, tool development, resource management, HTTP/stdio transports

## How It Works

GitHub Copilot automatically reads and applies these instructions based on the file patterns specified in each instruction file's frontmatter. When you're working on a file that matches one or more patterns, Copilot considers the relevant guidelines when providing suggestions.

### Frontmatter Format

Each instruction file starts with YAML frontmatter:

```yaml
---
description: 'Brief description of what this file covers'
applyTo: 'file pattern(s) that trigger these instructions'
---
```

### File Pattern Examples

- `**/*.py` - All Python files
- `**/Dockerfile` - All Dockerfiles
- `helm/*/templates/**` - All Helm templates
- `**/*.{yaml,yml}` - All YAML files

## Contributing

When adding new technologies or updating existing guidelines:

1. Create or update the appropriate instruction file
2. Include proper frontmatter with description and file patterns
3. Follow the established structure and format
4. Include practical examples and common patterns
5. Document common pitfalls and security considerations
6. Update this README with any new instruction files

## Repository-Specific Patterns

This repository focuses on:
- **Argo Workflows** - Kubernetes-native workflow engine
- **Argo CD** - GitOps continuous delivery
- **Authorization Adapter** - Flask-based RBAC service
- **Helm Charts** - Kubernetes package management
- **Multi-tenancy** - Namespace isolation and RBAC

The instruction files are tailored to these specific use cases while following industry best practices.

## Best Practices

### When Writing Instructions

- **Be specific** - Provide concrete examples and patterns
- **Be practical** - Focus on what developers actually need
- **Be current** - Keep up with best practices and tool updates
- **Be consistent** - Follow the established format and style
- **Be comprehensive** - Cover common scenarios and edge cases

### Testing Instructions

After adding or updating instruction files, verify they work correctly by:

1. Opening files that match the patterns
2. Checking that Copilot provides contextually appropriate suggestions
3. Ensuring suggestions follow the documented guidelines
4. Testing with different file types and scenarios

## Resources

- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [Best practices for Copilot coding agent](https://gh.io/copilot-coding-agent-tips)
- [Repository CONTRIBUTING.md](../../CONTRIBUTING.md)
- [Repository README.md](../../README.md)

## Maintenance

These instruction files should be reviewed and updated:
- When introducing new technologies or patterns
- When updating dependencies or frameworks
- When best practices evolve
- When team conventions change
- At least quarterly for general maintenance

## Questions?

If you have questions about these instructions or suggestions for improvements, please:
- Open an issue in the repository
- Submit a pull request with proposed changes
- Reach out to the maintainers

---

**Note**: These instructions are designed to assist GitHub Copilot in providing better suggestions. They represent our team's coding standards and should be followed by all contributors, whether using Copilot or not.
