# CL Client - Python Client Library

Python client library for interacting with the CL Server compute service. Provides an async API for submitting jobs, monitoring progress via MQTT, and downloading results.

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

```bash
# Install from PyPI (when published)
pip install cl-client

# Or with uv
uv pip install cl-client

# Or install locally for development
cd /path/to/cl_server/services/compute/client/python
uv sync
```

## Quick Start

### Basic Usage (MQTT Callbacks - Primary Workflow)

```python
import asyncio
from pathlib import Path
from cl_client import ComputeClient

async def main():
    # Create client (connects to localhost by default)
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
# Server connection
export COMPUTE_SERVER_URL="http://localhost:8002"

# MQTT broker
export MQTT_BROKER_HOST="localhost"
export MQTT_BROKER_PORT="1883"
```

### Programmatic Configuration

```python
from cl_client import ComputeClient

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
from cl_client.auth import JWTAuthProvider

# JWT authentication (Phase 2 - requires auth server)
auth_provider = JWTAuthProvider(token="your-jwt-token")
client = ComputeClient(auth_provider=auth_provider)
```

## Error Handling

```python
from cl_client.exceptions import (
    JobNotFoundError,
    JobFailedError,
    WorkerUnavailableError
)

try:
    job = await client.clip_embedding.embed_image(
        image=Path("photo.jpg"),
        wait=True
    )
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

## CLI Tool

A separate command-line interface tool is available in the `example/` directory. See [example/README.md](./example/README.md) for CLI documentation.

## License

MIT License - see [LICENSE](./LICENSE) file for details.

## Support

- **Issues**: Report bugs at https://github.com/your-org/cl-server/issues
- **Documentation**: See docs above
- **Examples**: Check `example/` directory for CLI usage
