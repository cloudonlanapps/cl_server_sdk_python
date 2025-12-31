# CL Client - Testing Guide

## Prerequisites

- Python 3.12+
- uv package manager
- Running compute server
- Running auth server (for authentication tests)
- Running workers with required capabilities
- Test media files (see [media/MEDIA_SETUP.md](./media/MEDIA_SETUP.md))

## Multi-Mode Authentication Testing

The test suite supports running tests in multiple authentication modes to ensure the SDK works correctly with different permission levels. This validates both positive (authorized) and negative (unauthorized) scenarios.

### Authentication Modes

Tests can run in four modes:

1. **admin** - User with admin privileges (can perform all operations)
2. **user-with-permission** - User with `ai_inference_support` permission (can use plugins)
3. **user-no-permission** - User without permissions (cannot use plugins)
4. **no-auth** - No authentication (only works if server has `AUTH_DISABLED=true`)

Additionally, there's an **auto** mode that detects the server's configuration and selects an appropriate mode automatically.

### Running Tests in Different Modes

```bash
# Auto-detect mode based on server configuration (default)
uv run pytest tests/test_integration/ --auth-mode=auto

# Run in admin mode
uv run pytest tests/test_integration/ --auth-mode=admin

# Run in user-with-permission mode
uv run pytest tests/test_integration/ --auth-mode=user-with-permission

# Run in user-no-permission mode (tests expect 403 errors)
uv run pytest tests/test_integration/ --auth-mode=user-no-permission

# Run in no-auth mode (requires AUTH_DISABLED=true on server)
uv run pytest tests/test_integration/ --auth-mode=no-auth
```

### Test Configuration

#### auth_config.json

Test user configuration is stored in `tests/auth_config.json`:

```json
{
  "default_auth_mode": "user-with-permission",
  "auth_url": "http://localhost:8000",
  "compute_url": "http://localhost:8002",
  "test_users": {
    "admin": {
      "username": "admin",
      "is_admin": true,
      "permissions": []
    },
    "user-with-permission": {
      "username": "test_user_perm",
      "password": "user123",
      "is_admin": false,
      "permissions": ["ai_inference_support"]
    },
    "user-no-permission": {
      "username": "test_user_noperm",
      "password": "user456",
      "is_admin": false,
      "permissions": []
    }
  }
}
```

**Note:** Admin password is NOT stored in the config file - it must be provided via environment variable.

#### Environment Variables

```bash
# REQUIRED for auth mode tests
export TEST_ADMIN_PASSWORD="your_admin_password"

# Optional - override server URLs
export AUTH_URL="http://localhost:8000"
export COMPUTE_URL="http://localhost:8002"
```

### Test Behavior by Mode

| Mode | Plugin Operations | Admin Operations | Server Requirements |
|------|------------------|------------------|---------------------|
| admin | ✅ Pass | ✅ Pass | auth_required=true |
| user-with-permission | ✅ Pass | ❌ 403 Forbidden | auth_required=true |
| user-no-permission | ❌ 403 Forbidden | ❌ 403 Forbidden | auth_required=true |
| no-auth | ❌ 401 Unauthorized | ⏭️ Skipped | auth_required=true |
| no-auth | ✅ Pass | ⏭️ Skipped | auth_required=false |

### Test User Management

Test users are automatically managed by the test suite:

- **Auto-creation**: If a test user doesn't exist, it will be created automatically
- **Validation**: If a test user exists, credentials are validated by attempting login
- **Permission sync**: Created users have permissions matching `auth_config.json`

To reset test users:
```bash
# Delete test users via auth service admin API, they will be recreated on next test run
```

### Conditional Test Assertions

Integration tests use conditional assertions to handle different auth modes:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_http_polling(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test CLIP embedding with HTTP polling."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        job = await client.clip_embedding.embed_image(
            image=test_image,
            wait=True,
            timeout=30.0,
        )
        assert job.status == "completed"
        assert job.task_output is not None
        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=True,
                timeout=30.0,
            )
        assert exc_info.value.response.status_code == expected_code
```

### Helper Functions

The `conftest.py` module provides helpers for conditional test logic:

#### `should_succeed(auth_config, operation_type)`

Determines if an operation should succeed based on auth configuration.

```python
# For plugin operations (requires ai_inference_support permission)
if should_succeed(auth_config, operation_type="plugin"):
    # Run test normally

# For admin operations (requires is_admin=True)
if should_succeed(auth_config, operation_type="admin"):
    # Run admin test normally
```

#### `get_expected_error(auth_config, operation_type)`

Returns expected HTTP error code for failed operations.

```python
expected_code = get_expected_error(auth_config, operation_type="plugin")
# Returns:
# - 401 if no credentials (no-auth mode with auth required)
# - 403 if insufficient permissions
# - None if operation should succeed
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=cl_client --cov-report=html

# Run specific test file
uv run pytest tests/test_plugins/test_clip_embedding.py

# Run only unit tests (skip integration)
uv run pytest -m "not integration"
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_client/             # Unit tests
│   ├── test_config.py
│   ├── test_compute_client.py
│   ├── test_auth.py
│   ├── test_mqtt_monitor.py
│   ├── test_models.py
│   └── test_cli.py
├── test_plugins/            # Plugin integration tests (9 files)
│   ├── test_clip_embedding.py
│   ├── test_dino_embedding.py
│   └── ...
├── test_workflows/          # Multi-plugin workflows
│   ├── test_image_processing_workflow.py
│   └── test_video_processing_workflow.py
└── media/
    └── MEDIA_SETUP.md       # Test media setup guide
```

## Worker Requirements

Tests validate worker availability before running. Required capabilities:

- `clip_embedding`
- `dino_embedding`
- `exif`
- `face_detection`
- `face_embedding`
- `hash`
- `hls_streaming`
- `image_conversion`
- `media_thumbnail`

Start workers:

```bash
# Start worker with specific capability
uv run compute-worker --tasks clip_embedding

# Or start with all capabilities
uv run compute-worker
```

## Test Media Setup

See [media/MEDIA_SETUP.md](./media/MEDIA_SETUP.md) for detailed instructions on obtaining and setting up test media files.

## Coverage Requirements

- Minimum coverage: **90%**
- All public APIs must be tested
- Both MQTT callback and HTTP polling workflows tested

## Test Patterns

### Plugin Tests

Each plugin test includes:

1. Worker capability validation
2. MQTT callback test (primary workflow)
3. HTTP polling test (secondary workflow)
4. Job cleanup verification

Example:

```python
@pytest.mark.asyncio
async def test_embed_image_mqtt_callback(client, test_image_hd, validate_workers):
    # Validate worker available
    await validate_workers(client, ["clip_embedding"])

    # Track completion via callback
    completed_job = None
    event = asyncio.Event()

    def on_complete(job):
        nonlocal completed_job
        completed_job = job
        event.set()

    # Submit job
    job = await client.clip_embedding.embed_image(
        image=test_image_hd,
        on_complete=on_complete
    )

    # Wait for callback
    await asyncio.wait_for(event.wait(), timeout=30.0)

    # Verify and cleanup
    assert completed_job.status == "completed"
    await client.delete_job(job.job_id)
```

### Workflow Tests

Parallel MQTT pattern:

```python
async def test_complete_image_analysis(client, test_image, validate_workers):
    # Validate all required workers
    await validate_workers(client, ["exif", "media_thumbnail", "clip_embedding"])

    # Register ALL callbacks upfront
    completed_jobs = {}
    events = {name: asyncio.Event() for name in ["exif", "thumb", "clip"]}

    def make_callback(name):
        def on_complete(job):
            completed_jobs[name] = job
            events[name].set()
        return on_complete

    # Submit ALL jobs with callbacks (non-blocking)
    job1 = await client.exif.extract(image=test_image, on_complete=make_callback("exif"))
    job2 = await client.media_thumbnail.generate(..., on_complete=make_callback("thumb"))
    job3 = await client.clip_embedding.embed_image(..., on_complete=make_callback("clip"))

    # Wait for ALL callbacks
    await asyncio.gather(
        events["exif"].wait(),
        events["thumb"].wait(),
        events["clip"].wait()
    )

    # Verify all completed
    assert all(j.status == "completed" for j in completed_jobs.values())

    # Cleanup
    for job in [job1, job2, job3]:
        await client.delete_job(job.job_id)
```

## Troubleshooting

### Tests Fail: "Worker unavailable"

Start required workers before running tests.

### Tests Fail: "Media not found"

Set up test media directory (see media/MEDIA_SETUP.md).

### Type Errors

Run basedpyright to catch issues:

```bash
uv run basedpyright
```
