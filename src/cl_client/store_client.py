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

    def _get_headers(self) -> dict[str, str]:
        """Get headers for requests (auth only, no Content-Type).

        Content-Type is automatically set by httpx for multipart/form-data.
        """
        headers: dict[str, str] = {}
        if self.auth_provider:
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
            headers=self._get_headers(),
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

        params: dict[str, int | str] = {
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
            headers=self._get_headers(),
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
            headers=self._get_headers(),
        )
        _ = response.raise_for_status()
        adapter = TypeAdapter(list[EntityVersion])
        return adapter.validate_python(response.json())

