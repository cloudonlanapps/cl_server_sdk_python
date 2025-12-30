"""Integration tests for cl_client.

These tests require:
- Compute server running (use: uv run compute-server --no-auth)
- Worker running (use: uv run compute-worker --worker-id test-worker --tasks media_thumbnail)
- MQTT broker running (mosquitto)
- Test media files available

To run:
    uv run pytest tests/test_integration/ -v
"""
