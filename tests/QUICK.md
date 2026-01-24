# QUICK – Test Commands

## Run all unit tests

```bash
uv run pytest -m "not integration" --no-cov
```

Duration: ~2 seconds
No external services required

## Run all tests with coverage (default)

```bash
uv run pytest tests/ --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin
```

Duration: ~30 seconds
Coverage: 90% minimum required (HTML + terminal reports)
Servers must be started first: Auth (8010), Store (8011), Compute (8012)

## Run all integration tests

```bash
uv run pytest -m "integration" --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin --no-cov
```

Duration: ~28 seconds
Servers must be started first: Auth (8010), Store (8011), Compute (8012)

## Run specific test file

```bash
uv run pytest tests/test_client/test_auth.py -v
uv run pytest tests/test_integration/test_clip_embedding_integration.py -v --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin
```

Duration: Varies (unit tests ~0.1s, integration tests ~2-5s)

## Run single test function

```bash
uv run pytest tests/test_client/test_auth.py::test_no_auth_provider -v
uv run pytest tests/test_integration/test_clip_embedding_integration.py::test_clip_embedding_http_polling -v --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin
```

## Run tests matching keyword

```bash
# All auth-related tests
uv run pytest -k "auth" -v

# All plugin tests
uv run pytest -k "embedding or face or hash" -v

# All MQTT tests
uv run pytest -k "mqtt" -v
```

## Run without coverage (faster)

```bash
uv run pytest --no-cov
```

Duration: ~15-20 seconds (faster than with coverage)

## View coverage report

```bash
open htmlcov/index.html
```

Opens HTML coverage report in browser after running tests with coverage

## Override coverage threshold

```bash
uv run pytest --cov-fail-under=0
```

For debugging - allows tests to pass with low coverage

## Type checking

```bash
uv run basedpyright
```

Runs strict type checking (must pass with 0 errors)
