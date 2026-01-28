"""Pydantic models for intelligence data (faces, jobs, etc.).

Mirrors server-side schemas from store.m_insight.intelligence.schemas.
"""

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box coordinates (normalized 0.0-1.0)."""
    x1: float
    y1: float
    x2: float
    y2: float


class FaceLandmarks(BaseModel):
    """Facial landmarks (normalized 0.0-1.0)."""
    right_eye: tuple[float, float]
    left_eye: tuple[float, float]
    nose_tip: tuple[float, float]
    mouth_right: tuple[float, float]
    mouth_left: tuple[float, float]


class FaceResponse(BaseModel):
    """Response schema for detected face."""
    id: int = Field(..., description="Face ID")
    entity_id: int = Field(..., description="Entity ID this face belongs to")
    bbox: BBox = Field(
        ..., description="Normalized bounding box [x1, y1, x2, y2] in range [0.0, 1.0]"
    )
    confidence: float = Field(..., description="Detection confidence score [0.0, 1.0]")
    landmarks: FaceLandmarks = Field(
        ..., description="Five facial keypoints [[x1, y1], [x2, y2], ...]"
    )
    file_path: str = Field(..., description="Relative path to cropped face image")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    known_person_id: int | None = Field(None, description="Known person ID (face recognition)")


class JobInfo(BaseModel):
    """Job tracking information."""
    job_id: str = Field(..., description="Compute service job ID")
    task_type: str = Field(..., description="Task type (face_detection, clip_embedding, dino_embedding)")
    status: str = Field(..., description="Job status (queued, in_progress, completed, failed)")
    started_at: int = Field(..., description="Job start timestamp (milliseconds)")
    completed_at: int | None = Field(None, description="Completion timestamp (milliseconds)")
    error_message: str | None = Field(None, description="Error message if failed")

# Alias for backward compatibility
EntityJobResponse = JobInfo


class InferenceStatus(BaseModel):
    """Fine-grained inference status."""
    face_detection: str = "pending"
    clip_embedding: str = "pending"
    dino_embedding: str = "pending"
    face_embeddings: list[str] | None = None


class EntityIntelligenceData(BaseModel):
    """Denormalized intelligence data (JSON field)."""
    overall_status: str = Field("queued", description="Overall status (queued, processing, completed, failed)")
    last_processed_md5: str | None = None
    last_processed_version: int | None = None
    face_count: int | None = None
    active_processing_md5: str | None = None
    active_jobs: list[JobInfo] = Field(default_factory=list)
    job_history: list[JobInfo] = Field(default_factory=list)
    inference_status: InferenceStatus = Field(default_factory=InferenceStatus)
    last_updated: int = Field(..., description="Last update timestamp (milliseconds)")
    error_message: str | None = None


class KnownPersonResponse(BaseModel):
    """Response schema for known person."""
    id: int = Field(..., description="Known person ID")
    name: str | None = Field(None, description="Person name (optional)")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    updated_at: int = Field(..., description="Last update timestamp (milliseconds)")
    face_count: int | None = Field(None, description="Number of faces for this person (optional)")



class UpdatePersonNameRequest(BaseModel):
    """Request to update a known person's name."""
    name: str = Field(..., description="New name for the person")
