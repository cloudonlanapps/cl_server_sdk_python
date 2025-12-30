# CL Client CLI Tool

Command-line interface for the CL Server compute service. Provides a user-friendly terminal interface to submit jobs, monitor progress, and download results.

## Features

- 🚀 **All 9 Plugins**: CLIP, DINO, EXIF, face detection/embedding, hashing, HLS streaming, image conversion, thumbnails
- 📊 **Real-time Progress**: MQTT-based live progress tracking with `--watch` flag
- 🎨 **Beautiful Output**: Rich terminal formatting with tables, progress bars, and colors
- 📥 **Automatic Downloads**: Download results with `--output` flag
- 🔄 **Two Modes**: Polling (default) and Watch (MQTT) workflows
- ⚡ **Fast & Efficient**: Built on the `cl-client` Python library

## Installation

### Prerequisites

- Python 3.12+
- `uv` package manager ([installation guide](https://github.com/astral-sh/uv))
- Running CL Server compute service (http://localhost:8002)
- MQTT broker (localhost:1883)

### Install CLI Tool

```bash
# Navigate to example directory
cd /path/to/cl_server/services/compute/client/python/example

# Install dependencies (includes cl-client library)
uv sync

# Verify installation
uv run cl-client --help
```

### Alternative: Install from Parent Directory

```bash
# Install library first
cd /path/to/cl_server/services/compute/client/python
uv pip install -e .

# Install CLI tool
cd example
uv pip install -e .

# Use directly
cl-client --help
```

## Quick Start

### Basic Usage (Polling Mode)

```bash
# Submit job and wait for completion
uv run cl-client clip-embedding embed photo.jpg
```

### Watch Mode (Real-time Progress)

```bash
# Submit job with live progress tracking via MQTT
uv run cl-client clip-embedding embed photo.jpg --watch
```

### Download Results

```bash
# Automatically download result file
uv run cl-client clip-embedding embed photo.jpg --output embedding.npy
```

## Available Commands

### 1. CLIP Embedding

Compute CLIP image embeddings (512-dimensional vectors).

```bash
# Basic usage
uv run cl-client clip-embedding embed photo.jpg

# With watch mode
uv run cl-client clip-embedding embed photo.jpg --watch

# Download embedding automatically
uv run cl-client clip-embedding embed photo.jpg --output clip_embed.npy
```

**Output**: 512-dimensional embedding saved as `.npy` file

### 2. DINO Embedding

Compute DINO image embeddings (384-dimensional vectors).

```bash
# Basic usage
uv run cl-client dino-embedding embed photo.jpg

# With download
uv run cl-client dino-embedding embed photo.jpg --output dino_embed.npy --watch
```

**Output**: 384-dimensional embedding saved as `.npy` file

### 3. EXIF Extraction

Extract EXIF metadata from images.

```bash
# Extract EXIF data
uv run cl-client exif extract photo.jpg

# With watch mode
uv run cl-client exif extract photo.jpg --watch
```

**Output**: JSON with camera make, model, GPS coordinates, datetime, orientation, etc.

### 4. Face Detection

Detect faces in images with bounding boxes.

```bash
# Detect faces
uv run cl-client face-detection detect photo.jpg

# With custom confidence threshold
uv run cl-client face-detection detect photo.jpg --confidence-threshold 0.8

# Download detection results
uv run cl-client face-detection detect photo.jpg --output detections.json --watch
```

**Output**: JSON with face bounding boxes, confidence scores, and count

**Parameters**:
- `--confidence-threshold`: Minimum confidence score (0.0-1.0, default: 0.7)

### 5. Face Embedding

Compute face embeddings for detected faces.

```bash
# Embed faces
uv run cl-client face-embedding embed photo.jpg

# With custom threshold
uv run cl-client face-embedding embed photo.jpg --confidence-threshold 0.75

# Download embeddings
uv run cl-client face-embedding embed photo.jpg --output face_embeddings.npy --watch
```

**Output**: 128-dimensional embeddings for each detected face

**Parameters**:
- `--confidence-threshold`: Face detection threshold (0.0-1.0, default: 0.7)

### 6. Perceptual Hashing

Compute perceptual hashes for image similarity detection.

```bash
# Compute hashes
uv run cl-client hash compute photo.jpg

# With watch mode
uv run cl-client hash compute photo.jpg --watch
```

**Output**: JSON with `phash` and `dhash` values

### 7. HLS Streaming

Generate HLS manifests for video streaming.

```bash
# Generate HLS manifest
uv run cl-client hls-streaming generate-manifest video.mp4

# With custom segment duration
uv run cl-client hls-streaming generate-manifest video.mp4 --segment-duration 6

# With watch mode
uv run cl-client hls-streaming generate-manifest video.mp4 --watch
```

**Output**: HLS manifest URL for adaptive streaming

**Parameters**:
- `--segment-duration`: HLS segment duration in seconds (default: 4)

### 8. Image Conversion

Convert images between formats (JPG, PNG, WebP).

```bash
# Convert PNG to JPG
uv run cl-client image-conversion convert input.png --output-format jpg

# With custom quality
uv run cl-client image-conversion convert input.png --output-format jpg --quality 95

# With custom dimensions
uv run cl-client image-conversion convert input.jpg \
  --output-format webp \
  --width 1920 \
  --height 1080 \
  --quality 90

# Download converted image
uv run cl-client image-conversion convert input.png \
  --output-format jpg \
  --output converted.jpg \
  --watch
```

**Parameters**:
- `--output-format`: Target format (jpg, png, webp) **[required]**
- `--quality`: Output quality 1-100 (default: 85)
- `--width`: Target width in pixels (optional, maintains aspect ratio if height not specified)
- `--height`: Target height in pixels (optional, maintains aspect ratio if width not specified)

### 9. Media Thumbnail

Generate thumbnails from images or videos.

```bash
# Generate thumbnail from image
uv run cl-client media-thumbnail generate photo.jpg --width 256 --height 256

# Generate thumbnail from video (first frame)
uv run cl-client media-thumbnail generate video.mp4 --width 512 --height 288

# Download thumbnail
uv run cl-client media-thumbnail generate video.mp4 \
  --width 256 \
  --height 256 \
  --output thumbnail.jpg \
  --watch
```

**Parameters**:
- `--width, -w`: Thumbnail width in pixels **[required]**
- `--height, -h`: Thumbnail height in pixels **[required]**

### Download Command

Download files from completed jobs.

```bash
# Download specific file from job
uv run cl-client download <job-id> output/clip_embedding.npy embedding.npy

# Download to current directory
uv run cl-client download <job-id> output/thumbnail.jpg .
```

**Arguments**:
1. `job-id`: UUID of completed job
2. `file-path`: Relative path of file in job output (e.g., `output/result.npy`)
3. `destination`: Local file path to save to (optional, defaults to filename)

## Command Options

### Global Options

All commands support these global options:

- `--timeout SECONDS`: Maximum wait time for job completion (default: 30.0)
- `--watch, -w`: Enable real-time MQTT progress tracking
- `--output, -o FILE`: Automatically download result to specified file
- `--help`: Show command help

### Examples with Options

```bash
# Custom timeout
uv run cl-client clip-embedding embed photo.jpg --timeout 60

# Watch mode with download
uv run cl-client clip-embedding embed photo.jpg --watch --output result.npy

# Combine all options
uv run cl-client media-thumbnail generate video.mp4 \
  --width 256 \
  --height 256 \
  --watch \
  --timeout 45 \
  --output thumb.jpg
```

## Workflow Examples

### Complete Image Analysis

```bash
# 1. Extract EXIF metadata
uv run cl-client exif extract photo.jpg

# 2. Generate thumbnail
uv run cl-client media-thumbnail generate photo.jpg -w 256 -h 256 --output thumb.jpg

# 3. Compute CLIP embedding
uv run cl-client clip-embedding embed photo.jpg --output clip.npy

# 4. Compute perceptual hash
uv run cl-client hash compute photo.jpg

# 5. Detect faces
uv run cl-client face-detection detect photo.jpg
```

### Video Processing Pipeline

```bash
# 1. Generate thumbnail from video
uv run cl-client media-thumbnail generate video.mp4 -w 512 -h 288 --output preview.jpg

# 2. Generate HLS manifest
uv run cl-client hls-streaming generate-manifest video.mp4 --watch

# 3. Embed video thumbnail
uv run cl-client clip-embedding embed preview.jpg --output video_embed.npy
```

### Batch Image Processing

```bash
# Process multiple images with watch mode
for img in *.jpg; do
  uv run cl-client clip-embedding embed "$img" \
    --output "embeddings/${img%.jpg}.npy" \
    --watch
done
```

## Configuration

### Environment Variables

Configure server connection and MQTT broker:

```bash
# Server connection
export COMPUTE_SERVER_URL="http://localhost:8002"

# MQTT broker
export MQTT_BROKER_HOST="localhost"
export MQTT_BROKER_PORT="1883"

# Test media location (for tests)
export CL_CLIENT_TEST_MEDIA="/path/to/test_media"
```

### Default Configuration

If environment variables are not set, the CLI uses these defaults:

- **Server**: `http://localhost:8002`
- **MQTT Broker**: `localhost:1883`
- **Timeout**: 30 seconds

## Output Formats

### Polling Mode Output

```
Submitting job...
✓ Job submitted: abc-123-def-456
Waiting for completion...
✓ Completed

Job ID: abc-123-def-456
Status: completed
Task Type: clip_embedding

Output:
╭───────────────┬────────╮
│ embedding_dim │    512 │
│ output_path   │ output │
╰───────────────┴────────╯
```

### Watch Mode Output

```
Submitting job...
✓ Job submitted: abc-123-def-456

Watching job progress...
Processing... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:02

✓ Completed

Job ID: abc-123-def-456
Status: completed
...
```

### Download Output

```
✓ Job submitted: abc-123-def-456
Waiting for completion...
✓ Completed
Downloading output/clip_embedding.npy...
✓ Downloaded to embedding.npy (2.1 KB)
```

## Error Handling

### Job Failures

```bash
$ uv run cl-client clip-embedding embed nonexistent.jpg
Error: File not found: nonexistent.jpg

$ uv run cl-client clip-embedding embed photo.jpg --timeout 1
Error: Job timeout after 1.0 seconds
```

### Server Connection Issues

```bash
$ uv run cl-client clip-embedding embed photo.jpg
Error: Could not connect to server at http://localhost:8002
Please ensure the compute server is running.
```

### Worker Unavailable

```bash
$ uv run cl-client clip-embedding embed photo.jpg
Error: No workers available with capability: clip_embedding
Please ensure workers are running.
```

## Testing

### Run CLI Tests

```bash
# Run all CLI tests
cd example
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=cl_client_cli --cov-report=html

# Run specific test file
uv run pytest tests/test_cli.py -v

# Run specific test
uv run pytest tests/test_cli.py::TestCLIPEmbedding::test_embed_polling_mode
```

### Test Coverage

Current test coverage: **80.48%** (21 tests)

**Test categories**:
- Command invocation tests (all 9 plugins)
- Polling mode tests
- Watch mode tests
- Parameter validation tests
- Error handling tests
- File download tests

### Test Requirements

Tests require:
- Mock compute client (provided by fixtures)
- Temporary test files (created automatically)
- No actual server connection needed

## Development

### Project Structure

```
example/
├── pyproject.toml          # CLI project configuration
├── README.md               # This file
├── src/
│   └── cl_client_cli/
│       ├── __init__.py
│       └── main.py         # CLI implementation
└── tests/
    ├── conftest.py         # Test fixtures
    ├── README.md           # Testing documentation
    └── test_cli.py         # CLI tests
```

### Development Setup

```bash
# Install in development mode
cd example
uv sync

# Run CLI from source
uv run cl-client --help

# Run with debugger
uv run python -m pdb -m cl_client_cli.main clip-embedding embed photo.jpg
```

### Adding a New Command

1. **Add command group** (if new plugin):
   ```python
   @cli.group()
   def my_plugin():
       """My plugin commands."""
       pass
   ```

2. **Add command**:
   ```python
   @my_plugin.command()
   @click.argument("input_file", type=click.Path(exists=True, path_type=Path))
   @common_options
   def process(input_file: Path, watch: bool, timeout: float, output: Optional[Path]):
       """Process input file."""
       async def run():
           async with ComputeClient() as client:
               job = await client.my_plugin.process(
                   input=input_file,
                   wait=not watch,
                   timeout=timeout
               )
               # Handle output...
       asyncio.run(run())
   ```

3. **Add tests** in `tests/test_cli.py`:
   ```python
   def test_my_plugin_process(self, mock_compute_client, temp_file, completed_job):
       mock_compute_client.my_plugin.process = AsyncMock(return_value=completed_job)
       runner = CliRunner()
       result = runner.invoke(cli, ["my-plugin", "process", str(temp_file)])
       assert result.exit_code == 0
   ```

### Code Quality

```bash
# Type checking
uv run basedpyright src/

# Linting
uv run ruff check src/

# Formatting
uv run ruff format src/

# All quality checks
uv run basedpyright src/ && uv run ruff check src/ && uv run pytest tests/
```

## Troubleshooting

### Command Not Found

```bash
# If cl-client command not found, use uv run:
uv run cl-client --help

# Or install globally:
uv pip install -e .
```

### Import Errors

```bash
# Ensure library is installed
cd ..
uv pip install -e .
cd example
uv sync
```

### Connection Refused

```bash
# Check server is running
curl http://localhost:8002/capabilities

# Check MQTT broker
telnet localhost 1883
```

### MQTT Progress Not Showing

```bash
# Verify MQTT broker is running
# Use --watch flag to enable MQTT mode
uv run cl-client clip-embedding embed photo.jpg --watch
```

## Integration with Library

The CLI tool is built on top of the `cl-client` Python library. For programmatic access and advanced usage, see the library documentation:

- **Library API**: [../README.md](../README.md)
- **Developer Guide**: [../INTERNALS.md](../INTERNALS.md)
- **Library Tests**: [../tests/README.md](../tests/README.md)

### Using Library Directly

```python
from cl_client import ComputeClient
from pathlib import Path

async with ComputeClient() as client:
    # Same operations as CLI, but in Python
    job = await client.clip_embedding.embed_image(
        image=Path("photo.jpg"),
        wait=True
    )
    print(f"Embedding: {job.task_output['embedding']}")
```

## Support

- **Documentation**: See this file and library docs
- **Issues**: Report at project issue tracker
- **Library API**: [../README.md](../README.md)
- **Testing Guide**: [tests/README.md](tests/README.md)

## Version

- **CLI Version**: 0.1.0
- **Library Version**: 0.1.0 (cl-client)
- **Python**: 3.12+

## License

MIT License - see [../LICENSE](../LICENSE) file for details.
