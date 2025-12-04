---
description: 'Instructions for writing Bash scripts following best practices and conventions'
applyTo: '**/*.sh, **/Makefile'
---

# Bash Scripting Instructions

## General Principles

- Write portable, readable, and maintainable shell scripts
- Follow POSIX standards where possible, use Bash-specific features when beneficial
- Include error handling and validation
- Make scripts idempotent when possible
- Document script usage and requirements

## Script Structure

### Shebang and Options

- Always start scripts with `#!/bin/bash` (or `#!/usr/bin/env bash` for portability)
- Use `set -e` to exit on errors (or `set -euo pipefail` for stricter error handling)
- Consider `set -u` to treat unset variables as errors
- Use `set -x` for debugging when needed (or enable via DEBUG environment variable)

Example:
```bash
#!/bin/bash
set -euo pipefail

# Optional debugging
[[ "${DEBUG:-}" == "true" ]] && set -x
```

### Script Organization

- Start with a header comment describing the script's purpose
- Define all functions before the main script logic
- Include a usage/help function
- Place main execution logic at the bottom
- Use clear section separators

Example:
```bash
#!/bin/bash
# Description: Deploy Argo stack to Kubernetes
# Usage: ./deploy.sh [options]

set -euo pipefail

#################
# Configuration #
#################

DEFAULT_NAMESPACE="argocd"
TIMEOUT="10m"

#############
# Functions #
#############

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
    -n, --namespace    Target namespace (default: ${DEFAULT_NAMESPACE})
    -h, --help         Show this help message
EOF
}

check_prerequisites() {
    # Check for required tools
    command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required"; exit 1; }
}

main() {
    check_prerequisites
    # Main logic here
}

########
# Main #
########

main "$@"
```

## Error Handling

### Exit Codes

- Use meaningful exit codes (0 for success, non-zero for errors)
- Document exit codes in help text for complex scripts
- Use consistent exit codes across scripts

### Validation

- Validate required environment variables early:
```bash
: "${REQUIRED_VAR:?Error: REQUIRED_VAR must be set}"
```

- Check for required commands:
```bash
command -v kubectl >/dev/null 2>&1 || {
    echo "Error: kubectl is required but not installed"
    exit 1
}
```

- Validate file existence:
```bash
[[ -f "${CONFIG_FILE}" ]] || {
    echo "Error: Config file not found: ${CONFIG_FILE}"
    exit 1
}
```

### Cleanup and Traps

- Use `trap` for cleanup operations:
```bash
cleanup() {
    rm -f "${TEMP_FILE}"
}
trap cleanup EXIT INT TERM
```

## Variables and Quoting

### Variable Naming

- Use UPPER_CASE for environment variables and constants
- Use lower_case for local variables
- Use descriptive names (avoid single letters except for loop counters)

### Quoting

- Always quote variables unless you explicitly want word splitting: `"${var}"`
- Quote command substitutions: `"$(command)"`
- Use arrays for lists instead of space-separated strings
- Don't quote variables in `[[ ]]` conditions (they're safe there)

### Arrays

- Use arrays for lists of items:
```bash
namespaces=("argo" "argocd" "security")
for ns in "${namespaces[@]}"; do
    echo "${ns}"
done
```

## Conditionals and Loops

### If Statements

- Use `[[ ]]` instead of `[ ]` for better error handling and features
- Prefer explicit comparisons:
```bash
if [[ "${STATUS}" == "ready" ]]; then
    echo "Ready"
fi

if [[ -n "${VAR}" ]]; then  # Check if variable is not empty
    echo "VAR is set"
fi

if [[ -z "${VAR}" ]]; then  # Check if variable is empty
    echo "VAR is not set"
fi
```

### Loops

- Use `for` loops for iterating over arrays
- Use `while read` for processing lines:
```bash
while IFS= read -r line; do
    echo "${line}"
done < file.txt
```

- Break long loops into functions for readability

## Functions

### Function Definition

- Define functions before use
- Use clear, descriptive function names
- Add comments describing parameters and return values
- Use `local` for function-scoped variables

```bash
# Deploy a Helm chart
# Arguments:
#   $1 - chart name
#   $2 - namespace
#   $3 - values file (optional)
# Returns:
#   0 on success, 1 on failure
deploy_chart() {
    local chart_name="${1}"
    local namespace="${2}"
    local values_file="${3:-}"
    
    local helm_args=(
        upgrade --install
        "${chart_name}"
        "./charts/${chart_name}"
        --namespace "${namespace}"
        --create-namespace
    )
    
    if [[ -n "${values_file}" ]]; then
        helm_args+=(--values "${values_file}")
    fi
    
    helm "${helm_args[@]}"
}
```

## Command Execution

### Command Substitution

- Use `$(command)` instead of backticks
- Check command success:
```bash
if output=$(kubectl get pods 2>&1); then
    echo "Success: ${output}"
else
    echo "Failed to get pods"
    exit 1
fi
```

### Pipelines

- Use `set -o pipefail` to catch errors in pipelines
- Consider breaking complex pipelines into steps

### Background Jobs

- Track background processes:
```bash
kubectl port-forward svc/myservice 8080:80 &
PF_PID=$!

# Later, clean up
kill "${PF_PID}" 2>/dev/null || true
```

## Output and Logging

### User Feedback

- Use descriptive output messages with emoji when appropriate:
```bash
echo "✅ Deployment successful"
echo "❌ Error: Deployment failed"
echo "🔍 Checking prerequisites..."
echo "⚠️  Warning: Resource limits not set"
```

### Debugging

- Use meaningful debug output:
```bash
if [[ "${DEBUG:-false}" == "true" ]]; then
    echo "DEBUG: Variable value: ${VAR}"
fi
```

### Error Messages

- Write errors to stderr:
```bash
echo "Error: Something went wrong" >&2
exit 1
```

## Kubernetes-Specific Patterns

### Waiting for Resources

- Use `kubectl wait` instead of sleep loops:
```bash
kubectl wait --for=condition=Ready pod \
    -l app=myapp \
    --timeout=120s \
    -n "${namespace}"
```

### Namespace Operations

- Always specify namespace explicitly:
```bash
kubectl get pods -n "${namespace}"
```

- Check if namespace exists:
```bash
if kubectl get namespace "${namespace}" >/dev/null 2>&1; then
    echo "Namespace exists"
fi
```

### Safe Deletions

- Use `|| true` for delete operations that might not find resources:
```bash
kubectl delete namespace "${namespace}" --ignore-not-found=true
# or
kubectl delete pod mypod 2>/dev/null || true
```

## Makefile Conventions

### Targets

- Use `.PHONY` for non-file targets
- Provide a `help` target as default
- Use descriptive target names
- Add comments explaining what each target does

### Variables

- Define configurable variables with defaults
- Use `?=` for variables that can be overridden
- Document required environment variables

Example:
```makefile
.PHONY: help deploy clean

NAMESPACE ?= default
TIMEOUT ?= 10m

help:
	@echo "Available targets:"
	@echo "  deploy    - Deploy the application"
	@echo "  clean     - Clean up resources"

deploy:
	@echo "🚀 Deploying to namespace: $(NAMESPACE)"
	helm upgrade --install myapp ./charts/myapp \
		--namespace $(NAMESPACE) \
		--timeout $(TIMEOUT)

clean:
	@echo "🧹 Cleaning up..."
	helm uninstall myapp -n $(NAMESPACE) || true
```

## Security Considerations

### Secrets and Sensitive Data

- Never hardcode secrets in scripts
- Use environment variables or secret management tools
- Don't echo sensitive variables (they'll appear in logs)
- Be careful with `set -x` when handling secrets

### Input Validation

- Validate all external inputs
- Sanitize user-provided values
- Be cautious with `eval` (avoid if possible)

## Testing

### Dry Runs

- Support dry-run mode where applicable:
```bash
DRY_RUN="${DRY_RUN:-false}"

run_command() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "Would run: $*"
    else
        "$@"
    fi
}
```

### ShellCheck

- Run `shellcheck` on all shell scripts before committing
- Address or suppress warnings with justification
- Add shellcheck directives when needed:
```bash
# shellcheck disable=SC2034  # VAR appears unused
VAR="value"
```

## Common Patterns

### Checking Command Availability

```bash
has_command() {
    command -v "$1" >/dev/null 2>&1
}

if ! has_command kubectl; then
    echo "kubectl not found"
    exit 1
fi
```

### Retry Logic

```bash
retry() {
    local max_attempts=$1
    shift
    local cmd=("$@")
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if "${cmd[@]}"; then
            return 0
        fi
        echo "Attempt ${attempt}/${max_attempts} failed, retrying..."
        ((attempt++))
        sleep 2
    done
    
    return 1
}

retry 3 kubectl get pods
```

### Temporary Files

```bash
# Create temp file safely
TEMP_FILE=$(mktemp)
trap 'rm -f "${TEMP_FILE}"' EXIT

# Use it
echo "data" > "${TEMP_FILE}"
```

## Common Pitfalls to Avoid

- Don't use `cd` without error checking or in subshells
- Don't parse `ls` output (use globs or `find` instead)
- Don't use `cat file | grep` (use `grep pattern file`)
- Don't ignore command failures with `;` (use `&&` for chaining)
- Don't use `echo` for complex output (use `printf` or heredocs)
- Don't assume scripts run from a specific directory (use absolute paths or `cd "$(dirname "$0")"`)
- Avoid `which` (use `command -v` instead)

## Documentation

- Include usage information in scripts (help function)
- Document required environment variables
- Add examples in comments
- Keep comments up to date with code
