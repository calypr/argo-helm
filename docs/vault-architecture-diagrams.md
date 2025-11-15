# Vault Integration Architecture Diagrams

This document contains architecture diagrams for the Vault + ESO integration.

## Overall Architecture

```mermaid
graph TB
    subgraph "HashiCorp Vault"
        V[Vault Server<br/>KV v2 Engine]
        VP[Vault Policies<br/>argo-stack-policy]
        VA[Vault Auth<br/>kubernetes/approle]
    end
    
    subgraph "Kubernetes Cluster"
        subgraph "ESO Namespace"
            ESO[External Secrets<br/>Operator]
        end
        
        subgraph "argocd Namespace"
            SS[SecretStore<br/>argo-stack-vault]
            SA[ServiceAccount<br/>eso-vault-auth]
            
            ES1[ExternalSecret<br/>argocd-secret]
            ES2[ExternalSecret<br/>argocd-initial-admin-secret]
            
            S1[Secret<br/>argocd-secret]
            S2[Secret<br/>argocd-initial-admin-secret]
            
            ACD[Argo CD<br/>Pods]
        end
        
        subgraph "argo-events Namespace"
            ES3[ExternalSecret<br/>github-secret]
            S3[Secret<br/>github-secret]
            AE[Argo Events<br/>EventSource]
        end
        
        subgraph "wf-poc Namespace"
            ES4[ExternalSecret<br/>s3-credentials]
            S4[Secret<br/>s3-credentials]
            AW[Argo Workflows<br/>Pods]
        end
    end
    
    V -->|1. Authenticate| VA
    SA -->|2. Request Token| VA
    SS -->|3. Connect with Auth| V
    ES1 -->|4. Reference| SS
    ES2 -->|4. Reference| SS
    ES3 -->|4. Reference| SS
    ES4 -->|4. Reference| SS
    
    ESO -->|5. Reconcile| ES1
    ESO -->|5. Reconcile| ES2
    ESO -->|5. Reconcile| ES3
    ESO -->|5. Reconcile| ES4
    
    ES1 -->|6. Fetch Secret| V
    ES2 -->|6. Fetch Secret| V
    ES3 -->|6. Fetch Secret| V
    ES4 -->|6. Fetch Secret| V
    
    ES1 -->|7. Create/Update| S1
    ES2 -->|7. Create/Update| S2
    ES3 -->|7. Create/Update| S3
    ES4 -->|7. Create/Update| S4
    
    S1 -->|8. Mount/Read| ACD
    S2 -->|8. Mount/Read| ACD
    S3 -->|8. Mount/Read| AE
    S4 -->|8. Mount/Read| AW
```

## Secret Synchronization Flow

```mermaid
sequenceDiagram
    participant Admin
    participant Vault
    participant ESO
    participant K8sSecret
    participant Pod
    
    Admin->>Vault: 1. Create/Update Secret
    Note over Vault: kv/argo/component/secret
    
    ESO->>Vault: 2. Authenticate (every token TTL)
    Vault-->>ESO: Token
    
    loop Every refreshInterval (default 1h)
        ESO->>Vault: 3. Fetch Secret Data
        Vault-->>ESO: Secret Value
        ESO->>K8sSecret: 4. Create/Update Secret
    end
    
    Pod->>K8sSecret: 5. Read Secret
    K8sSecret-->>Pod: Secret Data
    
    Admin->>Vault: 6. Rotate Secret
    Note over Vault: Secret updated
    
    ESO->>Vault: 7. Fetch (next refresh)
    Vault-->>ESO: New Secret Value
    ESO->>K8sSecret: 8. Update Secret
    
    Note over Pod: Pod may need restart<br/>to pick up change
```

## Authentication Flow: Kubernetes Auth

```mermaid
sequenceDiagram
    participant ESO as External Secrets<br/>Operator
    participant SA as ServiceAccount<br/>eso-vault-auth
    participant K8s as Kubernetes API
    participant Vault
    
    ESO->>SA: 1. Get ServiceAccount Token
    SA-->>ESO: JWT Token
    
    ESO->>Vault: 2. Login with JWT
    Note over Vault: POST /auth/kubernetes/login<br/>role=argo-stack<br/>jwt=<token>
    
    Vault->>K8s: 3. Validate Token
    K8s-->>Vault: Token Valid
    
    Vault-->>ESO: 4. Vault Token (TTL 1h)
    
    ESO->>Vault: 5. Read Secret
    Note over Vault: GET /kv/data/argo/component/secret<br/>X-Vault-Token: <vault-token>
    
    Vault-->>ESO: 6. Secret Data
```

## Vault Path Structure

```
vault
└── kv/                          (KV v2 secrets engine)
    └── argo/                     (defaultPathPrefix)
        ├── argocd/
        │   ├── admin             (password, bcryptHash)
        │   ├── oidc              (clientSecret)
        │   └── server            (secretKey)
        ├── workflows/
        │   ├── artifacts         (accessKey, secretKey)
        │   └── oidc              (clientSecret)
        ├── authz/                (clientSecret)
        ├── events/
        │   └── github            (token)
        └── apps/
            ├── nextflow-hello/
            │   └── s3            (accessKey, secretKey)
            └── nextflow-hello-2/
                └── s3            (accessKey, secretKey)
```

## ExternalSecret Resource Flow

```mermaid
graph LR
    V[values.yaml<br/>externalSecrets.secrets.argocd]
    T[Template<br/>externalsecret-argocd.yaml]
    ES[ExternalSecret<br/>argocd-secret]
    SS[SecretStore<br/>argo-stack-vault]
    K8S[Secret<br/>argocd-secret]
    
    V -->|Helm renders| T
    T -->|Creates| ES
    ES -->|References| SS
    ES -->|ESO reconciles| K8S
    
    style ES fill:#e1f5ff
    style K8S fill:#d4edda
```

## Helm Values to Vault Path Mapping

```mermaid
graph TB
    subgraph "values.yaml"
        V1[externalSecrets.secrets.argocd<br/>adminPasswordPath:<br/>'argocd/admin#password']
    end
    
    subgraph "Template Processing"
        H1[Helper: replace '#' with '/']
    end
    
    subgraph "ExternalSecret"
        E1[remoteRef.key:<br/>'argocd/admin/password']
    end
    
    subgraph "ESO Processing"
        P1[Prepend defaultPathPrefix]
    end
    
    subgraph "Vault API Call"
        VK[GET /v1/kv/data/argo/argocd/admin]
        VR[Response: data.data.password]
    end
    
    subgraph "Kubernetes Secret"
        KS[Secret 'argocd-secret'<br/>data.password: <value>]
    end
    
    V1 --> H1
    H1 --> E1
    E1 --> P1
    P1 --> VK
    VK --> VR
    VR --> KS
```

## Conditional Template Rendering

```mermaid
graph TB
    START{ESO Enabled?}
    START -->|externalSecrets.enabled=true| ESO_PATH
    START -->|externalSecrets.enabled=false| TRAD_PATH
    
    ESO_PATH[Render ESO Templates]
    ESO_PATH --> SS[SecretStore]
    ESO_PATH --> ES[ExternalSecrets]
    ESO_PATH --> SKIP[Skip traditional Secrets]
    
    TRAD_PATH[Render Traditional Templates]
    TRAD_PATH --> TS[Secret: github-secret]
    TRAD_PATH --> TS2[Secret: s3-credentials]
    TRAD_PATH --> SKIP2[Skip ESO resources]
    
    style ESO_PATH fill:#e1f5ff
    style TRAD_PATH fill:#fff3cd
```

## Multi-Tenancy with Vault Policies

```mermaid
graph TB
    subgraph "Vault Policies"
        P1[argo-cd-policy<br/>read: kv/data/argo/argocd/*]
        P2[argo-workflows-policy<br/>read: kv/data/argo/workflows/*<br/>read: kv/data/argo/apps/*]
        P3[argo-events-policy<br/>read: kv/data/argo/events/*]
    end
    
    subgraph "Vault Roles"
        R1[kubernetes/argo-cd-role<br/>bound_sa: eso-argocd<br/>policies: argo-cd-policy]
        R2[kubernetes/argo-workflows-role<br/>bound_sa: eso-workflows<br/>policies: argo-workflows-policy]
        R3[kubernetes/argo-events-role<br/>bound_sa: eso-events<br/>policies: argo-events-policy]
    end
    
    subgraph "Kubernetes"
        SA1[ServiceAccount<br/>eso-argocd<br/>namespace: argocd]
        SA2[ServiceAccount<br/>eso-workflows<br/>namespace: argo-workflows]
        SA3[ServiceAccount<br/>eso-events<br/>namespace: argo-events]
    end
    
    P1 --> R1
    P2 --> R2
    P3 --> R3
    
    R1 --> SA1
    R2 --> SA2
    R3 --> SA3
    
    style P1 fill:#ffe6e6
    style P2 fill:#e6f3ff
    style P3 fill:#e6ffe6
```

## Deployment Modes

### Mode 1: ESO Bundled (installOperator=true)

```mermaid
graph LR
    H[Helm Install<br/>argo-stack]
    
    subgraph "Chart Dependencies"
        D1[argo-workflows]
        D2[argo-cd]
        D3[external-secrets]
    end
    
    subgraph "Stack Templates"
        T1[SecretStore]
        T2[ExternalSecrets]
        T3[Other Resources]
    end
    
    H --> D1
    H --> D2
    H --> D3
    H --> T1
    H --> T2
    H --> T3
    
    D3 --> ESO[ESO Operator<br/>Running]
    T1 --> ESO
    T2 --> ESO
```

### Mode 2: ESO Pre-installed (installOperator=false)

```mermaid
graph LR
    PRE[Pre-installed<br/>ESO Operator]
    
    H[Helm Install<br/>argo-stack]
    
    subgraph "Chart Dependencies"
        D1[argo-workflows]
        D2[argo-cd]
    end
    
    subgraph "Stack Templates"
        T1[SecretStore]
        T2[ExternalSecrets]
        T3[Other Resources]
    end
    
    H --> D1
    H --> D2
    H --> T1
    H --> T2
    H --> T3
    
    T1 --> PRE
    T2 --> PRE
```

### Mode 3: ESO Disabled (enabled=false)

```mermaid
graph LR
    H[Helm Install<br/>argo-stack]
    
    subgraph "Chart Dependencies"
        D1[argo-workflows]
        D2[argo-cd]
    end
    
    subgraph "Stack Templates"
        T1[Traditional Secrets]
        T2[Other Resources]
    end
    
    H --> D1
    H --> D2
    H --> T1
    H --> T2
    
    style T1 fill:#fff3cd
```
