"""Pydantic models for compute client.

Mirrors server schemas with strict typing (NO Any types).
"""

from pydantic import BaseModel, Field

# JSON type hierarchy (from server schemas.py)
type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
type JSONObject = dict[str, JSONValue]


class JobResponse(BaseModel):
    """Response schema for job information (mirrors server schema)."""

    job_id: str = Field(..., description="Unique job identifier")
    task_type: str = Field(..., description="Type of task to execute")
    status: str = Field(..., description="Job status (queued, in_progress, completed, failed)")
    progress: int = Field(0, description="Progress percentage (0-100)")
    params: JSONObject = Field(default_factory=dict, description="Task parameters")
    task_output: JSONObject | None = Field(None, description="Task output/results")
    error_message: str | None = Field(None, description="Error message if job failed")

    priority: int = Field(5, description="Job priority (0-10)")
    created_at: int = Field(..., description="Job creation timestamp (milliseconds)")
    updated_at: int | None = Field(None, description="Job last update timestamp (milliseconds)")
    started_at: int | None = Field(None, description="Job start timestamp (milliseconds)")
    completed_at: int | None = Field(None, description="Job completion timestamp (milliseconds)")


class WorkerCapabilitiesResponse(BaseModel):
    """Response schema for worker capabilities endpoint (mirrors server schema)."""

    num_workers: int = Field(..., description="Total number of connected workers")
    capabilities: dict[str, int] = Field(..., description="Available capability counts")


class WorkerCapability(BaseModel):
    """Individual worker capability information (from MQTT messages)."""

    worker_id: str = Field(..., description="Worker unique ID")
    capabilities: list[str] = Field(..., description="List of task types worker supports")
    idle_count: int = Field(..., description="1 if idle, 0 if busy")
    timestamp: int = Field(..., description="Message timestamp (milliseconds)")
