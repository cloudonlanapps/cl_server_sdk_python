"""High-level facade for store service operations.

This module provides a high-level API for managing media entities in the store,
with consistent error handling via StoreOperationResult wrapper.

Matches the Dart SDK StoreManager pattern.
"""

from collections.abc import Callable
from pathlib import Path
from typing import cast

import httpx

from .auth import JWTAuthProvider
from .server_config import ServerConfig
from .store_client import StoreClient
from .store_models import (
    Entity,
    EntityListResponse,
    EntityVersion,
    StoreConfig,
    StoreOperationResult,
)


class StoreManager:
    """High-level manager for store operations.

    Provides a simple API for managing media entities with consistent error
    handling using StoreOperationResult wrapper.

    Two initialization modes:
    - Guest mode: No authentication (read-only if read_auth disabled)
    - Authenticated mode: Full access with SessionManager

    Examples:
        # Guest mode
        async with StoreManager.guest() as manager:
            result = await manager.list_entities()
            if result.is_success:
                for entity in result.data.items:
                    print(f"{entity.id}: {entity.label}")

        # Authenticated mode
        from cl_client import SessionManager
        async with SessionManager() as session:
            await session.login("user", "password")
            manager = session.create_store_manager()

            result = await manager.create_entity(
                label="My Photo",
                image_path=Path("photo.jpg")
            )
            if result.is_success:
                print(f"Created entity ID: {result.data.id}")
            else:
                print(f"Error: {result.error}")
    """

    def __init__(self, store_client: StoreClient):
        """Initialize with a StoreClient.

        Args:
            store_client: Configured StoreClient instance

        Note:
            Prefer using guest() or authenticated() class methods instead
            of calling this constructor directly.
        """
        self._store_client: StoreClient = store_client

    @property
    def store_client(self) -> StoreClient:
        """Access to underlying StoreClient for advanced operations.

        Provides direct access to StoreClient methods that aren't wrapped
        by StoreManager, such as database operations (faces, persons, images).

        Returns:
            The underlying StoreClient instance
        """
        return self._store_client

    @classmethod
    def guest(cls, base_url: str = "http://localhost:8001") -> "StoreManager":
        """Create StoreManager in guest mode (no authentication).

        Guest mode allows read operations if read_auth is disabled on the server.
        Write operations will fail with 401 Unauthorized.

        Args:
            base_url: Store service base URL

        Returns:
            StoreManager instance configured for guest access
        """
        return cls(StoreClient(base_url=base_url))

    @classmethod
    def authenticated(
        cls,
        config: ServerConfig,
        get_cached_token: Callable[[], str] | None = None,
        base_url: str | None = None,
    ) -> "StoreManager":
        """Create StoreManager with authentication from SessionManager.

        Args:
            session_manager: Authenticated SessionManager instance
            base_url: Optional store service URL (defaults to session's store_url)

        Returns:
            StoreManager instance configured with authentication
        """
        url = base_url or config.store_url
        auth_provider = JWTAuthProvider(get_cached_token=get_cached_token)
        return cls(StoreClient(base_url=url, auth_provider=auth_provider))

    async def __aenter__(self) -> "StoreManager":
        """Async context manager entry."""
        _ = await self._store_client.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self._store_client.__aexit__(exc_type, exc_val, exc_tb)

    def _handle_error(self, error: httpx.HTTPStatusError) -> StoreOperationResult[object]:
        """Map HTTP errors to StoreOperationResult.

        Args:
            error: HTTP error from httpx

        Returns:
            StoreOperationResult with error message
        """
        status_code = error.response.status_code
        try:
            error_data: dict[  # Error detail extraction  # pyright: ignore[reportAny]
                str, object
            ] = error.response.json()
            detail = str(error_data.get("detail", str(error)))
        except Exception:
            detail = str(error)

        if status_code == 401:
            return StoreOperationResult(error="Unauthorized: Invalid or missing token")
        elif status_code == 403:
            return StoreOperationResult(error="Forbidden: Insufficient permissions")
        elif status_code == 404:
            return StoreOperationResult(error=f"Not Found: {detail}")
        elif status_code == 422:
            return StoreOperationResult(error=f"Validation Error: {detail}")
        else:
            return StoreOperationResult(error=f"Error {status_code}: {detail}")

    # Read operations

    async def list_entities(
        self,
        page: int = 1,
        page_size: int = 20,
        search_query: str | None = None,
    ) -> StoreOperationResult[EntityListResponse]:
        """List entities with pagination and optional search.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            search_query: Optional search query for label/description

        Returns:
            StoreOperationResult containing EntityListResponse or error
        """
        try:
            result = await self._store_client.list_entities(
                page=page,
                page_size=page_size,
                search_query=search_query,
            )
            return StoreOperationResult[EntityListResponse](
                success="Entities retrieved successfully",
                data=result,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[EntityListResponse], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[EntityListResponse](error=f"Unexpected error: {str(e)}")

    async def read_entity(
        self,
        entity_id: int,
        version: int | None = None,
    ) -> StoreOperationResult[Entity]:
        """Get entity by ID, optionally a specific version.

        Args:
            entity_id: Entity ID to retrieve
            version: Optional specific version number

        Returns:
            StoreOperationResult containing Entity or error
        """
        try:
            entity = await self._store_client.read_entity(
                entity_id=entity_id,
                version=version,
            )
            return StoreOperationResult[Entity](
                success="Entity retrieved successfully",
                data=entity,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[Entity], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[Entity](error=f"Unexpected error: {str(e)}")

    async def get_versions(
        self,
        entity_id: int,
    ) -> StoreOperationResult[list[EntityVersion]]:
        """Get version history for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult containing list of EntityVersion or error
        """
        try:
            versions = await self._store_client.get_versions(entity_id=entity_id)
            return StoreOperationResult[list[EntityVersion]](
                success="Version history retrieved successfully",
                data=versions,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[list[EntityVersion]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[list[EntityVersion]](error=f"Unexpected error: {str(e)}")

    # Write operations

    async def create_entity(
        self,
        label: str | None = None,
        description: str | None = None,
        is_collection: bool = False,
        parent_id: int | None = None,
        image_path: Path | None = None,
    ) -> StoreOperationResult[Entity]:
        """Create a new entity with optional file upload.

        Requires media_store_write permission (always requires auth).

        Args:
            label: Optional display name
            description: Optional description
            is_collection: Whether this is a collection (folder) or media item
            parent_id: Optional parent collection ID
            image_path: Optional path to media file to upload

        Returns:
            StoreOperationResult containing created Entity or error
        """
        try:
            entity = await self._store_client.create_entity(
                is_collection=is_collection,
                label=label,
                description=description,
                parent_id=parent_id,
                image_path=image_path,
            )
            return StoreOperationResult[Entity](
                success="Entity created successfully",
                data=entity,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[Entity], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[Entity](error=f"Unexpected error: {str(e)}")

    async def update_entity(
        self,
        entity_id: int,
        label: str,
        description: str | None = None,
        is_collection: bool = False,
        parent_id: int | None = None,
        image_path: Path | None = None,
    ) -> StoreOperationResult[Entity]:
        """Full update of an entity (PUT).

        Requires media_store_write permission (always requires auth).

        Args:
            entity_id: Entity ID to update
            label: New label (required for PUT)
            description: Optional new description
            is_collection: Whether this is a collection
            parent_id: Optional new parent ID
            image_path: Optional new media file

        Returns:
            StoreOperationResult containing updated Entity or error
        """
        try:
            entity = await self._store_client.update_entity(
                entity_id=entity_id,
                is_collection=is_collection,
                label=label,
                description=description,
                parent_id=parent_id,
                image_path=image_path,
            )
            return StoreOperationResult[Entity](
                success="Entity updated successfully",
                data=entity,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[Entity], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[Entity](error=f"Unexpected error: {str(e)}")

    async def patch_entity(
        self,
        entity_id: int,
        label: str | None = None,
        description: str | None = None,
        parent_id: int | None = None,
        is_deleted: bool | None = None,
    ) -> StoreOperationResult[Entity]:
        """Partial update of an entity (PATCH).

        Requires media_store_write permission (always requires auth).

        Args:
            entity_id: Entity ID to patch
            label: Optional new label
            description: Optional new description
            parent_id: Optional new parent ID
            is_deleted: Optional soft delete flag

        Returns:
            StoreOperationResult containing updated Entity or error
        """
        try:
            entity = await self._store_client.patch_entity(
                entity_id=entity_id,
                label=label,
                description=description,
                parent_id=parent_id,
                is_deleted=is_deleted,
            )
            return StoreOperationResult[Entity](
                success="Entity patched successfully",
                data=entity,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[Entity], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[Entity](error=f"Unexpected error: {str(e)}")

    async def delete_entity(
        self,
        entity_id: int,
    ) -> StoreOperationResult[None]:
        """Hard delete an entity (permanent removal).

        Requires media_store_write permission (always requires auth).

        Args:
            entity_id: Entity ID to delete

        Returns:
            StoreOperationResult with success/error status
        """
        try:
            await self._store_client.delete_entity(entity_id=entity_id)
            return StoreOperationResult[None](
                success="Entity deleted successfully",
                data=None,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[None], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[None](error=f"Unexpected error: {str(e)}")

    # Admin operations

    async def get_config(self) -> StoreOperationResult[StoreConfig]:
        """Get store configuration (admin only).

        Requires admin role.

        Returns:
            StoreOperationResult containing StoreConfig or error
        """
        try:
            config = await self._store_client.get_config()
            return StoreOperationResult[StoreConfig](
                success="Configuration retrieved successfully",
                data=config,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[StoreConfig], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[StoreConfig](error=f"Unexpected error: {str(e)}")

    async def update_guest_mode(self, guest_mode: bool) -> StoreOperationResult[StoreConfig]:
        """Update guest mode configuration (admin only).

        Args:
            guest_mode: Whether to enable guest mode

        Returns:
            StoreOperationResult with success status
        """
        try:
            result = await self._store_client.update_guest_mode(guest_mode=guest_mode)
            return StoreOperationResult[StoreConfig](
                success="Guest mode configuration updated successfully",
                data=result,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[StoreConfig], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[StoreConfig](error=f"Unexpected error: {str(e)}")
