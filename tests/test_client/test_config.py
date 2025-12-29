"""Tests for config.py"""

import pytest
from cl_client.config import ComputeClientConfig


def test_default_values():
    """Test default configuration values."""
    assert ComputeClientConfig.DEFAULT_HOST == "localhost"
    assert ComputeClientConfig.DEFAULT_PORT == 8002
    assert ComputeClientConfig.DEFAULT_BASE_URL == "http://localhost:8002"
    assert ComputeClientConfig.DEFAULT_TIMEOUT == 30.0


def test_mqtt_config():
    """Test MQTT configuration values."""
    assert ComputeClientConfig.MQTT_BROKER_HOST == "localhost"
    assert ComputeClientConfig.MQTT_BROKER_PORT == 1883
    assert ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX == "inference/workers"
    assert ComputeClientConfig.MQTT_JOB_STATUS_TOPIC_PREFIX == "inference/job_status"


def test_core_endpoints():
    """Test core API endpoint templates."""
    assert ComputeClientConfig.ENDPOINT_GET_JOB == "/jobs/{job_id}"
    assert ComputeClientConfig.ENDPOINT_DELETE_JOB == "/jobs/{job_id}"
    assert ComputeClientConfig.ENDPOINT_GET_JOB_FILE == "/jobs/{job_id}/files/{file_path}"
    assert ComputeClientConfig.ENDPOINT_CAPABILITIES == "/capabilities"


def test_plugin_endpoints():
    """Test all plugin endpoints are defined."""
    plugins = ComputeClientConfig.PLUGIN_ENDPOINTS

    # Check all expected plugins exist
    expected_plugins = [
        "clip_embedding",
        "dino_embedding",
        "exif",
        "face_detection",
        "face_embedding",
        "hash",
        "hls_streaming",
        "image_conversion",
        "media_thumbnail",
    ]

    for plugin in expected_plugins:
        assert plugin in plugins
        assert plugins[plugin].startswith("/jobs/")


def test_get_plugin_endpoint_success():
    """Test get_plugin_endpoint returns correct endpoint."""
    endpoint = ComputeClientConfig.get_plugin_endpoint("clip_embedding")
    assert endpoint == "/jobs/clip_embedding"

    endpoint = ComputeClientConfig.get_plugin_endpoint("media_thumbnail")
    assert endpoint == "/jobs/media_thumbnail"


def test_get_plugin_endpoint_invalid():
    """Test get_plugin_endpoint raises ValueError for unknown plugin."""
    with pytest.raises(ValueError) as exc_info:
        ComputeClientConfig.get_plugin_endpoint("unknown_plugin")

    error_msg = str(exc_info.value)
    assert "Unknown task type" in error_msg
    assert "unknown_plugin" in error_msg
    assert "Available:" in error_msg


def test_job_monitoring_config():
    """Test job monitoring configuration."""
    assert ComputeClientConfig.DEFAULT_POLL_INTERVAL == 1.0
    assert ComputeClientConfig.MAX_POLL_BACKOFF == 10.0
    assert ComputeClientConfig.POLL_BACKOFF_MULTIPLIER == 1.5


def test_worker_validation_config():
    """Test worker validation configuration."""
    assert ComputeClientConfig.WORKER_WAIT_TIMEOUT == 30.0
    assert ComputeClientConfig.WORKER_CAPABILITY_CHECK_INTERVAL == 1.0
