# Integration Tests

Integration tests for the `cl_client` library that test against a real server, worker, and MQTT broker.

**All integration tests now run in BOTH no-auth and JWT auth modes via parametrization.**

## Prerequisites

### Core Services

1. **MQTT Broker** (mosquitto):
   ```bash
   # Check if running:
   ps aux | grep mosquitto

   # Start if needed:
   brew services start mosquitto
   ```

2. **Set CL_SERVER_DIR** (required for all services):
   ```bash
   export CL_SERVER_DIR=~/.data/cl_server_data
   mkdir -p $CL_SERVER_DIR
   ```

### Running in No-Auth Mode (Default)

3. **Compute Server** (no authentication):
   ```bash
   cd services/compute
   uv run compute-server --no-auth
   ```

4. **Worker** (with required capabilities):
   ```bash
   cd services/compute
   # For faster tests (2-second heartbeat):
   MQTT_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks media_thumbnail

   # Default (30-second heartbeat):
   uv run compute-worker --worker-id test-worker --tasks media_thumbnail
   ```

### Running in JWT Auth Mode

To test authentication, start these services **instead**:

1. **Auth Server** (required for JWT mode):
   ```bash
   cd services/auth
   # First time setup:
   uv sync
   uv run alembic upgrade head

   # Start server (creates default admin user: admin/admin):
   uv run auth-server --reload
   ```

2. **Compute Server** (WITH authentication):
   ```bash
   cd services/compute
   # Default mode - auth enabled (connects to auth server on port 8000)
   uv run compute-server
   ```

3. **Worker** (same as no-auth mode):
   ```bash
   cd services/compute
   MQTT_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks media_thumbnail
   ```

4. **Set Test Credentials** (required for JWT tests):
   ```bash
   export TEST_USERNAME=admin
   export TEST_PASSWORD=admin
   ```

### Test Media Files

Place test images in `/Users/anandasarangaram/Work/images/` or configure path in test fixtures.

## Running Tests

### No-Auth Mode Only (Default)

```bash
# Skip JWT tests (runs only [no_auth] variants):
AUTH_DISABLED=true uv run pytest tests/test_integration/ -v -m integration

# Run specific test file in no-auth mode:
AUTH_DISABLED=true uv run pytest tests/test_integration/test_clip_embedding_integration.py -v

# Run without coverage (faster):
AUTH_DISABLED=true uv run pytest tests/test_integration/ -v --no-cov -m integration
```

### Both Modes (No-Auth + JWT)

**Prerequisites:** Auth server, compute server, and worker running with auth enabled (see above)

```bash
# Run ALL tests in BOTH modes (50 tests total):
TEST_USERNAME=admin TEST_PASSWORD=admin uv run pytest tests/test_integration/ -v -m integration

# Run specific test in both modes:
TEST_USERNAME=admin TEST_PASSWORD=admin uv run pytest tests/test_integration/test_clip_embedding_integration.py -v
```

### JWT Mode Only

```bash
# Run only JWT auth variants:
TEST_USERNAME=admin TEST_PASSWORD=admin uv run pytest tests/test_integration/ -v -m integration -k "jwt"

# Or run only no-auth variants:
TEST_USERNAME=admin TEST_PASSWORD=admin uv run pytest tests/test_integration/ -v -m integration -k "no_auth"
```

## Test Configuration

### Understanding Parametrization

**All integration tests are parametrized** to run in both auth modes automatically:

- Each test function runs **twice**: `test_name[no_auth]` and `test_name[jwt]`
- 25 test functions → **50 total test runs**
- The `client` fixture automatically provides the correct client based on mode

**Environment Variables:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `AUTH_DISABLED` | Skip JWT tests if "true" | false |
| `TEST_USERNAME` | Username for JWT auth | (required for JWT) |
| `TEST_PASSWORD` | Password for JWT auth | (required for JWT) |

### Speed up tests with faster heartbeat:

Set `MQTT_HEARTBEAT_INTERVAL` to reduce worker capability broadcast interval:

```bash
# Start worker with 2-second heartbeat
MQTT_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks media_thumbnail

# Tests will complete much faster (1-2s vs 35s for capability detection)
```

### Test markers:
- `@pytest.mark.integration` - Marks test as integration test (requires server/worker)
- `@pytest.mark.asyncio` - Marks test as async
- `@pytest.mark.admin_only` - Marks test as requiring admin permissions (auto-skips in no-auth mode)

### Skip integration tests:
```bash
uv run pytest -m "not integration"
```

## Troubleshooting

### "No workers detected"
- Ensure worker is running with required tasks
- Workers broadcast on heartbeat interval (default 30s, configurable via `MQTT_HEARTBEAT_INTERVAL`)
- Tests retry for up to 35 seconds to detect workers

### "MQTT not connected"
- Check mosquitto is running: `ps aux | grep mosquitto`
- Check port 1883 is accessible: `netstat -an | grep 1883`

### "No test images found"
- Add test images to one of the configured locations
- Or modify `test_image` fixture in test files

### JWT Auth Test Failures

**Issue:** Tests skip with "JWT auth tests disabled"

**Solution:**
```bash
# Don't set AUTH_DISABLED=true when testing JWT mode
# Just set credentials:
export TEST_USERNAME=admin
export TEST_PASSWORD=admin
```

**Issue:** Tests skip with "JWT mode requires TEST_USERNAME and TEST_PASSWORD"

**Solution:**
```bash
export TEST_USERNAME=admin
export TEST_PASSWORD=admin
```

**Issue:** 401 Unauthorized errors in JWT tests

**Solutions:**
1. Verify auth server is running: `curl http://localhost:8000/`
2. Check compute server is running in auth mode (without `--no-auth`)
3. Verify credentials match admin user (default: admin/admin)
4. Check `CL_SERVER_DIR` is set and accessible

**Issue:** Connection refused to auth server

**Solution:**
```bash
# Start auth server first:
cd services/auth
uv run alembic upgrade head
uv run auth-server --reload
```

## Test Coverage

Integration tests verify:
- ✅ HTTP polling workflow (secondary)
- ✅ MQTT callback workflow (primary)
- ✅ Both on_progress and on_complete callbacks
- ✅ Worker capability detection
- ✅ File operations
