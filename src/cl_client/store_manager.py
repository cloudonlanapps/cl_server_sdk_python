"""High-level facade for store service operations.

This module provides a high-level API for managing media entities in the store,
with consistent error handling via StoreOperationResult wrapper.

Matches the Dart SDK StoreManager pattern.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import httpx
import uuid
import asyncio

from .auth import JWTAuthProvider
from .config import ComputeClientConfig
from .server_pref import ServerPref
from .store_client import StoreClient
from .mqtt_monitor import MQTTJobMonitor, EntityStatusPayload, get_mqtt_monitor, release_mqtt_monitor
from .types import UNSET, Unset
from .store_models import (
    Entity,
    EntityListResponse,
    EntityVersion,
    StoreConfig,
    StoreOperationResult,
    AuditReport,
    CleanupReport,
)
from .intelligence_models import (
    EntityIntelligenceData,
    EntityJobResponse,
    FaceResponse,
    KnownPersonResponse,
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

    def __init__(self, store_client: StoreClient, server_pref: ServerPref | None = None):
        """Initialize with a StoreClient.

        Args:
            store_client: Configured StoreClient instance
            server_pref: Server configuration (needed for MQTT connection info)
        """
        self._store_client: StoreClient = store_client
        self._mqtt_monitor: MQTTJobMonitor | None = None
        
        # Get config for defaults
        self._config: ServerPref = server_pref or ServerPref.from_env()
        self._mqtt_subscriptions: dict[str, str] = {} # user_sub_id -> internal_sub_id

    def _get_mqtt_monitor(self) -> MQTTJobMonitor:
        """Get or create MQTT monitor (lazy init)."""
        if self._mqtt_monitor:
            return self._mqtt_monitor
        
        # Need config to init MQTT
        # If created via guest() or authenticated(), we might have config stored?
        # Updated factories to pass config or we use defaults.
        
        url = ComputeClientConfig.MQTT_URL
        
        if self._config:
            url = self._config.mqtt_url
            
        self._mqtt_monitor = get_mqtt_monitor(url=url)
        return self._mqtt_monitor

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
    def guest(cls, base_url: str = "http://localhost:8001", timeout: float = 30.0) -> "StoreManager":
        """Create StoreManager in guest mode (no authentication).

        Guest mode allows read operations if read_auth is disabled on the server.
        Write operations will fail with 401 Unauthorized.

        Args:
            base_url: Store service base URL
            timeout: Request timeout in seconds (default: 30.0)

        Returns:
            StoreManager instance configured for guest access
        """
        manager = cls(StoreClient(base_url=base_url, timeout=timeout))
        # Note: Guest mode usually doesn't have config object passed, so we rely on defaults
        return manager

    @classmethod
    def authenticated(
        cls,
        server_pref: ServerPref,
        get_cached_token: Callable[[], str] | None = None,
        get_valid_token_async: Callable[[], Awaitable[str]] | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> "StoreManager":
        """Create StoreManager with authentication from SessionManager.

        Args:
            session_manager: Authenticated SessionManager instance
            base_url: Optional store service URL (defaults to session's store_url)
            get_cached_token: Synchronous token getter
            get_valid_token_async: Async token getter with auto-refresh
            timeout: Request timeout in seconds (default: 30.0)

        Returns:
            StoreManager instance configured with authentication
        """
        url = base_url or server_pref.store_url
        auth_provider = JWTAuthProvider(
            get_cached_token=get_cached_token,
            get_valid_token_async=get_valid_token_async
        )
        manager = cls(
            StoreClient(base_url=url, auth_provider=auth_provider, timeout=timeout),
            server_pref=server_pref
        )
        return manager

    async def __aenter__(self) -> "StoreManager":
        """Async context manager entry."""
        _ = await self._store_client.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        await self._store_client.__aexit__(None, None, None)
        if self._mqtt_monitor:
            release_mqtt_monitor(self._mqtt_monitor)
            self._mqtt_monitor = None

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
        exclude_deleted: bool = False,
    ) -> StoreOperationResult[EntityListResponse]:
        """List entities with pagination and optional search.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            search_query: Optional search query for label/description
            exclude_deleted: Whether to exclude soft-deleted entities

        Returns:
            StoreOperationResult containing EntityListResponse or error
        """
        try:
            result = await self._store_client.list_entities(
                page=page,
                page_size=page_size,
                search_query=search_query,
                exclude_deleted=exclude_deleted,
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

    def monitor_entity(
        self, 
        entity_id: int, 
        callback: Callable[[EntityStatusPayload], None] | Callable[[EntityStatusPayload], Awaitable[None]]
    ) -> str:
        """Monitor entity status changes via MQTT.
        
        Args:
            entity_id: Entity ID to monitor
            callback: Function called on status updates
            
        Returns:
            Subscription ID (use with stop_monitoring)
        """
        monitor = self._get_mqtt_monitor()
        
        # Determine store port (usually from config or default)
        store_port = 8001
        if self._config:
            try:
                # Extract port from store_url if possible, usually http://host:port/...
                from urllib.parse import urlparse
                parsed = urlparse(self._config.store_url)
                if parsed.port:
                    store_port = parsed.port
            except Exception:
                pass
        
        internal_sub_id = monitor.subscribe_entity_status(entity_id, store_port, callback)
        user_sub_id = str(uuid.uuid4())
        self._mqtt_subscriptions[user_sub_id] = internal_sub_id
        return user_sub_id

    def stop_monitoring(self, subscription_id: str) -> None:
        """Stop monitoring an entity.
        
        Args:
            subscription_id: ID returned from monitor_entity
        """
        if subscription_id in self._mqtt_subscriptions:
            internal_id = self._mqtt_subscriptions[subscription_id]
            if self._mqtt_monitor:
                self._mqtt_monitor.unsubscribe_entity_status(internal_id)
            del self._mqtt_subscriptions[subscription_id]

    async def wait_for_entity_status(
        self,
        entity_id: int,
        target_status: str = "completed",
        timeout: float = 60.0,
        fail_on_error: bool = True
    ) -> EntityStatusPayload:
        """Wait for entity to reach specific status.

        Args:
            entity_id: Entity ID
            target_status: Status to wait for (default: "completed")
            timeout: Max wait time in seconds
            fail_on_error: If True, raises exception if status becomes "failed"

        Returns:
            Final status payload

        Raises:
            TimeoutError: If timeout reached
            RuntimeError: If failed (and fail_on_error=True)
        """
        from loguru import logger

        loop = asyncio.get_running_loop()
        future: asyncio.Future[EntityStatusPayload] = loop.create_future()
        callback_executed = False
        callback_lock = asyncio.Lock()

        def _callback(payload: EntityStatusPayload):
            """Callback that ensures the future is only set once (prevents InvalidStateError)."""
            nonlocal callback_executed

            # Check if already executed without acquiring lock (fast path)
            if callback_executed or future.done():
                return

            if payload.status == target_status:
                logger.debug(f"Entity {entity_id} reached target status {target_status} via MQTT")
                # Use call_soon_threadsafe since MQTT callback runs in a different thread
                def _set_result():
                    nonlocal callback_executed
                    if not callback_executed and not future.done():
                        callback_executed = True
                        future.set_result(payload)
                loop.call_soon_threadsafe(_set_result)
            elif fail_on_error and payload.status == "failed":
                def _set_exception():
                    nonlocal callback_executed
                    if not callback_executed and not future.done():
                        callback_executed = True
                        future.set_exception(RuntimeError(f"Entity processing failed: {payload}"))
                loop.call_soon_threadsafe(_set_exception)

        # Subscribe to MQTT FIRST, before checking status
        # This ensures we won't miss messages that arrive after our status check
        sub_id = self.monitor_entity(entity_id, _callback)

        try:
            # Give MQTT subscription a moment to be established
            await asyncio.sleep(0.1)

            # Now check current status - if already at target, manually trigger callback
            # This catches entities that completed before/during MQTT subscription
            entity_result = await self.read_entity(entity_id)
            if entity_result.is_success:
                entity = entity_result.value_or_throw()
                current_status = entity.intelligence_status

                if current_status in (target_status, "failed"):
                    logger.debug(f"Entity {entity_id} already at status {current_status}, manually triggering callback")
                    # Create a payload and manually call the callback
                    payload = EntityStatusPayload(
                        entity_id=entity_id,
                        status=current_status,
                        timestamp=entity.intelligence_data.last_updated if entity.intelligence_data else 0,
                        face_detection=entity.intelligence_data.inference_status.face_detection if entity.intelligence_data else None,
                        face_count=entity.intelligence_data.face_count if entity.intelligence_data else None,
                        clip_embedding=entity.intelligence_data.inference_status.clip_embedding if entity.intelligence_data else None,
                        dino_embedding=entity.intelligence_data.inference_status.dino_embedding if entity.intelligence_data else None,
                        face_embeddings=entity.intelligence_data.inference_status.face_embeddings if entity.intelligence_data else None,
                    )
                    _callback(payload)

            # Wait for the callback to set the future (either from MQTT or manual trigger)
            return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Timeout waiting for entity {entity_id} to reach {target_status}")
        finally:
            # Always clean up subscription
            self.stop_monitoring(sub_id)

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
        label: str | None | Unset = UNSET,
        description: str | None | Unset = UNSET,
        parent_id: int | None | Unset = UNSET,
        is_deleted: bool | None | Unset = UNSET,
        is_collection: bool | None | Unset = UNSET,
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
                is_collection=is_collection,
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
        force: bool = True,
    ) -> StoreOperationResult[None]:
        """Hard delete an entity (permanent removal).

        Args:
            entity_id: Entity ID to delete
            force: If True (default), automatically soft-delete first if not already soft-deleted.
                   Implemented as a two-step process: PATCH is_deleted=True, then DELETE.

        Returns:
            StoreOperationResult with success/error status
        """
        try:
            if force:
                # Step 1: Ensure it's soft-deleted
                # We check current status first or just try to patch
                patch_res = await self.patch_entity(entity_id, is_deleted=True)
                if not patch_res.is_success:
                    # If entity doesn't exist, patch will fail with 404
                    if "Not Found" in str(patch_res.error) or "404" in str(patch_res.error):
                         return cast(StoreOperationResult[None], patch_res)
                    # For other errors (like permission), we can't proceed
                    return cast(StoreOperationResult[None], patch_res)

            # Step 2: Hard delete
            await self._store_client.delete_entity(entity_id=entity_id)
            return StoreOperationResult[None](
                success="Entity deleted successfully",
                data=None,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[None], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[None](error=f"Unexpected error: {str(e)}")

    async def delete_face(self, face_id: int) -> StoreOperationResult[None]:
        """Delete a face completely.

        Args:
            face_id: Face ID to delete

        Returns:
            StoreOperationResult with success/error status
        """
        try:
            await self._store_client.delete_face(face_id)
            return StoreOperationResult[None](
                success="Face deleted successfully",
                data=None,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[None], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[None](error=f"Unexpected error: {str(e)}")

    async def get_audit_report(self) -> StoreOperationResult[AuditReport]:
        """Generate a comprehensive audit report (admin only).

        Returns:
            StoreOperationResult with AuditReport
        """
        try:
            report = await self._store_client.get_audit_report()
            return StoreOperationResult[AuditReport](
                success="Audit report generated successfully",
                data=report,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[AuditReport], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[AuditReport](error=f"Unexpected error: {str(e)}")

    async def clear_orphans(self) -> StoreOperationResult[CleanupReport]:
        """Remove all orphaned resources (admin only).

        Returns:
            StoreOperationResult with CleanupReport
        """
        try:
            report = await self._store_client.clear_orphans()
            return StoreOperationResult[CleanupReport](
                success="Orphaned resources cleared successfully",
                data=report,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[CleanupReport], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[CleanupReport](error=f"Unexpected error: {str(e)}")

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

    async def get_m_insight_status(self) -> StoreOperationResult[dict[str, object]]:
        """Get MInsight process status (admin only).
        
        Requires admin role.
        
        Returns:
            StoreOperationResult with status dictionary
        """
        try:
            status = await self._store_client.get_m_insight_status()
            return StoreOperationResult[dict[str, object]](
                success="MInsight status retrieved successfully",
                data=status,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[dict[str, object]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[dict[str, object]](error=f"Unexpected error: {str(e)}")

    # Intelligence operations

    async def get_entity_intelligence(
        self, entity_id: int
    ) -> StoreOperationResult[EntityIntelligenceData | None]:
        """Get intelligence data for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult with EntityIntelligenceData or None
        """
        try:
            intelligence = await self._store_client.get_entity_intelligence(entity_id)
            return StoreOperationResult[EntityIntelligenceData | None](
                success="Intelligence data retrieved successfully",
                data=intelligence,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[EntityIntelligenceData | None], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[EntityIntelligenceData | None](error=f"Unexpected error: {str(e)}")

    async def get_entity_faces(self, entity_id: int) -> StoreOperationResult[list[FaceResponse]]:
        """Get all faces detected in an entity.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult with list of FaceResponse
        """
        try:
            faces = await self._store_client.get_entity_faces(entity_id)
            return StoreOperationResult[list[FaceResponse]](
                success="Faces retrieved successfully",
                data=faces,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[list[FaceResponse]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[list[FaceResponse]](error=f"Unexpected error: {str(e)}")

    async def get_entity_jobs(self, entity_id: int) -> StoreOperationResult[list[EntityJobResponse]]:
        """Get all compute jobs for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult with list of EntityJobResponse
        """
        try:
            jobs = await self._store_client.get_entity_jobs(entity_id)
            return StoreOperationResult[list[EntityJobResponse]](
                success="Jobs retrieved successfully",
                data=jobs,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[list[EntityJobResponse]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[list[EntityJobResponse]](error=f"Unexpected error: {str(e)}")

    async def download_entity_clip_embedding(self, entity_id: int) -> StoreOperationResult[bytes]:
        """Download entity CLIP embedding as .npy bytes.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult with raw bytes of .npy file
        """
        try:
            data = await self._store_client.download_entity_clip_embedding(entity_id)
            return StoreOperationResult[bytes](
                success="CLIP embedding downloaded successfully",
                data=data,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[bytes], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[bytes](error=f"Unexpected error: {str(e)}")

    async def download_entity_dino_embedding(self, entity_id: int) -> StoreOperationResult[bytes]:
        """Download entity DINO embedding as .npy bytes.

        Args:
            entity_id: Entity ID

        Returns:
            StoreOperationResult with raw bytes of .npy file
        """
        try:
            data = await self._store_client.download_entity_dino_embedding(entity_id)
            return StoreOperationResult[bytes](
                success="DINO embedding downloaded successfully",
                data=data,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[bytes], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[bytes](error=f"Unexpected error: {str(e)}")

    async def download_face_embedding(self, face_id: int) -> StoreOperationResult[bytes]:
        """Download face embedding as .npy bytes.

        Args:
            face_id: Face ID

        Returns:
            StoreOperationResult with raw bytes of .npy file
        """
        try:
            data = await self._store_client.download_face_embedding(face_id)
            return StoreOperationResult[bytes](
                success="Face embedding downloaded successfully",
                data=data,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[bytes], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[bytes](error=f"Unexpected error: {str(e)}")

    async def get_known_persons(self) -> StoreOperationResult[list[KnownPersonResponse]]:
        """Get all known persons.

        Returns:
            StoreOperationResult with list of KnownPersonResponse
        """
        try:
            persons = await self._store_client.get_known_persons()
            return StoreOperationResult[list[KnownPersonResponse]](
                success="Known persons retrieved successfully",
                data=persons,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[list[KnownPersonResponse]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[list[KnownPersonResponse]](error=f"Unexpected error: {str(e)}")

    async def get_known_person(self, person_id: int) -> StoreOperationResult[KnownPersonResponse]:
        """Get known person details.

        Args:
            person_id: Known person ID

        Returns:
            StoreOperationResult with KnownPersonResponse
        """
        try:
            person = await self._store_client.get_known_person(person_id)
            return StoreOperationResult[KnownPersonResponse](
                success="Known person details retrieved successfully",
                data=person,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[KnownPersonResponse], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[KnownPersonResponse](error=f"Unexpected error: {str(e)}")

    async def get_person_faces(self, person_id: int) -> StoreOperationResult[list[FaceResponse]]:
        """Get all faces associated with a known person.

        Args:
            person_id: Known person ID

        Returns:
            StoreOperationResult with list of FaceResponse
        """
        try:
            faces = await self._store_client.get_person_faces(person_id)
            return StoreOperationResult[list[FaceResponse]](
                success="Person faces retrieved successfully",
                data=faces,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[list[FaceResponse]], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[list[FaceResponse]](error=f"Unexpected error: {str(e)}")


    

    
    async def update_known_person_name(
        self,
        person_id: int,
        name: str,
    ) -> StoreOperationResult[KnownPersonResponse]:
        """Update a known person's name.

        Args:
            person_id: Known Person ID
            name: New name

        Returns:
            StoreOperationResult with updated KnownPersonResponse
        """
        try:
            person = await self._store_client.update_known_person_name(person_id, name)
            return StoreOperationResult[KnownPersonResponse](
                success="Person name updated successfully",
                data=person,
            )
        except httpx.HTTPStatusError as e:
            return cast(StoreOperationResult[KnownPersonResponse], self._handle_error(e))
        except Exception as e:
            return StoreOperationResult[KnownPersonResponse](error=f"Unexpected error: {str(e)}")
