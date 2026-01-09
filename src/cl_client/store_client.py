"""Low-level HTTP client for the CoLAN store service.

This module provides direct HTTP access to all store service endpoints.
All write operations use multipart/form-data (not JSON).
"""

from pathlib import Path
from typing import Any

import httpx

from cl_client.auth import AuthProvider
from cl_client.store_models import (
    Entity,
    EntityJobResponse,
    EntityListResponse,
    EntityVersion,
    FaceMatchResult,
    FaceResponse,
    KnownPersonResponse,
    RootResponse,
    SimilarFacesResponse,
    SimilarImagesResponse,
    StoreConfig,
)


class StoreClient:
    """Low-level HTTP client for store service operations.

    This client handles all HTTP communication with the store service,
    including multipart/form-data requests for write operations.

    All write operations (create, update, patch, update_read_auth) use
    multipart/form-data, NOT JSON.

    Examples:
        # Guest mode (no auth)
        async with StoreClient() as client:
            response = await client.list_entities()

        # With authentication
        from cl_client.auth import JWTAuthProvider
        auth = JWTAuthProvider(token="your-token")
        async with StoreClient(auth_provider=auth) as client:
            entity = await client.create_entity(
                is_collection=False,
                label="My Photo",
                image_path=Path("photo.jpg")
            )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        auth_provider: AuthProvider | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the store client.

        Args:
            base_url: Base URL of the store service
            auth_provider: Optional auth provider for authenticated requests
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._auth_provider = auth_provider
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "StoreClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get headers for requests (auth only, no Content-Type).

        Content-Type is automatically set by httpx for multipart/form-data.
        """
        headers: dict[str, str] = {}
        if self._auth_provider:
            headers.update(self._auth_provider.get_headers())
        return headers

    # Health check

    async def health_check(self) -> RootResponse:
        """Get service health status and configuration.

        Returns:
            RootResponse with service status, version, and guest mode setting

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return RootResponse.model_validate(response.json())

    # Read operations (use query parameters)

    async def list_entities(
        self,
        page: int = 1,
        page_size: int = 20,
        search_query: str | None = None,
        version: int | None = None,
    ) -> EntityListResponse:
        """List entities with pagination and optional search.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            search_query: Optional search query for label/description
            version: Optional version number to retrieve

        Returns:
            EntityListResponse with items and pagination metadata

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if search_query:
            params["search_query"] = search_query
        if version is not None:
            params["version"] = version

        response = await self._client.get(
            f"{self._base_url}/entities",
            params=params,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return EntityListResponse.model_validate(response.json())

    async def read_entity(
        self,
        entity_id: int,
        version: int | None = None,
    ) -> Entity:
        """Get entity by ID, optionally a specific version.

        Args:
            entity_id: Entity ID to retrieve
            version: Optional specific version number

        Returns:
            Entity model

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}",
            params=params if params else None,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return Entity.model_validate(response.json())

    async def get_versions(self, entity_id: int) -> list[EntityVersion]:
        """Get version history for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of EntityVersion models

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}/versions",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        version_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]  # Validated by Pydantic
        return [EntityVersion.model_validate(v) for v in version_data]

    async def get_entity_faces(self, entity_id: int) -> list[FaceResponse]:
        """Get all detected faces for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of FaceResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}/faces",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        faces_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]
        return [FaceResponse.model_validate(f) for f in faces_data]

    async def get_entity_jobs(self, entity_id: int) -> list[EntityJobResponse]:
        """Get all compute jobs for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of EntityJobResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}/jobs",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        jobs_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]
        return [EntityJobResponse.model_validate(j) for j in jobs_data]

    async def find_similar_images(
        self,
        entity_id: int,
        limit: int = 5,
        score_threshold: float = 0.85,
        include_details: bool = False,
    ) -> SimilarImagesResponse:
        """Find similar images using CLIP embeddings.

        Args:
            entity_id: Entity ID to find similar images for
            limit: Maximum number of results (1-50)
            score_threshold: Minimum similarity score (0.0-1.0)
            include_details: Whether to include full entity details in results

        Returns:
            SimilarImagesResponse with results

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found or no embedding)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params: dict[str, Any] = {
            "limit": limit,
            "score_threshold": score_threshold,
            "include_details": include_details,
        }

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}/similar",
            params=params,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return SimilarImagesResponse.model_validate(response.json())

    # Write operations (use multipart/form-data)

    async def create_entity(
        self,
        is_collection: bool,
        label: str | None = None,
        description: str | None = None,
        parent_id: int | None = None,
        image_path: Path | None = None,
    ) -> Entity:
        """Create a new entity with optional file upload.

        Args:
            is_collection: Whether this is a collection (folder) or media item
            label: Optional display name
            description: Optional description
            parent_id: Optional parent collection ID
            image_path: Optional path to media file to upload

        Returns:
            Created Entity model

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, 422, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        # Build form data
        data: dict[str, str] = {
            "is_collection": str(is_collection).lower(),
        }
        if label is not None:
            data["label"] = label
        if description is not None:
            data["description"] = description
        if parent_id is not None:
            data["parent_id"] = str(parent_id)

        # Handle file upload
        files: dict[str, Any] = {}
        file_handle = None
        try:
            if image_path is not None:
                file_handle = open(image_path, "rb")
                files["image"] = file_handle

            response = await self._client.post(
                f"{self._base_url}/entities",
                data=data,
                files=files if files else None,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return Entity.model_validate(response.json())
        finally:
            if file_handle:
                file_handle.close()

    async def update_entity(
        self,
        entity_id: int,
        is_collection: bool,
        label: str,
        description: str | None = None,
        parent_id: int | None = None,
        image_path: Path | None = None,
    ) -> Entity:
        """Full update of an entity (PUT).

        Args:
            entity_id: Entity ID to update
            is_collection: Whether this is a collection
            label: New label (required for PUT)
            description: Optional new description
            parent_id: Optional new parent ID
            image_path: Optional new media file

        Returns:
            Updated Entity model

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, 404, 422, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        # Build form data
        data: dict[str, str] = {
            "is_collection": str(is_collection).lower(),
            "label": label,
        }
        if description is not None:
            data["description"] = description
        if parent_id is not None:
            data["parent_id"] = str(parent_id)

        # Handle file upload
        files: dict[str, Any] = {}
        file_handle = None
        try:
            if image_path is not None:
                file_handle = open(image_path, "rb")
                files["image"] = file_handle

            response = await self._client.put(
                f"{self._base_url}/entities/{entity_id}",
                data=data,
                files=files if files else None,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return Entity.model_validate(response.json())
        finally:
            if file_handle:
                file_handle.close()

    async def patch_entity(
        self,
        entity_id: int,
        label: str | None = None,
        description: str | None = None,
        parent_id: int | None = None,
        is_deleted: bool | None = None,
    ) -> Entity:
        """Partial update of an entity (PATCH).

        Note: Uses multipart/form-data, NOT JSON.

        Args:
            entity_id: Entity ID to patch
            label: Optional new label
            description: Optional new description
            parent_id: Optional new parent ID
            is_deleted: Optional soft delete flag

        Returns:
            Updated Entity model

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, 404, 422, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        # Build form data (only include provided fields)
        data: dict[str, str] = {}
        if label is not None:
            data["label"] = label
        if description is not None:
            data["description"] = description
        if parent_id is not None:
            data["parent_id"] = str(parent_id)
        if is_deleted is not None:
            data["is_deleted"] = str(is_deleted).lower()

        response = await self._client.patch(
            f"{self._base_url}/entities/{entity_id}",
            data=data,  # Form data, not JSON
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return Entity.model_validate(response.json())

    async def delete_entity(self, entity_id: int) -> None:
        """Hard delete an entity (permanent removal).

        Args:
            entity_id: Entity ID to delete

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, 404, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.delete(
            f"{self._base_url}/entities/{entity_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()

    async def delete_all_entities(self) -> None:
        """Delete all entities (use with caution).

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.delete(
            f"{self._base_url}/entities",
            headers=self._get_headers(),
        )
        response.raise_for_status()

    # Admin operations

    async def get_config(self) -> StoreConfig:
        """Get store configuration (admin only).

        Returns:
            StoreConfig model

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/admin/config",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return StoreConfig.model_validate(response.json())

    async def update_guest_mode(self, guest_mode: bool) -> dict[str, bool | str]:
        """Update guest mode configuration (admin only).

        Note: Uses multipart/form-data, NOT JSON.

        Args:
            guest_mode: Whether to enable guest mode (true = no authentication required)

        Returns:
            Dictionary with guest_mode status and message

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        data = {
            "guest_mode": str(guest_mode).lower(),
        }

        response = await self._client.put(
            f"{self._base_url}/admin/config/guest-mode",
            data=data,  # Form data, not JSON
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]

    async def update_read_auth(self, enabled: bool) -> StoreConfig:
        """Update read authentication configuration (admin only).

        DEPRECATED: Use update_guest_mode() instead.
        This method is kept for backward compatibility.

        Note: Uses multipart/form-data, NOT JSON.

        Args:
            enabled: Whether to enable read authentication

        Returns:
            Updated StoreConfig model

        Raises:
            httpx.HTTPStatusError: If the request fails (401, 403, etc.)
        """
        # Convert enabled to guest_mode (inverted logic)
        guest_mode = not enabled
        result = await self.update_guest_mode(guest_mode)
        # Get updated config to return StoreConfig
        return await self.get_config()

    # Face recognition and similarity search endpoints

    async def find_similar_faces(
        self,
        face_id: int,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> SimilarFacesResponse:
        """Find similar faces using face embeddings.

        Args:
            face_id: Face ID to find similar faces for
            limit: Maximum number of results (1-50)
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            SimilarFacesResponse with results

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found or no embedding)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params: dict[str, Any] = {
            "limit": limit,
            "threshold": threshold,
        }

        response = await self._client.get(
            f"{self._base_url}/faces/{face_id}/similar",
            params=params,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return SimilarFacesResponse.model_validate(response.json())

    async def get_face_matches(self, face_id: int) -> list[FaceMatchResult]:
        """Get all match records for a face (similarity history).

        Args:
            face_id: Face ID

        Returns:
            List of FaceMatchResult models

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/faces/{face_id}/matches",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        matches_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]
        return [FaceMatchResult.model_validate(m) for m in matches_data]

    async def get_all_known_persons(self) -> list[KnownPersonResponse]:
        """Get all known persons (identified by face recognition).

        Returns:
            List of KnownPersonResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/known-persons",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        persons_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]
        return [KnownPersonResponse.model_validate(p) for p in persons_data]

    async def get_known_person(self, person_id: int) -> KnownPersonResponse:
        """Get details of a specific known person.

        Args:
            person_id: Person ID

        Returns:
            KnownPersonResponse model

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/known-persons/{person_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return KnownPersonResponse.model_validate(response.json())

    async def get_known_person_faces(self, person_id: int) -> list[FaceResponse]:
        """Get all faces for a specific known person.

        Args:
            person_id: Person ID

        Returns:
            List of FaceResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/known-persons/{person_id}/faces",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        faces_data: list[dict[str, object]] = response.json()  # type: ignore[reportAny]
        return [FaceResponse.model_validate(f) for f in faces_data]

    async def update_known_person_name(
        self, person_id: int, name: str
    ) -> KnownPersonResponse:
        """Update the name of a known person.

        Args:
            person_id: Person ID
            name: New name for the person

        Returns:
            Updated KnownPersonResponse model

        Raises:
            httpx.HTTPStatusError: If the request fails (404 if not found, 422 for validation)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        # Use JSON for PATCH request body
        body = {"name": name}

        response = await self._client.patch(
            f"{self._base_url}/known-persons/{person_id}",
            json=body,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return KnownPersonResponse.model_validate(response.json())
