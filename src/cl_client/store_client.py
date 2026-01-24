"""Low-level HTTP client for the CoLAN store service.

This module provides direct HTTP access to all store service endpoints.
All write operations use multipart/form-data (not JSON).
"""

from pathlib import Path

import httpx
from pydantic import TypeAdapter

from cl_client.auth import AuthProvider
from cl_client.http_utils import HttpUtils
from cl_client.store_models import (
    Entity,
    EntityListResponse,
    EntityVersion,
    RootResponse,
    EntityVersion,
    RootResponse,
    StoreConfig,
)
from cl_client.types import UNSET, Unset
from cl_client.intelligence_models import (
    EntityJobResponse,
    FaceMatchResult,
    FaceResponse,
    KnownPersonResponse,
    SimilarFacesResponse,
    SimilarImagesResponse,
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
        self._base_url: str = base_url.rstrip("/")
        self.auth_provider: AuthProvider | None = auth_provider
        self._timeout: float = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "StoreClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _get_headers(self) -> dict[str, str]:
        """Get headers for requests (auth only, no Content-Type).

        Content-Type is automatically set by httpx for multipart/form-data.
        Supports async token refresh if auth provider has refresh capability.
        """
        headers: dict[str, str] = {}
        if self.auth_provider:
            # Check if provider supports async token refresh
            if hasattr(self.auth_provider, 'refresh_token_if_needed'):
                await self.auth_provider.refresh_token_if_needed()
            headers.update(self.auth_provider.get_headers())
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
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return RootResponse.model_validate(response.json())

    # Read operations (use query parameters)

    async def list_entities(
        self,
        page: int = 1,
        page_size: int = 20,
        search_query: str | None = None,
        version: int | None = None,
        exclude_deleted: bool = False,
    ) -> EntityListResponse:
        """List entities with pagination and optional search.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            search_query: Optional search query for label/description
            version: Optional version number to retrieve
            exclude_deleted: Whether to exclude soft-deleted entities

        Returns:
            EntityListResponse with items and pagination metadata

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params: dict[str, int | str] = {
            "page": page,
            "page_size": page_size,
        }
        if search_query:
            params["search_query"] = search_query
        if version is not None:
            params["version"] = version
        if exclude_deleted:
            params["exclude_deleted"] = "true"
        # Type check doesn't know about filter_param yet in args, adding it manually
        # implementation details below

        if search_query:
            params["search_query"] = search_query
        if version is not None:
            params["version"] = version
        if exclude_deleted:
            params["exclude_deleted"] = "true"

        response = await self._client.get(
            f"{self._base_url}/entities",
            params=params,
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
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

        params: dict[str, int] = {}
        if version is not None:
            params["version"] = version

        response = await self._client.get(
            f"{self._base_url}/entities/{entity_id}",
            params=params if params else None,
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
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
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[EntityVersion])
        return adapter.validate_python(response.json())

    # Write operations

    async def create_entity(
        self,
        is_collection: bool,
        label: str | None = None,
        image_path: Path | None = None,
        description: str | None = None,
        parent_id: int | None = None,
    ) -> Entity:
        """Create a new entity (collection or item).

        Args:
            is_collection: True if creating a collection
            label: Entity label
            image_path: Optional path to image file
            description: Optional description
            parent_id: Optional parent collection ID

        Returns:
            Created Entity

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        data: dict[str, str] = {
            "is_collection": str(is_collection).lower(),
        }
        if label:
            data["label"] = label
        if description:
            data["description"] = description
        if parent_id is not None:
            data["parent_id"] = str(parent_id)

        files = None
        opened_files = None
        try:
            if image_path:
                files = {"image": image_path}
                opened_files = HttpUtils.open_multipart_files(files)

            response = await self._client.post(
                f"{self._base_url}/entities",
                data=data,
                files=opened_files,
                headers=await self._get_headers(),
            )
            _ = response.raise_for_status()
            return Entity.model_validate(response.json())
        finally:
            if opened_files:
                HttpUtils.close_multipart_files(opened_files)

    async def update_entity(
        self,
        entity_id: int,
        is_collection: bool,
        label: str,
        description: str | None = None,
        parent_id: int | None = None,
        image_path: Path | None = None,
    ) -> Entity:
        """Update an existing entity.

        Args:
            entity_id: ID of entity to update
            is_collection: True if collection
            label: New label
            description: Optional new description
            parent_id: Optional parent collection ID
            image_path: Optional new image file

        Returns:
            Updated Entity

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        data: dict[str, str] = {
            "is_collection": str(is_collection).lower(),
            "label": label,
        }
        if description:
            data["description"] = description
        if parent_id is not None:
            data["parent_id"] = str(parent_id)

        files = None
        opened_files = None
        try:
            if image_path:
                files = {"image": image_path}
                opened_files = HttpUtils.open_multipart_files(files)

            response = await self._client.put(
                f"{self._base_url}/entities/{entity_id}",
                data=data,
                files=opened_files,
                headers=await self._get_headers(),
            )
            _ = response.raise_for_status()
            return Entity.model_validate(response.json())
        finally:
            if opened_files:
                HttpUtils.close_multipart_files(opened_files)

    async def patch_entity(
        self,
        entity_id: int,
        label: str | None | Unset = UNSET,
        description: str | None | Unset = UNSET,
        is_deleted: bool | None | Unset = UNSET,
        is_collection: bool | None | Unset = UNSET,
        parent_id: int | None | Unset = UNSET,
    ) -> Entity:
        """Patch an entity (partial update).

        Args:
            entity_id: Entity ID
            label: Optional new label (use UNSET to leave unchanged)
            description: Optional new description (use UNSET to leave unchanged)
            is_deleted: Optional soft delete status (use UNSET to leave unchanged)
            is_collection: Optional collection status (use UNSET to leave unchanged)
            parent_id: Optional parent ID (use UNSET to leave unchanged, None to unset parent)

        Returns:
            Updated Entity

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        data: dict[str, str] = {}
        if not isinstance(label, Unset):
            # If explicit None, send empty string? Or server handles explicit None?
            # Server form receiving: label: str | None = Form(None)
            # If we send "label": None in param with httpx form, it might be string "None" or empty.
            # Best practice for Form: if None, do not send key if we want default None?
            # BUT patch needs to distinguish "don't change" (UNSET) vs "set to null" (None).
            # Server code: `if label is not None: patch_data["label"] = label`
            # Server `label` default is None. So if we don't send it, it's None, so it's not added to patch_data.
            # This implies we CANNOT set label to None currently on server if check is `is not None`.
            # Wait, server `patch_entity` says:
            # `if label is not None: patch_data["label"] = label`
            # If we want to unset label, we assume label is required string usually?
            # Actually label is `str | None`. If we want to set it to None, we'd need to send something that server converts to None?
            # Server: `label: str | None = Form(None)`.
            # If we send nothing, it is None. `patch_data["label"] = label` -> runs.
            # So if we send nothing, `label` is None, and `patch_data` gets `label`=None.
            # `BodyPatchEntity`: `label: str | None = Field(None)`.
            # `model_construct(..., _fields_set=...)`.
            # If `label` is in `_fields_set`, it updates.
            # If we don't send key in Form, `label` arg is None.
            # CAUTION: Server code: `label: str | None = Form(None)`.
            # If we DO NOT send `label`, `label` is `None`. Then `if label is not None` is False. Code block SKIPPED.
            # So sending NOTHING means NO CHANGE.
            # To set to None... we can't with current server logic `if label is not None`.
            # UNLESS `label` is required? No form default is None.
            # Let's assume standard behavior:
            # UNSET -> Don't send key.
            # Value -> Send key.
            # None -> Send key with empty value? or special null?
            # Httpx data dict: if value is None, what happens?
            # We'll treat None as empty string for optional text fields if that's safer, but for now:
            if label is None:
                 # If we want to unset, server needs to support it. 
                 # Current server `patch_entity` logic for label: `if label is not None`. 
                 # So we literally cannot set it to None via that endpoint logic if we pass None to it?
                 # Wait, if we pass "", it is not None. `patch_data["label"] = ""` -> Label becomes empty string.
                 # If validation allows empty string, that might be "unset".
                 data["label"] = ""
            else:
                 data["label"] = label

        if not isinstance(description, Unset):
            if description is None:
                data["description"] = ""
            else:
                data["description"] = description

        if not isinstance(is_deleted, Unset) and is_deleted is not None:
             data["is_deleted"] = str(is_deleted).lower()

        if not isinstance(is_collection, Unset) and is_collection is not None:
             data["is_collection"] = str(is_collection).lower()

        if not isinstance(parent_id, Unset):
             if parent_id is None:
                  data["parent_id"] = ""
             else:
                  data["parent_id"] = str(parent_id)
        
        # NOTE: Server `patch_entity` explicitly checks `if "parent_id" in form_keys`
        # and treats empty string as None. So sending "" works for unsetting parent_id.
        # For label/description, server `if label is not None` means we can't set it to None 
        # unless "" is treated as value.

        response = await self._client.patch(
            f"{self._base_url}/entities/{entity_id}",
            data=data,
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return Entity.model_validate(response.json())

    async def delete_entity(self, entity_id: int) -> None:
        """Hard delete an entity.

        Args:
            entity_id: Entity ID

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.delete(
            f"{self._base_url}/entities/{entity_id}",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()

    async def delete_all_entities(self) -> None:
        """Delete all entities (admin only).

        This performs a bulk delete of all entities in the store.

        Raises:
            httpx.HTTPStatusError: If the request fails (403 if not admin)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.delete(
            f"{self._base_url}/entities",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()

    # Admin operations

    async def get_config(self) -> StoreConfig:
        """Get store configuration (admin only).

        Returns:
            StoreConfig

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/admin/config",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return StoreConfig.model_validate(response.json())

    async def update_guest_mode(self, guest_mode: bool) -> StoreConfig:
        """Update guest mode setting (admin only).

        Args:
            guest_mode: New guest mode status

        Returns:
            Updated StoreConfig

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        data = {"guest_mode": str(guest_mode).lower()}

        response = await self._client.put(
            f"{self._base_url}/admin/config/guest-mode",
            data=data,
            headers=await self._get_headers(),
        )
        return await self.get_config()
    
    async def get_m_insight_status(self) -> dict[str, object]:
        """Get MInsight process status (admin only).
        
        Returns:
            Dictionary with status information
        
        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/m_insight/status",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return response.json()

    # Intelligence operations

    async def get_entity_faces(self, entity_id: int) -> list[FaceResponse]:
        """Get all faces detected in an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of FaceResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/entities/{entity_id}/faces",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[FaceResponse])
        return adapter.validate_python(response.json())

    async def get_entity_jobs(self, entity_id: int) -> list[EntityJobResponse]:
        """Get all compute jobs for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of EntityJobResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/entities/{entity_id}/jobs",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[EntityJobResponse])
        return adapter.validate_python(response.json())

        return response.content
    
    async def download_entity_clip_embedding(self, entity_id: int) -> bytes:
        """Download entity CLIP embedding as .npy bytes.

        Args:
            entity_id: Entity ID

        Returns:
            Raw bytes of .npy file

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/entities/{entity_id}/clip_embedding",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return response.content

    async def download_entity_dino_embedding(self, entity_id: int) -> bytes:
        """Download entity DINO embedding as .npy bytes.

        Args:
            entity_id: Entity ID

        Returns:
            Raw bytes of .npy file

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/entities/{entity_id}/dino_embedding",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return response.content

    async def download_face_embedding(self, face_id: int) -> bytes:
        """Download face embedding as .npy bytes.

        Args:
            face_id: Face ID

        Returns:
            Raw bytes of .npy file

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/faces/{face_id}/embedding",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return response.content

    async def get_known_persons(self) -> list[KnownPersonResponse]:
        """Get all known persons.

        Returns:
            List of KnownPersonResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/known-persons",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[KnownPersonResponse])
        return adapter.validate_python(response.json())

    async def get_person_faces(self, person_id: int) -> list[FaceResponse]:
        """Get all faces associated with a known person.

        Args:
            person_id: Known person ID

        Returns:
            List of FaceResponse models

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/known-persons/{person_id}/faces",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[FaceResponse])
        return adapter.validate_python(response.json())

    async def search_similar_images(
        self,
        entity_id: int,
        limit: int = 5,
        score_threshold: float = 0.85,
        include_details: bool = False,
    ) -> SimilarImagesResponse:
        """Find similar images using CLIP embeddings.

        Args:
            entity_id: Entity ID
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0.0 - 1.0)
            include_details: Whether to include full entity details

        Returns:
            SimilarImagesResponse object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params = {
            "limit": limit,
            "score_threshold": score_threshold,
            "include_details": str(include_details).lower(),
        }

        response = await self._client.get(
            f"{self._base_url}/intelligence/entities/{entity_id}/similar",
            params=params,
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return SimilarImagesResponse.model_validate(response.json())

    async def search_similar_faces(
        self,
        face_id: int,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> SimilarFacesResponse:
        """Find similar faces using face embeddings.

        Args:
            face_id: Face ID
            limit: Maximum number of results
            threshold: Minimum similarity score (0.0 - 1.0)

        Returns:
            SimilarFacesResponse object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        params = {
            "limit": limit,
            "threshold": threshold,
        }

        response = await self._client.get(
            f"{self._base_url}/intelligence/faces/{face_id}/similar",
            params=params,
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return SimilarFacesResponse.model_validate(response.json())

    async def get_face_matches(self, face_id: int) -> list[FaceMatchResult]:
        """Get all match records for a face.

        Args:
            face_id: Face ID

        Returns:
            List of FaceMatchResult
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(
            f"{self._base_url}/intelligence/faces/{face_id}/matches",
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[FaceMatchResult])
        return adapter.validate_python(response.json())

    async def update_known_person_name(
        self,
        person_id: int,
        name: str,
    ) -> KnownPersonResponse:
        """Update a known person's name.

        Args:
            person_id: Known Person ID
            name: New name

        Returns:
            Updated KnownPersonResponse
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.patch(
            f"{self._base_url}/intelligence/known-persons/{person_id}",
            json={"name": name},
            headers=await self._get_headers(),
        )
        _ = response.raise_for_status()
        return KnownPersonResponse.model_validate(response.json())



