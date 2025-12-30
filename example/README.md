# CL Client CLI

Command-line interface for the CL Client compute library.

## Installation

From the example directory:

```bash
# Install the library first (from parent directory)
cd ../cl_client
uv pip install -e .

# Install the CLI
cd ../example
uv pip install -e .
```

## Usage

```bash
# Submit a clip embedding job
cl-client clip-embedding embed image.jpg

# Submit with progress display
cl-client clip-embedding embed image.jpg --watch

# Generate thumbnail
cl-client media-thumbnail generate video.mp4 --width 256 --height 256

# Get help
cl-client --help
cl-client clip-embedding --help
```

## Features

- 🚀 All 9 plugin operations supported
- 📊 Real-time progress display via MQTT
- 🎨 Beautiful terminal output with Rich
- 📥 Automatic file downloads
- 🔄 Both sync (polling) and async (MQTT) workflows

## Development

```bash
# Run tests
uv run pytest tests/

# Install in development mode
uv pip install -e .
```
