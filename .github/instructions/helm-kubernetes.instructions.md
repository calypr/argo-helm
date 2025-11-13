---
description: 'Instructions for developing and maintaining Helm charts and Kubernetes manifests'
applyTo: '**/*.yaml, **/*.yml, **/Chart.yaml, **/values.yaml, **/templates/**'
---

# Helm and Kubernetes Development Instructions

## General Principles

- Follow Helm best practices and Kubernetes manifest conventions
- Write clean, maintainable, and reusable chart templates
- Ensure backward compatibility when making changes to existing charts
- Test all changes thoroughly before committing
- Document configuration options clearly in values.yaml and README files

## Helm Chart Development

### Chart Structure

- Organize charts following the standard Helm chart structure:
  - `Chart.yaml`: Chart metadata and dependencies
  - `values.yaml`: Default configuration values with comprehensive comments
  - `templates/`: Kubernetes manifest templates
  - `templates/_helpers.tpl`: Helper templates for reusable snippets
  - `README.md`: Chart documentation with usage examples

### Chart.yaml

- Follow semantic versioning for chart versions
- Increment `version` for chart changes, `appVersion` for application version changes
- List all dependencies with specific version constraints
- Include maintainer information and useful metadata
- Add keywords and home/source URLs for discoverability

### values.yaml

- Provide sensible defaults that work out of the box
- Document each configuration option with inline comments
- Group related settings logically with clear section headers
- Use consistent naming conventions (camelCase recommended)
- Mark required values clearly and provide example values
- Consider backward compatibility when adding or modifying values
- Use nested structures to organize complex configurations

### Templates

- Use consistent indentation (2 spaces)
- Include helpful comments explaining complex logic
- Use `{{- ` and ` -}}` to control whitespace appropriately
- Leverage `_helpers.tpl` for common patterns and labels
- Always quote string values in templates to prevent type issues
- Use `.Values`, `.Chart`, `.Release` objects appropriately
- Validate required values with `required` function
- Use `toYaml` and `nindent` for clean YAML output
- Include resource limits and requests for all containers
- Add health checks (liveness and readiness probes) where appropriate

### Template Best Practices

- Use `include` instead of `template` for better error messages
- Define common labels in `_helpers.tpl` and reuse them
- Use consistent naming for Kubernetes resources: `{{ include "chart.fullname" . }}`
- Implement conditional resource creation with `if` statements
- Validate inputs using the `required` and `fail` functions
- Use `lookup` function carefully (not available in `helm template`)
- Handle list values properly with `toYaml` and proper indentation

### Testing and Validation

- Run `helm lint` to check for issues before committing
- Use `helm template` to render manifests and verify output
- Test with `ct lint` (chart-testing tool) for comprehensive validation
- Use `kubeconform` or similar tools to validate Kubernetes manifests
- Test installation with `helm install` in a test cluster
- Verify upgrades work correctly with `helm upgrade`
- Test with different values files to ensure flexibility

## Kubernetes Manifest Best Practices

### Resource Specifications

- Always specify resource requests and limits
- Set appropriate security contexts (runAsNonRoot, readOnlyRootFilesystem, etc.)
- Use namespaces for resource isolation
- Apply proper RBAC (Roles, RoleBindings, ServiceAccounts)
- Add meaningful labels and annotations
- Use selectors consistently

### ConfigMaps and Secrets

- Use ConfigMaps for non-sensitive configuration
- Use Secrets for sensitive data
- Reference Secrets securely in pod specs
- Consider using external secret management solutions
- Document which secrets need to be created before installation

### Networking

- Define Services with appropriate types (ClusterIP, NodePort, LoadBalancer)
- Configure Ingress resources with proper annotations for your ingress controller
- Use NetworkPolicies for network segmentation when needed
- Document external dependencies and endpoints

### High Availability and Scaling

- Support replica configuration for stateless applications
- Use PodDisruptionBudgets for critical services
- Configure HorizontalPodAutoscaler when appropriate
- Consider anti-affinity rules for better pod distribution
- Use StatefulSets for stateful applications

### Observability

- Include health check endpoints for all services
- Add Prometheus annotations for metric scraping when applicable
- Configure proper logging (stdout/stderr)
- Add readiness and liveness probes with appropriate thresholds

## Argo-Specific Patterns

### Argo Workflows

- Follow Argo Workflows best practices for WorkflowTemplate definitions
- Use proper artifact repository configuration
- Configure service accounts with appropriate RBAC
- Use templates for reusable workflow components
- Document workflow parameters and usage

### Argo CD

- Structure Application manifests with proper sync policies
- Use automated sync with caution (prune and selfHeal options)
- Configure proper health checks for custom resources
- Use Projects for multi-tenancy when appropriate
- Document repository requirements and access patterns

### Argo Events

- Define EventSources with proper authentication
- Create Sensors with clear trigger conditions
- Use proper RBAC for event processing
- Document webhook configurations and expected payloads

## Multi-Tenancy and RBAC

- Create proper namespace isolation
- Define clear RBAC roles (viewer, runner, admin)
- Use RoleBindings and ClusterRoleBindings appropriately
- Document permission requirements
- Test RBAC policies with `kubectl auth can-i`

## Documentation

- Keep README.md up to date with:
  - Prerequisites and dependencies
  - Installation instructions
  - Configuration examples
  - Upgrade procedures
  - Troubleshooting tips
- Document breaking changes in CHANGELOG
- Provide example values files for common scenarios
- Include mermaid diagrams for architecture when helpful

## Common Pitfalls to Avoid

- Don't hardcode values that should be configurable
- Don't ignore backward compatibility in existing charts
- Don't skip testing with different values combinations
- Don't forget to update Chart.yaml version
- Don't use deprecated Kubernetes API versions
- Don't omit resource limits (can cause cluster issues)
- Don't expose secrets in logs or status outputs
- Avoid creating breaking changes without major version bump

## Validation Commands

Always run these commands before committing:

```bash
# Add Helm dependencies
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Build dependencies
helm dependency build helm/argo-stack

# Lint the chart
helm lint helm/argo-stack --values helm/argo-stack/values.yaml

# Render templates
helm template argo-stack helm/argo-stack \
  --values helm/argo-stack/values.yaml \
  --namespace argocd > rendered.yaml

# Validate manifests
kubeconform -strict -ignore-missing-schemas \
  -skip 'CustomResourceDefinition|Application|Workflow|WorkflowTemplate' \
  -summary rendered.yaml

# Test with ct (if available)
ct lint --config .ct.yaml
```

## Version Compatibility

- Target Kubernetes 1.20+ unless specific compatibility is needed
- Use stable API versions (avoid alpha/beta in production)
- Test with multiple Kubernetes versions when possible
- Document minimum required versions in Chart.yaml and README
