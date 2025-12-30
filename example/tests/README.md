# CLI Tests

Comprehensive unit tests for the `cl-client` CLI tool.

## Overview

This test suite validates all CLI commands and options using Click's `CliRunner` for isolated testing without requiring a running server.

## Test Coverage

- **21 tests** covering:
  - All 9 plugin commands (clip-embedding, dino-embedding, exif, etc.)
  - Both polling mode (default) and watch mode (--watch flag)
  - Parameter validation (--timeout, --width, --height, --quality, --format)
  - Error handling (missing files, failed jobs)
  - Output formatting verification

- **80.48% code coverage** (exceeds 70% threshold)

## Running Tests

### Run all tests:
```bash
uv run pytest tests/test_cli.py -v
```

### Run specific test class:
```bash
uv run pytest tests/test_cli.py::TestClipEmbedding -v
```

### Run with coverage report:
```bash
uv run pytest tests/test_cli.py --cov=cl_client_cli --cov-report=html
```

View HTML coverage report:
```bash
open htmlcov/index.html
```

## Test Structure

### `conftest.py`
Shared fixtures:
- `mock_compute_client` - Mock ComputeClient for testing
- `temp_image_file` - Temporary test image file
- `temp_video_file` - Temporary test video file
- `completed_job` - Mock completed job response
- `queued_job` - Mock queued job response
- `failed_job` - Mock failed job response

### `test_cli.py`
Test classes organized by plugin:
- `TestClipEmbedding` - CLIP embedding tests
- `TestDinoEmbedding` - DINO embedding tests
- `TestExif` - EXIF extraction tests
- `TestFaceDetection` - Face detection tests
- `TestFaceEmbedding` - Face embedding tests
- `TestHash` - Perceptual hashing tests
- `TestHlsStreaming` - HLS streaming tests
- `TestImageConversion` - Image conversion tests
- `TestMediaThumbnail` - Thumbnail generation tests
- `TestErrorHandling` - Error handling tests
- `TestAdditionalCommands` - Watch mode tests

## Test Patterns

### Polling Mode Test (Default):
```python
def test_embed_polling_mode(self, mock_compute_client, temp_image_file, completed_job):
    """Test clip-embedding embed in polling mode."""
    mock_compute_client.clip_embedding.embed_image = AsyncMock(return_value=completed_job)

    runner = CliRunner()
    result = runner.invoke(cli, ["clip-embedding", "embed", str(temp_image_file)])

    assert result.exit_code == 0
    assert "test-job-123" in result.output
```

### Watch Mode Test (--watch flag):
```python
def test_embed_watch_mode(self, mock_compute_client, temp_image_file, completed_job):
    """Test clip-embedding embed with --watch flag."""
    async def mock_embed(**kwargs):
        if "on_complete" in kwargs:
            kwargs["on_complete"](completed_job)
        return completed_job

    mock_compute_client.clip_embedding.embed_image = AsyncMock(side_effect=mock_embed)

    runner = CliRunner()
    result = runner.invoke(cli, ["clip-embedding", "embed", "--watch", str(temp_image_file)])

    assert result.exit_code == 0
```

## CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run CLI tests
  run: |
    uv sync --all-extras
    uv run pytest tests/test_cli.py -v --cov=cl_client_cli --cov-report=xml
```

## Coverage Requirements

- Minimum coverage: **70%** (configured in `pyproject.toml`)
- Current coverage: **80.48%**
- Missing coverage areas:
  - Some error handling paths
  - Edge cases in progress tracking

## Debugging Failed Tests

### View test output:
```bash
uv run pytest tests/test_cli.py -v -s
```

### Run specific test with debugging:
```bash
uv run pytest tests/test_cli.py::TestClipEmbedding::test_embed_polling_mode -v -s
```

### Check mock calls:
Add `print(mock_compute_client.clip_embedding.embed_image.call_args)` to inspect what was called.

## Adding New Tests

1. Add test method to appropriate test class
2. Use fixtures from `conftest.py`
3. Mock the ComputeClient methods
4. Use `CliRunner().invoke(cli, [...])`
5. Assert exit code and output
6. Run tests to verify coverage

Example:
```python
def test_new_feature(self, mock_compute_client, temp_image_file):
    """Test new CLI feature."""
    # Setup mock
    job = JobResponse(...)
    mock_compute_client.plugin.method = AsyncMock(return_value=job)

    # Run command
    runner = CliRunner()
    result = runner.invoke(cli, ["plugin", "command", str(temp_image_file)])

    # Verify
    assert result.exit_code == 0
    assert "expected output" in result.output
```

## Dependencies

Test dependencies (from `pyproject.toml`):
- `pytest>=9.0.2` - Test framework
- `pytest-asyncio>=1.3.0` - Async test support
- `pytest-cov>=7.0.0` - Coverage reporting
- `click` - CLI testing via `CliRunner`

## Notes

- Tests use mocked `ComputeClient` - no server required
- Temporary files created in pytest's `tmp_path`
- All tests are isolated and can run in parallel
- Coverage excludes `__init__.py` and test files
