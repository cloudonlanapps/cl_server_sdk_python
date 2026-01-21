# CL Client - Python Client Library

Python client library for interacting with the CL Server compute service. Provides an async API for submitting jobs, monitoring progress via MQTT, and downloading results.

**Package Manager:** uv
**Authentication Method:** ES256 JWT (optional)
**Type Safety:** Strict basedpyright checking with no `Any` types

> **For Developers:** See [INTERNALS.md](INTERNALS.md) for package structure, development workflow, and contribution guidelines.
>
> **For Testing:** See [tests/README.md](tests/README.md) for comprehensive testing guide, test organization, and coverage requirements.

## Features

- 🚀 **Async/Await Support**: Built on httpx for efficient async operations
- 📡 **Real-time MQTT Monitoring**: Track job progress with callbacks (primary workflow)
- 🔄 **HTTP Polling**: Fallback polling mode for simple workflows
- 🔌 **9 Plugin Integrations**: CLIP, DINO, EXIF, face detection/embedding, hashing, HLS streaming, image conversion, thumbnails
- 📥 **File Downloads**: Download job results (embeddings, images, etc.)
- 🎯 **Type-Safe**: Strict basedpyright checking with no `Any` types
- 🛡️ **Modular Authentication**: Swappable auth providers (no-auth, JWT)
- ⚡ **Production Ready**: 88.97% test coverage, 0 type errors

## Installation

**Individual Package Installation:**

```bash
# Install from PyPI (when published)
pip install cl-client

# Or with uv
uv pip install cl-client

# Or install locally for development
cd sdks/pysdk
uv sync
```

**Workspace Installation (All Packages):**

See root [README.md](../../README.md) for installing all packages using `./install.sh`.

## Quick Start

### No-Auth Mode (Default)

```python
import asyncio
from pathlib import Path
from cl_client import ComputeClient

async def main():
    # Create client (connects to localhost by default, no auth)
    async with ComputeClient() as client:
        # Define callback for job completion
        def on_complete(job):
            print(f"✓ Job completed: {job.job_id}")
            print(f"Status: {job.status}")
            if job.task_output:
                print(f"Output: {job.task_output}")

        # Submit CLIP embedding job with callback
        job = await client.clip_embedding.embed_image(
            image=Path("photo.jpg"),
            on_progress=lambda j: print(f"Progress: {j.progress}%"),
            on_complete=on_complete
        )

        print(f"Job submitted: {job.job_id}")

        # Keep running to receive callbacks
        await asyncio.sleep(10)

asyncio.run(main())
```

### JWT Auth Mode

```python
import asyncio
from pathlib import Path
from cl_client import SessionManager

async def main():
    # Create session manager and login
    async with SessionManager() as session:
        await session.login("username", "password")

        # Create authenticated client
        client = session.create_compute_client()

        # Use client as normal
        job = await client.clip_embedding.embed_image(
            image=Path("photo.jpg"),
            wait=True
        )

        print(f"Job {job.job_id} completed!")
        print(f"Embedding dimension: {job.task_output['embedding_dim']}")

asyncio.run(main())
```

### Polling Mode (Secondary Workflow)

```python
async def main():
    async with ComputeClient() as client:
        # Use wait=True for simple polling
        job = await client.clip_embedding.embed_image(
            image=Path("photo.jpg"),
            wait=True,  # Block until completion
            timeout=30.0
        )

        print(f"Job {job.job_id} completed!")
        print(f"Embedding dimension: {job.task_output['embedding_dim']}")

asyncio.run(main())
```

### Download Result Files

```python
async def main():
    async with ComputeClient() as client:
        # Submit job
        job = await client.clip_embedding.embed_image(
            image=Path("photo.jpg"),
            wait=True
        )

        # Download embedding file
        output_path = job.params["output_path"]  # e.g., "output/clip_embedding.npy"
        await client.download_job_file(
            job.job_id,
            output_path,
            Path("embedding.npy")
        )

        print(f"Downloaded to embedding.npy")

asyncio.run(main())
```

## Authentication

The library supports two authentication modes:

### 1. No-Auth Mode (Default)

No authentication required. Suitable for internal networks or development.

```python
from cl_client import ComputeClient

# Direct client usage - no auth
async with ComputeClient() as client:
    job = await client.clip_embedding.embed_image(image=Path("photo.jpg"))
```

### 2. JWT Auth Mode

Full JWT authentication with automatic token refresh.

```python
from cl_client import SessionManager

# High-level session management
async with SessionManager() as session:
    # Login with credentials
    await session.login("username", "password")

    # Check authentication status
    if session.is_authenticated():
        print("Logged in successfully!")

    # Get current user info
    user = await session.get_current_user()
    print(f"User: {user.username}, Admin: {user.is_admin}")

    # Create authenticated client (automatically includes auth headers)
    client = session.create_compute_client()

    # Use client normally - auth headers added automatically
    job = await client.clip_embedding.embed_image(image=Path("photo.jpg"))

    # Logout when done
    await session.logout()
```

### Token Refresh

SessionManager automatically refreshes tokens when they're about to expire (< 60 seconds remaining):

```python
async with SessionManager() as session:
    await session.login("username", "password")

    # Token automatically refreshed if needed
    token = await session.get_valid_token()

    # Use client - token refresh happens transparently
    client = session.create_compute_client()
    job = await client.clip_embedding.embed_image(image=Path("photo.jpg"))
```

### User Management (Admin Only)

Admin users can manage other users via SessionManager:

```python
from cl_client import SessionManager
from cl_client.auth_models import UserCreateRequest, UserUpdateRequest

async with SessionManager() as session:
    await session.login("admin", "admin_password")

    # Create new user
    user_create = UserCreateRequest(
        username="newuser",
        password="securepass",
        is_admin=False,
        permissions=["read:jobs", "write:jobs"]
    )
    user = await session._auth_client.create_user(
        token=session.get_token(),
        user_create=user_create
    )

    # List all users
    users = await session._auth_client.list_users(
        token=session.get_token(),
        skip=0,
        limit=10
    )

    # Update user permissions
    user_update = UserUpdateRequest(
        permissions=["read:jobs", "write:jobs", "admin"]
    )
    updated = await session._auth_client.update_user(
        token=session.get_token(),
        user_id=user.id,
        user_update=user_update
    )

    # Delete user
    await session._auth_client.delete_user(
        token=session.get_token(),
        user_id=user.id
    )
```

## Available Plugins

All plugins follow the same pattern with async methods and callback support:

### 1. CLIP Embedding
```python
job = await client.clip_embedding.embed_image(
    image=Path("photo.jpg"),
    on_complete=callback,
    wait=False  # Use callbacks
)
# Returns: 512-dimensional embedding in task_output
```

### 2. DINO Embedding
```python
job = await client.dino_embedding.embed_image(
    image=Path("photo.jpg"),
    on_complete=callback
)
# Returns: 384-dimensional embedding
```

### 3. EXIF Extraction
```python
job = await client.exif.extract(
    image=Path("photo.jpg"),
    on_complete=callback
)
# Returns: Camera make, model, GPS, datetime, etc.
```

### 4. Face Detection
```python
job = await client.face_detection.detect(
    image=Path("photo.jpg"),
    on_complete=callback
)
# Returns: Bounding boxes, confidence scores
```

### 5. Face Embedding
```python
job = await client.face_embedding.embed_faces(
    image=Path("photo.jpg"),
    on_complete=callback
)
# Returns: Face embeddings for detected faces
```

### 6. Perceptual Hashing
```python
job = await client.hash.compute(
    image=Path("photo.jpg"),
    on_complete=callback
)
# Returns: phash, dhash for similarity detection
```

### 7. HLS Streaming
```python
job = await client.hls_streaming.generate_manifest(
    video=Path("video.mp4"),
    on_complete=callback
)
# Returns: HLS manifest URL for adaptive streaming
```

### 8. Image Conversion
```python
job = await client.image_conversion.convert(
    image=Path("input.png"),
    output_format="jpg",
    quality=90,
    on_complete=callback
)
# Returns: Converted image path
```

### 9. Media Thumbnail
```python
job = await client.media_thumbnail.generate(
    media=Path("video.mp4"),
    width=256,
    height=256,
    on_complete=callback
)
# Returns: Thumbnail image path
```

## Configuration

### Environment Variables

```bash
# Server URLs
export AUTH_URL="http://localhost:8000"          # Auth service URL
export COMPUTE_URL="http://localhost:8002"       # Compute service URL
export STORE_URL="http://localhost:8001"         # Store service URL (future)

# MQTT broker
export MQTT_BROKER_HOST="localhost"
export MQTT_BROKER_PORT="1883"

# Authentication (for testing)
export TEST_USERNAME="testuser"                  # Test user credentials
export TEST_PASSWORD="testpass"
export TEST_ADMIN_USERNAME="admin"               # Admin credentials
export TEST_ADMIN_PASSWORD="admin"
```

### Programmatic Configuration

```python
from cl_client import ComputeClient, SessionManager
from cl_client.server_config import ServerConfig

# Using ServerConfig (recommended for auth mode)
config = ServerConfig(
    auth_url="http://localhost:8000",
    compute_url="http://localhost:8002",
    mqtt_broker="localhost",
    mqtt_port=1883
)

# SessionManager uses ServerConfig automatically
session = SessionManager(server_config=config)

# Or load from environment
session = SessionManager(server_config=ServerConfig.from_env())

# Direct client configuration (no-auth mode)
client = ComputeClient(
    base_url="http://localhost:8002",
    mqtt_broker="localhost",
    mqtt_port=1883,
    timeout=30.0
)
```

## Advanced Usage

### Progress Tracking

```python
def on_progress(job):
    print(f"Job {job.job_id}: {job.progress}% complete")

def on_complete(job):
    if job.status == "completed":
        print(f"✓ Success: {job.task_output}")
    else:
        print(f"✗ Failed: {job.error_message}")

job = await client.clip_embedding.embed_image(
    image=Path("photo.jpg"),
    on_progress=on_progress,
    on_complete=on_complete
)
```

### Manual Subscription Management

```python
# Subscribe to job updates
subscription_id = client.subscribe_job_updates(
    job_id="abc-123-def",
    on_progress=on_progress,
    on_complete=on_complete
)

# Later, unsubscribe
client.unsubscribe(subscription_id)
```

### Worker Capabilities

```python
# Check available workers
capabilities = await client.get_capabilities()
print(f"Workers: {capabilities.num_workers}")
print(f"Capabilities: {capabilities.capabilities}")

# Wait for specific capability
available = await client.wait_for_workers(
    required_capabilities=["clip_embedding"],
    timeout=30.0
)
```

### Custom Authentication

```python
from cl_client.auth import JWTAuthProvider, NoAuthProvider
from cl_client import SessionManager

# Option 1: Use SessionManager (recommended - handles token refresh)
session = SessionManager()
await session.login("username", "password")
client = session.create_compute_client()

# Option 2: Direct JWT provider (no automatic refresh)
auth_provider = JWTAuthProvider(token="your-jwt-token")
client = ComputeClient(auth_provider=auth_provider)

# Option 3: Explicit no-auth mode
client = ComputeClient(auth_provider=NoAuthProvider())
```

## Error Handling

```python
from cl_client.exceptions import (
    JobNotFoundError,
    JobFailedError,
    WorkerUnavailableError
)
import httpx

try:
    # With SessionManager
    async with SessionManager() as session:
        await session.login("username", "password")
        client = session.create_compute_client()

        job = await client.clip_embedding.embed_image(
            image=Path("photo.jpg"),
            wait=True
        )
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        print("Authentication failed - invalid credentials or token expired")
    elif e.response.status_code == 403:
        print("Forbidden - insufficient permissions")
    else:
        print(f"HTTP error: {e.response.status_code}")
except JobNotFoundError:
    print("Job not found")
except JobFailedError as e:
    print(f"Job failed: {e.job.error_message}")
except WorkerUnavailableError:
    print("No workers available for this task")
```

## Testing

See [tests/README.md](./tests/README.md) for comprehensive testing guide.

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=cl_client --cov-report=html

# Type checking
uv run basedpyright
```

## Documentation

- **[INTERNALS.md](./INTERNALS.md)** - Developer documentation, architecture, contributing guide
- **[tests/README.md](./tests/README.md)** - Testing guide with fixtures and patterns
- **[tests/media/MEDIA_SETUP.md](./tests/media/MEDIA_SETUP.md)** - Test media setup instructions
- **[Architecture Overview](../../docs/ARCHITECTURE.md)** - System-wide architecture and inter-service communication

## CLI Tools

The Python SDK provides two CLI tools for interacting with CL Server services.

### Command 1: cl_client (Job Management CLI)

Interactive command-line interface for submitting and managing compute jobs.

```bash
# Run the CLI tool
uv run cl_client

# Or if installed globally
cl_client
```

See [example/README.md](./example/README.md) for detailed CLI usage documentation.

### Command 2: cl-admin (Admin Utility)

Administrative utility for user and configuration management.

```bash
# Run admin utility
uv run cl-admin

# Or if installed globally
cl-admin
```

**Note:** Admin functionality requires appropriate permissions on the CL Server instance.

## License

MIT License - see [LICENSE](./LICENSE) file for details.

## Future Enhancements

The Dart SDK has implemented some high-level features that could be valuable for pysdk:

- **UserManager Module**: High-level user management API with command pattern architecture
- **StoreManager Module**: High-level store entity management API
- **User Prefixing System**: Automatic prefixing for utility-created users (prevents namespace conflicts)
- **Command Pattern**: Clean architecture with Result wrapper pattern for consistent error handling
- **Result Wrapper Pattern**: Type-safe error handling without raising exceptions

These features are documented in the Dart SDK and could be adapted to Python. See `sdks/dartsdk/PYSDK_ADOPTION.md` for implementation details and recommendations.

**Benefits for pysdk**:
- More Pythonic error handling (Result pattern similar to `Optional[T]`)
- Better code organization (command pattern for complex operations)
- Namespace management for testing/automation tools (user prefixing)
- Improved developer experience (high-level manager APIs)

## Support

- **Issues**: Report bugs at https://github.com/your-org/cl-server/issues
- **Documentation**: See docs above
- **Examples**: Check `example/` directory for CLI usage
