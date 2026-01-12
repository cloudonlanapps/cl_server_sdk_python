"""MQTT monitoring for job status and worker capabilities.

Primary job monitoring mechanism via MQTT callback registration.
Provides real-time job status updates and worker capability tracking.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import paho.mqtt.client as mqtt  # type: ignore[import-untyped]

from .config import ComputeClientConfig

if TYPE_CHECKING:
    from .models import JobResponse, WorkerCapability

logger = logging.getLogger(__name__)


class MQTTJobMonitor:
    """MQTT monitor for job status and worker capabilities."""

    def __init__(
        self,
        broker: str | None = None,
        port: int | None = None,
        connect_timeout: float = 5.0,
    ) -> None:
        """Initialize MQTT monitor.

        Args:
            broker: MQTT broker host (default from config)
            port: MQTT broker port (default from config)
            connect_timeout: Timeout for initial connection in seconds (default 5.0)
        """
        self.broker = broker or ComputeClientConfig.MQTT_BROKER_HOST
        self.port = port or ComputeClientConfig.MQTT_BROKER_PORT

        # Job subscriptions: subscription_id -> (job_id, callbacks)
        self._job_subscriptions: dict[
            str,
            tuple[
                str,
                Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None,
                Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None,
            ],
        ] = {}

        # Worker capability tracking
        self._workers: dict[str, WorkerCapability] = {}
        self._worker_callbacks: list[Callable[[str, WorkerCapability | None], None]] = []

        # Connection event for blocking until connected
        self._connect_event = threading.Event()
        self._connected = False

        # Event loop for scheduling async callbacks from MQTT thread
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, will be set when connect() is called
            self._event_loop = None

        # MQTT client
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # type: ignore[attr-defined]
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        # Connect to broker and wait for connection
        self._connect()

        # Wait for connection to establish (blocking)
        if not self._connect_event.wait(timeout=connect_timeout):
            logger.warning(f"MQTT connection timeout after {connect_timeout}s")
        elif not self._connected:
            logger.warning("MQTT connection failed")

    def _connect(self) -> None:
        """Connect to MQTT broker."""
        try:
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,  # type: ignore[name-defined]
        rc: mqtt.ReasonCode,  # type: ignore[name-defined]
        properties: mqtt.Properties | None = None,  # type: ignore[name-defined]
    ) -> None:
        """Handle MQTT connection."""
        _ = (client, userdata, flags, properties)
        if rc.is_failure:  # type: ignore[attr-defined]
            logger.error(f"MQTT connection failed: {rc}")
            self._connected = False
        else:
            logger.info("MQTT connected successfully")
            self._connected = True

            # Subscribe to worker capabilities
            capability_topic = f"{ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX}/+"
            self._client.subscribe(capability_topic)
            logger.debug(f"Subscribed to worker capabilities: {capability_topic}")

            # Subscribe to job events (single topic for all jobs)
            events_topic = ComputeClientConfig.MQTT_JOB_EVENTS_TOPIC
            self._client.subscribe(events_topic)
            logger.debug(f"Subscribed to job events: {events_topic}")

        # Signal connection attempt complete (success or failure)
        self._connect_event.set()

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT messages."""
        _ = (client, userdata)

        try:
            # Check if it's a worker capability message
            if msg.topic.startswith(ComputeClientConfig.MQTT_CAPABILITY_TOPIC_PREFIX):
                self._handle_worker_capability(msg)
            # Check if it's a job event message
            elif msg.topic == ComputeClientConfig.MQTT_JOB_EVENTS_TOPIC:
                self._handle_job_event(msg)
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}", exc_info=True)

    def _handle_worker_capability(self, msg: mqtt.MQTTMessage) -> None:
        """Handle worker capability message."""
        # Empty payload = worker disconnect (LWT)
        if not msg.payload:
            worker_id = msg.topic.split("/")[-1]
            self._remove_worker(worker_id)
            return

        # Parse capability message
        try:
            # json.loads returns Any, which we validate immediately
            if not isinstance(
                data_parsed := json.loads(msg.payload.decode()),  # type: ignore[misc]
                dict,
            ):
                logger.warning("Invalid worker capability message: not a dict")
                return

            # Safe to cast after isinstance check
            data = cast(dict[str, object], data_parsed)

            from .models import WorkerCapability

            # Extract and validate capabilities list
            caps_raw = data.get("capabilities", [])
            if not isinstance(caps_raw, list):
                caps_raw = []
            # Cast to list[object] for iteration
            caps_list = cast(list[object], caps_raw)
            capabilities_list: list[str] = []
            for item in caps_list:
                if item is not None:
                    capabilities_list.append(str(item))

            # Extract and validate other fields
            capability = WorkerCapability(
                worker_id=str(data.get("id", "")) if data.get("id") is not None else "",
                capabilities=capabilities_list,
                idle_count=(
                    int(idle_val)
                    if isinstance(idle_val := data.get("idle_count", 0), (int, float))
                    else 0
                ),
                timestamp=(
                    int(ts_val)
                    if isinstance(ts_val := data.get("timestamp", 0), (int, float))
                    else 0
                ),
            )

            self._update_worker(capability)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Invalid worker capability message: {e}")

    def _handle_job_event(self, msg: mqtt.MQTTMessage) -> None:
        """Handle job event message from inference/events topic."""
        if not msg.payload:
            return

        try:
            # Parse event message
            if not isinstance(
                data_parsed := json.loads(msg.payload.decode()),  # type: ignore[misc]
                dict,
            ):
                logger.warning("Invalid job event message: not a dict")
                return

            data = cast(dict[str, object], data_parsed)

            # Extract event fields
            job_id_val = data.get("job_id")
            event_type_val = data.get("event_type")
            progress_val = data.get("progress", 0)
            timestamp_val = data.get("timestamp", 0)

            if not job_id_val or not event_type_val:
                logger.warning("Job event missing required fields")
                return

            job_id = str(job_id_val)
            event_type = str(event_type_val)

            # Map event_type to status
            status_map = {
                "queued": "queued",
                "processing": "in_progress",
                "completed": "completed",
                "failed": "failed",
            }
            status = status_map.get(event_type, event_type)

            # Find matching subscriptions for this job
            for _sub_id, (sub_job_id, on_progress, on_complete) in list(
                self._job_subscriptions.items()
            ):
                if sub_job_id != job_id:
                    continue

                # Create minimal JobResponse from event data
                # Note: We don't have full job details from event, just status/progress
                from .models import JobResponse

                job = JobResponse(
                    job_id=job_id,
                    task_type="unknown",  # Not in event message
                    status=status,
                    progress=int(progress_val) if isinstance(progress_val, (int, float)) else 0,
                    created_at=int(timestamp_val) if isinstance(timestamp_val, (int, float)) else 0,
                    params={},
                    task_output=None,
                    error_message=None,
                    priority=5,
                    updated_at=None,
                    started_at=None,
                    completed_at=None,
                )

                # Call on_progress callback for any status update
                if on_progress:
                    try:
                        # Support both sync and async callbacks
                        import inspect

                        if inspect.iscoroutinefunction(on_progress):
                            # Schedule coroutine on event loop from MQTT thread
                            if self._event_loop and self._event_loop.is_running():
                                asyncio.run_coroutine_threadsafe(on_progress(job), self._event_loop)
                            else:
                                logger.warning(
                                    "Event loop not available for async on_progress callback"
                                )
                        else:
                            on_progress(job)
                    except Exception as e:
                        logger.error(f"Error in on_progress callback: {e}", exc_info=True)

                # Call on_complete callback only for terminal states
                if status in ["completed", "failed"] and on_complete:
                    try:
                        # Support both sync and async callbacks
                        import inspect

                        if inspect.iscoroutinefunction(on_complete):
                            # Schedule coroutine on event loop from MQTT thread
                            if self._event_loop and self._event_loop.is_running():
                                asyncio.run_coroutine_threadsafe(on_complete(job), self._event_loop)
                            else:
                                logger.warning(
                                    "Event loop not available for async on_complete callback"
                                )
                        else:
                            on_complete(job)
                    except Exception as e:
                        logger.error(f"Error in on_complete callback: {e}", exc_info=True)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Invalid job event message: {e}")

    def _update_worker(self, capability: WorkerCapability) -> None:
        """Update worker capability state."""
        self._workers[capability.worker_id] = capability

        # Notify callbacks
        for callback in self._worker_callbacks:
            try:
                callback(capability.worker_id, capability)
            except Exception as e:
                logger.error(f"Error in worker callback: {e}", exc_info=True)

    def _remove_worker(self, worker_id: str) -> None:
        """Remove worker from tracking."""
        if worker_id in self._workers:
            del self._workers[worker_id]

            # Notify callbacks
            for callback in self._worker_callbacks:
                try:
                    callback(worker_id, None)
                except Exception as e:
                    logger.error(f"Error in worker callback: {e}", exc_info=True)

    def subscribe_job_updates(
        self,
        job_id: str,
        on_progress: Callable[[JobResponse], None]
        | Callable[[JobResponse], Awaitable[None]]
        | None = None,
        on_complete: Callable[[JobResponse], None]
        | Callable[[JobResponse], Awaitable[None]]
        | None = None,
    ) -> str:
        """Subscribe to job status updates via MQTT.

        Returns unique subscription ID. Supports multiple subscriptions per job.

        Captures the running event loop for async callbacks.

        Args:
            job_id: Job ID to monitor
            on_progress: Called on each job update (queued → in_progress → ...)
            on_complete: Called only when job completes (status: completed/failed)

        Returns:
            Unique subscription ID for unsubscribing later

        Example:
            sub_id = monitor.subscribe_job_updates(
                job_id="abc-123",
                on_progress=lambda job: print(f"Progress: {job.progress}%"),
                on_complete=lambda job: print(f"Done: {job.status}")
            )
            # Later...
            monitor.unsubscribe(sub_id)
        """
        # Generate unique subscription ID
        subscription_id = str(uuid.uuid4())

        # Capture event loop for async callbacks (if not already captured)
        if self._event_loop is None:
            try:
                self._event_loop = asyncio.get_running_loop()
                logger.debug("Captured event loop for async MQTT callbacks")
            except RuntimeError:
                # No running loop yet, will be captured later or async callbacks will warn
                pass

        # Store subscription (no need to subscribe to MQTT - already subscribed to events topic)
        self._job_subscriptions[subscription_id] = (job_id, on_progress, on_complete)

        logger.debug(f"Registered callbacks for job {job_id} (sub_id: {subscription_id})")

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from job updates using subscription ID.

        Args:
            subscription_id: Subscription ID returned from subscribe_job_updates()
        """
        if subscription_id not in self._job_subscriptions:
            logger.warning(f"Subscription not found: {subscription_id}")
            return

        job_id, _, _ = self._job_subscriptions[subscription_id]
        del self._job_subscriptions[subscription_id]

        logger.debug(f"Removed callbacks for job {job_id} (sub_id: {subscription_id})")

    def get_worker_capabilities(self) -> dict[str, WorkerCapability]:
        """Get current worker capabilities (synchronous, from cached state)."""
        return self._workers.copy()

    def subscribe_worker_updates(
        self, callback: Callable[[str, WorkerCapability | None], None]
    ) -> None:
        """Subscribe to worker capability changes.

        Callback invoked when worker connects/disconnects or capabilities change.

        Args:
            callback: Function called with (worker_id, capability).
                     capability=None indicates worker disconnect.
        """
        self._worker_callbacks.append(callback)

    async def wait_for_capability(self, task_type: str, timeout: float | None = None) -> bool:
        """Wait for worker with specific capability to be available.

        Args:
            task_type: Required capability (e.g., "clip_embedding")
            timeout: Max wait time in seconds

        Returns:
            True if worker available, False if timeout

        Raises:
            WorkerUnavailableError: If timeout expires
        """
        from .exceptions import WorkerUnavailableError

        timeout_val = timeout or ComputeClientConfig.WORKER_WAIT_TIMEOUT
        check_interval = ComputeClientConfig.WORKER_CAPABILITY_CHECK_INTERVAL

        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if any worker has the required capability
            for worker in self._workers.values():
                if task_type in worker.capabilities and worker.idle_count > 0:
                    return True

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout_val:
                # Get current capabilities for error message
                capabilities: dict[str, int] = {}
                for worker in self._workers.values():
                    for cap in worker.capabilities:
                        capabilities[cap] = capabilities.get(cap, 0) + worker.idle_count

                raise WorkerUnavailableError(task_type, capabilities)

            # Wait before checking again
            await asyncio.sleep(check_interval)

    def close(self) -> None:
        """Close MQTT connection and cleanup."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
        logger.info("MQTT monitor closed")
