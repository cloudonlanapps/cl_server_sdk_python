"""Store service models for the CoLAN client SDK.

This module contains Pydantic models for the store service, including:
- Entity: Core media entity with metadata and file properties
- EntityListResponse: Paginated list of entities
- EntityVersion: Version history tracking
- StoreConfig: Store configuration settings
- StoreOperationResult: Wrapper for operation results with error handling
"""

from datetime import datetime

from pydantic import BaseModel, Field
from .intelligence_models import EntityIntelligenceData


class OrphanedFileInfo(BaseModel):
    """Information about an orphaned file."""
    file_path: str
    file_size: int | None = None
    last_modified: int | None = None


class OrphanedFaceInfo(BaseModel):
    """Information about an orphaned face record."""
    face_id: int
    entity_id: int


class OrphanedVectorInfo(BaseModel):
    """Information about an orphaned vector in Qdrant."""
    vector_id: str
    collection_name: str


class OrphanedMqttInfo(BaseModel):
    """Information about an orphaned MQTT retained message."""
    entity_id: int
    topic: str


class AuditReport(BaseModel):
    """Comprehensive audit report of data integrity issues."""
    orphaned_files: list[OrphanedFileInfo] = Field(default_factory=list)
    orphaned_faces: list[OrphanedFaceInfo] = Field(default_factory=list)
    orphaned_vectors: list[OrphanedVectorInfo] = Field(default_factory=list)
    orphaned_mqtt: list[OrphanedMqttInfo] = Field(default_factory=list)
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class CleanupReport(BaseModel):
    """Summary of cleaned up orphaned resources."""
    files_deleted: int = 0
    faces_deleted: int = 0
    vectors_deleted: int = 0
    mqtt_cleared: int = 0
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


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
    file_path: str | None = Field(default=None, description="Relative file path in storage")
    is_indirectly_deleted: bool | None = Field(
        default=None,
        description="True if any ancestor in the parent chain is soft-deleted",
    )
    intelligence_data: EntityIntelligenceData | None = Field(
        default=None,
        description="Denormalized intelligence data (JSON field)",
    )

    @property
    def intelligence_status(self) -> str | None:
        """Compatibility property for overall intelligence status."""
        if self.intelligence_data:
            return self.intelligence_data.overall_status
        return None

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


class StoreOperationResult[T](BaseModel):
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
