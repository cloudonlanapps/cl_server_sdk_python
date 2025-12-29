# CL Client - Testing Guide

## Prerequisites

- Python 3.12+
- uv package manager
- Running compute server (with --no-auth for tests)
- Running workers with required capabilities
- Test media files (see [media/MEDIA_SETUP.md](./media/MEDIA_SETUP.md))

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
