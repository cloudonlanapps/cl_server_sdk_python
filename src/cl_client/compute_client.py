"""Core compute client for job management and monitoring.

Provides high-level interface for:
- Job submission and management (via plugin clients)
- Job status monitoring (MQTT primary, HTTP polling secondary)
- Worker capability tracking
- File downloads from job outputs
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import httpx

from .auth import AuthProvider, NoAuthProvider
from .config import ComputeClientConfig
from .mqtt_monitor import MQTTJobMonitor
from .server_config import ServerConfig

if TYPE_CHECKING:
    from pathlib import Path

    from .models import JobResponse, WorkerCapabilitiesResponse
    from .plugins.clip_embedding import ClipEmbeddingClient
    from .plugins.dino_embedding import DinoEmbeddingClient
    from .plugins.exif import ExifClient
    from .plugins.face_detection import FaceDetectionClient
    from .plugins.face_embedding import FaceEmbeddingClient
    from .plugins.hash import HashClient
    from .plugins.hls_streaming import HlsStreamingClient
    from .plugins.image_conversion import ImageConversionClient
    from .plugins.media_thumbnail import MediaThumbnailClient


class ComputeClient:
    """Main client for interacting with compute service.

    Provides:
    - REST API access to jobs and capabilities
    - MQTT-based job monitoring (primary workflow)
    - Optional HTTP polling (secondary workflow)
    - Worker capability validation
    - Modular authentication (injectable auth provider)
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        mqtt_broker: str | None = None,
        mqtt_port: int | None = None,
        auth_provider: AuthProvider | None = None,
        server_config: ServerConfig | None = None,
    ) -> None:
        """Initialize compute client.

        Args:
            base_url: Server base URL (overrides server_config.compute_url)
            timeout: Request timeout in seconds (default from ComputeClientConfig)
            mqtt_broker: MQTT broker host (overrides server_config.mqtt_broker)
            mqtt_port: MQTT broker port (overrides server_config.mqtt_port)
            auth_provider: Authentication provider (default: NoAuthProvider)
            server_config: Server configuration (default: from environment)

        Example (Simple):
            client = ComputeClient()  # Uses defaults

        Example (With auth):
            auth = JWTAuthProvider(token="...")
            client = ComputeClient(auth_provider=auth)

        Example (Custom config):
            config = ServerConfig(compute_url="https://api.example.com")
            client = ComputeClient(server_config=config)
        """
        # Get config for defaults (from parameter or environment)
        config = server_config or ServerConfig.from_env()

        # Use explicit parameters if provided, otherwise fall back to config
        self.base_url = base_url or config.compute_url
        self.timeout = timeout or ComputeClientConfig.DEFAULT_TIMEOUT
        self.auth = auth_provider or NoAuthProvider()

        # HTTP client for REST API
        self._session = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.auth.get_headers(),
        )

        # MQTT monitor for job status and worker capabilities
        # Use explicit parameters if provided, otherwise fall back to config
        mqtt_broker_final = mqtt_broker or config.mqtt_broker
        mqtt_port_final = mqtt_port or config.mqtt_port
        self._mqtt = MQTTJobMonitor(broker=mqtt_broker_final, port=mqtt_port_final)

    # ============================================================================
    # Job Management (REST API)
    # ============================================================================

    async def get_job(self, job_id: str) -> JobResponse:
        """Get job status via REST API.

        Args:
            job_id: Job ID to query

        Returns:
            Current job status

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        from .models import JobResponse

        endpoint = ComputeClientConfig.ENDPOINT_GET_JOB.format(job_id=job_id)
        response = await self._session.get(endpoint)
        response.raise_for_status()

        # response.json() returns Any, validate and cast
        data_raw: object = response.json()  # type: ignore[misc]
        if not isinstance(data_raw, dict):
            msg = f"Invalid response format: expected dict, got {type(data_raw)}"
            raise ValueError(msg)

        data = cast(dict[str, object], data_raw)
        return JobResponse(**data)  # type: ignore[arg-type]

    async def delete_job(self, job_id: str) -> None:
        """Delete job via REST API.

        Args:
            job_id: Job ID to delete

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        endpoint = ComputeClientConfig.ENDPOINT_DELETE_JOB.format(job_id=job_id)
        response = await self._session.delete(endpoint)
        response.raise_for_status()

    async def download_job_file(self, job_id: str, file_path: str, dest: Path) -> None:
        """Download file from job's output directory.

        Args:
            job_id: Job ID
            file_path: Relative file path within job directory (from task_output)
            dest: Local destination path to save file

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        endpoint = ComputeClientConfig.ENDPOINT_GET_JOB_FILE.format(
            job_id=job_id, file_path=file_path
        )
        response = await self._session.get(endpoint)
        response.raise_for_status()

        # Write file content to destination
        dest.write_bytes(response.content)

    # ============================================================================
    # Worker Capabilities (REST API)
    # ============================================================================

    async def get_capabilities(self) -> WorkerCapabilitiesResponse:
        """Get current worker capabilities via REST API.

        Returns:
            Worker capabilities summary

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        from .models import WorkerCapabilitiesResponse

        endpoint = ComputeClientConfig.ENDPOINT_CAPABILITIES
        response = await self._session.get(endpoint)
        response.raise_for_status()

        # response.json() returns Any, validate and cast
        data_raw: object = response.json()  # type: ignore[misc]
        if not isinstance(data_raw, dict):
            msg = f"Invalid response format: expected dict, got {type(data_raw)}"
            raise ValueError(msg)

        data = cast(dict[str, object], data_raw)
        return WorkerCapabilitiesResponse(**data)  # type: ignore[arg-type]

    async def wait_for_workers(
        self,
        required_capabilities: list[str] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Wait for workers with required capabilities to be available.

        Args:
            required_capabilities: List of required task types (e.g., ["clip_embedding"])
            timeout: Max wait time in seconds (default from config)

        Returns:
            True if all required workers available

        Raises:
            WorkerUnavailableError: If timeout expires before workers available
        """
        if not required_capabilities:
            return True

        timeout_val = timeout or ComputeClientConfig.WORKER_WAIT_TIMEOUT

        # Wait for each required capability
        for capability in required_capabilities:
            await self._mqtt.wait_for_capability(capability, timeout=timeout_val)

        return True

    # ============================================================================
    # Job Monitoring - MQTT (PRIMARY WORKFLOW)
    # ============================================================================

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

        Primary workflow for job monitoring. Callbacks are invoked on each status update.

        Args:
            job_id: Job ID to monitor
            on_progress: Called on each job update (queued → in_progress → ...)
            on_complete: Called only when job completes (status: completed/failed)

        Returns:
            Unique subscription ID for unsubscribing later

        Example:
            sub_id = client.subscribe_job_updates(
                job_id="abc-123",
                on_progress=lambda job: print(f"Progress: {job.progress}%"),
                on_complete=lambda job: print(f"Done: {job.status}")
            )
            # Later...
            client.unsubscribe(sub_id)
        """
        return self._mqtt.subscribe_job_updates(
            job_id=job_id, on_progress=on_progress, on_complete=on_complete
        )

    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from job updates using subscription ID.

        Args:
            subscription_id: Subscription ID returned from subscribe_job_updates()
        """
        self._mqtt.unsubscribe(subscription_id)

    # ============================================================================
    # Job Monitoring - HTTP Polling (SECONDARY WORKFLOW)
    # ============================================================================

    async def wait_for_job(
        self,
        job_id: str,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> JobResponse:
        """Poll job status via HTTP until completion (secondary workflow).

        Use this for simple synchronous workflows. For production use,
        prefer MQTT callback-based monitoring (subscribe_job_updates).

        Args:
            job_id: Job ID to monitor
            poll_interval: Polling interval in seconds (default from config)
            timeout: Max wait time in seconds (None = no timeout)

        Returns:
            Final job status (completed or failed)

        Raises:
            TimeoutError: If timeout expires before job completes
            httpx.HTTPStatusError: If HTTP requests fail
        """
        start_time = time.time()
        interval = poll_interval or ComputeClientConfig.DEFAULT_POLL_INTERVAL
        backoff = interval

        while True:
            job = await self.get_job(job_id)

            # Check if job is terminal
            if job.status in ["completed", "failed"]:
                return job

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                msg = f"Job {job_id} timeout after {timeout}s (status: {job.status})"
                raise TimeoutError(msg)

            # Wait with exponential backoff
            await asyncio.sleep(backoff)
            backoff = min(
                backoff * ComputeClientConfig.POLL_BACKOFF_MULTIPLIER,
                ComputeClientConfig.MAX_POLL_BACKOFF,
            )

    # ============================================================================
    # Plugin Access (Lazy-loaded properties)
    # ============================================================================

    @property
    def clip_embedding(self) -> ClipEmbeddingClient:
        """Access CLIP embedding plugin.

        Returns:
            ClipEmbeddingClient instance

        Example:
            job = await client.clip_embedding.embed_image(
                image=Path("photo.jpg"),
                wait=True
            )
            embedding = job.task_output["embedding"]
        """
        if not hasattr(self, "_clip_embedding"):
            from .plugins.clip_embedding import ClipEmbeddingClient

            self._clip_embedding = ClipEmbeddingClient(self)
        return self._clip_embedding  # type: ignore[has-type]

    @property
    def dino_embedding(self) -> DinoEmbeddingClient:
        """Access DINO embedding plugin.

        Returns:
            DinoEmbeddingClient instance

        Example:
            job = await client.dino_embedding.embed_image(
                image=Path("photo.jpg"),
                wait=True
            )
            embedding = job.task_output["embedding"]
        """
        if not hasattr(self, "_dino_embedding"):
            from .plugins.dino_embedding import DinoEmbeddingClient

            self._dino_embedding = DinoEmbeddingClient(self)
        return self._dino_embedding  # type: ignore[has-type]

    @property
    def exif(self) -> ExifClient:
        """Access EXIF extraction plugin.

        Returns:
            ExifClient instance

        Example:
            job = await client.exif.extract(
                image=Path("photo.jpg"),
                wait=True
            )
            metadata = job.task_output
        """
        if not hasattr(self, "_exif"):
            from .plugins.exif import ExifClient

            self._exif = ExifClient(self)
        return self._exif  # type: ignore[has-type]

    @property
    def face_detection(self) -> FaceDetectionClient:
        """Access face detection plugin.

        Returns:
            FaceDetectionClient instance

        Example:
            job = await client.face_detection.detect(
                image=Path("photo.jpg"),
                wait=True
            )
            faces = job.task_output["faces"]
        """
        if not hasattr(self, "_face_detection"):
            from .plugins.face_detection import FaceDetectionClient

            self._face_detection = FaceDetectionClient(self)
        return self._face_detection  # type: ignore[has-type]

    @property
    def face_embedding(self) -> FaceEmbeddingClient:
        """Access face embedding plugin.

        Returns:
            FaceEmbeddingClient instance

        Example:
            job = await client.face_embedding.embed_faces(
                image=Path("photo.jpg"),
                wait=True
            )
            embeddings = job.task_output["embeddings"]
        """
        if not hasattr(self, "_face_embedding"):
            from .plugins.face_embedding import FaceEmbeddingClient

            self._face_embedding = FaceEmbeddingClient(self)
        return self._face_embedding  # type: ignore[has-type]

    @property
    def hash(self) -> HashClient:
        """Access perceptual hash plugin.

        Returns:
            HashClient instance

        Example:
            job = await client.hash.compute(
                image=Path("photo.jpg"),
                wait=True
            )
            hashes = job.task_output
        """
        if not hasattr(self, "_hash"):
            from .plugins.hash import HashClient

            self._hash = HashClient(self)
        return self._hash  # type: ignore[has-type]

    @property
    def hls_streaming(self) -> HlsStreamingClient:
        """Access HLS streaming plugin.

        Returns:
            HlsStreamingClient instance

        Example:
            job = await client.hls_streaming.generate_manifest(
                video=Path("video.mp4"),
                wait=True
            )
            manifest = job.task_output["manifest_path"]
        """
        if not hasattr(self, "_hls_streaming"):
            from .plugins.hls_streaming import HlsStreamingClient

            self._hls_streaming = HlsStreamingClient(self)
        return self._hls_streaming  # type: ignore[has-type]

    @property
    def image_conversion(self) -> ImageConversionClient:
        """Access image conversion plugin.

        Returns:
            ImageConversionClient instance

        Example:
            job = await client.image_conversion.convert(
                image=Path("photo.png"),
                output_format="jpg",
                quality=90,
                wait=True
            )
            output = job.task_output["output_path"]
        """
        if not hasattr(self, "_image_conversion"):
            from .plugins.image_conversion import ImageConversionClient

            self._image_conversion = ImageConversionClient(self)
        return self._image_conversion  # type: ignore[has-type]

    @property
    def media_thumbnail(self) -> MediaThumbnailClient:
        """Access media thumbnail plugin.

        Returns:
            MediaThumbnailClient instance

        Example:
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256
            )
        """
        if not hasattr(self, "_media_thumbnail"):
            from .plugins.media_thumbnail import MediaThumbnailClient

            self._media_thumbnail = MediaThumbnailClient(self)
        return self._media_thumbnail  # type: ignore[has-type]

    # ============================================================================
    # Cleanup
    # ============================================================================

    async def close(self) -> None:
        """Close client connections and cleanup resources."""
        await self._session.aclose()
        self._mqtt.close()

    async def __aenter__(self) -> ComputeClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self.close()
