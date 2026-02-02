"""Tests for mqtt_monitor.py"""

import json
from unittest.mock import MagicMock, patch

import pytest

from cl_client.config import ComputeClientConfig
from cl_client.exceptions import WorkerUnavailableError
from cl_client.models import JobResponse, WorkerCapability
from cl_client.mqtt_monitor import MQTTJobMonitor


@pytest.fixture
def mock_mqtt_client():
    """Create a mock MQTT client."""
    with patch("cl_client.mqtt_monitor.mqtt.Client") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def monitor(mock_mqtt_client, mqtt_url):
    """Create MQTT monitor with mocked client and mqtt_url."""
    return MQTTJobMonitor(mqtt_url=mqtt_url)


def test_init_connects_to_broker(mock_mqtt_client, mqtt_url):
    """Test that monitor connects to MQTT broker on init."""
    monitor = MQTTJobMonitor(mqtt_url=mqtt_url)

    # Verify connection was attempted
    mock_mqtt_client.connect.assert_called_once_with(
        "localhost",
        1883,
        keepalive=60,
    )
    mock_mqtt_client.loop_start.assert_called_once()


def test_init_with_custom_mqtt_url():
    """Test monitor with custom mqtt_url settings."""
    with patch("cl_client.mqtt_monitor.mqtt.Client") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        monitor = MQTTJobMonitor(mqtt_url="mqtt://custom-broker:1234")

        assert monitor.broker == "custom-broker"
        assert monitor.port == 1234
        assert monitor.mqtt_url == "mqtt://custom-broker:1234"
        mock_instance.connect.assert_called_once_with("custom-broker", 1234, keepalive=60)





def test_subscribe_job_updates_returns_subscription_id(monitor, mock_mqtt_client):
    """Test that subscribe_job_updates returns unique subscription ID."""
    job_id = "test-job-123"

    sub_id = monitor.subscribe_job_updates(job_id=job_id)

    # Verify subscription ID is a UUID string
    assert isinstance(sub_id, str)
    assert len(sub_id) == 36  # UUID format

    # Verify subscription was registered (MQTT subscribe happens once during init)
    assert sub_id in monitor._job_subscriptions


def test_multiple_subscriptions_same_job(monitor, mock_mqtt_client):
    """Test multiple subscriptions for the same job."""
    job_id = "test-job-123"

    # Create two subscriptions for same job
    sub_id_1 = monitor.subscribe_job_updates(job_id=job_id)
    sub_id_2 = monitor.subscribe_job_updates(job_id=job_id)

    # Verify different subscription IDs
    assert sub_id_1 != sub_id_2

    # Both should be stored
    assert sub_id_1 in monitor._job_subscriptions
    assert sub_id_2 in monitor._job_subscriptions


def test_unsubscribe_with_subscription_id(monitor, mock_mqtt_client):
    """Test unsubscribe using subscription ID."""
    job_id = "test-job-123"

    sub_id = monitor.subscribe_job_updates(job_id=job_id)
    monitor.unsubscribe(sub_id)

    # Verify subscription removed
    assert sub_id not in monitor._job_subscriptions

    # MQTT topic remains subscribed (single events topic for all jobs)
    # No unsubscribe should be called
    mock_mqtt_client.unsubscribe.assert_not_called()


def test_unsubscribe_keeps_topic_if_other_subs_exist(monitor, mock_mqtt_client):
    """Test that MQTT topic remains subscribed if other subscriptions exist."""
    job_id = "test-job-123"

    # Create two subscriptions
    sub_id_1 = monitor.subscribe_job_updates(job_id=job_id)
    sub_id_2 = monitor.subscribe_job_updates(job_id=job_id)

    # Reset mock to clear previous calls
    mock_mqtt_client.reset_mock()

    # Unsubscribe first one
    monitor.unsubscribe(sub_id_1)

    # Verify first subscription removed
    assert sub_id_1 not in monitor._job_subscriptions
    assert sub_id_2 in monitor._job_subscriptions

    # Now unsubscribe second one
    monitor.unsubscribe(sub_id_2)

    # Verify both subscriptions removed
    assert sub_id_2 not in monitor._job_subscriptions

    # MQTT topic remains subscribed (single events topic for all jobs)
    mock_mqtt_client.unsubscribe.assert_not_called()


def test_two_callback_system(monitor, mock_mqtt_client):
    """Test on_progress and on_complete callbacks."""
    job_id = "test-job-123"

    progress_calls = []
    complete_calls = []

    def on_progress(job: JobResponse):
        progress_calls.append(job)

    def on_complete(job: JobResponse):
        complete_calls.append(job)

    # Subscribe with both callbacks
    sub_id = monitor.subscribe_job_updates(
        job_id=job_id, on_progress=on_progress, on_complete=on_complete
    )

    # Simulate job status update (in_progress)
    job_in_progress = JobResponse(
        job_id=job_id,
        task_type="test_task",
        status="processing",
        progress=50,
        created_at=1234567890,
    )

    # Manually trigger the handler (simulating MQTT message)
    mock_msg = MagicMock()
    mock_msg.topic = ComputeClientConfig.MQTT_JOB_EVENTS_TOPIC
    mock_msg.payload = json.dumps(
        {
            "job_id": job_id,
            "event_type": "processing",
            "progress": 50,
            "timestamp": 1234567890,
        }
    ).encode()

    monitor._handle_job_event(mock_msg)

    # on_progress should be called, on_complete should NOT
    assert len(progress_calls) == 1
    assert len(complete_calls) == 0

    # Simulate job completion
    mock_msg.payload = json.dumps(
        {
            "job_id": job_id,
            "event_type": "completed",
            "progress": 100,
            "timestamp": 1234567891,
        }
    ).encode()

    monitor._handle_job_event(mock_msg)

    # Both callbacks should be called now
    assert len(progress_calls) == 2  # Called for both updates
    assert len(complete_calls) == 1  # Only called for completion


def test_worker_capability_tracking(monitor, mock_mqtt_client):
    """Test worker capability message handling."""
    worker_id = "worker-123"

    # Simulate worker capability message
    mock_msg = MagicMock()
    mock_msg.topic = f"{ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX}/{worker_id}"
    mock_msg.payload = json.dumps(
        {
            "worker_id": worker_id,
            "capabilities": ["clip_embedding", "dino_embedding"],
            "idle_count": 1,
            "timestamp": 1234567890,
        }
    ).encode()

    monitor._handle_worker_capability(mock_msg)

    # Verify worker is tracked
    workers = monitor.get_worker_capabilities()
    assert worker_id in workers
    assert workers[worker_id].worker_id == worker_id
    assert "clip_embedding" in workers[worker_id].capabilities
    assert "dino_embedding" in workers[worker_id].capabilities
    assert workers[worker_id].idle_count == 1


def test_worker_disconnect_lwt(monitor, mock_mqtt_client):
    """Test worker disconnect (empty payload = Last Will & Testament)."""
    worker_id = "worker-123"

    # First, add a worker
    monitor._workers[worker_id] = WorkerCapability(
        worker_id=worker_id, capabilities=["test"], idle_count=1, timestamp=1234567890
    )

    # Simulate disconnect (empty payload)
    mock_msg = MagicMock()
    mock_msg.topic = f"{ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX}/{worker_id}"
    mock_msg.payload = b""

    monitor._handle_worker_capability(mock_msg)

    # Verify worker is removed
    workers = monitor.get_worker_capabilities()
    assert worker_id not in workers


def test_subscribe_worker_updates(monitor, mock_mqtt_client):
    """Test subscribing to worker capability changes."""
    worker_id = "worker-123"
    callback_calls = []

    def callback(wid: str, capability: WorkerCapability | None):
        callback_calls.append((wid, capability))

    monitor.subscribe_worker_updates(callback)

    # Simulate worker capability message
    mock_msg = MagicMock()
    mock_msg.topic = f"{ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX}/{worker_id}"
    mock_msg.payload = json.dumps(
        {
            "worker_id": worker_id,
            "capabilities": ["test"],
            "idle_count": 1,
            "timestamp": 1234567890,
        }
    ).encode()

    monitor._handle_worker_capability(mock_msg)

    # Verify callback was called
    assert len(callback_calls) == 1
    assert callback_calls[0][0] == worker_id
    assert callback_calls[0][1] is not None
    assert callback_calls[0][1].worker_id == worker_id


@pytest.mark.asyncio
async def test_wait_for_capability_success(monitor, mock_mqtt_client):
    """Test wait_for_capability succeeds when worker available."""
    # Add a worker with the required capability
    monitor._workers["worker-123"] = WorkerCapability(
        worker_id="worker-123",
        capabilities=["clip_embedding"],
        idle_count=1,
        timestamp=1234567890,
    )

    result = await monitor.wait_for_capability("clip_embedding", timeout=1.0)

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_capability_timeout(monitor, mock_mqtt_client):
    """Test wait_for_capability raises error on timeout."""
    # No workers with required capability
    with pytest.raises(WorkerUnavailableError) as exc_info:
        await monitor.wait_for_capability("clip_embedding", timeout=0.5)

    assert "clip_embedding" in str(exc_info.value)


def test_close(monitor, mock_mqtt_client):
    """Test monitor cleanup."""
    monitor.close()

    mock_mqtt_client.loop_stop.assert_called_once()
    mock_mqtt_client.disconnect.assert_called_once()
    assert monitor._connected is False


def test_invalid_json_message_handling(monitor, mock_mqtt_client):
    """Test that invalid JSON messages are handled gracefully."""
    mock_msg = MagicMock()
    mock_msg.topic = ComputeClientConfig.MQTT_JOB_EVENTS_TOPIC
    mock_msg.payload = b"invalid json {{"

    # Should not raise exception
    monitor._handle_job_event(mock_msg)


def test_invalid_dict_message_handling(monitor, mock_mqtt_client):
    """Test that non-dict JSON messages are handled gracefully."""
    mock_msg = MagicMock()
    mock_msg.topic = ComputeClientConfig.MQTT_JOB_EVENTS_TOPIC
    mock_msg.payload = b'"not a dict"'

    # Should not raise exception
    monitor._handle_job_event(mock_msg)
