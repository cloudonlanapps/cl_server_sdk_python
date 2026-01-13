"""Custom exceptions for compute client."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import JobResponse


class ComputeClientError(Exception):
    """Base exception for compute client errors."""

    pass


class JobNotFoundError(ComputeClientError):
    """Job not found (404)."""

    def __init__(self, job_id: str) -> None:
        """Initialize JobNotFoundError.

        Args:
            job_id: Job ID that was not found
        """
        super().__init__(f"Job not found: {job_id}")
        self.job_id: str = job_id


class JobFailedError(ComputeClientError):
    """Job failed during execution."""

    def __init__(self, job: JobResponse) -> None:
        """Initialize JobFailedError.

        Args:
            job: Failed job response
        """
        msg = f"Job {job.job_id} failed: {job.error_message}"
        super().__init__(msg)
        self.job: JobResponse = job


class AuthenticationError(ComputeClientError):
    """Authentication failed (401)."""

    pass


class PermissionError(ComputeClientError):
    """Insufficient permissions (403)."""

    pass


class WorkerUnavailableError(ComputeClientError):
    """No workers available for task type."""

    def __init__(self, task_type: str, available_capabilities: dict[str, int]) -> None:
        """Initialize WorkerUnavailableError.

        Args:
            task_type: Required task type
            available_capabilities: Currently available capabilities
        """
        msg = (
            f"No workers available for task type: {task_type}\n"
            f"Available capabilities: {available_capabilities}"
        )
        super().__init__(msg)
        self.task_type: str = task_type
        self.available_capabilities: dict[str, int] = available_capabilities
