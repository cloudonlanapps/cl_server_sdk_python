"""Pydantic models for intelligence data (faces, jobs, etc.).

Mirrors server-side schemas from store.m_insight.intelligence.schemas.
"""

from typing import Any
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
    image_id: int = Field(..., description="Image ID this face belongs to")
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


class EntityJobResponse(BaseModel):
    """Response schema for entity job status."""
    id: int = Field(..., description="Job record ID")
    image_id: int = Field(..., description="Image ID")
    job_id: str = Field(..., description="Compute service job ID")
    task_type: str = Field(..., description="Task type (face_detection or clip_embedding)")
    status: str = Field(..., description="Job status (queued, in_progress, completed, failed)")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    updated_at: int = Field(..., description="Last update timestamp (milliseconds)")
    completed_at: int | None = Field(None, description="Completion timestamp (milliseconds)")
    error_message: str | None = Field(None, description="Error message if failed")


class KnownPersonResponse(BaseModel):
    """Response schema for known person."""
    id: int = Field(..., description="Known person ID")
    name: str | None = Field(None, description="Person name (optional)")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    updated_at: int = Field(..., description="Last update timestamp (milliseconds)")
    face_count: int | None = Field(None, description="Number of faces for this person (optional)")


class FaceMatchResult(BaseModel):
    """Response schema for face match."""
    id: int = Field(..., description="Match record ID")
    face_id: int = Field(..., description="Source face ID")
    matched_face_id: int = Field(..., description="Matched face ID")
    similarity_score: float = Field(..., description="Similarity score [0.0, 1.0]")
    created_at: int = Field(..., description="Match timestamp (milliseconds)")
    matched_face: FaceResponse | None = Field(None, description="Matched face details (optional)")


class SimilarImageResult(BaseModel):
    """Result item for similar image search."""
    image_id: int = Field(..., description="Entity ID")
    score: float = Field(..., description="Similarity score [0.0, 1.0]")
    entity: Any | None = Field(None, description="Entity details if requested")


class SimilarImagesResponse(BaseModel):
    """Response for similar image search."""
    results: list[SimilarImageResult] = Field(..., description="List of similar images")
    query_image_id: int = Field(..., description="ID of the query image")


class SimilarFaceResult(BaseModel):
    """Result item for similar face search."""
    face_id: int = Field(..., description="Face ID")
    score: float = Field(..., description="Similarity score [0.0, 1.0]")
    face: FaceResponse | None = Field(None, description="Face details if available")


class SimilarFacesResponse(BaseModel):
    """Response for similar face search."""
    results: list[SimilarFaceResult] = Field(..., description="List of similar faces")
    query_face_id: int = Field(..., description="ID of the query face")


class UpdatePersonNameRequest(BaseModel):
    """Request to update a known person's name."""
    name: str = Field(..., description="New name for the person")
