#!/bin/bash

# Face Detection Integration Test Script
# Starts servers and runs only face detection tests

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Port Configuration
HOST="localhost"
PORT_AUTH="${TEST_PORT_AUTH:-8010}"
PORT_STORE="${TEST_PORT_STORE:-8011}"
PORT_COMPUTE="${TEST_PORT_COMPUTE:-8012}"

# Configuration
SERVICES_DIR="/Users/anandasarangaram/Work/cl_server/services"
TEST_DIR="/Users/anandasarangaram/Work/cl_server/sdks/pysdk"
LOG_DIR="/tmp/cl_server_test_logs"

# Capture timestamp for logs
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_LOG_DIR="${LOG_DIR}/run_${RUN_TIMESTAMP}"

# Worker ID based on compute port
WORKER_ID="test-worker-${PORT_COMPUTE}"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[$(date +%H:%M:%S)][INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)][SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)][ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}========================================${NC}"
}

# Kill processes on specific ports
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        log_info "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Kill worker by ID
kill_worker() {
    local worker_id=$1
    log_info "Killing worker with ID: $worker_id"
    pkill -f "compute-worker --worker-id $worker_id" 2>/dev/null || true
    sleep 1
}

# Wait for server to be ready
wait_for_server() {
    local url=$1
    local max_attempts=30
    local attempt=0

    log_info "Waiting for $url to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_success "$url is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    log_error "$url failed to start"
    return 1
}

# Start all servers
start_servers() {
    log_section "Starting Servers"

    # Create data directory
    local data_dir="${RUN_LOG_DIR}/data"
    mkdir -p "$data_dir"
    log_info "Using data directory: $data_dir"

    # Set environment variables
    export CL_SERVER_DIR="$data_dir"
    export TEST_ADMIN_PASSWORD="admin"

    # Run database migrations
    log_info "Running database migrations..."
    cd "${SERVICES_DIR}/auth"
    uv run alembic upgrade head > "${RUN_LOG_DIR}/auth_migration.log" 2>&1
    cd "${SERVICES_DIR}/store"
    uv run alembic upgrade head > "${RUN_LOG_DIR}/store_migration.log" 2>&1
    cd "${SERVICES_DIR}/compute"
    uv run alembic upgrade head > "${RUN_LOG_DIR}/compute_migration.log" 2>&1
    log_success "Database migrations completed"

    # Start Auth Server
    log_info "Starting Auth server on port ${PORT_AUTH}..."
    cd "${SERVICES_DIR}/auth"
    uv run auth-server --port ${PORT_AUTH} > "${RUN_LOG_DIR}/server_auth.log" 2>&1 &

    # Start Store Server
    log_info "Starting Store server on port ${PORT_STORE}..."
    cd "${SERVICES_DIR}/store"
    uv run store --port ${PORT_STORE} > "${RUN_LOG_DIR}/server_store.log" 2>&1 &

    # Start Compute Server (no auth for simplicity)
    log_info "Starting Compute server on port ${PORT_COMPUTE}..."
    cd "${SERVICES_DIR}/compute"
    uv run compute-server --port ${PORT_COMPUTE} --no-auth > "${RUN_LOG_DIR}/server_compute.log" 2>&1 &

    # Wait for all servers to be ready
    if ! wait_for_server "http://${HOST}:${PORT_AUTH}"; then
        log_error "Auth server failed to start"
        return 1
    fi

    if ! wait_for_server "http://${HOST}:${PORT_STORE}"; then
        log_error "Store server failed to start"
        return 1
    fi

    if ! wait_for_server "http://${HOST}:${PORT_COMPUTE}"; then
        log_error "Compute server failed to start"
        return 1
    fi

    # Start Worker
    log_info "Starting Compute worker (ID: ${WORKER_ID})..."
    cd "${SERVICES_DIR}/compute"
    uv run compute-worker \
        --worker-id "${WORKER_ID}" \
        --port ${PORT_COMPUTE} \
        --tasks face_detection \
        > "${RUN_LOG_DIR}/server_worker.log" 2>&1 &

    sleep 3
    log_success "All servers started"
    return 0
}

# Stop all servers
stop_servers() {
    log_info "Stopping all servers..."
    kill_port ${PORT_AUTH}
    kill_port ${PORT_STORE}
    kill_port ${PORT_COMPUTE}
    kill_worker "${WORKER_ID}"
    sleep 2
    log_success "All servers stopped"
}

# Cleanup on exit
cleanup() {
    log_section "Cleanup"
    stop_servers
}

trap cleanup EXIT

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log_section "Face Detection Integration Test"

    log_info "Using ports: Auth=${PORT_AUTH}, Store=${PORT_STORE}, Compute=${PORT_COMPUTE}"
    log_info "Test run ID: ${RUN_TIMESTAMP}"

    # Create log directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$RUN_LOG_DIR"

    log_info "Server logs: ${RUN_LOG_DIR}/"

    # Stop any existing servers
    stop_servers

    # Start servers
    if ! start_servers; then
        log_error "Failed to start servers"
        exit 1
    fi

    # Run face detection tests
    log_section "Running Face Detection Tests"

    cd "$TEST_DIR"

    log_info "Running PySDK face detection integration tests..."
    AUTH_DISABLED=true uv run pytest tests/test_integration/test_face_detection_integration.py -v --tb=short

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        log_success "Face detection tests passed!"
    else
        log_error "Face detection tests failed with exit code $exit_code"
    fi

    log_info "Server logs available at: ${RUN_LOG_DIR}/"

    return $exit_code
}

# Run main function
main "$@"
