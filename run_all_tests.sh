#!/bin/bash

# Comprehensive Integration Test Script
# Tests all combinations of server configurations and auth modes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Port Configuration - can be overridden via environment variables
# Servers are always started on localhost since this script starts them locally
HOST="localhost"
PORT_AUTH="${TEST_PORT_AUTH:-8010}"
PORT_STORE="${TEST_PORT_STORE:-8011}"
PORT_COMPUTE="${TEST_PORT_COMPUTE:-8012}"

# Configuration
SERVICES_DIR="/Users/anandasarangaram/Work/cl_server/services"
TEST_DIR="/Users/anandasarangaram/Work/cl_server/sdks/pysdk"
LOG_DIR="/tmp/cl_server_test_logs"

# Capture timestamp once for all logs
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="${LOG_DIR}/test_results_${RUN_TIMESTAMP}.txt"
RUN_LOG_DIR="${LOG_DIR}/run_${RUN_TIMESTAMP}"

# Worker ID based on compute port to avoid conflicts
WORKER_ID="test-worker-${PORT_COMPUTE}"

# Read auth modes from auth_config.json (test_users keys + "no-auth")
read_auth_modes() {
    local config_file="${TEST_DIR}/tests/auth_config.json"

    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        echo -e "${RED}ERROR: Auth config file not found: $config_file${NC}" >&2
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}ERROR: jq is not installed. Required for parsing auth_config.json${NC}" >&2
        exit 1
    fi

    # Extract test_users keys from JSON
    local users
    users=$(jq -r '.test_users | keys[]' "$config_file" 2>&1)
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to parse auth_config.json${NC}" >&2
        echo -e "${YELLOW}JSON parse error: $users${NC}" >&2
        exit 1
    fi

    if [ -z "$users" ]; then
        echo -e "${RED}ERROR: No test_users found in auth_config.json${NC}" >&2
        exit 1
    fi

    # Build AUTH_MODES array from test_users + "no-auth"
    AUTH_MODES=()
    while IFS= read -r user; do
        AUTH_MODES+=("$user")
    done <<< "$users"
    AUTH_MODES+=("no-auth")
}

# Initialize AUTH_MODES (will be populated in main())
AUTH_MODES=()

# Server configurations to test
# Format: "compute_auth:store_guest_mode:description"
# Note: Only 2 configs needed - services are independent, no cross-interaction
CONFIGURATIONS=(
    "true:off:Auth-Required"  # Both services require authentication
    "false:on:Guest-Mode"     # Both services in guest mode (no auth)
)

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[$(date +%H:%M:%S)][INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)][SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)][WARNING]${NC} $1"
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

# Set store guest mode via admin API
set_store_guest_mode() {
    local mode=$1  # "on" or "off"
    local enabled="false"
    if [ "$mode" = "off" ]; then
        enabled="true"  # read_auth_enabled=true means guest mode off
    fi

    log_info "Setting store guest mode to: $mode (read_auth_enabled=$enabled)"

    # Get admin token
    local token=$(curl -s -X POST "http://${HOST}:${PORT_AUTH}/auth/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=admin&password=admin" 2>/dev/null | jq -r '.access_token' 2>/dev/null)

    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get admin token"
        return 1
    fi

    # Set read_auth configuration
    curl -s -X PUT "http://${HOST}:${PORT_STORE}/admin/config/read-auth" \
        -H "Authorization: Bearer $token" \
        -F "enabled=$enabled" > /dev/null 2>&1

    sleep 1

    # Verify
    local result=$(curl -s "http://${HOST}:${PORT_STORE}" 2>/dev/null | jq -r '.guestMode' 2>/dev/null)
    if [ "$result" = "$mode" ]; then
        log_success "Store guest mode set to: $mode"
        return 0
    else
        log_error "Failed to set store guest mode. Expected: $mode, Got: $result"
        return 1
    fi
}

# Set compute auth via admin API
set_compute_auth() {
    local auth_required=$1  # "true" or "false"
    local enabled="$auth_required"  # auth_enabled=true means auth required

    log_info "Setting compute auth to: $auth_required (auth_enabled=$enabled)"

    # Get admin token
    local token=$(curl -s -X POST "http://${HOST}:${PORT_AUTH}/auth/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=admin&password=admin" 2>/dev/null | jq -r '.access_token' 2>/dev/null)

    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get admin token"
        return 1
    fi

    # Set auth_enabled configuration
    curl -s -X PUT "http://${HOST}:${PORT_COMPUTE}/admin/config/auth" \
        -H "Authorization: Bearer $token" \
        -F "enabled=$enabled" > /dev/null 2>&1

    sleep 1

    # Verify
    local result=$(curl -s "http://${HOST}:${PORT_COMPUTE}" 2>/dev/null | jq -r '.guestMode' 2>/dev/null)
    local expected_guest_mode="on"
    if [ "$auth_required" = "true" ]; then
        expected_guest_mode="off"
    fi

    if [ "$result" = "$expected_guest_mode" ]; then
        log_success "Compute auth set to: auth_required=$auth_required (guestMode=$result)"
        return 0
    else
        log_error "Failed to set compute auth. Expected guestMode: $expected_guest_mode, Got: $result"
        return 1
    fi
}

# Start all servers
start_servers() {
    log_section "Starting Servers"

    # Create data directory
    local data_dir="${RUN_LOG_DIR}/data"
    mkdir -p "$data_dir"
    log_info "Using data directory: $data_dir"

    # Set environment variables (override any existing ones)
    export CL_SERVER_DIR="$data_dir"
    export TEST_ADMIN_PASSWORD="admin"

    # Run database migrations for all services
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

    # Start Compute Server (auth will be configured via API after startup)
    log_info "Starting Compute server on port ${PORT_COMPUTE}..."
    cd "${SERVICES_DIR}/compute"
    uv run compute-server --port ${PORT_COMPUTE} > "${RUN_LOG_DIR}/server_compute.log" 2>&1 &

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
    log_info "Starting Compute worker (ID: ${WORKER_ID}, connecting to port ${PORT_COMPUTE})..."
    cd "${SERVICES_DIR}/compute"
    uv run compute-worker \
        --worker-id "${WORKER_ID}" \
        --port ${PORT_COMPUTE} \
        --tasks clip_embedding,dino_embedding,exif,face_detection,face_embedding,hash,hls_streaming,image_conversion,media_thumbnail \
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

    # Kill worker by ID
    kill_worker "${WORKER_ID}"

    sleep 2
    log_success "All servers stopped"
}

# Update test config with correct URLs (host and ports)
update_test_config() {
    log_info "Updating test configuration with URLs: http://${HOST}:{${PORT_AUTH},${PORT_STORE},${PORT_COMPUTE}}"

    cd "$TEST_DIR"

    # Read existing config to preserve test_users, then update URLs
    local config_file="tests/auth_config.json"
    local temp_config=$(mktemp)

    # Update URLs while preserving test_users
    jq --arg auth_url "http://${HOST}:${PORT_AUTH}" \
       --arg compute_url "http://${HOST}:${PORT_COMPUTE}" \
       --arg store_url "http://${HOST}:${PORT_STORE}" \
       '.auth_url = $auth_url | .compute_url = $compute_url | .store_url = $store_url' \
       "$config_file" > "$temp_config"

    if [ $? -eq 0 ]; then
        mv "$temp_config" "$config_file"
        log_success "Test configuration updated"
    else
        rm -f "$temp_config"
        log_error "Failed to update test configuration"
        return 1
    fi
}

# Run tests for a specific auth mode
run_test_mode() {
    local auth_mode=$1
    local config_desc=$2

    log_info "Running tests in $auth_mode mode..."

    cd "$TEST_DIR"
    local test_log="${RUN_LOG_DIR}/test_${config_desc}_${auth_mode}.log"

    # Run tests (always return success to continue)
    uv run pytest tests/test_integration/ \
        --auth-mode="$auth_mode" \
        -v \
        --tb=short \
        > "$test_log" 2>&1 || true

    # Parse results
    local passed=$(grep -E "passed" "$test_log" 2>/dev/null | tail -1 | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    local failed=$(grep -E "failed" "$test_log" 2>/dev/null | tail -1 | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    local skipped=$(grep -E "skipped" "$test_log" 2>/dev/null | tail -1 | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")

    # Log result
    local result_line="$config_desc | $auth_mode | Passed: $passed | Failed: $failed | Skipped: $skipped"
    echo "$result_line" >> "$RESULTS_FILE"

    if [ "$failed" = "0" ]; then
        log_success "$auth_mode: $passed passed, $failed failed, $skipped skipped"
    else
        log_warning "$auth_mode: $passed passed, $failed failed, $skipped skipped"
    fi
}

# Run all auth modes for current configuration
run_all_auth_modes() {
    local config_desc=$1

    for auth_mode in "${AUTH_MODES[@]}"; do
        run_test_mode "$auth_mode" "$config_desc"
    done
}

# ============================================================================
# Main Test Execution
# ============================================================================

main() {
    log_section "Starting Comprehensive Integration Tests"

    # Read auth modes from config file (must be first to fail fast if config is invalid)
    read_auth_modes
    log_info "Auth modes to test: ${AUTH_MODES[*]}"

    log_info "Using ports: Auth=${PORT_AUTH}, Store=${PORT_STORE}, Compute=${PORT_COMPUTE}"
    log_info "Test run ID: ${RUN_TIMESTAMP}"

    # Create log directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$RUN_LOG_DIR"

    # Print log locations
    log_info "Results file: ${RESULTS_FILE}"
    log_info "Server and test logs: ${RUN_LOG_DIR}/"

    # Initialize results file
    echo "CL Server Integration Test Results - $(date)" > "$RESULTS_FILE"
    echo "=============================================" >> "$RESULTS_FILE"
    echo "Run ID: ${RUN_TIMESTAMP}" >> "$RESULTS_FILE"
    echo "Ports: Auth=${PORT_AUTH}, Store=${PORT_STORE}, Compute=${PORT_COMPUTE}" >> "$RESULTS_FILE"
    echo "Logs: ${RUN_LOG_DIR}/" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"

    # Start servers once before testing all configurations
    log_section "Starting Servers Once"

    # Stop any existing servers first
    stop_servers

    # Start all servers (will be configured via API for each test)
    if ! start_servers; then
        log_error "Failed to start servers"
        echo "FAILED TO START SERVERS" >> "$RESULTS_FILE"
        return 1
    fi

    # Update test configuration with correct ports
    update_test_config

    # Test each configuration
    for config in "${CONFIGURATIONS[@]}"; do
        # Parse configuration
        IFS=':' read -r compute_auth store_guest config_desc <<< "$config"

        log_section "Configuration: $config_desc"
        log_info "Compute auth_required=$compute_auth, Store guestMode=$store_guest"

        # Set store guest mode via API
        if ! set_store_guest_mode "$store_guest"; then
            log_error "Failed to set store guest mode for $config_desc"
            echo "FAILED TO CONFIGURE STORE: $config_desc" >> "$RESULTS_FILE"
            continue
        fi

        # Set compute auth via API
        if ! set_compute_auth "$compute_auth"; then
            log_error "Failed to set compute auth for $config_desc"
            echo "FAILED TO CONFIGURE COMPUTE: $config_desc" >> "$RESULTS_FILE"
            continue
        fi

        # Run all auth mode tests
        echo "" >> "$RESULTS_FILE"
        echo "Configuration: $config_desc" >> "$RESULTS_FILE"
        echo "-------------------------------------------" >> "$RESULTS_FILE"

        run_all_auth_modes "$config_desc"

        # Brief pause between configurations
        sleep 2
    done

    # Stop servers once after all tests complete
    log_section "Stopping Servers"
    stop_servers

    # ========================================================================
    # Final Summary
    # ========================================================================

    log_section "Test Run Complete"

    echo "" >> "$RESULTS_FILE"
    echo "=============================================" >> "$RESULTS_FILE"
    echo "Test run completed at $(date)" >> "$RESULTS_FILE"

    # Display results
    echo ""
    cat "$RESULTS_FILE"
    echo ""

    log_info "Full results saved to: $RESULTS_FILE"
    log_info "Individual test logs in: $LOG_DIR"

    log_success "All configurations tested!"
}

# Run main function
main "$@"
