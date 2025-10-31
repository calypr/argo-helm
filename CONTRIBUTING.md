# Contributing to Argo Stack with Authorization Adapter

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/argo-helm.git
   cd argo-helm
   ```
3. **Create a feature branch** from main:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🏗️ Development Environment

### Prerequisites

- Docker
- Kubernetes cluster (kind, minikube, or cloud)
- Helm v3.x
- Python 3.9+ (for authz-adapter development)

### Setup

```bash
# Install Python dependencies for authz-adapter
cd authz-adapter
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Build Docker image
docker build -t authz-adapter:dev .
```

## 📝 Contribution Types

### 🐛 Bug Reports

- Use the GitHub issue tracker
- Include detailed reproduction steps
- Provide logs and configuration details
- Test with the latest version first

### ✨ Feature Requests

- Open a GitHub issue with the `enhancement` label
- Describe the use case and expected behavior
- Consider backward compatibility

### 🔧 Code Contributions

1. **Write tests** for new functionality
2. **Follow code style** guidelines (see below)
3. **Update documentation** as needed
4. **Ensure all tests pass**
5. **Submit a pull request**

## 📋 Code Style

### Python (authz-adapter)

- Follow PEP 8
- Use type hints where possible
- Maximum line length: 88 characters (Black formatter)
- Use meaningful variable and function names

### YAML/Helm

- Use 2 spaces for indentation
- Keep lines under 120 characters
- Use descriptive comments for complex logic

### Shell Scripts

- Use `#!/usr/bin/env bash`
- Set `set -euo pipefail`
- Quote variables: `"$VAR"`
- Use meaningful function names

## 🧪 Testing

### Python Tests

```bash
cd authz-adapter
python -m pytest tests/ -v --cov=app
```

### Helm Chart Testing

```bash
# Lint charts
helm lint helm/argo-stack/

# Template validation
helm template test-release helm/argo-stack/ --values helm/argo-stack/ci-values.yaml

# Install in test cluster
helm upgrade --install test-stack helm/argo-stack/ \
  --namespace test --create-namespace \
  --values test-values.yaml \
  --dry-run
```

## 📤 Pull Request Process

1. **Update documentation** for any user-facing changes
2. **Add/update tests** for new functionality
3. **Ensure CI passes** (GitHub Actions)
4. **Use descriptive commit messages**:
   ```
   feat: add support for external OIDC providers
   fix: resolve authz-adapter timeout issues
   docs: update installation instructions
   ```
5. **Request review** from maintainers

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

## 🔒 Security

- **Report security issues** privately to the maintainers
- **Don't commit secrets** or credentials
- **Use secrets management** for sensitive configuration
- **Follow security best practices** in code

## 📋 Review Criteria

Pull requests will be reviewed for:

- **Functionality**: Does it work as intended?
- **Testing**: Are there adequate tests?
- **Documentation**: Is it properly documented?
- **Style**: Does it follow project conventions?
- **Security**: Are there any security concerns?
- **Performance**: Does it impact performance?

## 🏷️ Release Process

1. **Version bumping** follows semantic versioning
2. **Changelog** is maintained in CHANGELOG.md
3. **Releases** are tagged and published via GitHub
4. **Container images** are built and pushed automatically

## 🤝 Community

- Be respectful and inclusive
- Follow the Code of Conduct
- Help others in issues and discussions
- Share knowledge and best practices

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For general questions and ideas
- **Documentation**: Check the README and wiki first

## 📄 License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.