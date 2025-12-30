# Integration Tests

Integration tests for the `cl_client` library that test against a real server, worker, and MQTT broker.

## Prerequisites

1. **Compute Server** (running in no-auth mode):
   ```bash
   uv run compute-server --no-auth
   ```

2. **Worker** (with required capabilities):
   ```bash
   # For faster tests (2-second heartbeat):
   MQTT_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks media_thumbnail
   
   # Default (30-second heartbeat):
   uv run compute-worker --worker-id test-worker --tasks media_thumbnail
   ```

3. **MQTT Broker** (mosquitto):
   ```bash
   # Check if running:
   ps aux | grep mosquitto
   
   # Start if needed:
   brew services start mosquitto
   ```

4. **Test Media Files**:
   - Place test images in `/Users/anandasarangaram/Work/images/` or
   - Configure path in test fixtures

## Running Tests

### Run all integration tests:
```bash
uv run pytest tests/test_integration/ -v -m integration
```

### Run specific test file:
```bash
uv run pytest tests/test_integration/test_media_thumbnail_integration.py -v
```

### Run without coverage (faster):
```bash
uv run pytest tests/test_integration/ -v --no-cov -m integration
```

## Test Configuration

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

## Test Coverage

Integration tests verify:
- ✅ HTTP polling workflow (secondary)
- ✅ MQTT callback workflow (primary)
- ✅ Both on_progress and on_complete callbacks
- ✅ Worker capability detection
- ✅ File operations
