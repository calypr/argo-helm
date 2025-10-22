# Nextflow Workflow Testing

This directory contains tests and workflows for validating Nextflow execution through Argo Workflows with authorization.

## Files

### Workflows
- `nextflow-hello-world.yaml` - A simple Nextflow "Hello World" workflow that can be submitted to Argo Workflows

### Test Scripts
- `test_nextflow_execution.py` - Tests actual Nextflow workflow execution in Argo Workflows
- `test_authorization.py` - Tests authorization through the authz-adapter for workflow operations

## Usage

### Local Testing

1. **Set up a local environment:**
   ```bash
   # Start a kind cluster with Argo Workflows
   kind create cluster --name nextflow-test
   
   # Install Argo Workflows
   kubectl create namespace argo-workflows
   helm repo add argo https://argoproj.github.io/argo-helm
   helm install argo-workflows argo/argo-workflows -n argo-workflows
   
   # Port forward to access the API
   kubectl port-forward -n argo-workflows svc/argo-workflows-server 2746:2746 &
   ```

2. **Run the Nextflow execution test:**
   ```bash
   python test_nextflow_execution.py
   ```

3. **Run the authorization test:**
   ```bash
   python test_authorization.py
   ```

### CI Testing

The tests are automatically run in the GitHub Actions workflow `ci-nextflow.yaml` which:

1. Sets up a kind cluster
2. Installs the complete Argo stack with authorization
3. Runs the Nextflow workflow execution test
4. Validates authorization is working correctly

## Test Workflow Details

### nextflow-hello-world.yaml

This workflow:
- Uses the official Nextflow Docker image
- Creates a simple Nextflow script that processes multiple inputs
- Generates execution reports and traces
- Demonstrates container-based workflow execution
- Includes resource limits appropriate for CI environments

The workflow includes:
- **Input processing**: Processes a channel of test strings
- **Report generation**: Creates a summary report of execution
- **Artifact collection**: Saves execution traces and reports
- **Resource management**: Appropriate CPU and memory limits

### test_nextflow_execution.py

This script:
- Submits the workflow to Argo Workflows via REST API
- Monitors execution progress with timeout handling
- Retrieves and displays workflow logs
- Validates successful completion
- Provides detailed error reporting on failures

Features:
- Configurable Argo Workflows URL
- Configurable workflow file path
- Comprehensive logging and progress reporting
- Graceful error handling and cleanup

### test_authorization.py

This script validates:
- AuthZ adapter health and connectivity
- Workflow submission authorization for different user types
- Resource-specific authorization (Argo workflows vs other resources)
- Header-based authorization context (X-Resource-* headers)

Test scenarios:
- **Authorized users**: Users with workflow creation permissions
- **Read-only users**: Users with only workflow viewing permissions  
- **Unauthorized users**: Users without any workflow permissions
- **Resource context**: Authorization with Kubernetes resource context

## Expected Outcomes

### Successful Execution
When everything works correctly, you should see:

1. **Workflow submission**: HTTP 201 response from Argo Workflows API
2. **Execution progress**: Status updates showing workflow phases (Running → Succeeded)
3. **Nextflow output**: Log messages showing Nextflow process execution
4. **Test reports**: Generated files showing successful data processing
5. **Authorization**: Proper group assignments (argo-runner, argo-viewer)

### Common Issues

#### Network Connectivity
- Ensure port forwarding is active: `kubectl port-forward -n argo-workflows svc/argo-workflows-server 2746:2746`
- Check firewall settings and cluster networking

#### Authorization Failures
- Verify authz-adapter is deployed and healthy
- Check environment variables for Fence configuration
- Validate user tokens and permissions

#### Resource Constraints
- Monitor cluster resources: `kubectl top nodes`
- Check pod resource requests vs available capacity
- Adjust workflow resource limits if needed

#### Nextflow Issues
- Verify Nextflow image is accessible
- Check for script syntax errors in workflow definition
- Review container logs for Nextflow-specific errors

## Customization

### Modifying the Workflow
To customize the Nextflow workflow:

1. Edit `nextflow-hello-world.yaml`
2. Modify the Nextflow script embedded in the container args
3. Adjust resource requests and limits as needed
4. Add additional output artifacts if required

### Adding Test Cases
To add new test scenarios:

1. Create new workflow YAML files following the same pattern
2. Extend `test_nextflow_execution.py` with additional test methods
3. Add authorization test cases to `test_authorization.py`
4. Update the CI workflow to run new tests

### Environment Configuration
The tests support configuration via:

- Command line arguments (--argo-url, --authz-url, etc.)
- Environment variables
- Configuration files (for complex scenarios)

## Integration with CI/CD

The `ci-nextflow.yaml` GitHub Actions workflow provides:

- **Reproducible testing**: Same environment every time
- **Resource isolation**: Clean kind cluster for each run
- **Comprehensive validation**: Both functional and authorization testing
- **Artifact collection**: Logs and reports for debugging failures
- **Cleanup**: Automatic cleanup of resources after testing

This ensures that Nextflow workflows will work correctly in production Kubernetes environments with proper authorization controls.