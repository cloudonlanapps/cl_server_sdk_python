# QUICK – Test Commands

## Run all unit tests

```bash
uv run pytest -m "not integration" --no-cov
```

Duration: ~2 seconds
No external services required

## Run all tests

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
