"""Store service models for the CoLAN client SDK.

This module contains Pydantic models for the store service, including:
- Entity: Core media entity with metadata and file properties
- EntityListResponse: Paginated list of entities
- EntityVersion: Version history tracking
- StoreConfig: Store configuration settings
- StoreOperationResult: Wrapper for operation results with error handling
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class Entity(BaseModel):
    """Media entity with metadata and file properties.

    Represents a single entity in the store, which can be either a collection
    (folder) or a media item (image, video, etc.) with associated file metadata.
    """

    # Core fields
    id: int = Field(..., description="Unique entity identifier")
    is_collection: bool | None = Field(
        default=None, description="Whether this is a collection (folder) or media item"
    )
    label: str | None = Field(default=None, description="Display name for the entity")
    description: str | None = Field(default=None, description="Entity description")
    parent_id: int | None = Field(
        default=None, description="ID of parent collection (for hierarchical organization)"
    )

    # Audit/metadata fields (milliseconds since epoch)
    added_date: int | None = Field(
        default=None, description="Creation timestamp (milliseconds since epoch)"
    )
    updated_date: int | None = Field(
        default=None, description="Last modification timestamp (milliseconds since epoch)"
    )
    create_date: int | None = Field(
        default=None, description="Initial creation timestamp (milliseconds since epoch)"
    )
    added_by: str | None = Field(default=None, description="User who created the entity")
    updated_by: str | None = Field(default=None, description="User who last modified the entity")
    is_deleted: bool | None = Field(default=None, description="Soft delete flag")

    # Media file properties (only populated for media items, not collections)
    file_size: int | None = Field(default=None, description="File size in bytes")
    height: int | None = Field(default=None, description="Image/video height in pixels")
    width: int | None = Field(default=None, description="Image/video width in pixels")
    duration: float | None = Field(default=None, description="Audio/video duration in seconds")
    mime_type: str | None = Field(default=None, description="MIME type (e.g., image/jpeg)")
    type: str | None = Field(default=None, description="Media type category (image, video, etc.)")
    extension: str | None = Field(default=None, description="File extension (e.g., jpg, mp4)")
    md5: str | None = Field(default=None, description="MD5 checksum (unique constraint)")
    file_path: str | None = Field(
        default=None, description="Relative file path in storage"
    )

    @property
    def added_date_datetime(self) -> datetime | None:
        """Convert added_date (milliseconds) to Python datetime."""
        if self.added_date is None:
            return None
        return datetime.fromtimestamp(self.added_date / 1000)

    @property
    def updated_date_datetime(self) -> datetime | None:
        """Convert updated_date (milliseconds) to Python datetime."""
        if self.updated_date is None:
            return None
        return datetime.fromtimestamp(self.updated_date / 1000)

    @property
    def create_date_datetime(self) -> datetime | None:
        """Convert create_date (milliseconds) to Python datetime."""
        if self.create_date is None:
            return None
        return datetime.fromtimestamp(self.create_date / 1000)


class EntityPagination(BaseModel):
    """Pagination metadata for entity lists."""

    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of entities")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class EntityListResponse(BaseModel):
    """Paginated list of entities."""

    items: list[Entity] = Field(..., description="List of entities in this page")
    pagination: EntityPagination = Field(..., description="Pagination metadata")


class EntityVersion(BaseModel):
    """Version history for an entity.

    Tracks changes to entities using SQLAlchemy-Continuum versioning.
    """

    version: int = Field(..., description="Version number")
    transaction_id: int = Field(..., description="Transaction identifier")
    end_transaction_id: int | None = Field(
        default=None, description="End of version range (null for current version)"
    )
    operation_type: str | None = Field(
        default=None, description="Type of operation (INSERT, UPDATE, DELETE)"
    )
    label: str | None = Field(default=None, description="Label in this version")
    description: str | None = Field(default=None, description="Description in this version")

    # Note: Version contains all fields that were versioned, but we only expose
    # the most common ones above. Additional fields can be accessed via dict access.


class StoreConfig(BaseModel):
    """Store configuration settings."""

    guest_mode: bool = Field(
        ...,
        description="Whether guest mode is enabled (true = no authentication required)",
    )
    updated_at: int | None = Field(
        default=None, description="Last configuration update (milliseconds since epoch)"
    )
    updated_by: str | None = Field(
        default=None, description="User who last updated the configuration"
    )

    @property
    def updated_at_datetime(self) -> datetime | None:
        """Convert updated_at (milliseconds) to Python datetime."""
        if self.updated_at is None:
            return None
        return datetime.fromtimestamp(self.updated_at / 1000)


class StoreOperationResult(BaseModel, Generic[T]):
    """Wrapper for store operation results with error handling.

    Provides consistent error handling across all store operations, matching
    the Dart SDK pattern.

    Either `success` or `error` will be set, never both.
    `data` is only populated on success.
    """

    success: str | None = Field(default=None, description="Success message if operation succeeded")
    error: str | None = Field(default=None, description="Error message if operation failed")
    data: T | None = Field(default=None, description="Result data (only on success)")

    @property
    def is_success(self) -> bool:
        """Return True if the operation succeeded."""
        return self.error is None and self.success is not None

    @property
    def is_error(self) -> bool:
        """Return True if the operation failed."""
        return self.error is not None

    def value_or_throw(self) -> T:
        """Get the data value or raise an exception if error.

        Returns:
            The data value

        Raises:
            RuntimeError: If the operation failed
        """
        if self.is_error:
            raise RuntimeError(f"Operation failed: {self.error}")
        if self.data is None:
            raise RuntimeError("Operation succeeded but data is None")
        return self.data


# Request models (these are not sent as JSON, but used for type hints)
# The actual requests use multipart/form-data


class CreateEntityRequest(BaseModel):
    """Request model for creating an entity (for type hints only).

    Note: Actual API uses multipart/form-data, not JSON.
    """

    is_collection: bool
    label: str | None = None
    description: str | None = None
    parent_id: int | None = None
    # image_path would be a Path object, not included in this model


class UpdateEntityRequest(BaseModel):
    """Request model for updating an entity (for type hints only).

    Note: Actual API uses multipart/form-data, not JSON.
    """

    is_collection: bool
    label: str
    description: str | None = None
    parent_id: int | None = None
    # image_path would be a Path object, not included in this model


class PatchEntityRequest(BaseModel):
    """Request model for patching an entity (for type hints only).

    Note: Actual API uses multipart/form-data, not JSON.
    """

    label: str | None = None
    description: str | None = None
    parent_id: int | None = None
    is_deleted: bool | None = None


class UpdateReadAuthRequest(BaseModel):
    """Request model for updating read auth configuration (for type hints only).

    Note: Actual API uses multipart/form-data, not JSON.
    """

    enabled: bool


# Health check response model
class RootResponse(BaseModel):
    """Response model for root health check endpoint."""

    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    guestMode: str = Field(..., description="Guest mode status (on/off)")


# Face detection and job models
class FaceResponse(BaseModel):
    """Response model for detected face."""

    id: int = Field(..., description="Face ID")
    entity_id: int = Field(..., description="Entity ID this face belongs to")
    bbox: list[float] = Field(
        ..., description="Normalized bounding box [x1, y1, x2, y2] in range [0.0, 1.0]"
    )
    confidence: float = Field(..., description="Detection confidence score [0.0, 1.0]")
    landmarks: list[list[float]] = Field(
        ..., description="Five facial keypoints [[x1, y1], [x2, y2], ...]"
    )
    file_path: str = Field(..., description="Relative path to cropped face image")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    known_person_id: int | None = Field(None, description="Known person ID (face recognition)")

    @property
    def created_at_datetime(self) -> datetime | None:
        """Convert created_at (milliseconds) to Python datetime."""
        if self.created_at is None:
            return None
        return datetime.fromtimestamp(self.created_at / 1000)


class EntityJobResponse(BaseModel):
    """Response model for entity job status."""

    id: int = Field(..., description="Job record ID")
    entity_id: int = Field(..., description="Entity ID")
    job_id: str = Field(..., description="Compute service job ID")
    task_type: str = Field(..., description="Task type (face_detection or clip_embedding)")
    status: str = Field(..., description="Job status (queued, in_progress, completed, failed)")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    updated_at: int = Field(..., description="Last update timestamp (milliseconds)")
    completed_at: int | None = Field(None, description="Completion timestamp (milliseconds)")
    error_message: str | None = Field(None, description="Error message if failed")

    @property
    def created_at_datetime(self) -> datetime | None:
        """Convert created_at (milliseconds) to Python datetime."""
        if self.created_at is None:
            return None
        return datetime.fromtimestamp(self.created_at / 1000)

    @property
    def updated_at_datetime(self) -> datetime | None:
        """Convert updated_at (milliseconds) to Python datetime."""
        if self.updated_at is None:
            return None
        return datetime.fromtimestamp(self.updated_at / 1000)

    @property
    def completed_at_datetime(self) -> datetime | None:
        """Convert completed_at (milliseconds) to Python datetime."""
        if self.completed_at is None:
            return None
        return datetime.fromtimestamp(self.completed_at / 1000)


# Similarity search models
class SimilarImageResult(BaseModel):
    """Response model for similar image search result."""

    entity_id: int = Field(..., description="Entity ID of similar image")
    score: float = Field(..., description="Similarity score [0.0, 1.0]")
    entity: Entity | None = Field(None, description="Entity details (optional)")


class SimilarImagesResponse(BaseModel):
    """Response model for similar image search."""

    results: list[SimilarImageResult] = Field(..., description="List of similar images")
    query_entity_id: int = Field(..., description="Query entity ID")


# Known persons (face recognition) models
class KnownPersonResponse(BaseModel):
    """Response model for known person."""

    id: int = Field(..., description="Known person ID")
    name: str | None = Field(None, description="Person name (optional)")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    updated_at: int = Field(..., description="Last update timestamp (milliseconds)")
    face_count: int | None = Field(None, description="Number of faces for this person (optional)")

    @property
    def created_at_datetime(self) -> datetime | None:
        """Convert created_at (milliseconds) to Python datetime."""
        if self.created_at is None:
            return None
        return datetime.fromtimestamp(self.created_at / 1000)

    @property
    def updated_at_datetime(self) -> datetime | None:
        """Convert updated_at (milliseconds) to Python datetime."""
        if self.updated_at is None:
            return None
        return datetime.fromtimestamp(self.updated_at / 1000)


class UpdatePersonNameRequest(BaseModel):
    """Request model for updating person name."""

    name: str = Field(..., min_length=1, max_length=255, description="Person name")


class FaceMatchResult(BaseModel):
    """Response model for face match."""

    id: int = Field(..., description="Match record ID")
    face_id: int = Field(..., description="Source face ID")
    matched_face_id: int = Field(..., description="Matched face ID")
    similarity_score: float = Field(..., description="Similarity score [0.0, 1.0]")
    created_at: int = Field(..., description="Match timestamp (milliseconds)")
    matched_face: FaceResponse | None = Field(None, description="Matched face details (optional)")

    @property
    def created_at_datetime(self) -> datetime | None:
        """Convert created_at (milliseconds) to Python datetime."""
        if self.created_at is None:
            return None
        return datetime.fromtimestamp(self.created_at / 1000)


class SimilarFacesResult(BaseModel):
    """Response model for similar face search result."""

    face_id: int = Field(..., description="Face ID")
    score: float = Field(..., description="Similarity score [0.0, 1.0]")
    known_person_id: int | None = Field(None, description="Known person ID")
    face: FaceResponse | None = Field(None, description="Face details (optional)")


class SimilarFacesResponse(BaseModel):
    """Response model for similar face search."""

    results: list[SimilarFacesResult] = Field(..., description="List of similar faces")
    query_face_id: int = Field(..., description="Query face ID")
