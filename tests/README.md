# Tests — CL Client SDK

Comprehensive guide to the test suite. For quick commands, see [QUICK.md](QUICK.md).

## Overview & Structure

The test suite is organized into two categories:

- **Unit tests** (`test_client/`) — Test the SDK client APIs, models, and configuration. No external services required.
- **Integration tests** (`test_integration/`) — Test plugins and store operations with live servers, workers, and MQTT.

## Test Organization

### Unit Tests (`test_client/`)

Run locally with no external dependencies:

```
test_auth.py                     # Auth providers (JWT, NoAuth, default)
test_auth_client.py              # AuthClient API (login, register, permissions)
test_auth_models.py              # Auth response models and serialization
test_compute_client.py           # ComputeClient API (job submission, polling, callbacks)
test_config.py                   # ServerPref and SessionManager configuration
test_exceptions.py               # SDK exception types and error handling
test_models.py                   # Job, Task, and capability models
test_mqtt_monitor.py             # MQTT connection and callback routing
test_plugins.py                  # Plugin client factories (clip_embedding, exif, etc.)
test_server_pref.py            # ServerPref and credential management
test_session_manager.py          # SessionManager (login, logout, token refresh)
test_store_client.py             # StoreClient API (entity CRUD, versioning)
test_store_manager.py            # StoreManager (context manager, authentication)
test_store_models.py             # Store entity models and metadata
```

Run unit tests:

```bash
uv run pytest -m "not integration" --no-cov
```

### Integration Tests (`test_integration/`)

Test the SDK against running servers, workers, and MQTT broker. **Servers must be started first.**

#### Plugin Tests (9 files)

Each plugin test validates two execution workflows:

1. **HTTP Polling** — Submit job, wait via HTTP polling
2. **MQTT Callbacks** — Submit job with on_progress/on_complete callbacks via MQTT

Example: `test_clip_embedding_integration.py`
- `test_clip_embedding_http_polling()` — Standard wait-for-completion flow
- `test_clip_embedding_mqtt_callbacks()` — Real-time MQTT callbacks + job fetch
- Tests run in all auth modes; conditionally assert success/failure

Other plugin tests follow the same pattern:
- `test_dino_embedding_integration.py` — Vision transformer embeddings
- `test_exif_integration.py` — EXIF metadata extraction
- `test_face_detection_integration.py` — Face detection in images
- `test_face_embedding_integration.py` — Face embeddings + matching
- `test_hash_integration.py` — Perceptual image hashing
- `test_hls_streaming_integration.py` — HLS streaming setup
- `test_image_conversion_integration.py` — Format/resolution conversion
- `test_media_thumbnail_integration.py` — Thumbnail generation

#### Store Tests

`test_store_integration.py` — Entity CRUD, versioning, and auth modes:
- List/create/read/update/patch/delete entities
- Soft deletes and version history
- Admin operations (config, read auth settings)

#### Auth Tests

`test_auth_errors_integration.py` — Server auth behavior:
- Unauthenticated requests (401/403 vs guest mode 200)
- Insufficient permissions (403)
- Admin-only operations
- Expected HTTP status codes in each auth mode

`test_user_management_integration.py` — User and permission management:
- Admin can create/delete/update users
- Permission assignment and validation
- Admin-only operations

---

## Worker Requirements

Integration tests require **workers with specific capabilities**. Each capability is a task type the worker can execute.

### Required Capabilities

```
clip_embedding          CLIP vision model embeddings (512-dim)
dino_embedding          DINOv2 vision model embeddings
exif                    EXIF metadata extraction from JPEG
face_detection          Face detection bounding boxes
face_embedding          Face embeddings + similarity matching
hash                    Perceptual image hashing (pHash, etc.)
hls_streaming           HTTP Live Streaming setup
image_conversion        Format/resolution conversion
media_thumbnail         Thumbnail generation
```

### Starting Workers

Workers are started as part of server launching process.

## Conditional Test Assertions

Integration tests adapt behavior based on **auth mode** (determined at runtime from server config and CLI args).

### Auth Modes

| Mode        | Description                         | Requirements                           |
| ----------- | ----------------------------------- | -------------------------------------- |
| **auth**    | Authenticated via username/password | `--username` and `--password` provided |
| **no-auth** | No authentication                   | No credentials provided                |

### Permission Model

Within "auth" mode, tests check **user permissions**:

- **admin** — Full access (all operations succeed)
- **media_store_read** — Can read from store
- **media_store_write** — Can write to store
- **ai_inference_support** — Can use plugins (clip, dino, etc.)

### How Tests Use Conditional Logic

Each test checks the auth config and branches:

```python
@pytest.mark.integration
async def test_clip_embedding_http_polling(test_image: Path, client: ComputeClient, auth_config: AuthConfig):
    """Test CLIP embedding with HTTP polling."""
    
    # Branch based on whether this operation should succeed
    if should_succeed(auth_config, operation_type="plugin"):
        # Expected success path
        job = await client.clip_embedding.embed_image(image=test_image, wait=True, timeout=30.0)
        assert job.status == "completed"
        assert job.task_output is not None
        await client.delete_job(job.job_id)
    else:
        # Expected failure path — expect specific HTTP error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(image=test_image, wait=True, timeout=30.0)
        assert exc_info.value.response.status_code == expected_code  # 401 or 403
```

### Helper Functions

`should_succeed(auth_config, operation_type) -> bool`
- Returns `True` if the operation should succeed for this auth config
- `operation_type`: `"plugin"`, `"store_read"`, `"store_write"`, or `"admin"`

`get_expected_error(auth_config, operation_type) -> int`
- Returns expected HTTP error code (401 Unauthorized or 403 Forbidden)
- Only called when `should_succeed()` returns `False`

### Example: Store Write in No-Auth Mode

```python
if should_succeed(auth_config, operation_type="store_write"):
    # Auth mode: write succeeds (user has permission)
    await store_manager.create_entity(...)
else:
    # No-auth mode: write fails with 401 (no token provided)
    expected_code = get_expected_error(auth_config, operation_type="store_write")
    with pytest.raises(HTTPStatusError) as exc_info:
        await store_manager.create_entity(...)
    assert exc_info.value.response.status_code == expected_code
```

---

## Execution Workflows

### HTTP Polling (Secondary Workflow)

Submit job and poll for completion via HTTP:

```python
job = await client.clip_embedding.embed_image(image=test_image, wait=True, timeout=30.0)
assert job.status == "completed"
await client.delete_job(job.job_id)
```

**When to use:** Simpler flow, works without MQTT.

### MQTT Callbacks (Primary Workflow)

Submit job with callbacks; server pushes updates via MQTT:

```python
completion_event = asyncio.Event()
final_job = None

def on_complete(job):
    global final_job
    final_job = job
    completion_event.set()

job = await client.clip_embedding.embed_image(
    image=test_image,
    on_progress=lambda j: print(f"Progress: {j.progress}%"),
    on_complete=on_complete
)

# Wait for MQTT callback
await asyncio.wait_for(completion_event.wait(), timeout=30.0)
assert final_job.status == "completed"
```

**When to use:** Real-time updates, testing callback infrastructure, production use case.

### Workflow Tests (Multi-Plugin)

Tests can combine multiple plugins in parallel:

```python
# Register callbacks upfront
events = {"clip": asyncio.Event(), "dino": asyncio.Event()}
results = {}

def make_callback(name):
    def on_complete(job):
        results[name] = job
        events[name].set()
    return on_complete

# Submit all jobs (non-blocking)
job1 = await client.clip_embedding.embed_image(..., on_complete=make_callback("clip"))
job2 = await client.dino_embedding.embed_image(..., on_complete=make_callback("dino"))

# Wait for all completions
await asyncio.gather(events["clip"].wait(), events["dino"].wait())

# Verify results
assert results["clip"].status == "completed"
assert results["dino"].status == "completed"
```

---

## Code Coverage

The SDK requires **≥90% code coverage** on all public APIs.

### Coverage Configuration

Coverage rules in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--cov=cl_client --cov-report=html --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["src/cl_client"]
omit = ["*/tests/*", "*/__pycache__/*", "*/venv/*", "*/.venv/*"]

[tool.coverage.report]
precision = 2
skip_empty = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

### Current Coverage

Run with coverage:

```bash
uv run pytest --cov=cl_client --cov-report=html --cov-report=term-missing
```

Output:
- **Terminal:** Line-by-line coverage summary (lines marked with `?` are uncovered)
- **HTML:** `htmlcov/index.html` — Interactive coverage report

### What Must Be Tested

- ✅ All public methods and properties
- ✅ Happy path + error paths
- ✅ Both HTTP polling and MQTT callback workflows
- ✅ Auth modes (success + failure scenarios)
- ✅ Store operations (read/write/admin)
- ✅ Session management and token refresh

---

## Starting Servers

**Required before running integration tests.**

Refer cl_server project (workspace) on how to launch servers / services.

---

## Running Tests

### Quick Reference

### Unit Tests Only (Fast, No Servers)

```bash
uv run pytest -m "not integration" --no-cov
```

### Integration Tests (Requires Servers)

Ensure servers are running first (see "Starting Servers" section above).

```bash
uv run pytest -m "integration" \
  --auth-url=http://localhost:8010 \
  --compute-url=http://localhost:8012 \
  --store-url=http://localhost:8011 \
  --username=admin \
  --password=admin \
  --no-cov
```

### All Tests with Coverage

```bash
uv run pytest tests/ \
  --auth-url=http://localhost:8010 \
  --compute-url=http://localhost:8012 \
  --store-url=http://localhost:8011 \
  --username=admin \
  --password=admin
```

(Coverage report auto-generated to `htmlcov/index.html`)

### Run Specific Test File

```bash
uv run pytest tests/test_client/test_auth.py -v
uv run pytest tests/test_integration/test_clip_embedding_integration.py -v
```

### Run Tests Matching Pattern

```bash
# All auth-related tests
uv run pytest -k "auth" -v

# All plugin tests
uv run pytest -k "embedding or face or hash" -v
```

---

## Test Media

Integration tests require **test media files** (images, videos):

- Images: `test_image_1920x1080.jpg`, `test_exif_rich.jpg`, `test_face_single.jpg`, etc.
- Videos: `test_video_1080p_10s.mp4`, `test_video_720p_5s.mp4`

**Location:** `TEST_VECTORS_DIR` environment variable (defaults to `~/cl_server_test_media`)

If media not found, integration tests fail with:
```
AssertionError: Test image not found: /path/to/test_image_1920x1080.jpg
```

To use custom media location:

```bash
export TEST_VECTORS_DIR=/path/to/test/media
uv run pytest -m "integration" ...
```

---

## Troubleshooting

### Integration Tests Fail: "Cannot connect to server"

Servers not running. Start them

### Tests Fail: "Worker unavailable"

No workers with required capabilities running. Start at least one with required capabilities


### Tests Fail: "Test image not found"

Test media directory not found. Set `TEST_VECTORS_DIR`:

```bash
export TEST_VECTORS_DIR=/path/to/test/media
```

### Type Errors

Run strict type checker to catch issues:

```bash
uv run basedpyright
```

### Coverage Below 90%

Identify uncovered lines:

```bash
uv run pytest --cov=cl_client --cov-report=term-missing | grep "?"
```

Open `htmlcov/index.html` for interactive coverage drill-down.
