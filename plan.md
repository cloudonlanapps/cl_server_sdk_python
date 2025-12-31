# Python SDK (`pysdk`) Implementation Plan

## Overview
Create a standalone Python SDK package `pysdk` for the compute service, with comprehensive integration tests using pre-provided test media.

## User Requirements Clarifications

### Phase 1 Requirements (Current)
- **Package Location**: Separate package named `pysdk` (future-proof to support other service)
- **Plugin Discovery**: Hardcode plugin schemas (9 plugins from cl_ml_tools) in config
- **MQTT Integration**: Full job progress tracking + worker capabilities (primary workflow)
- **Job Monitoring**: MQTT callback-based (primary), HTTP polling optional (secondary)
- **Configuration Management**: All endpoints, hosts, ports in separate config class (NO hardcoding)
- **Test Media**: Pre-provided, NOT in git. Tests fail with clear error if missing
- **Authentication**: No-auth mode ONLY (token auth deferred to Phase 2)
- **Type Safety**: Strict basedpyright, no Any types, no warnings/errors
- **Worker Validation**: Tests fail if required capability workers don't exist
- **Documentation**: Follow PROJECT_STRUCTURE.md standard (README.md, INTERNALS.md, tests/README.md, tests/media/MEDIA_SETUP.md)
- **Consistency**: Follow compute service's pyproject.toml structure/naming/order

### Phase 2 Requirements (In Progress)
- **Authentication**: JWT token support with auth server integration
- **SessionManager**: High-level auth facade matching Dart SDK
- **Automatic Token Refresh**: Refresh when < 1 minute before expiry
- **Test Parametrization**: Multi-mode testing with server detection
  - Config-file based test user management (`tests/auth_config.json`)
  - Server auth detection via RootResponse (`auth_required` field)
  - Multiple test modes: admin, user-with-permission, user-no-permission, no-auth
  - Automatic user creation/validation
  - Smart skip/fail logic based on server vs test mode mismatch
  - Test matrix validation (4 scenarios: auth+enabled, no-auth+disabled, etc.)
- **CLI Auth Support**: --username, --password, --no-auth flags
- **Backward Compatibility**: No-auth remains default

## Coding Guidelines

### Pydantic-First Data Handling
**CRITICAL**: Always use Pydantic for data validation and parsing. Avoid manual dictionary manipulation.

**❌ AVOID - Manual dictionary parsing:**
```python
data_raw: object = response.json()
if not isinstance(data_raw, dict):
    raise ValueError(...)
data = cast(dict[str, object], data_raw)
return TokenResponse(**data)
```

**✅ PREFER - Pydantic validation:**
```python
return TokenResponse.model_validate(response.json())
```

**Benefits:**
- Cleaner, more maintainable code
- Better type safety (no Any types)
- Automatic validation with clear error messages
- Consistent with Pydantic best practices
- Reduces boilerplate code

**Application:**
- Use `Model.model_validate(data)` for single objects
- Use `Model.model_validate(item) for item in data` for lists
- Let Pydantic handle type coercion and validation
- Only use dictionaries for dynamic data that doesn't fit a schema

## Plan Revision Summary

This plan has been revised based on 16 critical requirements (8 initial + 8 refinements):

### Initial Requirements (1-8)

1. **Configuration Management** ✅
   - Added `config.py` with `ComputeClientConfig` class
   - ALL endpoints, hosts, ports as class variables (NO hardcoding anywhere)
   - All implementations use config lookups

2. **MQTT Callback-Based Monitoring** ✅
   - MQTT callbacks are PRIMARY workflow (not polling)
   - HTTP polling is SECONDARY/optional (via `wait=True`)
   - Tests demonstrate both workflows
   - Job status from cl_server_shared JobRepository

3. **Project Structure Consistency** ✅
   - pyproject.toml mirrors compute service structure/naming/order
   - Same tool configurations (pytest, coverage, ruff)
   - Same development patterns

4. **MQTT Job Status Tracking** ✅
   - Job status messages published by JobRepository (cl_server_shared)
   - Topic: `inference/job_status/{job_id}`
   - Full JobResponse in MQTT messages

5. **Documentation Structure** ✅
   - Follows PROJECT_STRUCTURE.md template
   - README.md (user docs), INTERNALS.md (developer docs)
   - tests/README.md (testing docs)
   - tests/media/MEDIA_SETUP.md (media setup - moved from tests/)

6. **Authentication Phase Separation** ✅
   - Phase 1: No-auth mode ONLY
   - Phase 2: JWT token support (deferred, requires auth server)

7. **Strict Type Checking** ✅
   - basedpyright configuration in pyrightconfig.json (separate file)
   - NO Any types allowed
   - JSONObject type alias for type-safe dict usage
   - Zero warnings/errors required

8. **Worker Capability Validation** ✅
   - Tests validate worker availability BEFORE running
   - `validate_workers()` fixture raises WorkerUnavailableError
   - Clear error messages when workers missing

### Refinement Requirements (9-16)

9. **MQTT Subscription IDs** ✅
   - `subscribe_job_updates()` returns unique subscription ID
   - `unsubscribe()` uses subscription ID (not job_id)
   - Supports multiple callbacks per job

10. **Plugin Method Separation** ✅
    - `submit_job()` as stub (NotImplementedError) for future file-less plugins
    - `submit_with_files()` fully implemented (primary method)
    - Keep both separate, not interdependent

11. **Plugin Modularity** ✅
    - Each plugin's logic and schema completely separate
    - No cross-talk between plugins
    - Easy to add/remove plugins independently

12. **Modular Authentication** ✅
    - FastAPI Depends()-style pattern for auth
    - Auth provider is detachable and swappable
    - Easy to extend with new auth methods

13. **Two-Callback System** ✅
    - `on_progress` callback for job progress updates
    - `on_complete` callback for job completion/failure
    - Both optional, can use either or both

14. **Parallel MQTT Workflow Tests** ✅
    - Register ALL MQTT callbacks upfront
    - Submit ALL tasks with callbacks
    - Wait for ALL callbacks to complete
    - Main thread exits after all callbacks

15. **Separate pyrightconfig.json** ✅
    - basedpyright config in pyrightconfig.json (NOT pyproject.toml)
    - Mirrors server's pyrightconfig.json structure
    - Includes venv paths, include/exclude patterns

16. **CLI Tool** ✅
    - Add command-line interface using the library
    - Subcommands for each plugin (e.g., `pysdk image_conversion ...`)
    - File download endpoint (to be implemented on server later)

### Major Architectural Decisions

- **Config-First**: No hardcoded values, all in ComputeClientConfig
- **MQTT-First**: Callback-based monitoring is primary, polling is fallback
- **Modular**: Plugins, auth, callbacks all independent and swappable
- **Type-Safe**: Strict basedpyright, no Any, explicit type hints everywhere
- **Test-Driven**: Worker validation, media validation, comprehensive error messages
- **Consistent**: Mirrors compute service patterns and structure
- **CLI + Library**: Both programmatic API and command-line interface

## Implementation Structure

### Package Structure: `pysdk/`
```
pysdk/
├── pyproject.toml                # Package config (mirrors compute service structure)
├── pyrightconfig.json            # Basedpyright configuration (separate file)
├── README.md                     # User documentation
├── INTERNALS.md                  # Developer documentation
├── src/
│   └── pysdk/
│       ├── __init__.py           # Public API exports
│       ├── config.py             # Configuration class (all endpoints/hosts/ports)
│       ├── compute_client.py     # Main client class
│       ├── auth.py               # Modular auth (FastAPI Depends-style)
│       ├── models.py             # Pydantic models (mirror server schemas)
│       ├── exceptions.py         # Custom exceptions
│       ├── mqtt_monitor.py       # MQTT job/worker monitoring (subscription IDs)
│       ├── cli.py                # CLI tool entry point
│       └── plugins/              # Plugin-specific SDK (completely modular)
│           ├── __init__.py
│           ├── base.py           # BasePluginClient (submit_job stub, submit_with_files implemented)
│           ├── clip_embedding.py # Each plugin fully independent
│           ├── dino_embedding.py
│           ├── exif.py
│           ├── face_detection.py
│           ├── face_embedding.py
│           ├── hash.py
│           ├── hls_streaming.py
│           ├── image_conversion.py
│           └── media_thumbnail.py
└── tests/
    ├── conftest.py               # Shared fixtures
    ├── README.md                 # Testing documentation
    ├── media/
    │   └── MEDIA_SETUP.md        # Instructions for obtaining test media
    ├── test_client/              # Client unit tests
    │   ├── test_config.py
    │   ├── test_compute_client.py
    │   ├── test_auth.py
    │   ├── test_mqtt_monitor.py
    │   ├── test_models.py
    │   └── test_cli.py           # CLI tests
    ├── test_plugins/             # Plugin integration tests (9 files)
    │   ├── test_clip_embedding.py
    │   ├── test_dino_embedding.py
    │   ├── test_exif.py
    │   ├── test_face_detection.py
    │   ├── test_face_embedding.py
    │   ├── test_hash.py
    │   ├── test_hls_streaming.py
    │   ├── test_image_conversion.py
    │   └── test_media_thumbnail.py
    └── test_workflows/           # Multi-plugin workflows (parallel MQTT)
        ├── test_image_processing_workflow.py
        └── test_video_processing_workflow.py
```

### External Test Media (NOT in git): `pysdk_test_media/`
```
pysdk_test_media/              # Separate directory, user-provided
├── images/
│   ├── test_image_1920x1080.jpg  # Standard HD image
│   ├── test_image_800x600.png    # Smaller image, PNG format
│   ├── test_face_single.jpg      # Image with 1 face
│   ├── test_face_multiple.jpg    # Image with 3+ faces
│   └── test_exif_rich.jpg        # Image with full EXIF data
└── videos/
    ├── test_video_1080p_10s.mp4  # 10 second 1080p video
    └── test_video_720p_5s.mp4    # 5 second 720p video
```

## Server Endpoint Requirements

### File Download Endpoint (To Be Implemented)

**Current Status**: This endpoint does NOT exist in the server yet. It needs to be implemented when CLI file download functionality is required.

**Endpoint**: `GET /jobs/{job_id}/files/{file_path:path}`

**Purpose**: Download output files from completed jobs. The `task_output` field in JobResponse contains relative paths to output files. This endpoint enables downloading those files using the job_id and relative path.

**Request**:
```http
GET /jobs/{job_id}/files/{file_path:path}
```

**Parameters**:
- `job_id` (path): Job UUID
- `file_path` (path): Relative file path from `task_output` (e.g., `output/thumbnail.jpg`, `streaming/manifest.m3u8`)

**Response**:
- **200 OK**: File content with appropriate Content-Type header
- **404 Not Found**: Job or file not found
- **403 Forbidden**: Permission denied (if auth enabled)

**Example Usage**:
```python
# From JobResponse task_output
task_output = {
    "thumbnail_path": "output/thumbnail.jpg",
    "width": 256,
    "height": 256
}

# Construct download URL
file_path = task_output["thumbnail_path"]  # "output/thumbnail.jpg"
download_url = f"{base_url}/jobs/{job_id}/files/{file_path}"

# Download file
response = await client.get(download_url)
with open("downloaded_thumbnail.jpg", "wb") as f:
    f.write(response.content)
```

**Implementation Notes**:
- Server should validate that file path is within job's output directory (prevent path traversal)
- Use `FileResponse` from FastAPI to serve files
- Set appropriate `Content-Type` based on file extension
- Respect authentication/authorization (same as get_job endpoint)
- Clean up files when job is deleted

**Server Implementation Timing**: Implement when CLI tool requires file download functionality. Server restart will be required after adding this endpoint.

## Critical Implementation Components

### 0. Configuration Management (`config.py`)

**Purpose**: Centralize all configuration values (endpoints, hosts, ports, timeouts) to avoid hardcoding and enable easy modification.

**Design Pattern:**
```python
class ComputeClientConfig:
    """Configuration for compute client.

    All endpoints, hosts, ports, and parameters are defined here as class variables.
    This enables easy modification without changing code throughout the library.
    """

    # Server Connection
    DEFAULT_HOST: str = "localhost"
    DEFAULT_PORT: int = 8002
    DEFAULT_BASE_URL: str = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    DEFAULT_TIMEOUT: float = 30.0

    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CAPABILITY_TOPIC_PREFIX: str = "inference/workers"
    MQTT_JOB_STATUS_TOPIC_PREFIX: str = "inference/job_status"

    # Core API Endpoints
    ENDPOINT_GET_JOB: str = "/jobs/{job_id}"
    ENDPOINT_DELETE_JOB: str = "/jobs/{job_id}"
    ENDPOINT_CAPABILITIES: str = "/capabilities"

    # Plugin Endpoints (from cl_ml_tools)
    PLUGIN_ENDPOINTS: dict[str, str] = {
        "clip_embedding": "/clip_embedding/jobs",
        "dino_embedding": "/dino_embedding/jobs",
        "exif": "/exif/jobs",
        "face_detection": "/face_detection/jobs",
        "face_embedding": "/face_embedding/jobs",
        "hash": "/hash/jobs",
        "hls_streaming": "/hls_streaming/jobs",
        "image_conversion": "/image_conversion/jobs",
        "media_thumbnail": "/media_thumbnail/jobs",
    }

    # Job Monitoring Configuration
    DEFAULT_POLL_INTERVAL: float = 1.0
    MAX_POLL_BACKOFF: float = 10.0
    POLL_BACKOFF_MULTIPLIER: float = 1.5

    # Worker Validation
    WORKER_WAIT_TIMEOUT: float = 30.0
    WORKER_CAPABILITY_CHECK_INTERVAL: float = 1.0

    @classmethod
    def get_plugin_endpoint(cls, task_type: str) -> str:
        """Get endpoint for plugin task type.

        Args:
            task_type: Plugin task type (e.g., "clip_embedding")

        Returns:
            Endpoint path

        Raises:
            ValueError: If task_type not found
        """
        if task_type not in cls.PLUGIN_ENDPOINTS:
            raise ValueError(
                f"Unknown task type: {task_type}. "
                f"Available: {list(cls.PLUGIN_ENDPOINTS.keys())}"
            )
        return cls.PLUGIN_ENDPOINTS[task_type]
```

**Key Benefits:**
- **No hardcoding**: All values in one place
- **Easy modification**: Change endpoints/ports without touching implementation code
- **Type-safe**: All values have explicit types (basedpyright compatible)
- **Validation**: Helper methods to validate task types
- **Future-proof**: Easy to extend with environment variable overrides

### 1. Core Client (`compute_client.py`)

**Key Methods:**
```python
class ComputeClient:
    def __init__(
        base_url: str | None = None,  # Uses ComputeClientConfig.DEFAULT_BASE_URL if None
        timeout: float | None = None,  # Uses ComputeClientConfig.DEFAULT_TIMEOUT if None
        mqtt_broker: str | None = None,  # Uses ComputeClientConfig.MQTT_BROKER_HOST if None
        mqtt_port: int | None = None,  # Uses ComputeClientConfig.MQTT_BROKER_PORT if None
    ):
        """Initialize compute client.

        Args:
            base_url: Server base URL (default from config)
            timeout: Request timeout (default from config)
            mqtt_broker: MQTT broker host (default from config)
            mqtt_port: MQTT broker port (default from config)
        """

    # Job Management (REST API)
    async def get_job(job_id: str) -> JobResponse
    async def delete_job(job_id: str) -> None

    # Optional: HTTP Polling (secondary workflow)
    async def wait_for_job(
        job_id: str,
        poll_interval: float | None = None,  # Uses config default
        timeout: float | None = None
    ) -> JobResponse

    # Worker Capabilities (REST API)
    async def get_capabilities() -> WorkerCapabilitiesResponse
    async def wait_for_workers(
        required_capabilities: list[str] | None = None,
        timeout: float | None = None  # Uses config default
    ) -> bool

    # MQTT Job Monitoring (primary workflow)
    def subscribe_job_updates(
        job_id: str,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None
    ) -> str:
        """Subscribe to job status updates via MQTT.

        Primary workflow for job monitoring. Returns unique subscription ID.
        Supports multiple subscriptions per job.

        Args:
            job_id: Job ID to monitor
            on_progress: Called on each job update (queued → in_progress → ...)
            on_complete: Called only when job completes (status: completed/failed)

        Returns:
            Unique subscription ID for unsubscribing later
        """

    def unsubscribe(subscription_id: str) -> None:
        """Unsubscribe from job updates using subscription ID (not job_id).

        Args:
            subscription_id: Subscription ID returned from subscribe_job_updates()
        """

    # Plugin Access (lazy-loaded properties)
    @property
    def clip_embedding() -> ClipEmbeddingClient
    @property
    def dino_embedding() -> DinoEmbeddingClient
    # ... (7 more plugin properties)
```

**Implementation Details:**
- Use `httpx.AsyncClient` for async HTTP requests
- All defaults from `ComputeClientConfig` (NO hardcoded values)
- Auth: No-auth mode only in Phase 1 (no auth headers)
- MQTT callback registration via internal `MQTTJobMonitor` instance
- Optional polling with exponential backoff (secondary workflow)
- Timeout handling for all async operations

### 2. MQTT Monitor (`mqtt_monitor.py`)

**Purpose**: Primary job monitoring mechanism via MQTT callback registration. Provides real-time job status updates and worker capability tracking.

**Key Features:**
```python
class MQTTJobMonitor:
    def __init__(
        broker: str | None = None,  # Uses ComputeClientConfig.MQTT_BROKER_HOST if None
        port: int | None = None,  # Uses ComputeClientConfig.MQTT_BROKER_PORT if None
    ):
        """Initialize MQTT monitor.

        Args:
            broker: MQTT broker host (default from config)
            port: MQTT broker port (default from config)
        """

    # Job Status Tracking (PRIMARY WORKFLOW)
    def subscribe_job_updates(
        job_id: str,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None
    ) -> str:
        """Subscribe to job status updates via MQTT.

        Returns unique subscription ID. Supports multiple subscriptions per job.
        Job status messages published by JobRepository from cl_server_shared library.

        Args:
            job_id: Job ID to monitor
            on_progress: Called on each job update (queued → in_progress → ...)
            on_complete: Called only when job completes (status: completed/failed)

        Returns:
            Unique subscription ID for unsubscribing later

        Example:
            sub_id = monitor.subscribe_job_updates(
                job_id="abc-123",
                on_progress=lambda job: print(f"Progress: {job.progress}%"),
                on_complete=lambda job: print(f"Done: {job.status}")
            )
            # Later...
            monitor.unsubscribe(sub_id)
        """

    def unsubscribe(subscription_id: str) -> None:
        """Unsubscribe from job updates using subscription ID.

        Args:
            subscription_id: Subscription ID returned from subscribe_job_updates()
        """

    # Worker Capability Monitoring
    def get_worker_capabilities() -> dict[str, WorkerCapability]:
        """Get current worker capabilities (synchronous, from cached state)."""

    def subscribe_worker_updates(
        callback: Callable[[str, WorkerCapability | None], None]
    ) -> None:
        """Subscribe to worker capability changes.

        Callback invoked when worker connects/disconnects or capabilities change.

        Args:
            callback: Function called with (worker_id, capability).
                     capability=None indicates worker disconnect.
        """

    async def wait_for_capability(
        task_type: str,
        timeout: float | None = None  # Uses config default
    ) -> bool:
        """Wait for worker with specific capability to be available.

        Args:
            task_type: Required capability (e.g., "clip_embedding")
            timeout: Max wait time in seconds

        Returns:
            True if worker available, False if timeout

        Raises:
            WorkerUnavailableError: If timeout expires
        """
```

**MQTT Topics:**
- **Job Status**: `{MQTT_JOB_STATUS_TOPIC_PREFIX}/{job_id}` (from cl_server_shared JobRepository)
- **Worker Capabilities**: `{MQTT_CAPABILITY_TOPIC_PREFIX}/{worker_id}` (from CapabilityBroadcaster)

**Message Formats:**

1. **Job Status Message** (published by JobRepository):
```json
{
  "job_id": "uuid",
  "task_type": "clip_embedding",
  "status": "completed",
  "progress": 100,
  "params": {},
  "task_output": {"embedding": [...]},
  "error_message": null,
  "priority": 5,
  "created_at": 1234567890000,
  "updated_at": 1234567891000,
  "started_at": 1234567890500,
  "completed_at": 1234567891000
}
```

2. **Worker Capability Message** (from CapabilityBroadcaster):
```json
{
  "id": "worker-uuid",
  "capabilities": ["clip_embedding", "dino_embedding"],
  "idle_count": 1,
  "timestamp": 1234567890000
}
```

**Implementation Details:**
- Subscribe to `{prefix}/+` wildcard for all workers
- Handle empty payloads (Last Will & Testament = worker disconnect)
- Track worker states in-memory dict
- Parse JobResponse from job status messages
- Callback-based (non-blocking, async-compatible)
- All configuration from `ComputeClientConfig`

### 3. Plugin SDK (`plugins/*.py`)

**Base Pattern:**
```python
class BasePluginClient:
    def __init__(self, client: ComputeClient, task_type: str):
        """Initialize plugin client.

        Args:
            client: ComputeClient instance
            task_type: Plugin task type (used to lookup endpoint from config)
        """
        self.client = client
        self.task_type: str = task_type
        # Get endpoint from config (NOT hardcoded)
        self.endpoint: str = ComputeClientConfig.get_plugin_endpoint(task_type)

    async def submit_job(
        self,
        params: dict[str, JSONValue],
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None
    ) -> JobResponse:
        """Submit job without files (STUB for future file-less plugins).

        Currently raises NotImplementedError as all existing plugins require files.
        This method exists for future plugins that don't need file uploads.

        Args:
            params: Task parameters
            priority: Job priority (0-10)
            wait: If True, use HTTP polling (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates
            on_complete: Callback for job completion/failure

        Returns:
            JobResponse with job details

        Raises:
            NotImplementedError: All current plugins require file uploads
        """
        raise NotImplementedError(
            f"Plugin '{self.task_type}' requires file uploads. "
            "Use submit_with_files() instead."
        )

    async def submit_with_files(
        self,
        files: dict[str, Path],
        params: dict[str, JSONValue] | None = None,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None
    ) -> JobResponse:
        """Submit job with file uploads (PRIMARY METHOD).

        Args:
            files: Dict mapping field names to file paths
            params: Additional task parameters
            priority: Job priority (0-10)
            wait: If True, use HTTP polling (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates
            on_complete: Callback for job completion/failure

        Returns:
            JobResponse with job details (initially status=queued)

        Implementation:
            - POST multipart/form-data to plugin endpoint
            - If callbacks provided, register MQTT subscription (primary workflow)
            - If wait=True, poll via HTTP until completion (secondary workflow)
            - Returns JobResponse after submission (or completion if wait=True)
        """
```

**Per-Plugin Implementation (9 Total):**

Each plugin client is **completely independent and modular**:
- **No cross-talk**: Each plugin's logic, schema, and implementation are self-contained
- **Easy removal**: Plugins can be added/removed without affecting others
- **Separate files**: Each plugin in its own `plugins/<name>.py` file
- **Config-driven endpoints**: Gets endpoint from `ComputeClientConfig.PLUGIN_ENDPOINTS` (NO hardcoding)
- **Typed schemas**: Defines typed request parameters and documents task_output structure
- **File requirements**: Implements file upload requirements specific to plugin

**Example: ClipEmbeddingClient** (`plugins/clip_embedding.py`)
```python
"""CLIP embedding plugin - completely independent module."""

from pathlib import Path
from collections.abc import Callable

from ..compute_client import ComputeClient
from ..models import JobResponse, JSONValue
from .base import BasePluginClient


class ClipEmbeddingClient(BasePluginClient):
    """Client for CLIP image embedding tasks.

    Task Output Schema:
        {
            "embedding": list[float]  # 512-dimensional vector
        }
    """

    def __init__(self, client: ComputeClient):
        # Endpoint looked up from config (NOT hardcoded)
        super().__init__(client, task_type="clip_embedding")

    async def embed_image(
        self,
        image: Path,
        wait: bool = False,  # MQTT is primary (callback-based)
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None
    ) -> JobResponse:
        """Submit CLIP embedding job for an image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling (secondary workflow)
            timeout: Timeout for wait
            on_progress: Callback for job progress updates
            on_complete: Callback for job completion/failure

        Returns:
            JobResponse with embedding in task_output["embedding"] (512-dim list)

        Example:
            # MQTT callback (primary)
            job = await client.clip_embedding.embed_image(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Embedding: {j.task_output['embedding']}")
            )

            # HTTP polling (secondary)
            job = await client.clip_embedding.embed_image(
                image=Path("photo.jpg"),
                wait=True
            )
            print(job.task_output["embedding"])
        """
        return await self.submit_with_files(
            files={"image": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete
        )
```

**Plugin Modularity Benefits:**
- Each plugin can be independently tested, updated, or removed
- No shared state or dependencies between plugins
- Easy to add new plugins by creating new file in `plugins/` directory
- Clear separation of concerns (one plugin = one file = one responsibility)

**Key Implementation Requirements:**
- Endpoints from `ComputeClientConfig`, NOT hardcoded
- Two-callback system (on_progress, on_complete) - both optional
- Support both MQTT callback (primary) and polling (secondary via `wait=True`)
- Strict typing (no `Any` types) - use JSONValue, JSONObject
- Default `wait=False` (MQTT is primary workflow)

### 4. Authentication (`auth.py`)

**Modular Design Pattern (FastAPI Depends-style)**

Auth is designed to be **modular, detachable, and swappable** following FastAPI's dependency injection pattern.

```python
"""Modular authentication system.

Auth providers follow a simple protocol: they must implement get_headers().
This allows easy swapping between no-auth, JWT, API key, etc.
"""

from abc import ABC, abstractmethod


class AuthProvider(ABC):
    """Abstract base class for auth providers (protocol-based)."""

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """Get authentication headers for HTTP requests.

        Returns:
            Dictionary of headers to add to requests
        """
        pass


class NoAuthProvider(AuthProvider):
    """No authentication (Phase 1).

    Returns empty headers for all requests.
    """

    def get_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Returns:
            Empty dict (no authentication)
        """
        return {}


class JWTAuthProvider(AuthProvider):
    """JWT token authentication (Phase 2 - FUTURE).

    Will integrate with auth server for token management.
    """

    def __init__(self, token: str):
        """Initialize with JWT token.

        Args:
            token: JWT token from auth server
        """
        self.token = token

    def get_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Returns:
            Authorization header with Bearer token
        """
        return {"Authorization": f"Bearer {self.token}"}


# Default auth provider for Phase 1
def get_default_auth() -> AuthProvider:
    """Get default auth provider (no-auth for Phase 1).

    Returns:
        NoAuthProvider instance
    """
    return NoAuthProvider()
```

**Usage in ComputeClient:**
```python
class ComputeClient:
    def __init__(
        self,
        base_url: str | None = None,
        auth_provider: AuthProvider | None = None,  # Injectable!
        # ... other params
    ):
        """Initialize compute client.

        Args:
            base_url: Server base URL
            auth_provider: Auth provider (default: NoAuthProvider)
        """
        self.auth = auth_provider or get_default_auth()

    async def _make_request(self, method: str, url: str, **kwargs):
        """Make HTTP request with auth headers."""
        headers = kwargs.get("headers", {})
        headers.update(self.auth.get_headers())  # Inject auth headers
        kwargs["headers"] = headers
        return await self._session.request(method, url, **kwargs)
```

**Benefits:**
- **Swappable**: Easy to switch auth providers (NoAuth → JWT → API Key)
- **Testable**: Can inject mock auth providers for testing
- **Extensible**: Add new auth methods by implementing AuthProvider
- **Clean separation**: Auth logic separate from client logic
- **Future-proof**: Phase 2 JWT integration requires minimal changes

**Phase 1**: Use `NoAuthProvider` (default)
**Phase 2**: Add `JWTAuthProvider` with auth server integration

### 5. Models (`models.py`)

**Purpose**: Mirror server schemas with strict typing (basedpyright compatible, NO `Any` types)

```python
from pydantic import BaseModel, Field

# JSON type hierarchy (from server schemas.py)
type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
type JSONObject = dict[str, JSONValue]


class JobResponse(BaseModel):
    """Response schema for job information (mirrors server schema)."""

    job_id: str = Field(..., description="Unique job identifier")
    task_type: str = Field(..., description="Type of task to execute")
    status: str = Field(..., description="Job status (queued, in_progress, completed, failed)")
    progress: int = Field(0, description="Progress percentage (0-100)")
    params: JSONObject = Field(default_factory=dict, description="Task parameters")
    task_output: JSONObject | None = Field(None, description="Task output/results")
    error_message: str | None = Field(None, description="Error message if job failed")

    priority: int = Field(5, description="Job priority (0-10)")
    created_at: int = Field(..., description="Job creation timestamp (milliseconds)")
    updated_at: int | None = Field(None, description="Job last update timestamp (milliseconds)")
    started_at: int | None = Field(None, description="Job start timestamp (milliseconds)")
    completed_at: int | None = Field(None, description="Job completion timestamp (milliseconds)")


class CapabilityStats(BaseModel):
    """Aggregated capability statistics."""

    root: dict[str, int]  # Capability name -> idle count


class WorkerCapabilitiesResponse(BaseModel):
    """Response schema for worker capabilities endpoint (mirrors server schema)."""

    num_workers: int = Field(..., description="Total number of connected workers")
    capabilities: dict[str, int] = Field(..., description="Available capability counts")


class WorkerCapability(BaseModel):
    """Individual worker capability information (from MQTT messages)."""

    worker_id: str = Field(..., description="Worker unique ID")
    capabilities: list[str] = Field(..., description="List of task types worker supports")
    idle_count: int = Field(..., description="1 if idle, 0 if busy")
    timestamp: int = Field(..., description="Message timestamp (milliseconds)")
```

**Key Points:**
- Exact mirror of server schemas (from `src/compute/schemas.py`)
- Strict typing: Use `JSONObject` type alias (NO `dict[str, Any]`)
- All fields have descriptions (from server)
- basedpyright compatible (no `Any` types)

### 6. Exceptions (`exceptions.py`)

```python
class ComputeClientError(Exception):
    """Base exception"""

class JobNotFoundError(ComputeClientError):
    """Job not found (404)"""

class JobFailedError(ComputeClientError):
    """Job failed during execution"""
    def __init__(self, job: JobResponse)

class AuthenticationError(ComputeClientError):
    """Authentication failed (401)"""

class PermissionError(ComputeClientError):
    """Insufficient permissions (403)"""

class WorkerUnavailableError(ComputeClientError):
    """No workers available for task type"""
```

## Test Suite Implementation

### Test Fixtures (`conftest.py`)

**Key Fixtures:**
```python
@pytest.fixture(scope="session")
def test_media_dir() -> Path:
    """Locate test media directory.

    Checks:
    1. Environment variable: pysdk_TEST_MEDIA
    2. Default: ../pysdk_test_media/

    Raises:
        FileNotFoundError: If media directory not found with helpful message
    """

@pytest.fixture
def test_image_hd(test_media_dir: Path) -> Path:
    """Provide HD test image.

    Raises:
        FileNotFoundError: "Missing media: images/test_image_1920x1080.jpg
                           Please see tests/media/MEDIA_SETUP.md"
    """

@pytest.fixture
def client() -> ComputeClient:
    """Create compute client (no-auth mode in Phase 1).

    Uses env vars (optional overrides):
    - COMPUTE_SERVER_URL (default from ComputeClientConfig.DEFAULT_BASE_URL)
    - MQTT_BROKER_HOST (default from ComputeClientConfig.MQTT_BROKER_HOST)
    """

@pytest.fixture
async def validate_workers(client: ComputeClient):
    """Validate that required workers are available.

    Usage in tests:
        await validate_workers(client, ["clip_embedding", "dino_embedding"])

    Raises:
        WorkerUnavailableError: If required capability workers don't exist
    """
```

### Plugin Test Pattern (`test_plugins/test_clip_embedding.py`)

```python
class TestClipEmbedding:
    """End-to-end tests for CLIP embedding plugin."""

    @pytest.mark.asyncio
    async def test_embed_image_mqtt_callback(
        self,
        client: ComputeClient,
        test_image_hd: Path,
        validate_workers
    ):
        """Test CLIP embedding with MQTT two-callback system (primary workflow)."""
        # Validate worker availability FIRST
        await validate_workers(client, ["clip_embedding"])

        # Track job progress and completion via callbacks
        progress_updates: list[int] = []
        completed_job: JobResponse | None = None
        event = asyncio.Event()

        def on_progress(job: JobResponse):
            """Called on each job update."""
            progress_updates.append(job.progress)
            print(f"Progress: {job.progress}% - Status: {job.status}")

        def on_complete(job: JobResponse):
            """Called only when job completes or fails."""
            nonlocal completed_job
            completed_job = job
            event.set()
            print(f"Job completed with status: {job.status}")

        # Submit job with both callbacks
        job = await client.clip_embedding.embed_image(
            image=test_image_hd,
            on_progress=on_progress,
            on_complete=on_complete
        )

        # Wait for completion callback (with timeout)
        await asyncio.wait_for(event.wait(), timeout=30.0)

        # Verify completion
        assert completed_job is not None
        assert completed_job.status == "completed"
        assert completed_job.task_output is not None

        # Verify progress updates were received
        assert len(progress_updates) > 0, "Should receive progress updates"
        assert 100 in progress_updates, "Should receive 100% progress"

        # Validate embedding
        assert "embedding" in completed_job.task_output
        embedding = completed_job.task_output["embedding"]
        assert isinstance(embedding, list)
        assert len(embedding) == 512  # CLIP dimension
        assert all(isinstance(x, (int, float)) for x in embedding)

        # Cleanup
        await client.delete_job(job.job_id)

    @pytest.mark.asyncio
    async def test_embed_image_polling(
        self,
        client: ComputeClient,
        test_image_hd: Path,
        validate_workers
    ):
        """Test CLIP embedding with HTTP polling (secondary workflow)."""
        await validate_workers(client, ["clip_embedding"])

        # Use polling (wait=True)
        job = await client.clip_embedding.embed_image(
            image=test_image_hd,
            wait=True,  # Enable HTTP polling
            timeout=30.0
        )

        # Verify completion
        assert job.status == "completed"
        assert "embedding" in job.task_output
        assert len(job.task_output["embedding"]) == 512

        # Cleanup
        await client.delete_job(job.job_id)

    @pytest.mark.asyncio
    async def test_embed_image_formats(
        self,
        client: ComputeClient,
        test_media_dir: Path,
        validate_workers
    ):
        """Test CLIP embedding with JPG and PNG."""
        await validate_workers(client, ["clip_embedding"])

        for image_name in ["test_image_1920x1080.jpg", "test_image_800x600.png"]:
            image_path = test_media_dir / "images" / image_name
            job = await client.clip_embedding.embed_image(
                image=image_path,
                wait=True
            )
            assert job.status == "completed"
            await client.delete_job(job.job_id)
```

**All 9 Plugin Tests:**
1. `test_clip_embedding.py` - CLIP embeddings (512-dim vectors)
2. `test_dino_embedding.py` - DINO embeddings (384-dim vectors)
3. `test_exif.py` - EXIF metadata extraction
4. `test_face_detection.py` - Face bounding boxes
5. `test_face_embedding.py` - Face embeddings (128-dim vectors)
6. `test_hash.py` - Perceptual hashes (phash, dhash)
7. `test_hls_streaming.py` - HLS manifest generation
8. `test_image_conversion.py` - Format conversion (JPG ↔ PNG ↔ WebP)
9. `test_media_thumbnail.py` - Thumbnail generation

### Workflow Tests (`test_workflows/test_image_processing_workflow.py`)

```python
class TestImageProcessingWorkflow:
    """End-to-end multi-plugin workflows using parallel MQTT pattern."""

    @pytest.mark.asyncio
    async def test_complete_image_analysis(
        self,
        client: ComputeClient,
        test_image_exif_rich: Path,
        validate_workers
    ):
        """Test complete image analysis pipeline with parallel MQTT callbacks.

        Parallel MQTT Pattern:
        1. Register ALL MQTT callbacks upfront
        2. Submit ALL tasks with callbacks (non-blocking)
        3. Wait for ALL callbacks to complete
        4. Main thread exits after all complete

        Tasks:
        - Extract EXIF metadata
        - Generate thumbnail
        - Compute CLIP embedding
        - Compute perceptual hash
        """
        # Validate all required workers available
        await validate_workers(client, ["exif", "media_thumbnail", "clip_embedding", "hash"])

        # Track completion for all jobs
        completed_jobs: dict[str, JobResponse] = {}
        completion_events: dict[str, asyncio.Event] = {
            "exif": asyncio.Event(),
            "thumbnail": asyncio.Event(),
            "clip": asyncio.Event(),
            "hash": asyncio.Event(),
        }

        # Define callbacks for each task
        def make_on_complete(task_name: str):
            def on_complete(job: JobResponse):
                if job.status in ["completed", "failed"]:
                    completed_jobs[task_name] = job
                    completion_events[task_name].set()
            return on_complete

        # STEP 1: Register ALL MQTT callbacks and submit ALL tasks (non-blocking)
        print("Submitting all tasks with MQTT callbacks...")

        exif_job = await client.exif.extract(
            image=test_image_exif_rich,
            on_complete=make_on_complete("exif")
        )

        thumb_job = await client.media_thumbnail.generate(
            media=test_image_exif_rich,
            width=256,
            height=256,
            on_complete=make_on_complete("thumbnail")
        )

        clip_job = await client.clip_embedding.embed_image(
            image=test_image_exif_rich,
            on_complete=make_on_complete("clip")
        )

        hash_job = await client.hash.compute(
            image=test_image_exif_rich,
            on_complete=make_on_complete("hash")
        )

        print("All tasks submitted! Waiting for callbacks...")

        # STEP 2: Wait for ALL callbacks to complete (with timeout)
        await asyncio.wait_for(
            asyncio.gather(
                completion_events["exif"].wait(),
                completion_events["thumbnail"].wait(),
                completion_events["clip"].wait(),
                completion_events["hash"].wait(),
            ),
            timeout=60.0  # Generous timeout for all tasks
        )

        print("All callbacks received!")

        # STEP 3: Verify all tasks completed successfully
        assert all(job.status == "completed" for job in completed_jobs.values()), \
            f"Some jobs failed: {[(k, v.status) for k, v in completed_jobs.items() if v.status != 'completed']}"

        # Verify all expected outputs exist
        assert "metadata" in completed_jobs["exif"].task_output
        assert "thumbnail_path" in completed_jobs["thumbnail"].task_output
        assert "embedding" in completed_jobs["clip"].task_output
        assert len(completed_jobs["clip"].task_output["embedding"]) == 512
        assert "phash" in completed_jobs["hash"].task_output

        # Cleanup all jobs
        all_jobs = [exif_job, thumb_job, clip_job, hash_job]
        for job in all_jobs:
            await client.delete_job(job.job_id)

        # STEP 4: Main thread exits after all callbacks complete
        print("Workflow complete, all jobs cleaned up")
```

### Test Media Setup (`tests/MEDIA_SETUP.md`)

```markdown
# Test Media Setup Guide

## Overview
Tests require pre-provided media files in `pysdk_test_media/` directory.
This directory is **NOT in git** and must be set up separately.

## Quick Setup

1. Create media directory:
   ```bash
   mkdir -p pysdk_test_media/images
   mkdir -p pysdk_test_media/videos
   ```

2. Set environment variable (optional):
   ```bash
   export pysdk_TEST_MEDIA=/path/to/pysdk_test_media
   ```
   Default: `../pysdk_test_media/` relative to test directory

3. Provide test media files (see requirements below)

## Required Media Files

### Images (5 files required)

#### 1. `images/test_image_1920x1080.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080
- **Purpose**: Standard HD image testing
- **Source**: Any HD photo (Unsplash, Pexels, or personal)

#### 2. `images/test_image_800x600.png`
- **Format**: PNG
- **Resolution**: 800x600
- **Purpose**: Smaller image, PNG format testing
- **Source**: Any medium-size photo converted to PNG

#### 3. `images/test_face_single.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080+
- **Purpose**: Face detection with 1 clear face
- **Requirements**:
  - 1 human face, front-facing
  - Good lighting
  - Face size >200px
- **Source**: Portrait photo (stock or personal)

#### 4. `images/test_face_multiple.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080+
- **Purpose**: Face detection with multiple faces
- **Requirements**:
  - 3-5 human faces
  - Various angles acceptable
- **Source**: Group photo (stock or personal)

#### 5. `images/test_exif_rich.jpg`
- **Format**: JPEG with EXIF
- **Resolution**: Any
- **Purpose**: EXIF metadata extraction
- **Requirements**:
  - Must have EXIF data (camera model, date, GPS if possible)
  - NOT a screenshot or edited image
- **Source**: Direct camera photo with EXIF preserved

### Videos (2 files required)

#### 1. `videos/test_video_1080p_10s.mp4`
- **Format**: MP4 (H.264)
- **Resolution**: 1920x1080
- **Duration**: 10 seconds
- **Purpose**: HLS streaming, thumbnail generation
- **Source**: Any 1080p video (stock or screen recording)

#### 2. `videos/test_video_720p_5s.mp4`
- **Format**: MP4 (H.264)
- **Resolution**: 1280x720
- **Duration**: 5 seconds
- **Purpose**: Video processing tests
- **Source**: Any 720p video

## Recommended Sources

### Free Stock Media (CC0/Public Domain)
- **Pexels**: https://www.pexels.com/
- **Unsplash**: https://unsplash.com/
- **Pixabay**: https://pixabay.com/

### Generating Test Media
You can generate synthetic media using:
- **Images**: PIL/Pillow (gradients, patterns)
- **Videos**: ffmpeg (test patterns, color bars)

Example - Generate test pattern image:
```python
from PIL import Image, ImageDraw
img = Image.new('RGB', (1920, 1080), color=(73, 109, 137))
draw = ImageDraw.Draw(img)
# Add patterns...
img.save('test_image_1920x1080.jpg')
```

## Validation

Run this to check media setup:
```bash
pytest tests/test_client/test_media_validation.py -v
```

This test checks:
- All required files exist
- Correct formats and resolutions
- Files are readable
```

## Implementation Roadmap

### Phase 1: Core SDK (Week 1)

**Day 1: Project Setup & Configuration**
- [ ] Create `pysdk/` package structure
- [ ] Set up `pyproject.toml` (mirror compute service structure)
  - [ ] Configure pytest, coverage, ruff (same as server)
  - [ ] Add CLI dependencies (click, rich)
  - [ ] Add CLI entry point in [project.scripts]
  - [ ] Match server's naming, order, and structure
- [ ] Create `pyrightconfig.json` (separate file, NOT in pyproject.toml)
  - [ ] Mirror server's pyrightconfig.json structure
  - [ ] Strict type checking mode
  - [ ] reportAny = "error" (NO Any types allowed)
- [ ] Implement `config.py` with `ComputeClientConfig` class
  - [ ] All endpoints, hosts, ports as class variables
  - [ ] NO hardcoded values elsewhere
  - [ ] Type-safe (basedpyright compatible)
- [ ] Create documentation skeletons:
  - [ ] README.md (user docs)
  - [ ] INTERNALS.md (developer docs)
  - [ ] tests/README.md (testing docs)
  - [ ] tests/media/MEDIA_SETUP.md (media setup)
- [ ] Run `uv run basedpyright` to verify strict mode setup

**Day 2: Models & Exceptions**
- [ ] Define models in `models.py` (mirror server schemas)
  - [ ] Use JSONObject type alias (NO Any types)
  - [ ] JobResponse, WorkerCapabilitiesResponse, WorkerCapability
  - [ ] All fields with type hints and descriptions
- [ ] Implement custom exceptions in `exceptions.py`
  - [ ] ComputeClientError, JobNotFoundError, JobFailedError
  - [ ] AuthenticationError, PermissionError
  - [ ] **WorkerUnavailableError** (for capability validation)
- [ ] Implement modular auth in `auth.py` (FastAPI Depends-style)
  - [ ] AuthProvider abstract base class
  - [ ] NoAuthProvider (Phase 1 default)
  - [ ] JWTAuthProvider stub (Phase 2 future)
  - [ ] Injectable auth providers for testability
- [ ] Write unit tests for models, exceptions, auth
- [ ] Run `uv run basedpyright` to verify (zero errors)

**Day 3: MQTT Monitor (Primary Workflow)**
- [ ] Implement `MQTTJobMonitor` using paho-mqtt
  - [ ] Job status subscription with unique subscription IDs (supports multiple callbacks per job)
  - [ ] Two-callback system: on_progress and on_complete
  - [ ] subscribe_job_updates() returns subscription ID
  - [ ] unsubscribe(subscription_id) uses ID, not job_id
  - [ ] Worker capability subscription and parsing
  - [ ] In-memory worker state tracking
  - [ ] `wait_for_capability()` method (for test validation)
- [ ] All configuration from `ComputeClientConfig` (NO hardcoding)
- [ ] Write integration tests for MQTT (test both callbacks)
- [ ] Run `uv run basedpyright` to verify

**Day 4: Core Client**
- [ ] Implement `ComputeClient` class
  - [ ] REST API methods (get_job, delete_job, get_capabilities)
  - [ ] MQTT callback registration with two-callback system (on_progress, on_complete)
  - [ ] subscribe_job_updates() returns subscription ID
  - [ ] unsubscribe(subscription_id) method
  - [ ] Optional HTTP polling (wait_for_job, secondary workflow)
  - [ ] Worker validation (wait_for_workers)
  - [ ] Injectable auth_provider (modular auth)
- [ ] All defaults from `ComputeClientConfig`
- [ ] Internal MQTT monitor instance
- [ ] Write unit tests for client core
- [ ] Run `uv run basedpyright` to verify

**Day 5: Plugin System & CLI**
- [ ] Implement `BasePluginClient`
  - [ ] Endpoint lookup from config (NO hardcoding)
  - [ ] submit_job() as stub (NotImplementedError) for future file-less plugins
  - [ ] submit_with_files() fully implemented (primary method)
  - [ ] Two-callback system (on_progress, on_complete)
  - [ ] Support MQTT callback (primary) and polling (secondary via wait=True)
  - [ ] File upload mechanism (multipart/form-data)
- [ ] Create all 9 plugin client classes (separate files, modular)
  - [ ] Each gets endpoint from `ComputeClientConfig.PLUGIN_ENDPOINTS`
  - [ ] Typed parameters (no Any)
  - [ ] Document expected task_output structure
  - [ ] Complete independence (no cross-talk)
- [ ] Add lazy-loading plugin properties to `ComputeClient`
- [ ] Implement CLI tool (`cli.py`)
  - [ ] Use click for command framework
  - [ ] Use rich for terminal output
  - [ ] Subcommands for each plugin
  - [ ] Real-time progress via MQTT callbacks
  - [ ] File download placeholder (notes when endpoint doesn't exist)
- [ ] Write unit tests for plugin clients and CLI
- [ ] Run `uv run basedpyright` and `uv run pytest` to verify

### Phase 2: Test Suite (Week 2)

**Day 1: Test Infrastructure**
- [ ] Create test directory structure
- [ ] Implement `conftest.py` with all fixtures
  - [ ] `test_media_dir()` - locates media with helpful errors
  - [ ] Media file fixtures (test_image_hd, test_video_1080p, etc.)
  - [ ] `client()` - creates ComputeClient (no-auth mode)
  - [ ] **`validate_workers()` - FAILS if required capability missing**
  - [ ] Environment variable handling (pysdk_TEST_MEDIA)
- [ ] Write `tests/media/MEDIA_SETUP.md` documentation
- [ ] Create media validation tests
- [ ] Run `uv run basedpyright` and `uv run pytest` to verify

**Day 2-3: Plugin Tests (1-6) - MQTT Primary**
- [ ] `test_clip_embedding.py`
  - [ ] Test with MQTT callback (primary workflow)
  - [ ] Test with HTTP polling (optional, secondary)
  - [ ] Worker capability validation before tests
- [ ] `test_dino_embedding.py`
- [ ] `test_exif.py`
- [ ] `test_face_detection.py`
- [ ] `test_face_embedding.py`
- [ ] `test_hash.py`
- [ ] All tests clean up jobs after completion
- [ ] Run `uv run pytest` to verify

**Day 4: Plugin Tests (7-9)**
- [ ] `test_hls_streaming.py`
- [ ] `test_image_conversion.py`
- [ ] `test_media_thumbnail.py`
- [ ] All tests validate worker availability
- [ ] Run `uv run pytest` to verify

**Day 5: Workflow Tests (Parallel MQTT Pattern)**
- [ ] `test_image_processing_workflow.py`
  - [ ] Register ALL MQTT callbacks upfront
  - [ ] Submit ALL tasks with callbacks (non-blocking)
  - [ ] Wait for ALL callbacks to complete
  - [ ] Main thread exits after all complete
  - [ ] Worker capability validation before submission
  - [ ] Cleanup verification (all jobs deleted)
- [ ] `test_video_processing_workflow.py`
- [ ] Run full test suite
- [ ] Verify ≥90% coverage

### Phase 3: Documentation & Polish (Week 3)

**Day 1-2: Documentation (PROJECT_STRUCTURE.md Standard)**
- [ ] Complete `README.md` (user-facing)
  - [ ] Quick start (installation, basic usage)
  - [ ] Environment variables
  - [ ] Client API reference with examples
  - [ ] MQTT callback vs polling workflows
  - [ ] Troubleshooting
  - [ ] Link to INTERNALS.md for developers
- [ ] Complete `INTERNALS.md` (developer-facing)
  - [ ] Package structure explanation
  - [ ] Development setup
  - [ ] Testing instructions (link to tests/README.md)
  - [ ] Code quality tools (basedpyright, ruff)
  - [ ] Architecture notes (config-first, MQTT-first)
  - [ ] Contributing guidelines
- [ ] Complete `tests/README.md` (testing-specific)
  - [ ] Prerequisites (Python 3.12+, uv)
  - [ ] How to run tests (`uv run pytest`)
  - [ ] Worker capability requirements
  - [ ] Coverage requirements (≥90%)
  - [ ] Test file organization
  - [ ] Example commands
- [ ] Complete `tests/media/MEDIA_SETUP.md` (already written)
- [ ] API reference docstrings (all public methods)

**Day 3-4: Test Media & Validation**
- [ ] Acquire/create test media per tests/media/MEDIA_SETUP.md
- [ ] Validate all media files
- [ ] Run full test suite with worker validation
- [ ] Fix any integration issues
- [ ] Verify tests fail correctly when:
  - [ ] Media missing
  - [ ] Workers unavailable

**Day 5: Final Polish & Quality Checks**
- [ ] Code review and cleanup
- [ ] Verify type hints on all public APIs
- [ ] Run quality checks:
  - [ ] `uv run basedpyright` → ZERO errors
  - [ ] `uv run ruff check src/` → PASS
  - [ ] `uv run ruff format src/` → Format code
  - [ ] `uv run pytest` → ≥90% coverage, all tests pass
- [ ] Verify package structure matches PROJECT_STRUCTURE.md
- [ ] Final documentation review
- [ ] Ready for Phase 2 (JWT auth integration)

## CLI Tool Implementation

### Overview

The `pysdk` CLI tool provides a command-line interface to the compute service, built on top of the Python SDK. It enables users to submit jobs, download results, and monitor progress from the terminal.

### CLI Architecture (`cli.py`)

```python
"""Command-line interface for pysdk.

Usage:
    pysdk <plugin> <subcommand> [options]

Examples:
    pysdk clip_embedding embed photo.jpg
    pysdk image_conversion convert input.png output.jpg --format jpeg
    pysdk media_thumbnail generate video.mp4 thumb.jpg --width 256 --height 256
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .compute_client import ComputeClient
from .models import JobResponse

console = Console()


@click.group()
@click.option("--base-url", envvar="COMPUTE_SERVER_URL", help="Compute server URL")
@click.option("--mqtt-broker", envvar="MQTT_BROKER_HOST", help="MQTT broker host")
@click.pass_context
def cli(ctx: click.Context, base_url: str | None, mqtt_broker: str | None):
    """CL Client - Command-line interface for compute service."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["mqtt_broker"] = mqtt_broker


@cli.group()
def clip_embedding():
    """CLIP image embedding tasks."""
    pass


@clip_embedding.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--wait/--no-wait", default=True, help="Wait for job completion")
@click.pass_context
def embed(ctx: click.Context, image: Path, wait: bool):
    """Generate CLIP embedding for an image."""
    asyncio.run(_embed_image(ctx, image, wait))


async def _embed_image(ctx: click.Context, image: Path, wait: bool):
    """Async implementation of embed command."""
    client = ComputeClient(
        base_url=ctx.obj.get("base_url"),
        mqtt_broker=ctx.obj.get("mqtt_broker")
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Submitting job...", total=None)

        # Track progress via callback
        def on_progress(job: JobResponse):
            progress.update(task, description=f"Processing: {job.progress}%")

        def on_complete(job: JobResponse):
            if job.status == "completed":
                progress.update(task, description="✓ Completed", completed=True)
            else:
                progress.update(task, description=f"✗ Failed: {job.error_message}", completed=True)

        # Submit job
        job = await client.clip_embedding.embed_image(
            image=image,
            on_progress=on_progress if wait else None,
            on_complete=on_complete if wait else None
        )

        if wait:
            # Wait for completion
            await asyncio.sleep(0)  # Allow callbacks to process
            while job.status not in ["completed", "failed"]:
                await asyncio.sleep(0.5)
                job = await client.get_job(job.job_id)

            # Display results
            if job.status == "completed":
                console.print(f"[green]✓ Job completed: {job.job_id}")
                console.print(f"Embedding dimensions: {len(job.task_output['embedding'])}")
                # Note: File download not yet implemented on server
                console.print("[yellow]Note: File download endpoint not yet available")
            else:
                console.print(f"[red]✗ Job failed: {job.error_message}", file=sys.stderr)
                sys.exit(1)
        else:
            console.print(f"Job submitted: {job.job_id}")
            console.print("Use --wait to monitor progress")


@cli.group()
def image_conversion():
    """Image format conversion tasks."""
    pass


@image_conversion.command()
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.argument("output", type=click.Path(path_type=Path))
@click.option("--format", type=click.Choice(["jpeg", "png", "webp"]), required=True)
@click.option("--quality", type=int, default=85, help="Output quality (1-100)")
@click.option("--wait/--no-wait", default=True, help="Wait for job completion")
@click.pass_context
def convert(ctx: click.Context, input: Path, output: Path, format: str, quality: int, wait: bool):
    """Convert image to different format."""
    asyncio.run(_convert_image(ctx, input, output, format, quality, wait))


async def _convert_image(
    ctx: click.Context,
    input: Path,
    output: Path,
    format: str,
    quality: int,
    wait: bool
):
    """Async implementation of convert command."""
    client = ComputeClient(
        base_url=ctx.obj.get("base_url"),
        mqtt_broker=ctx.obj.get("mqtt_broker")
    )

    # Submit conversion job
    job = await client.image_conversion.convert(
        image=input,
        output_format=format,
        quality=quality,
        wait=wait
    )

    if wait and job.status == "completed":
        console.print(f"[green]✓ Conversion complete: {job.job_id}")

        # TODO: Download file when server endpoint is available
        # For now, show relative path from task_output
        if "output_path" in job.task_output:
            console.print(f"Output path (on server): {job.task_output['output_path']}")
            console.print("[yellow]Note: File download endpoint not yet available")
            console.print(f"[yellow]Will download to: {output} (when implemented)")
    elif job.status == "failed":
        console.print(f"[red]✗ Conversion failed: {job.error_message}", file=sys.stderr)
        sys.exit(1)
    else:
        console.print(f"Job submitted: {job.job_id}")


# Add more plugin subcommands (media_thumbnail, exif, etc.)
# Each plugin gets its own group with relevant subcommands


def main():
    """Entry point for CLI tool."""
    cli(obj={})


if __name__ == "__main__":
    main()
```

### CLI Features

1. **Rich Output**: Uses `rich` library for progress bars, colors, and formatting
2. **Async Support**: Built on asyncio for efficient job monitoring
3. **MQTT Integration**: Real-time progress updates via MQTT callbacks
4. **Plugin Subcommands**: Each plugin has its own subcommand group
5. **Environment Variables**: Supports COMPUTE_SERVER_URL, MQTT_BROKER_HOST
6. **File Download Placeholder**: Shows where file download will be implemented when server endpoint exists

### Installation Entry Point

Add to `pyproject.toml`:
```toml
[project.scripts]
pysdk = "pysdk.cli:main"
```

### CLI Testing

Add `tests/test_client/test_cli.py`:
```python
"""CLI tool tests."""

import pytest
from click.testing import CliRunner

from pysdk.cli import cli


def test_cli_help():
    """Test CLI help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Command-line interface for compute service" in result.output


def test_clip_embedding_help():
    """Test CLIP embedding subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["clip_embedding", "--help"])
    assert result.exit_code == 0
    assert "CLIP image embedding tasks" in result.output
```

### Future Enhancements

- **File Download**: Implement when server endpoint (`GET /jobs/{job_id}/files/{path}`) is added
- **Batch Processing**: Process multiple files in parallel
- **Job Management**: List, cancel, retry jobs
- **Output Formats**: JSON, CSV output for scripting

## pyrightconfig.json Configuration

### Purpose

Separate basedpyright configuration file (not in pyproject.toml) following the server's pattern.

### Configuration File

Create `pyrightconfig.json` at package root:
```json
{
  "venvPath": ".",
  "venv": ".venv",
  "include": [
    "src",
    "tests"
  ],
  "exclude": [
    "**/__pycache__",
    "**/node_modules",
    ".venv"
  ],
  "reportMissingTypeStubs": true,
  "reportCallInDefaultInitializer": "none",
  "extraPaths": [
    "src"
  ],
  "typeCheckingMode": "strict",
  "reportAny": "error",
  "reportUnknownVariableType": "error",
  "reportUnknownMemberType": "error",
  "reportUnknownArgumentType": "error",
  "reportUnknownParameterType": "error",
  "reportMissingTypeArgument": "error",
  "pythonVersion": "3.12"
}
```

### Key Settings

- **venvPath/venv**: Points to `.venv` directory for dependency resolution
- **include**: Source and test directories
- **exclude**: Ignore __pycache__, node_modules, venv
- **strict mode**: Full type checking with no Any types allowed
- **reportAny**: Error on Any type usage (enforces strict typing)
- **pythonVersion**: Target Python 3.12

### Differences from pyproject.toml Approach

**Advantages of separate pyrightconfig.json:**
1. **IDE Integration**: Better support in VS Code, PyCharm
2. **Tooling**: Standalone basedpyright command respects it
3. **Clarity**: Clearer separation of build config vs type checking config
4. **Server Consistency**: Matches server's configuration pattern

### Running Type Checks

```bash
# Type check all code
uv run basedpyright

# Type check specific file
uv run basedpyright src/pysdk/compute_client.py

# Type check with verbose output
uv run basedpyright --verbose
```

### Development Workflow

1. Write code with type hints
2. Run `uv run basedpyright` to verify (must pass with zero errors)
3. Fix any type errors before committing
4. CI/CD should enforce zero type errors

## Key Implementation Notes

### 1. Configuration-First Design (NO Hardcoding)

**All configuration in `config.py`:**
```python
# From ComputeClientConfig class
PLUGIN_ENDPOINTS: dict[str, str] = {
    "clip_embedding": "/clip_embedding/jobs",
    "dino_embedding": "/dino_embedding/jobs",
    "exif": "/exif/jobs",
    "face_detection": "/face_detection/jobs",
    "face_embedding": "/face_embedding/jobs",
    "hash": "/hash/jobs",
    "hls_streaming": "/hls_streaming/jobs",
    "image_conversion": "/image_conversion/jobs",
    "media_thumbnail": "/media_thumbnail/jobs",
}
```

**Usage pattern:**
```python
# WRONG: Hardcoded endpoint
endpoint = "/clip_embedding/jobs"

# CORRECT: From config
endpoint = ComputeClientConfig.get_plugin_endpoint("clip_embedding")
```

### 2. File Upload Implementation

```python
async def submit_with_files(
    self,
    files: dict[str, Path],
    params: dict | None = None,
    **kwargs
) -> JobResponse:
    """Submit job with file uploads."""

    files_data = {}
    for name, path in files.items():
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        files_data[name] = (
            path.name,
            open(path, 'rb'),
            self._guess_mime_type(path)
        )

    response = await self.client._session.post(
        f"{self.client.base_url}{self.endpoint}",
        files=files_data,
        data=params or {},
        headers=self.client.auth.get_headers()
    )

    # Handle response, get job_id, poll if wait=True
```

### 3. MQTT Callback-Based Job Monitoring (PRIMARY Workflow)

```python
# Submit job and monitor via MQTT (non-blocking, callback-based)
def on_job_complete(job: JobResponse):
    if job.status == "completed":
        print(f"Job {job.job_id} completed!")
        print(f"Result: {job.task_output}")
    else:
        print(f"Job {job.job_id} failed: {job.error_message}")

# Submit job
job = await client.clip_embedding.embed_image(
    image=Path("image.jpg"),
    callback=on_job_complete
)

# Job submitted, callback will be invoked on completion
# Main thread can continue other work...
```

**Implementation:**
- Client subscribes to `inference/job_status/{job_id}` topic
- Callback invoked on each job status update
- Non-blocking, async-compatible
- Primary workflow for production use

### 4. HTTP Polling (SECONDARY Workflow, Optional)

```python
# Optional: Use HTTP polling instead of MQTT
job = await client.clip_embedding.embed_image(
    image=Path("image.jpg"),
    wait=True,  # Enable polling
    timeout=30.0
)
# Blocks until job completes
print(f"Result: {job.task_output}")
```

**Implementation with Exponential Backoff:**
```python
async def wait_for_job(
    self,
    job_id: str,
    poll_interval: float | None = None,  # From config
    timeout: float | None = None
) -> JobResponse:
    """Poll job until completion (secondary workflow)."""
    start_time = time.time()
    interval = poll_interval or ComputeClientConfig.DEFAULT_POLL_INTERVAL
    backoff = interval

    while True:
        job = await self.get_job(job_id)

        if job.status in ["completed", "failed"]:
            return job

        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError(f"Job {job_id} timeout")

        await asyncio.sleep(backoff)
        backoff = min(
            backoff * ComputeClientConfig.POLL_BACKOFF_MULTIPLIER,
            ComputeClientConfig.MAX_POLL_BACKOFF
        )
```

### 5. MQTT Message Parsing

```python
def _on_message(self, client, userdata, msg):
    """Handle incoming MQTT messages."""
    try:
        # Empty payload = worker disconnect (LWT)
        if not msg.payload:
            worker_id = msg.topic.split('/')[-1]
            self._remove_worker(worker_id)
            return

        # Parse capability message
        data = json.loads(msg.payload)
        capability = WorkerCapability(
            worker_id=data["id"],
            capabilities=data["capabilities"],
            idle_count=data["idle_count"],
            timestamp=data["timestamp"]
        )

        self._update_worker(capability)

    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON in MQTT message: {msg.payload}")
```

### 6. Worker Capability Validation in Tests

**Requirement**: Tests must fail if required capability workers don't exist

```python
@pytest.fixture
async def validate_workers(client: ComputeClient, required_capabilities: list[str]):
    """Validate that workers with required capabilities are available.

    Raises:
        WorkerUnavailableError: If required capability not available
    """
    # Wait briefly for workers to register
    await asyncio.sleep(1.0)

    # Get current capabilities
    caps_response = await client.get_capabilities()

    # Check each required capability
    missing = []
    for capability in required_capabilities:
        if capability not in caps_response.capabilities or caps_response.capabilities[capability] == 0:
            missing.append(capability)

    if missing:
        raise WorkerUnavailableError(
            f"Required capabilities not available: {missing}\n"
            f"Available capabilities: {dict(caps_response.capabilities)}\n"
            f"Please ensure workers are running with required capabilities."
        )

# Usage in tests:
@pytest.mark.asyncio
async def test_clip_embedding(client: ComputeClient, test_image_hd: Path):
    """Test CLIP embedding."""
    # Validate worker availability FIRST
    await validate_workers(client, ["clip_embedding"])

    # Now run test...
    job = await client.clip_embedding.embed_image(image=test_image_hd, wait=True)
    assert job.status == "completed"
```

### 7. Test Media Directory Discovery

```python
def get_test_media_dir() -> Path:
    """Find test media directory.

    Priority:
    1. pysdk_TEST_MEDIA env var
    2. ../pysdk_test_media/ relative to test dir

    Raises:
        FileNotFoundError: With setup instructions
    """
    # Check env var
    env_path = os.getenv("pysdk_TEST_MEDIA")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # Check default location
    default_path = Path(__file__).parent.parent.parent / "pysdk_test_media"
    if default_path.exists():
        return default_path

    # Not found - helpful error
    raise FileNotFoundError(
        "Test media directory not found!\n"
        "Please create and populate: pysdk_test_media/\n"
        "See tests/MEDIA_SETUP.md for detailed setup instructions.\n\n"
        "Quick setup:\n"
        "  1. mkdir -p pysdk_test_media/images\n"
        "  2. mkdir -p pysdk_test_media/videos\n"
        "  3. Add required media files (see MEDIA_SETUP.md)\n"
    )
```

## Dependencies (`pyproject.toml`)

**Structure**: Mirrors compute service pyproject.toml structure, naming, and order

```toml
[project]
name = "cl-client"
version = "0.1.0"
description = "Python SDK for CL Server compute service"
readme = "README.md"
requires-python = ">=3.12"
license = { file = "LICENSE" }
authors = [
    {name = "Ananda Sarangaram"}
]
keywords = ["compute", "client", "tasks", "jobs", "mqtt"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "basedpyright>=1.36.2",       # Strict type checker
    "click>=8.1.0",               # CLI framework
    "httpx>=0.28.1",              # Async HTTP client
    "paho-mqtt>=2.1.0",           # MQTT client for monitoring
    "pydantic>=2.12.5",           # Schema validation
    "rich>=13.0.0",               # Rich terminal output for CLI
]

[project.scripts]
pysdk = "pysdk.cli:main"  # CLI tool entry point

[project.optional-dependencies]
dev = [
    "httpx>=0.28.1",
    "pillow>=11.0.0",             # Image validation in tests
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
]
all = [
    "cl-client[dev]",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pysdk"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
]
addopts = "--cov=pysdk --cov-report=html --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["src/pysdk"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/venv/*",
    "*/.venv/*",
]

[tool.coverage.report]
precision = 2
skip_empty = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
    "@abc.abstractmethod",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "F811", "F401", "UP",
    "F841",  # local variable assigned but never used
    "B018",  # useless expression
]
ignore = ["E501"]
```

**NOTE**: basedpyright configuration is in separate `pyrightconfig.json` file (NOT in pyproject.toml)

**Key Differences from Server:**
- Package name: `cl-client` (not `compute`)
- **HAS scripts**: CLI tool entry point (`pysdk = "pysdk.cli:main"`)
- Added CLI dependencies: click, rich
- Added pillow to dev dependencies (for test media validation)
- basedpyright config in separate pyrightconfig.json (mirrors server pattern)

**Consistency with Server:**
- Same structure order (project → build-system → tool configs)
- Same author, license, classifiers pattern
- Same pytest, coverage, ruff configuration
- Same Python version (3.12)

## Success Criteria

### SDK (Phase 1)
- [ ] All 9 plugin clients implemented
- [ ] Configuration class with all endpoints/hosts/ports (NO hardcoding)
- [ ] No-auth mode working (JWT auth deferred to Phase 2)
- [ ] MQTT callback-based job monitoring (primary workflow)
- [ ] MQTT worker capability monitoring functional
- [ ] Optional HTTP polling (secondary workflow)
- [ ] Comprehensive error handling
- [ ] 90%+ code coverage on SDK
- [ ] Full type hints on public APIs
- [ ] **basedpyright strict mode passing (NO Any types, NO warnings/errors)**

### Test Suite
- [ ] All 9 plugins have end-to-end tests
- [ ] 2+ workflow tests implemented
- [ ] Tests fail clearly when media missing (with helpful error message)
- [ ] **Tests fail if required capability workers don't exist**
- [ ] Tests clean up all created jobs
- [ ] Tests use MQTT callback-based monitoring (primary)
- [ ] Tests optionally use HTTP polling (secondary)
- [ ] Documentation complete:
  - [ ] README.md (user docs)
  - [ ] INTERNALS.md (developer docs)
  - [ ] tests/README.md (testing docs)
  - [ ] tests/media/MEDIA_SETUP.md (media setup guide)

### Code Quality
- [ ] Follows PROJECT_STRUCTURE.md template
- [ ] Mirrors compute service pyproject.toml structure/naming/order
- [ ] basedpyright strict: `uv run basedpyright` passes with zero errors
- [ ] Ruff linting: `uv run ruff check src/` passes
- [ ] Test coverage: `uv run pytest` shows ≥90% coverage
- [ ] All public APIs have docstrings with type hints

## Critical Files to Reference

From compute service (`/Users/anandasarangaram/Work/cl_server/services/compute/`):
- `src/compute/routes.py` - API endpoints to mirror
- `src/compute/schemas.py` - Response schemas for models.py
- `src/compute/plugins.py` - Plugin registration pattern
- `src/compute/capability_manager.py` - MQTT message format
- `src/compute/auth.py` - JWT authentication mechanism

---

# Phase 2: Authentication Support (NEW)

## Overview

Add JWT-based authentication to the Python SDK, matching Dart SDK architecture while maintaining backward compatibility with no-auth mode.

**Folder Structure Changed:**
- CLI app moved to: `../../apps/cli_python`
- Auth service location: `../../services/auth`
- Dart SDK reference: `../../sdks/dartsdk`

## Requirements

### Core Features
1. **Auth Service Integration**: Support all 9 auth endpoints
2. **SessionManager**: High-level facade (matching Dart SDK)
3. **Automatic Token Refresh**: Refresh when < 60 seconds before expiry (Dart SDK behavior)
4. **Test Parametrization**: All tests run in both no-auth and JWT modes
5. **CLI Authentication**: --username, --password, --no-auth flags
6. **Backward Compatibility**: No-auth remains default

### Architecture (Three-Layer Design - Matching Dart SDK)

```
SessionManager (High-Level Facade)
  ├── login(), logout(), get_valid_token()
  ├── Automatic token refresh (< 1 min)
  └── create_compute_client() with auth
       ↓
AuthClient (Low-Level API Wrapper)
  ├── POST /auth/token, /auth/token/refresh
  ├── GET /auth/public-key, /users/me
  └── User CRUD (admin endpoints)
       ↓
JWTAuthProvider (Enhanced)
  ├── JWT token parsing for expiry
  ├── Integrates with SessionManager
  └── Authorization header injection
```

## Implementation Steps

### Phase 2a: Core Auth Infrastructure (Week 1)

#### Day 1: Auth Models & ServerConfig

**New Files:**
1. `src/cl_client/auth_models.py` - Auth request/response models
   - TokenResponse (access_token, token_type)
   - PublicKeyResponse (public_key, algorithm)
   - UserResponse (id, username, is_admin, is_active, created_at, permissions)
   - UserCreateRequest (username, password, is_admin, permissions)
   - UserUpdateRequest (all fields optional for partial updates)

2. `src/cl_client/server_config.py` - Centralized URL management
   - ServerConfig dataclass with auth_url, compute_url, store_url (Phase 3)
   - from_env() class method for environment variable loading
   - Matches Dart SDK's ServerConfig pattern

**Tests:**
- `tests/test_client/test_auth_models.py`
- `tests/test_client/test_server_config.py`

#### Day 2-3: AuthClient

**New File:** `src/cl_client/auth_client.py`

**All 9 Endpoints:**
1. `login(username, password) -> TokenResponse`
2. `refresh_token(token) -> TokenResponse`
3. `get_public_key() -> PublicKeyResponse`
4. `get_current_user(token) -> UserResponse`
5. `create_user(token, user_create) -> UserResponse` (admin)
6. `list_users(token, skip, limit) -> list[UserResponse]` (admin)
7. `get_user(token, user_id) -> UserResponse` (admin)
8. `update_user(token, user_id, user_update) -> UserResponse` (admin)
9. `delete_user(token, user_id) -> None` (admin)

**Key Points:**
- httpx.AsyncClient for HTTP
- Strict type casting (no Any types)
- Async context manager support
- Direct endpoint wrappers (no state management)

**Tests:** `tests/test_client/test_auth_client.py`

#### Day 4: Enhanced JWTAuthProvider

**Modify File:** `src/cl_client/auth.py`

**Enhancements:**
- Two modes: direct token OR SessionManager-based
- JWT token parsing (base64 decode, no external dependencies)
- Token expiry checking (_parse_token_expiry)
- Auto-refresh logic (_should_refresh - < 60 sec threshold)
- _get_token() method for SessionManager integration

**Tests:** Update `tests/test_client/test_auth.py`

#### Day 5: SessionManager

**New File:** `src/cl_client/session_manager.py`

**Core Methods:**
- `login(username, password) -> TokenResponse`
- `logout() -> None`
- `is_authenticated() -> bool`
- `get_current_user() -> UserResponse | None`
- `get_valid_token() -> str` (with auto-refresh)
- `create_compute_client() -> ComputeClient` (pre-configured auth)

**Key Points:**
- Matches Dart SDK SessionManager API
- Automatic token refresh when < 60 seconds remaining
- In-memory token storage (Phase 2)
- Guest mode vs authenticated mode support

**Tests:** `tests/test_client/test_session_manager.py`

### Phase 2b: Integration (Week 2)

#### Day 1: Update ComputeClient

**Modify File:** `src/cl_client/compute_client.py`

**Changes:**
- Add `server_config: ServerConfig | None` parameter
- Use config for all defaults (base_url, mqtt_broker, mqtt_port)
- Backward compatible (all existing params work)

**Tests:** Update `tests/test_client/test_compute_client.py`

#### Day 2-3: Parametrize Tests

**Modify File:** `tests/conftest.py`

**Add Fixtures:**
```python
@pytest.fixture(params=["no_auth", "jwt"], scope="session")
def auth_mode(request):
    # Skip JWT if AUTH_DISABLED=true

@pytest.fixture
async def authenticated_session(auth_mode):
    # Create SessionManager, login with test credentials
    # Only for JWT mode

@pytest.fixture
async def client(auth_mode, authenticated_session):
    # Return ComputeClient based on auth_mode
```

**Key Points:**
- Automatic parametrization: tests run twice
- Test credentials from environment (TEST_USERNAME, TEST_PASSWORD)
- Mark admin-only tests: `@pytest.mark.admin_only`

#### Day 4-5: Update CLI

**Modify File:** `../../apps/cli_python/src/cl_client_cli/main.py`

**Add Global Flags:**
- `--username` (envvar: CL_USERNAME)
- `--password` (envvar: CL_PASSWORD)
- `--auth-url` (envvar: AUTH_URL, default: http://localhost:8000)
- `--compute-url` (envvar: COMPUTE_URL, default: http://localhost:8002)
- `--no-auth` (flag, default: False)

**Helper Functions:**
```python
async def get_client(ctx) -> ComputeClient:
    # If no_auth or no credentials: return ComputeClient()
    # Else: create SessionManager, login, return client

async def get_session_manager(ctx) -> SessionManager:
    # Create and login SessionManager for auth operations
    # Required for user management commands
```

**Plugin Command Updates:**
- Add `--output` flag to ALL plugin commands (9 total)
- Download output file to specified path when --output provided
- Use client.download_job_file() after job completion

**New User Management Commands** (matching Dart SDK):
```python
@cli.group()
def user():
    """User management commands (admin only)."""
    pass

@user.command()
@click.argument("username")
@click.option("--password", required=True, prompt=True, hide_input=True)
@click.option("--admin", is_flag=True, default=False)
@click.option("--permissions", multiple=True)
async def create(username, password, admin, permissions):
    """Create new user (admin only)."""

@user.command()
@click.option("--skip", default=0)
@click.option("--limit", default=100)
async def list(skip, limit):
    """List all users (admin only)."""

@user.command()
@click.argument("user_id", type=int)
async def get(user_id):
    """Get user details (admin only)."""

@user.command()
@click.argument("user_id", type=int)
@click.option("--password", prompt=True, hide_input=True, default=None)
@click.option("--permissions", multiple=True, default=None)
@click.option("--admin", type=bool, default=None)
@click.option("--active", type=bool, default=None)
async def update(user_id, password, permissions, admin, active):
    """Update user (admin only)."""

@user.command()
@click.argument("user_id", type=int)
@click.confirmation_option(prompt="Are you sure you want to delete this user?")
async def delete(user_id):
    """Delete user (admin only)."""
```

**Tests:** Update CLI tests
- Test all plugin commands with --output flag
- Test user management commands (with admin credentials)
- Test permission errors for non-admin users

### Phase 2c: Testing & Documentation (Week 3)

#### Day 1-2: Integration Testing

**Service Startup Order** (Critical):

1. **Start Auth Service First**
   ```bash
   cd ../../services/auth
   auth-server --port 8000
   # Wait for startup, verify: curl http://localhost:8000/
   ```

2. **Restart Compute Service with Auth Enabled**
   ```bash
   cd ../../services/compute

   # For AUTH MODE testing:
   # Compute service needs to know auth service URL for token verification
   export AUTH_SERVICE_URL=http://localhost:8000
   export AUTH_ENABLED=true
   compute-server --port 8002

   # For NO-AUTH MODE testing:
   # export AUTH_ENABLED=false
   # compute-server --port 8002
   ```

3. **Start Workers** (after auth + compute services are running)
   ```bash
   cd ../../workers/ml_worker
   # Workers will connect to compute service
   # If auth enabled, workers may need credentials (check worker implementation)
   python -m ml_worker --compute-url http://localhost:8002
   ```

4. **Create Test Users via Admin API**
   ```bash
   # Default admin user (created on auth service startup)
   # Username: admin (from ADMIN_USERNAME env var)
   # Password: admin (from ADMIN_PASSWORD env var)

   # Create test user for integration tests
   curl -X POST http://localhost:8000/users/ \
     -H "Authorization: Bearer $(curl -X POST http://localhost:8000/auth/token \
       -d username=admin -d password=admin | jq -r .access_token)" \
     -F username=test_user \
     -F password=test_pass \
     -F is_admin=false
   ```

**Test Environment Variables:**
```bash
# Auth service
export AUTH_SERVICE_URL=http://localhost:8000
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin

# Compute service (when auth enabled)
export AUTH_ENABLED=true

# Python SDK tests
export TEST_USERNAME=test_user
export TEST_PASSWORD=test_pass
export AUTH_DISABLED=false  # Enable JWT tests

# Test credentials for admin operations
export TEST_ADMIN_USERNAME=admin
export TEST_ADMIN_PASSWORD=admin
```

**Test Scenarios:**
1. Run all plugin tests in both auth modes
2. Test token refresh (mock expiry)
3. Test admin operations (user management with admin credentials)
4. Test auth error handling (401, 403)
5. Test CLI in both modes (no-auth and JWT)
6. Test permission errors (non-admin user trying admin operations)

**Test Execution:**
```bash
# Run all tests with AUTH DISABLED (no-auth mode only)
export AUTH_DISABLED=true
uv run pytest tests/ -v

# Run all tests with AUTH ENABLED (both modes - parametrized)
export AUTH_DISABLED=false
uv run pytest tests/ -v

# Run only auth-related tests
uv run pytest tests/test_client/test_auth_client.py -v
uv run pytest tests/test_client/test_session_manager.py -v
```

#### Day 3-4: Documentation

**Update Files:**
1. `README.md` - Add auth examples, SessionManager usage, CLI flags
2. `INTERNALS.md` - Add SessionManager architecture, token refresh mechanism
3. `tests/README.md` - Document auth test setup, environment variables

**Key Sections:**
- Quick Start (with and without auth)
- SessionManager vs Direct Client
- Token refresh behavior
- CLI authentication
- Troubleshooting (401, 403 errors)

#### Day 5: Final QA

**Quality Checks:**
```bash
uv run basedpyright                          # 0 errors expected
uv run pytest tests/test_client -v           # All pass, >90% coverage
AUTH_DISABLED=false uv run pytest -v         # Both auth modes
uv run ruff check src/                       # Clean
```

## Success Criteria

### Functional Requirements
- [ ] All 9 auth endpoints implemented
- [ ] SessionManager provides login/logout/refresh
- [ ] Automatic token refresh (< 1 min threshold)
- [ ] ComputeClient works in both auth modes
- [ ] CLI supports auth flags
- [ ] Backward compatible (no-auth default)

### Testing Requirements
- [ ] All tests parametrized (both modes)
- [ ] Admin tests skip in no-auth mode
- [ ] Integration tests pass with real auth service
- [ ] >90% coverage maintained
- [ ] basedpyright: 0 errors

### Documentation Requirements
- [ ] README updated with auth examples
- [ ] Environment variables documented
- [ ] Troubleshooting guide added
- [ ] SessionManager architecture documented

## Critical Files Summary

### Files to Create (4 new files)
1. `src/cl_client/auth_models.py` - Auth request/response models
2. `src/cl_client/server_config.py` - Centralized URL config
3. `src/cl_client/auth_client.py` - Low-level auth API wrapper
4. `src/cl_client/session_manager.py` - High-level auth facade

### Files to Modify (4 existing files)
1. `src/cl_client/auth.py` - Enhance JWTAuthProvider
2. `src/cl_client/compute_client.py` - Add server_config parameter
3. `tests/conftest.py` - Add auth_mode parametrization
4. `../../apps/cli_python/src/cl_client_cli/main.py` - Add auth flags

### Files to Update (documentation)
1. `README.md` - Add auth examples
2. `INTERNALS.md` - Add architecture docs
3. `tests/README.md` - Add auth test setup

## Usage Examples

### Library - No Auth (Backward Compatible)
```python
from cl_client import ComputeClient

async with ComputeClient() as client:
    job = await client.clip_embedding.embed_image(image=Path("photo.jpg"))
```

### Library - With Auth (New)
```python
from cl_client import SessionManager

async with SessionManager() as session:
    await session.login("user", "password")

    client = session.create_compute_client()
    job = await client.clip_embedding.embed_image(image=Path("photo.jpg"))
```

### CLI - No Auth
```bash
cl-client clip-embedding embed photo.jpg --no-auth
```

### CLI - With Auth
```bash
cl-client --username user --password pass clip-embedding embed photo.jpg

# Or with environment variables
export CL_USERNAME=user
export CL_PASSWORD=pass
cl-client clip-embedding embed photo.jpg
```

### CLI - Output File Downloads
```bash
# Download CLIP embedding to file
cl-client clip-embedding embed photo.jpg --output embedding.npy

# Download thumbnail with auth
cl-client --username user --password pass \
  media-thumbnail generate video.mp4 --output thumb.jpg --width 256 --height 256
```

### CLI - User Management (Admin Only)
```bash
# Create user
cl-client --username admin --password admin123 \
  user create newuser --password userpass --permissions read:jobs write:jobs

# List users
cl-client --username admin --password admin123 user list

# Get user details
cl-client --username admin --password admin123 user get 2

# Update user
cl-client --username admin --password admin123 \
  user update 2 --admin true --permissions "*"

# Delete user
cl-client --username admin --password admin123 user delete 2
```
