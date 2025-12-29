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

### Modular Authentication

Auth providers are injectable and swappable:

```python
from cl_client.auth import NoAuthProvider, JWTAuthProvider

# No-auth mode (default)
client = ComputeClient(auth_provider=NoAuthProvider())

# JWT mode
client = ComputeClient(auth_provider=JWTAuthProvider(token="..."))
```

## Code Quality Standards

### Type Checking

Strict basedpyright mode - **zero `Any` types allowed**:

```bash
uv run basedpyright  # Must pass with 0 errors
```

### Testing

- ≥90% code coverage required
- All tests must validate worker availability before running
- Tests must clean up jobs after completion

```bash
uv run pytest --cov=cl_client --cov-fail-under=90
```

### Plugin Modularity

Each plugin is completely independent:

- Separate file in `plugins/<name>.py`
- No cross-talk between plugins
- Easy to add/remove without affecting others

## Project Structure

```
cl_client/
├── pyproject.toml          # Dependencies, scripts, tool config
├── pyrightconfig.json      # Type checking config (separate from pyproject.toml)
├── src/cl_client/
│   ├── __init__.py
│   ├── config.py           # All configuration (NO hardcoding)
│   ├── compute_client.py   # Main client class
│   ├── auth.py             # Modular auth providers
│   ├── models.py           # Pydantic models
│   ├── exceptions.py       # Custom exceptions
│   ├── mqtt_monitor.py     # MQTT monitoring with subscription IDs
│   ├── cli.py              # CLI tool
│   └── plugins/            # Plugin clients (9 total)
│       ├── base.py
│       ├── clip_embedding.py
│       └── ...
└── tests/
    ├── test_client/
    ├── test_plugins/       # 9 plugin tests
    └── test_workflows/     # Multi-plugin workflows
```

## Contributing

1. Create feature branch
2. Implement changes with type hints
3. Run `uv run basedpyright` - must pass
4. Run `uv run pytest` - must pass with ≥90% coverage
5. Run `uv run ruff check src/ && uv run ruff format src/`
6. Submit PR

## Testing Guide

See [tests/README.md](./tests/README.md) for detailed testing instructions.
