"""Configuration for compute client.

All endpoints, hosts, ports, and parameters are defined here as class variables.
This enables easy modification without changing code throughout the library.
"""


class ComputeClientConfig:
    """Configuration for compute client.

    All endpoints, hosts, ports, and parameters are defined here as class variables.
    This enables easy modification without changing code throughout the library.
    """

    # Server Connection
    DEFAULT_HOST: str = "localhost"
    DEFAULT_PORT: int = 8002
    DEFAULT_BASE_URL: str = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    DEFAULT_TIMEOUT: float = 30.0

    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CAPABILITY_TOPIC_PREFIX: str = "inference/workers"
    MQTT_JOB_EVENTS_TOPIC: str = "inference/events"  # Single topic for all job events

    # Core API Endpoints
    ENDPOINT_GET_JOB: str = "/jobs/{job_id}"
    ENDPOINT_DELETE_JOB: str = "/jobs/{job_id}"
    ENDPOINT_GET_JOB_FILE: str = "/jobs/{job_id}/files/{file_path}"
    ENDPOINT_CAPABILITIES: str = "/capabilities"

    # Plugin Endpoints (from cl_ml_tools)
    PLUGIN_ENDPOINTS: dict[str, str] = {
        "clip_embedding": "/jobs/clip_embedding",
        "dino_embedding": "/jobs/dino_embedding",
        "exif": "/jobs/exif",
        "face_detection": "/jobs/face_detection",
        "face_embedding": "/jobs/face_embedding",
        "hash": "/jobs/hash",
        "hls_streaming": "/jobs/hls_streaming",
        "image_conversion": "/jobs/image_conversion",
        "media_thumbnail": "/jobs/media_thumbnail",
    }

    # Job Monitoring Configuration
    DEFAULT_POLL_INTERVAL: float = 1.0
    MAX_POLL_BACKOFF: float = 10.0
    POLL_BACKOFF_MULTIPLIER: float = 1.5

    # Worker Validation
    WORKER_WAIT_TIMEOUT: float = 30.0
    WORKER_CAPABILITY_CHECK_INTERVAL: float = 1.0

    @classmethod
    def get_plugin_endpoint(cls, task_type: str) -> str:
        """Get endpoint for plugin task type.

        Args:
            task_type: Plugin task type (e.g., "clip_embedding")

        Returns:
            Endpoint path

        Raises:
            ValueError: If task_type not found
        """
        if task_type not in cls.PLUGIN_ENDPOINTS:
            msg = (
                f"Unknown task type: {task_type}. "
                f"Available: {list(cls.PLUGIN_ENDPOINTS.keys())}"
            )
            raise ValueError(msg)
        return cls.PLUGIN_ENDPOINTS[task_type]
