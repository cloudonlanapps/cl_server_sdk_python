# CL Client - Python Client Library for CL Server Compute Service

Python client library for interacting with the CL Server compute service. Provides both a programmatic API and CLI tool for submitting jobs, monitoring progress, and downloading results.

## Features

- 🚀 **Async/Await Support**: Built on httpx for efficient async operations
- 📡 **Real-time MQTT Monitoring**: Track job progress with callbacks
- 🔌 **9 Plugin Integrations**: CLIP, DINO, EXIF, face detection/embedding, hashing, HLS streaming, image conversion, thumbnails
- 🎯 **Type-Safe**: Strict basedpyright checking with no `Any` types
- 🛡️ **Modular Authentication**: Swappable auth providers (no-auth, JWT)
- 🎨 **Rich CLI**: Beautiful terminal interface with progress bars

## Installation

```bash
# Install the client library
pip install cl-client

# Or with uv
uv pip install cl-client
```

## Quick Start

### Programmatic API

```python
import asyncio
from cl_client import ComputeClient

async def main():
    # Create client
    client = ComputeClient(
        base_url="http://localhost:8002",
        mqtt_broker="localhost"
    )

    # Submit job with MQTT callback (primary workflow)
    def on_complete(job):
        print(f"Job completed! Status: {job.status}")
        if job.status == "completed":
            print(f"Embedding: {job.task_output['embedding'][:5]}...")

    job = await client.clip_embedding.embed_image(
        image=Path("photo.jpg"),
        on_complete=on_complete
    )

    print(f"Job submitted: {job.job_id}")

    # Wait a bit for callback
    await asyncio.sleep(10)

asyncio.run(main())
```

### CLI Tool

```bash
# Generate CLIP embedding
cl_client clip_embedding embed photo.jpg

# Convert image format
cl_client image_conversion convert input.png output.jpg --format jpeg

# Generate thumbnail
cl_client media_thumbnail generate video.mp4 thumb.jpg --width 256 --height 256
```

## Configuration

Set environment variables for default configuration:

```bash
export COMPUTE_SERVER_URL="http://localhost:8002"
export MQTT_BROKER_HOST="localhost"
```

## Documentation

- [INTERNALS.md](./INTERNALS.md) - Developer documentation
- [tests/README.md](./tests/README.md) - Testing guide
- [tests/media/MEDIA_SETUP.md](./tests/media/MEDIA_SETUP.md) - Test media setup

## License

MIT License - see [LICENSE](./LICENSE) file for details.
