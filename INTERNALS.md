# CL Client - Internal Documentation

Developer documentation for the `cl_client` Python library.

## Development Setup

```bash
# Clone repository
cd /path/to/cl_server/services/compute/client/python

# Install dependencies
uv sync

# Run type checking
uv run basedpyright

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run ruff format src/
```

## Architecture

### Configuration-First Design

All endpoints, hosts, ports are centralized in `config.py`:

```python
from cl_client.config import ComputeClientConfig

# NO hardcoding - always use config
endpoint = ComputeClientConfig.get_plugin_endpoint("clip_embedding")
base_url = ComputeClientConfig.DEFAULT_BASE_URL
```

**Benefits:**
- Single source of truth for all configuration
- Easy to modify endpoints without touching implementation
- Type-safe with explicit types
- Future-proof for environment variable overrides

### Two-Callback System

MQTT monitoring uses separate callbacks for progress and completion:

```python
def on_progress(job):
    print(f"Progress: {job.progress}%")

def on_complete(job):
    print(f"Completed: {job.status}")

job = await client.plugin.method(
    ...,
    on_progress=on_progress,
    on_complete=on_complete
)
```

**Why two callbacks?**
- `on_progress`: Called on every status update (useful for UI updates)
- `on_complete`: Called once when job finishes (completed/failed)
- Allows different handling for progress vs completion

### Subscription IDs

MQTT subscriptions return unique IDs for unsubscribing:

```python
sub_id = client.subscribe_job_updates(
    job_id="abc-123",
    on_complete=callback
)

# Later...
client.unsubscribe(sub_id)
```

**Why subscription IDs?**
- Allows multiple callbacks per job
- Clean unsubscribe mechanism
- Prevents accidental unsubscription of other listeners

### Modular Authentication

Auth providers are injectable and swappable:

```python
from cl_client.auth import NoAuthProvider, JWTAuthProvider

# No-auth mode (default)
client = ComputeClient(auth_provider=NoAuthProvider())

# JWT mode (Phase 2)
client = ComputeClient(auth_provider=JWTAuthProvider(token="..."))
```

**Implementation:**
- Abstract `AuthProvider` base class
- Each provider implements `get_headers()` method
- Injected via constructor for easy testing
- Future providers can be added without modifying core client

## Code Quality Standards

### Type Checking

Strict basedpyright mode - **zero `Any` types allowed**:

```bash
uv run basedpyright  # Must pass with 0 errors
```

**Type Safety Rules:**
- Use `JSONObject` type alias instead of `dict[str, Any]`
- All public methods have explicit type hints
- No `cast()` without validation
- Pydantic models for all API responses

### Testing

**Coverage Requirements:**
- Core library: ≥90% code coverage (current: 88.97%)
- CLI tool: ≥70% code coverage (current: 80.48%)
- All tests must pass with 0 failures

```bash
# Run with coverage
uv run pytest --cov=cl_client --cov-fail-under=88

# View HTML report
uv run pytest --cov=cl_client --cov-report=html
open htmlcov/index.html
```

**Test Patterns:**
- Integration tests with live server
- Unit tests with mocked dependencies
- All tests clean up jobs after completion
- Worker capability validation before tests

### Plugin Modularity

Each plugin is completely independent:

- Separate file in `plugins/<name>.py`
- No cross-talk between plugins
- Easy to add/remove without affecting others
- Each plugin inherits from `BasePluginClient`

**Adding a new plugin:**
1. Create `plugins/new_plugin.py`
2. Inherit from `BasePluginClient`
3. Implement plugin-specific methods
4. Add lazy-loading property to `ComputeClient`
5. Add endpoint to `ComputeClientConfig.PLUGIN_ENDPOINTS`
6. Write tests in `tests/test_plugins/test_new_plugin.py`

## Project Structure

```
cl_client/
├── pyproject.toml          # Dependencies, scripts, tool config
├── pyrightconfig.json      # Type checking config (separate from pyproject.toml)
├── README.md               # User documentation
├── INTERNALS.md            # This file
├── task.md                 # Implementation progress tracker
├── src/cl_client/
│   ├── __init__.py         # Public API exports
│   ├── config.py           # All configuration (NO hardcoding)
│   ├── compute_client.py   # Main client class
│   ├── auth.py             # Modular auth providers
│   ├── models.py           # Pydantic models (mirror server schemas)
│   ├── exceptions.py       # Custom exceptions
│   ├── mqtt_monitor.py     # MQTT monitoring with subscription IDs
│   └── plugins/            # Plugin clients (9 total)
│       ├── __init__.py
│       ├── base.py
│       ├── clip_embedding.py
│       ├── dino_embedding.py
│       ├── exif.py
│       ├── face_detection.py
│       ├── face_embedding.py
│       ├── hash.py
│       ├── hls_streaming.py
│       ├── image_conversion.py
│       └── media_thumbnail.py
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── README.md           # Testing guide
│   ├── media/              # Test media files (NOT in git)
│   │   ├── MEDIA_SETUP.md
│   │   ├── images/
│   │   └── videos/
│   ├── test_client/        # Unit tests
│   │   ├── test_auth.py
│   │   ├── test_compute_client.py
│   │   ├── test_config.py
│   │   ├── test_models.py
│   │   ├── test_mqtt_monitor.py
│   │   └── test_plugins.py (74 tests)
│   └── test_plugins/       # Integration tests
│       ├── test_clip_embedding.py
│       ├── test_dino_embedding.py
│       └── ... (9 plugin tests, 25 total)
└── example/                # Separate CLI tool project
    ├── README.md
    ├── pyproject.toml
    ├── src/cl_client_cli/
    │   ├── __init__.py
    │   └── main.py         # CLI implementation
    └── tests/              # CLI tests (21 tests)
        ├── conftest.py
        └── test_cli.py
```

## MQTT Architecture

### Topics

**Job Status Updates:**
- Topic: `inference/events`
- Message format: Full `JobResponse` JSON
- Published by: Server's `JobRepository`
- Subscribed by: Client's `MQTTJobMonitor`

**Worker Capabilities:**
- Topic: `inference/workers/{worker_id}`
- Message format: Worker capability JSON
- Empty payload = worker disconnect (Last Will & Testament)

### Event Flow

```
1. Client submits job → Server
2. Server publishes job created → inference/events
3. Worker picks up job
4. Worker publishes progress updates → inference/events
5. Client receives updates → invokes on_progress callback
6. Job completes
7. Worker publishes completion → inference/events
8. Client receives completion → invokes on_complete callback
```

## File Downloads

### Implementation

```python
async def download_job_file(
    self,
    job_id: str,
    file_path: str,
    dest: Path
) -> None:
    """Download file from job's output directory.

    Args:
        job_id: Job UUID
        file_path: Relative path (e.g., "output/embedding.npy")
        dest: Local destination path
    """
    endpoint = f"/jobs/{job_id}/files/{file_path}"
    response = await self._session.get(endpoint)
    response.raise_for_status()
    dest.write_bytes(response.content)
```

### Security

Server validates:
- Job exists and is accessible
- File path doesn't contain `..` (path traversal protection)
- File is within job's directory
- File is not a directory

## Known Issues (Not Blocking)

### 1. Face Detection Returns 0 Faces

**Symptom:**
- Face detection jobs complete successfully
- Returns `{"faces": [], "num_faces": 0}` even on images with faces
- Test images: `test_face_single.jpg`, `test_face_multiple.jpg`

**Analysis:**
- ✅ CLI submits jobs correctly
- ✅ Jobs complete without errors
- ✅ Image dimensions detected correctly
- ❌ No faces detected (expected: at least 1 face)

**Root Cause:**
- This is a **server/worker issue**, not a client library issue
- Possible causes:
  1. Face detection model not loaded correctly in worker
  2. Confidence threshold too high (current: 0.7)
  3. Model incompatible with test images
  4. Image preprocessing issues in worker

**Workaround:**
- None currently - requires server-side debugging

**Priority:** Low (separate server issue to debug later)

---

## Optional Future Work

These are enhancements for future development, not current requirements:

### 1. Workflow Tests

**Description:** Multi-plugin integration tests simulating real-world workflows

**Examples:**
```python
# Complete image analysis pipeline
async def test_complete_image_analysis():
    # 1. Extract EXIF
    exif_job = await client.exif.extract(image)

    # 2. Generate thumbnail
    thumb_job = await client.media_thumbnail.generate(image, 256, 256)

    # 3. Compute CLIP embedding
    clip_job = await client.clip_embedding.embed_image(image)

    # 4. Compute perceptual hash
    hash_job = await client.hash.compute(image)

    # Verify all succeeded
    assert all(j.status == "completed" for j in [exif_job, thumb_job, clip_job, hash_job])
```

**Benefits:**
- Tests real-world use cases
- Validates plugin interactions
- Catches integration issues

### 2. JWT Authentication (Phase 2)

**Description:** Complete JWT authentication implementation

**Requirements:**
- Auth server integration
- Token refresh mechanism
- Session management
- Secure token storage

**Implementation:**
```python
class JWTAuthProvider(AuthProvider):
    def __init__(self, token: str):
        self.token = token

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def refresh_token(self) -> str:
        # Implement token refresh logic
        pass
```

**Status:** Deferred pending auth server availability

### 3. Additional CLI Features

**Batch Operations:**
```bash
# Process multiple files
cl-client clip-embedding embed *.jpg --output-dir embeddings/

# Parallel job submission
cl-client batch submit jobs.json
```

**Job Management:**
```bash
# List all jobs
cl-client jobs list --status completed

# Get job details
cl-client jobs get <job-id>

# Cancel job
cl-client jobs cancel <job-id>
```

**Configuration Files:**
```bash
# Load config from file
cl-client --config config.yaml clip-embedding embed photo.jpg
```

### 4. Documentation Improvements

- **API Reference:** Auto-generated from docstrings (Sphinx/mkdocs)
- **Video Tutorials:** Walkthrough videos for common workflows
- **Interactive Examples:** Jupyter notebooks with live demonstrations
- **Migration Guides:** Guides for upgrading between versions

### 5. Performance Optimizations

**Connection Pooling:**
```python
# Reuse HTTP connections
client = ComputeClient(
    pool_size=10,
    pool_maxsize=20
)
```

**Caching:**
```python
# Cache worker capabilities
capabilities = await client.get_capabilities(cache=True, ttl=60)

# Cache job results
result = await client.get_job(job_id, cache=True)
```

**Batch Downloads:**
```python
# Download multiple files in parallel
await client.download_job_files(
    job_id,
    files=["output/embedding.npy", "output/metadata.json"],
    dest_dir=Path("results/")
)
```

---

## Contributing

### Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement changes**
   - Add type hints to all new code
   - Follow existing code patterns
   - Update tests

3. **Run quality checks**
   ```bash
   # Type checking (must pass)
   uv run basedpyright

   # Linting (must pass)
   uv run ruff check src/

   # Formatting
   uv run ruff format src/

   # Tests (must pass with ≥88% coverage)
   uv run pytest --cov=cl_client --cov-fail-under=88
   ```

4. **Update documentation**
   - Update README.md if public API changed
   - Update INTERNALS.md if architecture changed
   - Add docstrings to new public methods

5. **Submit PR**
   - Clear description of changes
   - Link to related issues
   - Include test results

### Code Review Checklist

- [ ] Type checking passes (0 errors)
- [ ] All tests pass
- [ ] Coverage ≥88%
- [ ] No `Any` types introduced
- [ ] Documentation updated
- [ ] No hardcoded values (use config)
- [ ] Error handling appropriate
- [ ] Follows existing patterns

### Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Tag release: `git tag v0.1.0`
5. Push to repository
6. Build package: `uv build`
7. Publish to PyPI: `uv publish`

---

## Testing Guide

See [tests/README.md](./tests/README.md) for detailed testing instructions.

### Quick Reference

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_client/test_plugins.py

# Run with coverage
uv run pytest --cov=cl_client --cov-report=html

# Run only integration tests
uv run pytest tests/test_plugins/

# Run only unit tests
uv run pytest tests/test_client/
```

---

## Troubleshooting

### Type Checking Errors

**Problem:** `reportAny` errors
**Solution:** Use `JSONObject` instead of `dict[str, Any]`

**Problem:** Unknown type errors
**Solution:** Add explicit type hints, avoid relying on inference

### MQTT Connection Issues

**Problem:** Callbacks not firing
**Solution:** Check MQTT broker is running, verify topic subscriptions

**Problem:** Connection refused
**Solution:** Verify `MQTT_BROKER_HOST` and `MQTT_BROKER_PORT` are correct

### Test Failures

**Problem:** `WorkerUnavailableError`
**Solution:** Ensure workers are running with required capabilities

**Problem:** File download failures
**Solution:** Check job completed successfully, verify file path in `params`

---

## Performance Considerations

- **MQTT is primary:** Always prefer MQTT callbacks over HTTP polling
- **Connection reuse:** Use `async with ComputeClient()` for automatic cleanup
- **Batch operations:** Submit multiple jobs concurrently when possible
- **Worker selection:** Server automatically routes to available workers

---

## Security Notes

- **No-auth mode:** Currently only no-auth is supported (suitable for internal networks)
- **JWT auth:** Coming in Phase 2 (requires auth server)
- **File downloads:** Server validates all file paths (path traversal protection)
- **MQTT security:** Consider enabling MQTT authentication in production

---

## Support

- **Documentation:** See README.md, this file, and tests/README.md
- **Issues:** Report at project issue tracker
- **Examples:** Check `example/` directory for CLI usage patterns
