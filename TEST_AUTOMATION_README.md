# Comprehensive Integration Test Automation

## Overview

The `run_all_tests.sh` script provides comprehensive automated testing across all combinations of server configurations and authentication modes.

## What It Tests

### Server Configurations (4 combinations)

1. **Compute Auth ON + Store Guest OFF**
   - Compute requires authentication
   - Store requires authentication for both read and write

2. **Compute Auth ON + Store Guest ON**
   - Compute requires authentication
   - Store allows public read, requires auth for write

3. **Compute Auth OFF + Store Guest ON**
   - Compute allows all operations without auth
   - Store allows public read, requires auth for write

4. **Compute Auth OFF + Store Guest OFF**
   - Compute allows all operations without auth
   - Store requires authentication for both read and write

### Authentication Modes (4 modes per configuration)

1. **admin** - Admin user with all permissions
2. **user-with-permission** - Regular user with `ai_inference_support`, `media_store_read`, `media_store_write` permissions
3. **user-no-permission** - Regular user with no permissions
4. **no-auth** - No authentication provided

**Total Tests:** 4 configurations × 4 auth modes = **16 test runs**

## Usage

### Run All Tests

Basic usage with default settings (localhost, ports 8010-8012):

```bash
cd /Users/anandasarangaram/Work/cl_server/sdks/pysdk
./run_all_tests.sh
```

### Run Tests with Custom Ports

Override ports via environment variables (servers always start on localhost):

```bash
# Use different ports to avoid conflicts
TEST_PORT_AUTH=9010 TEST_PORT_STORE=9011 TEST_PORT_COMPUTE=9012 ./run_all_tests.sh
```

### Prerequisites

1. **Required Tools:**
   - `jq` - JSON processor for parsing configuration files
     - Install on Ubuntu/Debian: `sudo apt-get install jq`
     - Install on macOS: `brew install jq`
     - Install on RHEL/CentOS: `sudo yum install jq`
   - Script will fail with clear error if `jq` is not installed

2. **Environment Setup:**
   - All services installed with `uv sync` in auth, store, and compute directories
   - Test data available in `tests/media/`
   - Valid `tests/auth_config.json` with `test_users` defined
   - `CL_SERVER_DIR` is set automatically by script for each configuration

3. **Auth Configuration:**
   - Script reads test users from `tests/auth_config.json`
   - Auth modes are derived automatically from `test_users` keys + "no-auth"
   - Add/remove test users in config file, no script changes needed
   - Script fails immediately if config file is missing or malformed

4. **No Running Servers on Test Ports:**
   - Default ports: 8010 (auth), 8011 (store), 8012 (compute) on localhost
   - Override via: `TEST_PORT_AUTH`, `TEST_PORT_STORE`, `TEST_PORT_COMPUTE`
   - Script will automatically kill any processes on configured test ports
   - Safe to run while production servers are running on default ports (8000-8002)

5. **Admin Password:**
   - Script uses default password "admin"
   - Configurable via `TEST_ADMIN_PASSWORD` environment variable in script

6. **Database Isolation:**
   - Each configuration uses its own isolated database directory
   - No interference with existing data in `~/.data/cl_server_data`
   - Migrations run automatically for each configuration

## What the Script Does

### Initial Setup:

1. **Creates Isolated Environment**
   - Generates unique timestamp (RUN_TIMESTAMP) for this test run
   - Creates dedicated log directory: `/tmp/cl_server_test_logs/run_YYYYMMDD_HHMMSS/`
   - Prints results file and log directory locations

### For Each Configuration:

1. **Cleanup**
   - Kills processes on ports 8010, 8011, 8012 (by port, not process name)
   - Kills worker by specific worker ID

2. **Database Setup**
   - Creates isolated data directory: `run_YYYYMMDD_HHMMSS/data_{config_desc}/`
   - Sets CL_SERVER_DIR to this unique directory
   - Runs database migrations (alembic upgrade head) for all three services
   - Each configuration starts with fresh, clean databases

3. **Server Startup**
   - Starts Auth server on port 8010
   - Starts Store server on port 8011
   - Starts Compute server on port 8012 (with/without auth based on config)
   - Starts Compute worker (with unique worker ID based on port)
   - Waits for all servers to be healthy

4. **Configuration**
   - Updates test config file (tests/auth_config.json) with correct ports
   - Sets store guest mode via admin API
   - Verifies configuration applied correctly

5. **Test Execution**
   - Runs full integration test suite in each auth mode
   - Captures results and logs with timestamps
   - Continues even if tests fail

6. **Cleanup**
   - Stops all servers
   - Prepares for next configuration

## Output

### Test Results

Results are saved to `/tmp/cl_server_test_logs/test_results_YYYYMMDD_HHMMSS.txt`

Example output:
```
CL Server Integration Test Results - Thu Jan  1 21:06:48 IST 2026
=============================================
Run ID: 20260101_210648
Ports: Auth=8010, Store=8011, Compute=8012
Logs: /tmp/cl_server_test_logs/run_20260101_210648/

Configuration: Compute-Auth-ON_Store-Guest-OFF
-------------------------------------------
Compute-Auth-ON_Store-Guest-OFF | admin | Passed: 48 | Failed: 2 | Skipped: 1
Compute-Auth-ON_Store-Guest-OFF | user-with-permission | Passed: 48 | Failed: 2 | Skipped: 1
Compute-Auth-ON_Store-Guest-OFF | user-no-permission | Passed: 48 | Failed: 0 | Skipped: 3
Compute-Auth-ON_Store-Guest-OFF | no-auth | Passed: 34 | Failed: 0 | Skipped: 17

Configuration: Compute-Auth-ON_Store-Guest-ON
-------------------------------------------
Compute-Auth-ON_Store-Guest-ON | admin | Passed: 48 | Failed: 2 | Skipped: 1
...
```

### Console Output

All console messages include timestamps for tracking execution time:

```
[21:06:48][INFO] Using ports: Auth=8010, Store=8011, Compute=8012
[21:06:48][INFO] Test run ID: 20260101_210648
[21:06:48][INFO] Results file: /tmp/cl_server_test_logs/test_results_20260101_210648.txt
[21:06:48][INFO] Server and test logs: /tmp/cl_server_test_logs/run_20260101_210648/
[21:06:51][INFO] Using data directory: /tmp/cl_server_test_logs/run_20260101_210648/data_Compute-Auth-ON_Store-Guest-OFF
[21:06:51][INFO] Running database migrations...
[21:06:54][SUCCESS] Database migrations completed
[21:06:55][INFO] Starting Auth server on port 8010...
...
```

### Logs

All logs are organized in a single timestamped directory: `/tmp/cl_server_test_logs/run_YYYYMMDD_HHMMSS/`

**Log File Naming Convention:**

Database Migration Logs:
- `migration_auth_{config_desc}.log` - Auth service migration logs
- `migration_store_{config_desc}.log` - Store service migration logs
- `migration_compute_{config_desc}.log` - Compute service migration logs

Server Logs:
- `server_auth_{config_desc}.log` - Auth server logs
- `server_store_{config_desc}.log` - Store server logs
- `server_compute_{config_desc}.log` - Compute server logs
- `server_worker_{config_desc}.log` - Worker logs

Test Logs:
- `test_{config_desc}_{auth_mode}.log` - Individual test run logs

Data Directories:
- `data_{config_desc}/` - Isolated database directory for each configuration

**Example Log Directory Structure:**
```
/tmp/cl_server_test_logs/run_20260101_210648/
├── migration_auth_Compute-Auth-ON_Store-Guest-OFF.log
├── migration_store_Compute-Auth-ON_Store-Guest-OFF.log
├── migration_compute_Compute-Auth-ON_Store-Guest-OFF.log
├── server_auth_Compute-Auth-ON_Store-Guest-OFF.log
├── server_store_Compute-Auth-ON_Store-Guest-OFF.log
├── server_compute_Compute-Auth-ON_Store-Guest-OFF.log
├── server_worker_Compute-Auth-ON_Store-Guest-OFF.log
├── test_Compute-Auth-ON_Store-Guest-OFF_admin.log
├── test_Compute-Auth-ON_Store-Guest-OFF_user-with-permission.log
├── test_Compute-Auth-ON_Store-Guest-OFF_user-no-permission.log
├── test_Compute-Auth-ON_Store-Guest-OFF_no-auth.log
├── data_Compute-Auth-ON_Store-Guest-OFF/
│   ├── user_auth.db
│   ├── media_store.db
│   └── compute.db
└── ... (logs for other configurations)
```

## Customization

### Modify Configurations

Edit the `CONFIGURATIONS` array in the script:

```bash
CONFIGURATIONS=(
    "true:off:Compute-Auth-ON_Store-Guest-OFF"
    "true:on:Compute-Auth-ON_Store-Guest-ON"
    # Add more configurations...
)
```

Format: `"compute_auth:store_guest_mode:description"`
- `compute_auth`: `true` or `false`
- `store_guest_mode`: `on` or `off`
- `description`: Human-readable name

### Modify Auth Modes

**Recommended:** Edit `tests/auth_config.json` to add/remove test users:

```json
{
  "auth_url": "http://localhost:8010",
  "compute_url": "http://localhost:8012",
  "store_url": "http://localhost:8011",
  "default_auth_mode": "user-with-permission",
  "test_users": {
    "admin": { ... },
    "user-with-permission": { ... },
    "user-no-permission": { ... },
    "my-custom-user": {
      "username": "custom",
      "password": "password",
      "is_admin": false,
      "permissions": ["custom_permission"]
    }
  }
}
```

The script automatically discovers all test users from this file. No script modifications needed!

### Change Ports

**Via Environment Variables (Recommended):**

```bash
TEST_PORT_AUTH=9000 \
TEST_PORT_STORE=9001 \
TEST_PORT_COMPUTE=9002 \
./run_all_tests.sh
```

**Via Script Defaults:**

Edit the default values at the top of the script:

```bash
PORT_AUTH="${TEST_PORT_AUTH:-8010}"
PORT_STORE="${TEST_PORT_STORE:-8011}"
PORT_COMPUTE="${TEST_PORT_COMPUTE:-8012}"
```

**Note:** Servers always start on localhost since this script starts them locally.

## Exit Codes

- `0` - All tests passed
- `1` - One or more configurations had failures

## Notes

- **Test Duration:** Approximately 5-10 minutes per auth mode (20-40 minutes per configuration)
- **Total Run Time:** Approximately 1.5-3 hours for all 16 combinations (4 configs × 4 auth modes)
- **Known Issues:** Face detection tests may fail (known issue - 2 failures expected)
- **Parallel Execution:** Not supported - tests run sequentially
- **Coverage:** Script focuses on functionality, not code coverage thresholds
- **Database Isolation:** Each configuration gets a fresh database - no state carryover
- **Timestamps:** All log messages include timestamps for performance analysis
- **Log Organization:** All logs for a single run stored in one timestamped directory

## Troubleshooting

### Servers Won't Start

Check logs in the run directory (printed at script startup) for specific services:
- `server_auth_{config}.log` - Auth server errors
- `server_store_{config}.log` - Store server errors
- `server_compute_{config}.log` - Compute server errors
- `migration_*.log` - Database migration errors

Common issues:
- Port conflicts (check ports 8010, 8011, 8012)
- Database migration failures (check migration logs)
- Missing dependencies (ensure `uv sync` completed in all service directories)

### Tests Fail Unexpectedly

1. **Check Test Logs:**
   - Look at `test_{config}_{auth_mode}.log` for detailed error messages
   - Search for "FAILED" or "ERROR" to find specific failures

2. **Check Server Logs:**
   - Review `server_*.log` files for server-side errors
   - Check if servers crashed during tests

3. **Verify Prerequisites:**
   - Test media files exist in `tests/media/`
   - Worker has all required capabilities (check `server_worker_*.log`)
   - Database migrations completed successfully (check `migration_*.log`)

4. **Database State:**
   - Each configuration uses isolated database in `data_{config}/`
   - Migrations should create: `user_auth.db`, `media_store.db`, `compute.db`

### Script Hangs

- **Health Check Timeout:** Servers may not be responding
  - Check `server_*.log` to see if servers started
  - Verify no port conflicts on 8010, 8011, 8012
  - Increase timeout in `wait_for_server` function if needed

- **Test Hanging:** Some tests (especially face detection) may take longer
  - Check test log to see which test is running
  - Face detection tests may timeout (expected 2 failures)

## Example Run

```bash
$ ./run_all_tests.sh

========================================
Starting Comprehensive Integration Tests
========================================
[21:06:48][INFO] Using ports: Auth=8010, Store=8011, Compute=8012
[21:06:48][INFO] Test run ID: 20260101_210648
[21:06:48][INFO] Results file: /tmp/cl_server_test_logs/test_results_20260101_210648.txt
[21:06:48][INFO] Server and test logs: /tmp/cl_server_test_logs/run_20260101_210648/

========================================
Configuration: Compute-Auth-ON_Store-Guest-OFF
========================================
[21:06:48][INFO] Compute auth_required=true, Store guestMode=off
[21:06:48][INFO] Stopping all servers...
[21:06:51][SUCCESS] All servers stopped

========================================
Starting Servers (Compute auth=true)
========================================
[21:06:51][INFO] Using data directory: /tmp/cl_server_test_logs/run_20260101_210648/data_Compute-Auth-ON_Store-Guest-OFF
[21:06:51][INFO] Running database migrations...
[21:06:54][SUCCESS] Database migrations completed
[21:06:55][INFO] Starting Auth server on port 8010...
[21:06:55][INFO] Starting Store server on port 8011...
[21:06:55][INFO] Starting Compute server on port 8012 (auth=true)...
[21:06:55][INFO] Waiting for http://localhost:8010 to be ready...
[21:06:57][SUCCESS] http://localhost:8010 is ready
[21:06:57][INFO] Waiting for http://localhost:8011 to be ready...
[21:06:57][SUCCESS] http://localhost:8011 is ready
[21:06:57][INFO] Waiting for http://localhost:8012 to be ready...
[21:06:58][SUCCESS] http://localhost:8012 is ready
[21:06:58][INFO] Starting Compute worker (ID: test-worker-8012)...
[21:07:01][SUCCESS] All servers started
[21:07:01][INFO] Updating test configuration with ports...
[21:07:01][SUCCESS] Test configuration updated
[21:07:01][INFO] Setting store guest mode to: off
[21:07:02][SUCCESS] Store guest mode set to: off
[21:07:02][INFO] Running tests in admin mode...
[21:15:13][WARNING] admin: 48 passed, 2 failed, 1 skipped
[21:15:13][INFO] Running tests in user-with-permission mode...
[21:23:24][WARNING] user-with-permission: 48 passed, 2 failed, 1 skipped
...

========================================
Test Run Complete
========================================

CL Server Integration Test Results - Thu Jan  1 21:06:48 IST 2026
=============================================
Run ID: 20260101_210648
Ports: Auth=8010, Store=8011, Compute=8012
Logs: /tmp/cl_server_test_logs/run_20260101_210648/
...

[21:45:30][SUCCESS] All configurations tested!
```
