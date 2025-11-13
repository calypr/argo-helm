#!/usr/bin/env bash
# MinIO Development Helper Script
#
# This script helps developers start, stop, and manage a local MinIO instance
# for testing Argo Workflows artifact storage.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# MinIO configuration
MINIO_ENDPOINT="http://localhost:9000"
MINIO_CONSOLE="http://localhost:9001"
MINIO_ACCESS_KEY="${MINIO_ROOT_USER:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_ROOT_PASSWORD:-minioadmin}"

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo ""
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

start_minio() {
    print_header "Starting Local MinIO Server"
    
    check_docker
    
    print_info "Starting MinIO container..."
    docker-compose up -d
    
    print_info "Waiting for MinIO to be ready..."
    sleep 5
    
    # Wait for MinIO to be healthy
    MAX_RETRIES=30
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -sf "${MINIO_ENDPOINT}/minio/health/live" > /dev/null 2>&1; then
            print_success "MinIO is ready!"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            print_error "MinIO failed to start after ${MAX_RETRIES} retries"
            exit 1
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
    print_success "MinIO is running!"
    echo ""
    print_info "Access URLs:"
    echo "  - S3 API:        ${MINIO_ENDPOINT}"
    echo "  - Console:       ${MINIO_CONSOLE}"
    echo ""
    print_info "Credentials:"
    echo "  - Access Key:    ${MINIO_ACCESS_KEY}"
    echo "  - Secret Key:    ${MINIO_SECRET_KEY}"
    echo ""
    print_info "Created Buckets:"
    echo "  - argo-artifacts"
    echo "  - argo-artifacts-dev"
    echo "  - calypr-nextflow-hello"
    echo "  - calypr-nextflow-hello-2"
    echo ""
    print_warning "These are development credentials. DO NOT use in production!"
}

stop_minio() {
    print_header "Stopping Local MinIO Server"
    
    check_docker
    
    print_info "Stopping MinIO container..."
    docker-compose down
    
    print_success "MinIO stopped"
}

clean_minio() {
    print_header "Cleaning MinIO Data"
    
    check_docker
    
    print_warning "This will delete all MinIO data and volumes!"
    read -p "Are you sure? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Cancelled"
        exit 0
    fi
    
    print_info "Stopping and removing MinIO with volumes..."
    docker-compose down -v
    
    print_success "MinIO data cleaned"
}

status_minio() {
    print_header "MinIO Status"
    
    check_docker
    
    if docker-compose ps | grep -q "minio"; then
        print_success "MinIO is running"
        docker-compose ps
        echo ""
        print_info "Access URLs:"
        echo "  - S3 API:        ${MINIO_ENDPOINT}"
        echo "  - Console:       ${MINIO_CONSOLE}"
    else
        print_warning "MinIO is not running"
        echo ""
        print_info "Run './dev-minio.sh start' to start MinIO"
    fi
}

logs_minio() {
    print_header "MinIO Logs"
    
    check_docker
    
    docker-compose logs -f minio
}

print_values() {
    print_header "Helm Values for Local MinIO"
    
    cat <<EOF
# Add these values to your Helm deployment to use local MinIO:

s3:
  enabled: true
  hostname: "localhost:9000"
  bucket: "argo-artifacts-dev"
  region: "us-east-1"
  insecure: true
  pathStyle: true
  accessKey: "${MINIO_ACCESS_KEY}"
  secretKey: "${MINIO_SECRET_KEY}"

# Or use this command:
helm upgrade --install argo-stack ./helm/argo-stack \\
  --namespace argocd \\
  --create-namespace \\
  --set s3.enabled=true \\
  --set s3.hostname=localhost:9000 \\
  --set s3.bucket=argo-artifacts-dev \\
  --set s3.region=us-east-1 \\
  --set s3.insecure=true \\
  --set s3.pathStyle=true \\
  --set s3.accessKey=${MINIO_ACCESS_KEY} \\
  --set s3.secretKey=${MINIO_SECRET_KEY}

# For per-repository artifacts:
applications:
  - name: my-app
    repoURL: https://github.com/org/repo.git
    targetRevision: main
    path: "."
    destination:
      namespace: wf-poc
    artifacts:
      bucket: calypr-nextflow-hello
      endpoint: http://localhost:9000
      region: us-east-1
      insecure: true
      pathStyle: true
      credentialsSecret: minio-creds
EOF
}

print_usage() {
    cat <<EOF
Usage: $0 [COMMAND]

Local MinIO management for Argo Workflows development

Commands:
  start      Start MinIO server
  stop       Stop MinIO server
  clean      Stop MinIO and remove all data
  status     Check MinIO status
  logs       Show MinIO logs (follow mode)
  values     Print Helm values for MinIO configuration
  help       Show this help message

Examples:
  $0 start         # Start MinIO for development
  $0 status        # Check if MinIO is running
  $0 values        # Show Helm configuration
  $0 stop          # Stop MinIO when done

For more information, see docs/development.md
EOF
}

# Main command router
case "${1:-help}" in
    start)
        start_minio
        ;;
    stop)
        stop_minio
        ;;
    clean)
        clean_minio
        ;;
    status)
        status_minio
        ;;
    logs)
        logs_minio
        ;;
    values)
        print_values
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        print_usage
        exit 1
        ;;
esac
