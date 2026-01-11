"""Base plugin client for job submission.

Provides common functionality for all plugin clients:
- Job submission with file uploads
- MQTT callback-based monitoring (primary)
- Optional HTTP polling (secondary)
- Configuration-based endpoint lookup
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ..config import ComputeClientConfig

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class BasePluginClient:
    """Base class for plugin-specific clients.

    Each plugin client extends this to provide typed, plugin-specific methods.
    Handles job submission, file uploads, and monitoring.
    """

    def __init__(self, client: ComputeClient, task_type: str) -> None:
        """Initialize plugin client.

        Args:
            client: ComputeClient instance
            task_type: Plugin task type (used to lookup endpoint from config)
        """
        self.client = client
        self.task_type: str = task_type

        # Get endpoint from config (NOT hardcoded)
        self.endpoint: str = ComputeClientConfig.get_plugin_endpoint(task_type)

    async def submit_job(
        self,
        params: dict[str, object] | None = None,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None = None,
        on_complete: Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None = None,
    ) -> JobResponse:
        """Submit job without files (STUB for future file-less plugins).

        This method is a stub for future plugins that don't require file uploads.
        Currently, all 9 plugins require files, so this raises NotImplementedError.

        Args:
            params: Task parameters (plugin-specific)
            priority: Job priority (0-10)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (primary workflow)
            on_complete: Callback for job completion (primary workflow)

        Returns:
            JobResponse with job details

        Raises:
            NotImplementedError: All current plugins require file uploads (use submit_with_files)
        """
        _ = (params, priority, wait, timeout, on_progress, on_complete)
        msg = (
            f"{self.task_type} requires file uploads. "
            "Use submit_with_files() instead. "
            "This method is reserved for future file-less plugins."
        )
        raise NotImplementedError(msg)

    async def submit_with_files(
        self,
        files: dict[str, Path],
        params: dict[str, object] | None = None,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None = None,
        on_complete: Callable[[JobResponse], None] | Callable[[JobResponse], Awaitable[None]] | None = None,
    ) -> JobResponse:
        """Submit job with file uploads (PRIMARY METHOD).

        Uploads files via multipart/form-data and optionally monitors completion.
        Uses MQTT callbacks (primary) or HTTP polling (secondary) based on parameters.

        Args:
            files: Dict mapping field names to file paths (e.g., {"image": Path("img.jpg")})
            params: Additional task parameters (plugin-specific)
            priority: Job priority (0-10)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with job details
            - If wait=True: Returns final job status (completed/failed)
            - If callbacks provided: Returns initial job status, callbacks invoked later
            - Otherwise: Returns initial job status (queued)

        Raises:
            FileNotFoundError: If any file doesn't exist
            httpx.HTTPStatusError: If request fails

        Example (MQTT callbacks - primary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                on_complete=lambda j: print(f"Done: {j.status}")
            )

        Example (HTTP polling - secondary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                wait=True,
                timeout=30.0
            )
        """
        # Prepare multipart file uploads
        files_data: dict[str, tuple[str, object, str]] = {}
        for name, path in files.items():
            if not path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            files_data[name] = (
                path.name,
                path.open("rb"),
                self._guess_mime_type(path),
            )

        # Prepare form data
        form_data: dict[str, object] = {"priority": str(priority)}
        if params:
            # Flatten params into form fields
            for key, value in params.items():
                form_data[key] = str(value) if value is not None else ""

        try:
            # Submit job (accessing protected _session is intentional for plugin clients)
            response = await self.client._session.post(  # type: ignore[reportPrivateUsage]
                self.endpoint,
                files=files_data,  # type: ignore[arg-type]
                data=form_data,
            )
            response.raise_for_status()

            # Parse response - may be minimal (just job_id)
            data_raw: object = response.json()  # type: ignore[misc]
            if not isinstance(data_raw, dict):
                msg = f"Invalid response format: expected dict, got {type(data_raw)}"
                raise ValueError(msg)

            data = cast(dict[str, object], data_raw)

            # Get job_id from response
            job_id = str(data.get("job_id", ""))
            if not job_id:
                msg = "Server response missing job_id"
                raise ValueError(msg)

            # Fetch full job details (submission response may be minimal)
            job = await self.client.get_job(job_id)

            # Subscribe to MQTT callbacks if provided
            if on_progress or on_complete:
                self.client.subscribe_job_updates(
                    job_id=job.job_id, on_progress=on_progress, on_complete=on_complete
                )

            # Wait for completion if requested (secondary workflow)
            if wait:
                job = await self.client.wait_for_job(job_id=job.job_id, timeout=timeout)

            return job

        finally:
            # Close file handles
            for _name, file_tuple in files_data.items():
                file_handle = file_tuple[1]
                if hasattr(file_handle, "close"):
                    file_handle.close()  # type: ignore[union-attr]

    def _guess_mime_type(self, path: Path) -> str:
        """Guess MIME type from file extension.

        Args:
            path: File path

        Returns:
            MIME type string
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"
