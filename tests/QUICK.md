# QUICK – Test Commands

## Run all tests

```bash
uv run pytest tests/  --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin
```

- This also runs test coverage
- Servers must be started before triggering this test

## Run all tests **except** integration tests (unit tests only)

```bash
uv run pytest -m "not integration" --no-cov
```

## Run only integration tests

```bash
uv run pytest -m "integration" --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin --no-cov
```

- Servers must be started before triggering this test

## Collect all tests (no execution)

```bash
uv run pytest --collect-only -q --no-cov
```
