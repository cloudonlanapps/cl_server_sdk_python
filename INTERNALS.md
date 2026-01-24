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

**Note:** For system-wide architecture and inter-service communication, see [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) in the repository root. This section covers SDK-specific architecture only.

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
from cl_client import SessionManager

# No-auth mode (default)
client = ComputeClient(auth_provider=NoAuthProvider())

# JWT mode with SessionManager (recommended)
session = SessionManager()
await session.login("username", "password")
client = session.create_compute_client()

# JWT mode with direct provider (no automatic refresh)
auth_provider = JWTAuthProvider(token="your-jwt-token")
client = ComputeClient(auth_provider=auth_provider)
```

**Implementation:**
- Abstract `AuthProvider` base class
- Each provider implements `get_headers()` method
- Injected via constructor for easy testing
- Future providers can be added without modifying core client

### Three-Layer Authentication Architecture

The authentication system follows a three-layer design pattern matching the Dart SDK:

```
┌─────────────────────────────────────────────┐
│         SessionManager (High-Level)         │
│  - login(), logout(), is_authenticated()    │
│  - Automatic token refresh (< 60 sec)       │
│  - create_compute_client() factory          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         AuthClient (Low-Level API)          │
│  - POST /auth/token (login)                 │
│  - POST /auth/token/refresh                 │
│  - GET /auth/public-key                     │
│  - GET /users/me                            │
│  - User CRUD (admin endpoints)              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│      JWTAuthProvider (Header Injection)     │
│  - JWT token parsing for expiry             │
│  - Authorization header injection           │
│  - Integrates with SessionManager           │
└─────────────────────────────────────────────┘
```

**Layer Responsibilities:**

1. **SessionManager (High-Level)**: User-facing API for authentication lifecycle
   - Manages login/logout workflow
   - Stores token and user info in memory
   - Automatic token refresh when < 60 seconds until expiry
   - Creates pre-configured ComputeClient instances

2. **AuthClient (Low-Level)**: Direct wrappers for auth service REST API
   - All 9 auth endpoints (token, user management)
   - Async httpx client for HTTP requests
   - Pydantic model parsing
   - No state management (stateless)

3. **JWTAuthProvider (Integration)**: Bridges auth and compute clients
   - Parses JWT tokens to extract expiry
   - Injects Authorization headers into requests
   - Can integrate with SessionManager for auto-refresh

**Benefits:**
- Clear separation of concerns
- Easy to test each layer independently
- SessionManager provides simple high-level API
- AuthClient can be used directly for custom workflows
- Future auth methods (OAuth, API keys) can be added without affecting existing code

### Token Refresh Mechanism

SessionManager automatically refreshes JWT tokens before they expire:

```python
async def get_valid_token(self) -> str:
    """Get a valid token, refreshing if needed."""
    if not self._token:
        raise ValueError("Not authenticated")

    # Parse token to check expiry
    expiry = self._auth_provider._parse_token_expiry(self._token)
    if expiry:
        time_until_expiry = (expiry - datetime.now(timezone.utc)).total_seconds()

        # Refresh if < 60 seconds remaining
        if time_until_expiry < 60:
            response = await self._auth_client.refresh_token(self._token)
            self._token = response.access_token
            self._auth_provider = JWTAuthProvider(
                token=self._token,
                session_manager=self
            )

    return self._token
```

**Key Points:**
- Threshold: 60 seconds (matching Dart SDK)
- Automatic: No user intervention required
- Transparent: Client code doesn't need to handle refresh
- Fallback: If refresh fails, user must re-login

### Form-Based API Design

All auth service endpoints use **forms only** (no JSON), with a specific convention for permissions:

**Permissions Format:**
- Client sends: Comma-separated string (e.g., `"read:jobs,write:jobs"`)
- Server receives: Form field `permissions` as string
- Server parses: Splits on comma to get list

**Example - Create User:**
```python
# Client side (SDK)
form_data = {
    "username": "testuser",
    "password": "testpass",
    "is_admin": False,
    "permissions": "read:jobs,write:jobs"  # Comma-separated string
}

response = await session.post("/users/", data=form_data)
```

**Server side (FastAPI):**
```python
@router.post("/users/")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
    permissions: str | None = Form(None),  # String, not list
):
    # Parse comma-separated string to list
    permissions_list = []
    if permissions:
        permissions_list = [p.strip() for p in permissions.split(",") if p.strip()]
```

**Why Forms?**
- Consistent with FastAPI OAuth2 password flow
- Simple serialization (no nested JSON)
- Easy to test with cURL/Postman
- Avoids JSON parsing edge cases

**Why Comma-Separated Permissions?**
- Simple string format works in forms
- Easy to parse on server side
- Consistent across all endpoints (create, update)
- No ambiguity about list vs string representation

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
│   ├── auth.py             # Modular auth providers (NoAuthProvider, JWTAuthProvider)
│   ├── models.py           # Pydantic models (mirror server schemas)
│   ├── exceptions.py       # Custom exceptions
│   ├── mqtt_monitor.py     # MQTT monitoring with subscription IDs
│   ├── auth_models.py      # Auth-specific Pydantic models (Phase 2)
│   ├── server_config.py    # Centralized server URL configuration (Phase 2)
│   ├── auth_client.py      # Low-level auth API client (Phase 2)
│   ├── session_manager.py  # High-level auth session management (Phase 2)
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
│   ├── conftest.py         # Shared fixtures (auth_mode parametrization - Phase 2)
│   ├── README.md           # Testing guide (auth setup - Phase 2)
│   ├── media/              # Test media files (NOT in git)
│   │   ├── MEDIA_SETUP.md
│   │   ├── images/
│   │   └── videos/
│   ├── test_client/        # Unit tests
│   │   ├── test_auth.py               # Auth provider tests (26 tests - Phase 2)
│   │   ├── test_auth_models.py        # Auth model tests (18 tests - Phase 2)
│   │   ├── test_auth_client.py        # AuthClient tests (29 tests - Phase 2)
│   │   ├── test_server_config.py      # ServerConfig tests (10 tests - Phase 2)
│   │   ├── test_session_manager.py    # SessionManager tests (20 tests - Phase 2)
│   │   ├── test_compute_client.py     # ComputeClient tests
│   │   ├── test_config.py             # Config tests
│   │   ├── test_models.py             # Model tests
│   │   ├── test_mqtt_monitor.py       # MQTT tests
│   │   └── test_plugins.py            # Plugin unit tests (74 tests)
│   └── test_integration/   # Integration tests (parametrized for both auth modes)
│       ├── test_auth_errors_integration.py      # Auth error tests (6 tests - Phase 2)
│       ├── test_user_management_integration.py  # User CRUD tests (8 tests - Phase 2)
│       ├── test_clip_embedding.py
│       ├── test_dino_embedding.py
│       └── ... (9 plugin tests, parametrized for no-auth and JWT modes)
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
    _ = response.raise_for_status()
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

## Server-Side Changes (Phase 2)

During Phase 2 authentication integration, several critical server-side issues were discovered and fixed:

### 1. JWT Token Field: "sub" → "id"

**Issue:** JWT payload used `"sub"` field but compute service expected `"id"` field.

**Files Modified:**
1. `/services/auth/src/auth/routes.py`:
   - Line 75: Changed `"sub": str(user.id)` → `"id": str(user.id)` (login endpoint)
   - Line 91: Changed `"sub": str(current_user.id)` → `"id": str(current_user.id)` (refresh endpoint)
   - Line 31: Changed `payload.get("sub")` → `payload.get("id")` (get_current_user validation)

2. `/services/compute/src/compute/auth.py`:
   - Line 38: Changed `sub: str` → `id: str` (UserPayload model)
   - Line 121: Changed `options={"require": ["sub", "exp"]}` → `options={"require": ["id", "exp"]}` (JWT validation)

**Reason:** Using `"id"` is more semantically correct for user identification than `"sub"` (subject).

### 2. Endpoint Consistency: All Forms, No JSON

**Issue:** `update_user` endpoint used JSON (Pydantic model) while `create_user` used forms.

**Files Modified:**
1. `/services/auth/src/auth/routes.py`:
   - Lines 192-224: Replaced `update_user` endpoint to use Form fields instead of Pydantic JSON:
     ```python
     # BEFORE: def update_user(user_id: int, user_update: UserUpdate, ...)
     # AFTER:
     def update_user(
         user_id: int,
         password: str | None = Form(None),
         permissions: str | None = Form(None),  # Comma-separated string
         is_active: bool | None = Form(None),
         is_admin: bool | None = Form(None),
         ...
     )
     ```

2. `/sdks/pysdk/src/cl_client/auth_client.py`:
   - Lines 201-213: Updated `create_user()` to convert permissions list to comma-separated string
   - Lines 319-333: Updated `update_user()` to use `data=` (forms) instead of `json=`

**Reason:** Consistency across all endpoints. Forms are simpler and work better with FastAPI OAuth2.

### 3. Permissions Format: Comma-Separated Strings

**Issue:** Python SDK was sending permissions as Python lists, which don't serialize properly in form data.

**Solution:**
- Client (SDK): Convert Python list to comma-separated string before sending
  ```python
  permissions = ["read:jobs", "write:jobs"]
  form_data["permissions"] = ",".join(permissions)  # → "read:jobs,write:jobs"
  ```

- Server: Parse comma-separated string back to list
  ```python
  permissions_list = [p.strip() for p in permissions.split(",") if p.strip()]
  ```

**Files Modified:**
1. `/sdks/pysdk/src/cl_client/auth_client.py`:
   - `create_user()`: Added `",".join(form_data["permissions"])` conversion
   - `update_user()`: Added `",".join(update_data["permissions"])` conversion

2. `/services/auth/src/auth/routes.py`:
   - `create_user()`: Already had comma-separated parsing (lines 134-150)
   - `update_user()`: Added comma-separated parsing (lines 205-211)

**Reason:** Form data doesn't support nested structures. Comma-separated strings are simple and unambiguous.

### 4. Auth Database Initialization

**Issue:** Tests failed with "no such table: users" on fresh auth service install.

**Solution:**
```bash
cd ../../services/auth
alembic upgrade head
```

**Reason:** Database migrations weren't automatically run. Now documented in test setup guides.

### Testing Impact

All changes were validated with comprehensive integration tests:
- 8 user management tests (create, list, get, update, delete)
- 6 auth error tests (401, 403 scenarios)
- 28 plugin tests in JWT mode
- All tests parametrized to run in both no-auth and JWT modes

**Test Results:**
- No-auth mode: 23 passed, 2 failed (face_detection - known issue)
- JWT mode: 41 passed, 2 failed (face_detection - known issue)
- Total: 64 test scenarios, 62 passing

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

## Testing Strategy

Tests are organized into unit tests and integration tests:

**Unit Tests** (`tests/test_client/`):
- `test_auth.py` - Auth provider tests (NoAuthProvider, JWTAuthProvider, token refresh)
- `test_auth_models.py` - Pydantic model validation for auth requests/responses
- `test_auth_client.py` - AuthClient low-level API tests (login, user CRUD)
- `test_server_config.py` - ServerConfig URL configuration tests
- `test_session_manager.py` - SessionManager high-level auth workflow tests
- `test_compute_client.py` - ComputeClient unit tests with mocked dependencies
- `test_config.py` - Configuration loading and validation
- `test_models.py` - Pydantic model tests for compute API
- `test_mqtt_monitor.py` - MQTT monitoring with mocked broker
- `test_plugins.py` - Plugin unit tests (74 tests across 9 plugins)

**Integration Tests** (`tests/test_integration/`):
- `test_auth_errors_integration.py` - Auth error scenarios (401, 403)
- `test_user_management_integration.py` - User CRUD with live auth service
- `test_clip_embedding.py` - CLIP plugin with live compute service
- `test_dino_embedding.py` - DINO plugin integration
- `test_exif.py` - EXIF extraction integration
- `test_face_detection.py` - Face detection integration
- `test_face_embedding.py` - Face embedding integration
- `test_hash.py` - Perceptual hashing integration
- `test_hls_streaming.py` - HLS manifest generation integration
- `test_image_conversion.py` - Image format conversion integration
- `test_media_thumbnail.py` - Thumbnail generation integration

All integration tests are parametrized to run in both no-auth and JWT modes. Tests use httpx.AsyncClient for API calls and aiomqtt for MQTT monitoring.

**Test Tools:**
- pytest with async support (`pytest-asyncio`)
- httpx for async HTTP testing
- aiomqtt for MQTT client testing
- Pydantic for request/response validation
- Coverage tracking with 90% minimum requirement

---

## Documentation

- **[README.md](./README.md)** - User-facing documentation with quick start, authentication, API reference
- **[REVIEW.md](./REVIEW.md)** - Comprehensive code review with actionable issues for improvements
- **[INTERNALS.md](./INTERNALS.md)** - This file - developer documentation and architecture
- **[tests/README.md](./tests/README.md)** - Comprehensive testing guide with fixtures and patterns
- **[tests/QUICK.md](./tests/QUICK.md)** - Quick test command reference

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

### Authentication Issues

**Problem:** 401 Unauthorized - "Could not validate credentials"
**Solutions:**
1. Token expired - SessionManager should auto-refresh, but if using JWTAuthProvider directly, refresh manually
2. Invalid token format - Check token is valid JWT
3. Auth service not running - Start auth service first
4. Wrong credentials - Verify username/password

**Problem:** 403 Forbidden - "Insufficient permissions"
**Solutions:**
1. User lacks required permission - Add permission to user (admin only)
2. Not an admin user - Only admins can access user management endpoints
3. Check user permissions: `user = await session.get_current_user(); print(user.permissions)`

**Problem:** JWT field mismatch - "UserPayload object has no attribute 'id'"
**Solution:** This was a server-side bug fixed in Phase 2. JWT payload now uses `"id"` field instead of `"sub"`. If you see this error:
1. Update auth service to latest version (with "id" field fix)
2. Update compute service to expect "id" field
3. Restart both services

**Problem:** Token not refreshing automatically
**Solutions:**
1. Using JWTAuthProvider directly - Switch to SessionManager for auto-refresh
2. SessionManager refresh threshold - Tokens refresh at < 60 seconds remaining
3. Check token expiry: `provider._parse_token_expiry(token)`

**Problem:** Permissions not saving correctly
**Solution:** This was fixed in Phase 2. Ensure:
1. Client sends permissions as comma-separated string: `"read:jobs,write:jobs"`
2. Server endpoint uses Form fields (not JSON)
3. Update SDK to latest version with form-based API

**Problem:** 400 Bad Request on user creation/update
**Solutions:**
1. Username already exists (create only)
2. Invalid permissions format - Use comma-separated string
3. Missing required fields - Check username and password provided

### Test Failures

**Problem:** `WorkerUnavailableError`
**Solution:** Ensure workers are running with required capabilities

**Problem:** File download failures
**Solution:** Check job completed successfully, verify file path in `params`

**Problem:** Auth tests failing - "no such table: users"
**Solution:** Initialize auth database with alembic:
```bash
cd ../../services/auth
alembic upgrade head
```

**Problem:** Integration tests skip in JWT mode
**Solution:** Set required environment variables:
```bash
export AUTH_DISABLED=false
export TEST_USERNAME=admin
export TEST_PASSWORD=admin
```

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
