# Argo-Wrapper Architecture Documentation

## Overview

**argo-wrapper** is a Python-based FastAPI service that provides a REST API wrapper around Argo Workflows, facilitating workflow execution for GWAS (Genome-Wide Association Studies) and PLP (Patient Level Prediction) analyses in Gen3 Data Commons environments.  The service acts as an intermediary between frontend applications and the underlying Argo Workflows engine, handling authentication, authorization, and workflow lifecycle management.

## System Architecture

### High-Level Components

```
┌─────────────────┐
│   Frontend      │
│   (GWAS UI)     │
└────────┬────────┘
         │ Bearer Token
         ▼
┌─────────────────────────────────────┐
│      Argo-Wrapper Service           │
│  ┌──────────────────────────────┐   │
│  │  FastAPI Routes              │   │
│  │  - /submit                   │   │
│  │  - /status/{workflow_name}   │   │
│  │  - /workflows                │   │
│  │  - /cancel/{workflow_name}   │   │
│  │  - /retry/{workflow_name}    │   │
│  └──────────┬───────────────────┘   │
│             │                        │
│  ┌──────────▼───────────────────┐   │
│  │  Authentication/Authorization│   │
│  │  (Fence + Arborist)          │   │
│  └──────────┬───────────────────┘   │
│             │                        │
│  ┌──────────▼───────────────────┐   │
│  │  Workflow Factory            │   │
│  │  - GWAS                      │   │
│  │  - PLP                       │   │
│  └──────────┬───────────────────┘   │
│             │                        │
│  ┌──────────▼───────────────────┐   │
│  │  Argo Engine Client          │   │
│  │  (Kubernetes Client)         │   │
│  └──────────┬───────────────────┘   │
└─────────────┼───────────────────────┘
              │
              ▼
┌───────────────────────────────────────┐
│   Argo Workflows Engine               │
│   (Kubernetes Namespace:  argo)        │
│                                       │
│   ┌─────────────────────────────┐     │
│   │  Workflow Templates          │     │
│   │  - gwas-template-{version}   │     │
│   │  - plp-template-{version}    │     │
│   └─────────────────────────────┘     │
│                                       │
│   ┌─────────────────────────────┐     │
│   │  Running Workflows           │     │
│   │  (Workflow Pods)             │     │
│   └─────────────────────────────┘     │
└───────────────────────────────────────┘
```

## Kubernetes Namespace Usage

### Namespace Configuration

Argo-wrapper uses Kubernetes namespaces in the following ways:

#### 1. **Argo Workflows Namespace**

- **Default Namespace**: `argo`
- **Configuration**: Set via `ARGO_NAMESPACE` in `config.ini`
- **Purpose**: All Argo workflow resources (workflows, pods, templates) run within this namespace

```ini
[DEFAULT]
ARGO_NAMESPACE = argo
```

**Source**: `src/argowrapper/constants. py`
```python
ARGO_NAMESPACE:  Final = config["DEFAULT"]["ARGO_NAMESPACE"]
```

#### 2. **Workflow Metadata Namespace**

Every workflow submission includes namespace metadata:

**Source**: `src/argowrapper/workflows/workflow_metadata.py`
```python
class WorkflowMetadata:
    def __init__(self, namespace: str):
        self.namespace = namespace
        # ... other fields
```

The namespace is passed when creating workflow instances: 

**Source**: `src/argowrapper/workflows/workflow_base.py`
```python
class WorkflowBase:
    def __init__(self, namespace: str, entrypoint:  WORKFLOW_ENTRYPOINT, dry_run=False):
        self.metadata = WorkflowMetadata(namespace)
```

#### 3. **Workflow Operations Namespace**

All Argo API operations specify the namespace:

- **Creating workflows**: `self.api_instance.create_workflow(namespace=ARGO_NAMESPACE, ... )`
- **Terminating workflows**: `self.api_instance.terminate_workflow(namespace=ARGO_NAMESPACE, ... )`
- **Retrying workflows**: `self.api_instance.retry_workflow(namespace=ARGO_NAMESPACE, ... )`

**Source**: `src/argowrapper/engine/argo_engine.py`
```python
response = self.api_instance.create_workflow(
    namespace=ARGO_NAMESPACE,
    body=IoArgoprojWorkflowV1alpha1WorkflowCreateRequest(
        workflow=workflow_yaml,
        _check_return_type=False,
        _check_type=False,
    ),
    _check_return_type=False,
    async_req=False,
)
```

#### 4. **Namespace Isolation**

- All workflows run in the same `argo` namespace
- User isolation is achieved through **labels** and **metadata**, not separate namespaces
- Users are identified via `gen3username` and `gen3teamproject` labels on workflows

### Key Takeaway on Namespaces

**The service uses a single, configurable Kubernetes namespace (default: `argo`) for all workflow execution. ** Multi-tenancy and user isolation are implemented through Kubernetes labels and Gen3's authorization layer (Arborist/Fence), not through separate namespaces. 

## Bearer Token Handling

### Token Flow Architecture

The user's Bearer token flows through the system as follows:

```
User Request
    │
    ├─ Authorization:  Bearer <JWT>
    │
    ▼
FastAPI Routes (routes. py)
    │
    ├─ Extract token from request. headers. get("Authorization")
    │
    ▼
Authentication Decorators
    │
    ├─ @check_auth
    ├─ @check_auth_and_team_project
    │
    ▼
Auth Module (auth/auth.py)
    │
    ├─ Validate with Fence (Gen3 auth service)
    ├─ Check Arborist permissions
    │
    ▼
Workflow Factory
    │
    ├─ Pass auth_header to workflow constructors
    │
    ▼
Workflow Classes (GWAS, PLP)
    │
    ├─ Extract username from JWT
    │   argo_engine_helper.get_username_from_token(auth_header)
    │
    ├─ Add as workflow metadata labels
    │
    ▼
Workflow Submission
    │
    └─ Token NOT passed to Argo workflow pods
        (Authentication happens at submission time only)
```

### Token Extraction and User Identification

**Source**: `src/argowrapper/workflows/argo_workflows/gwas.py`
```python
def __init__(
    self,
    namespace: str,
    request_body: Dict,
    auth_header: Optional[str],
    dry_run=False,
):
    self.username = argo_engine_helper. get_username_from_token(auth_header)
    self.gen3username_label = argo_engine_helper. convert_gen3username_to_pod_label(
        self.username
    )
```

The `get_username_from_token()` helper decodes the JWT token to extract the username: 

**Source**: `src/argowrapper/engine/helpers/argo_engine_helper.py`
```python
# Token is decoded to extract user context
# Example JWT payload:
# {
#   "context": {"user": {"name": "dummyuser"}}
# }
```

### Token Usage in Workflow Lifecycle

#### 1. **Workflow Submission** (`/submit`)

```python
@router.post("/submit", status_code=HTTP_200_OK)
@check_auth_and_team_project
def submit_workflow(
    request_body: Dict[Any, Any],
    request: Request,
) -> Union[str, Any]:
    return argo_engine. workflow_submission(
        request_body, request.headers.get("Authorization")
    )
```

**Purpose**: 
- Authenticate user
- Authorize access to `argo_workflow` service
- Verify team project permissions
- Extract username for workflow labels

#### 2. **Workflow Status** (`/status/{workflow_name}`)

```python
@router.get("/status/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_details(
    workflow_name: str,
    uid: str,
    request: Request,
) -> Union[Dict[str, Any], str, Any]:
```

**Purpose**:
- Verify user owns the workflow (via `gen3username` label)
- OR verify user has access to the workflow's team project

#### 3. **Token-Based Authorization Logic**

**Source**: `src/argowrapper/routes/routes.py`
```python
def check_auth(fn):
    """custom annotation to authenticate user request and check whether the
    user is authorized to access argo-wrapper and the workflow in question"""
    
    @wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs["request"]
        token = request. headers.get("Authorization")
        
        # Check authentication and basic argo-wrapper authorization: 
        if not auth. authenticate(token=token):
            return HTMLResponse(
                content="token is missing, not authorized, out of date, or malformed",
                status_code=HTTP_401_UNAUTHORIZED,
            )
        
        # Get workflow details.  If the workflow has a "team project" label, 
        # check if the user is authorized to this "team project": 
        workflow_details = argo_engine. get_workflow_details(workflow_name, uid)
        
        if GEN3_TEAM_PROJECT_METADATA_LABEL in workflow_details: 
            if not auth.authenticate(
                token=token,
                team_project=workflow_details[GEN3_TEAM_PROJECT_METADATA_LABEL],
            ):
                return HTMLResponse(
                    content="token is missing, not authorized.. .",
                    status_code=HTTP_401_UNAUTHORIZED,
                )
        else:
            # Check if the workflow is one of the user's own workflows:
            workflow_user = workflow_details[GEN3_USER_METADATA_LABEL]
            username = argo_engine_helper. get_username_from_token(token)
            current_user = argo_engine_helper.convert_gen3username_to_pod_label(username)
            
            if current_user != workflow_user: 
                return HTMLResponse(
                    content="user is not the author of this workflow.. .",
                    status_code=HTTP_401_UNAUTHORIZED,
                )
```

### How Token is Stored in Workflow Metadata

The Bearer token itself is **NOT** passed to the workflow pods. Instead:

1. **Username is extracted** from the JWT token
2. **Username is stored as labels and annotations** on the workflow metadata
3. **Team project** (if applicable) is stored as a label

**Source**: `src/argowrapper/workflows/argo_workflows/plp.py`
```python
def _add_metadata_labels(self):
    super()._add_metadata_labels()
    self.metadata.add_metadata_label(
        GEN3_USER_METADATA_LABEL, self.gen3username_label
    )
    self.metadata.add_metadata_label(
        GEN3_TEAM_PROJECT_METADATA_LABEL, self.gen3teamproject_label
    )

def _add_spec_podMetadata_annotations(self):
    self.spec.add_pod_metadata_annotation("gen3username", self.username)
```

### Security Consideration

**The Bearer token is NOT passed to Argo workflow containers. ** This is a security best practice: 
- Authentication happens at the API boundary
- Workflows run with their own service account permissions
- User context is preserved via metadata labels, not active credentials

## Workflow Selection Mechanism

### How Users Determine Which Workflow to Run

Users specify the workflow type through the `template_version` parameter in the request body. 

#### 1. **Workflow Factory Pattern**

**Source**: `src/argowrapper/engine/helpers/workflow_factory.py`
```python
class WorkflowFactory:
    @staticmethod
    def _get_workflow(
        namespace: str,
        request_body: Dict[str, Any],
        auth_header: Optional[str],
    ):
        if request_body["template_version"]. startswith("plp-template"):
            workflow = PLP
        elif request_body["template_version"].startswith("gwas-template"):
            workflow = GWAS

        return workflow(namespace, request_body, auth_header)
```

**Workflow types are determined by the `template_version` field prefix:**
- `plp-template*` → Patient Level Prediction workflow
- `gwas-template*` → Genome-Wide Association Study workflow

#### 2. **Template Version Format**

Template versions follow this pattern:
```
{workflow-type}-template-{version}
```

Examples:
- `gwas-template-latest`
- `gwas-template-abc123` (git hash)
- `plp-template-v1.2.3`

**Source**: `test/test_routes.py`
```python
request_body = {
    # ...  other parameters
    "template_version": "gwas-template-latest",
    # ... 
}
```

#### 3. **Workflow Template Reference**

The `template_version` is used to reference pre-deployed Argo Workflow Templates in the cluster:

**Source**: `src/argowrapper/workflows/argo_workflows/gwas.py`
```python
def setup_spec(self):
    super().setup_spec()
    self.spec.set_podGC_strategy(POD_COMPLETION_STRATEGY. ONPODCOMPLETION. value)
    self._add_spec_scaling_group()
    self._add_spec_podMetadata_annotations()
    self._add_spec_podMetadata_labels()
    self._add_spec_parameters()
    self._add_spec_volumes()
    # Template version from request body references the Argo WorkflowTemplate
    self.spec.set_workflow_template_ref(
        self.workflow_parameters. get("template_version")
    )
```

**Source**: `src/argowrapper/workflows/workflow_spec.py`
```python
def set_workflow_template_ref(self, workflow_template_name: str) -> None:
    self.workflowTemplateRef = {"name": workflow_template_name}
```

#### 4. **Available Workflow Types**

**Source**: `src/argowrapper/constants.py`
```python
class WORKFLOW_ENTRYPOINT(Enum):
    GWAS_ENTRYPOINT = "gwas-workflow"
    PLP_ENTRYPOINT = "plp"

class WORKFLOW(Enum):
    GWAS = "GWAS"
    PLP = "PLP"
```

#### 5. **Workflow Template Deployment**

Argo Workflow Templates must be pre-deployed to the cluster:

**From**:  `docs/readmes/argo-templates.md`
```markdown
### Adding a new workflow template to data commons

1. scp the new template. yaml to the data commons you want to add it to. 
2. ssh onto the environment and run `argo template create -n argo {location_of_the_template_yaml}`
3. confirm that the template is created via running `argo template list -n argo`
```

Templates are stored externally (e.g., in the [vadc-genesis-cwl](https://github.com/uc-cdis/vadc-genesis-cwl/tree/master/argo/gwas-workflows) repository) and versioned by git hash.

### Workflow Selection Flow

```
User Request
    │
    ├─ POST /submit
    ├─ Body: { "template_version": "gwas-template-abc123", ... }
    │
    ▼
WorkflowFactory._get_workflow()
    │
    ├─ Check template_version prefix
    │   ├─ "plp-template*" → PLP class
    │   └─ "gwas-template*" → GWAS class
    │
    ▼
Workflow Class Constructor
    │
    ├─ Initialize with namespace, request_body, auth_header
    ├─ Extract user context from token
    ├─ Set metadata labels
    │
    ▼
setup_spec()
    │
    ├─ Configure workflow specification
    ├─ Set workflowTemplateRef to template_version value
    │   e.g., {"name": "gwas-template-abc123"}
    │
    ▼
Submit to Argo
    │
    └─ Argo resolves the WorkflowTemplate reference
        and instantiates the workflow
```

### Example Request

```bash
curl -d '{
  "template_version": "gwas-template-latest",
  "team_project": "my-research-project",
  "n_pcs": 3,
  "case_cohort_definition_id": 401,
  "control_cohort_definition_id": -1,
  "hare_population": "ASN",
  "outcome": 2000006885,
  "variables": [... ],
  "genome_build": "hg19",
  "maf_threshold": 0.01,
  "imputation_score_cutoff": 0.3,
  "workflow_name": "my-gwas-analysis"
}' \
-X POST \
-H "Content-Type: application/json" \
-H "Authorization: bearer <JWT_TOKEN>" \
https://{commons-url}/ga4gh/wes/v2/submit
```

### Key Parameters

| Parameter | Purpose |
|-----------|---------|
| `template_version` | **Required**. Determines workflow type and references specific Argo WorkflowTemplate |
| `team_project` | **Required**. Team project for authorization and resource labeling |
| `workflow_name` | User-friendly name stored in workflow annotations |
| Additional parameters | Workflow-specific inputs (GWAS vs PLP have different parameters) |

## Configuration

### Environment Configuration

**Source**: `config. ini`
```ini
[DEFAULT]
ARGO_ACCESS_METHOD = access
ARGO_HOST = http://argo-argo-workflows-server. argo.svc.cluster.local:2746
ARGO_NAMESPACE = argo
COHORT_MIDDLEWARE_URL = http://cohort-middleware-service
```

### Key Configuration Constants

**Source**: `src/argowrapper/constants.py`
```python
ARGO_HOST: Final = config["DEFAULT"]["ARGO_HOST"]
ARGO_NAMESPACE: Final = config["DEFAULT"]["ARGO_NAMESPACE"]
COHORT_MIDDLEWARE_URL:  Final = config["DEFAULT"]["COHORT_MIDDLEWARE_URL"]

# Authorization
ARGO_ACCESS_SERVICE:  Final = "argo_workflow"
ARGO_ACCESS_METHOD: Final = config["DEFAULT"]["ARGO_ACCESS_METHOD"]
TEAM_PROJECT_ACCESS_SERVICE: Final = "atlas-argo-wrapper-and-cohort-middleware"
TEAM_PROJECT_ACCESS_METHOD: Final = "access"

# Workflow metadata labels
GEN3_USER_METADATA_LABEL:  Final = "gen3username"
GEN3_TEAM_PROJECT_METADATA_LABEL: Final = "gen3teamproject"
GEN3_WORKFLOW_PHASE_LABEL: Final = "phase"

# Workflow limits
GEN3_NON_VA_WORKFLOW_MONTHLY_CAP: Final = 20
GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP: Final = 50
```

## Authorization Model

### Multi-Level Authorization

1. **Service-level authorization**:  User must have `argo_workflow. access` permission
2. **Team project authorization**: User must have access to specified team project
3. **Workflow ownership**: Users can only access workflows they own or their team owns

### Authorization Flow

```python
# 1. Basic service access
auth. authenticate(token=token)
# Checks: argo_workflow.access permission in Arborist

# 2. Team project access (for submission)
auth.authenticate(token=token, team_project="my-project")
# Checks: atlas-argo-wrapper-and-cohort-middleware.access for team_project

# 3. Workflow access (for status/cancel/retry)
# Checks: gen3username label OR gen3teamproject label matches user
```

## Workflow Lifecycle

### 1. Submission

```
POST /submit
    │
    ├─ Authenticate user
    ├─ Authorize team project access
    ├─ Validate request parameters
    ├─ Check monthly workflow cap
    │
    ▼
Create workflow object (GWAS or PLP)
    │
    ├─ Extract username from token
    ├─ Set metadata labels (gen3username, gen3teamproject)
    ├─ Configure workflow spec
    ├─ Reference workflow template
    │
    ▼
Submit to Argo Workflows API
    │
    └─ Return workflow name
```

### 2. Monitoring

```
GET /status/{workflow_name}? uid={uid}
    │
    ├─ Authenticate user
    ├─ Get workflow details from Argo
    ├─ Verify user owns workflow OR has team project access
    │
    └─ Return workflow status
```

### 3. Management

- **Retry**: `POST /retry/{workflow_name}? uid={uid}`
- **Cancel**: `POST /cancel/{workflow_name}`
- **Logs**: `GET /logs/{workflow_name}?uid={uid}`

## Data Flow

### Workflow Parameters

User-provided parameters flow through: 

1. **Request body** → Validated and sanitized
2. **WorkflowFactory** → Creates appropriate workflow class
3. **Workflow spec arguments** → Added as Argo workflow parameters
4. **Argo WorkflowTemplate** → Receives parameters and executes

**Source**: `src/argowrapper/workflows/argo_workflows/gwas.py`
```python
def _add_spec_parameters(self):
    """spec parameter ordering matters and must align with input parameter order
    in the self.template_ref.  Thus we setup the user defined parameters then
    hard coded ones."""
    self._add_user_defined_spec_parameters()
    self._add_hard_coded_spec_parameters()
    self._add_param_helper(
        {"internal_api_env":  argo_engine_helper._get_internal_api_env()}
    )
```

### Storage Integration

Workflows access shared data via Persistent Volume Claims: 

**Source**: `src/argowrapper/workflows/argo_workflows/gwas.py`
```python
def _add_spec_volumes(self):
    pvc_name = argo_engine_helper._get_argo_config_dict().get(
        "pvc", BACKUP_PVC_NAME
    )
    logger.info(f"pvc {pvc_name} is used as storage gateway pvc")
    self.spec.add_persistent_volume_claim("gateway", pvc_name)
    self.spec.add_empty_dir("workdir", "20Gi")
```

## API Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/submit` | POST | Submit new workflow | `@check_auth_and_team_project` |
| `/status/{workflow_name}` | GET | Get workflow status | `@check_auth` |
| `/workflows` | GET | List user's workflows | `@check_auth_and_optional_team_projects` |
| `/cancel/{workflow_name}` | POST | Cancel running workflow | `@check_auth` |
| `/retry/{workflow_name}` | POST | Retry failed workflow | `@check_auth` |
| `/logs/{workflow_name}` | GET | Get workflow logs | `@check_auth` |
| `/workflows/user-monthly` | GET | Get monthly usage stats | None (uses token) |

## Key Design Patterns

### 1. **Factory Pattern**
- `WorkflowFactory` creates appropriate workflow instances based on `template_version`

### 2. **Template Method Pattern**
- `WorkflowBase` defines common workflow structure
- `GWAS` and `PLP` classes override specific setup methods

### 3. **Decorator Pattern**
- `@check_auth`, `@check_auth_and_team_project` for authentication/authorization

### 4. **Builder Pattern**
- `WorkflowMetadata` and `WorkflowSpec` build workflow definitions incrementally

## Security Considerations

1. **Token Isolation**: Bearer tokens never passed to workflow pods
2. **Label-Based Authorization**: Workflows tagged with user and team project
3. **Monthly Caps**: Workflow submission limits prevent resource abuse
4. **Namespace Isolation**: All workflows in single namespace, isolated via RBAC
5. **Validation**: Input parameters validated before workflow creation

## Monitoring and Observability

### Workflow Metadata

Every workflow includes:
- `gen3username`: User who submitted (label and annotation)
- `gen3teamproject`: Associated team project
- `workflow_name`: User-provided friendly name
- `phase`: Current workflow state (Running, Succeeded, Failed)
- `submittedAt`: Submission timestamp

### Query Patterns

Users can query workflows by:
- **Username**: All workflows for a user
- **Team project**: All workflows for a project
- **Phase**: Filter by status (running, succeeded, failed)
- **Monthly**:  Workflows submitted in current month

## Deployment

### Prerequisites
- Kubernetes cluster
- Argo Workflows deployed in `argo` namespace
- Gen3 Fence (authentication service)
- Gen3 Arborist (authorization service)
- Workflow templates pre-deployed

### Configuration Steps

1. Deploy Argo Workflows to cluster
2. Create workflow templates (from vadc-genesis-cwl repo)
3. Configure `config.ini` with Argo host and namespace
4. Deploy argo-wrapper service
5. Configure Arborist policies for workflow access

**From**:  `docs/readmes/deploy. md`
```yaml
# Arborist role definition
- id: 'workflow_admin'
  permissions:
    - id: 'argo_access'
      action: 
        service: 'argo_workflow'
        method: 'access'
```

## Further Documentation

- **API Documentation**: See `/docs` Swagger UI when service is running
- **Workflow Templates**: [vadc-genesis-cwl repository](https://github.com/uc-cdis/vadc-genesis-cwl/tree/master/argo/gwas-workflows)
- **Local Development**: `docs/readmes/local-dev.md`
- **Deployment Guide**: `docs/readmes/deploy.md`

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-29  
**Repository**: [uc-cdis/argo-wrapper](https://github.com/uc-cdis/argo-wrapper)