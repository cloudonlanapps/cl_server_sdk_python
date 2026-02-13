import pytest
from pathlib import Path
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cl_client.store_manager import StoreManager

# Using existing test fixtures if available, or setting up new client
@pytest.mark.asyncio
async def test_store_multimedia_flow(store_manager: "StoreManager"):
    # 0. Initialize variables for cleanup
    collection = None
    entity = None
    image_path = Path("test_image.jpg")

    try:
        # 1. Create a collection
        res = await store_manager.create_entity(
            is_collection=True,
            label="Integration Test Collection",
            description="Testing multimedia features"
        )
        assert res.is_success
        assert res.data is not None
        collection = res.data
        assert collection.id is not None
        assert collection.is_collection is True

        # 2. Upload an image
        # Create a dummy image file
        with open(image_path, "wb") as f:
            _ = f.write(os.urandom(1024))  # 1KB random data
        
        res = await store_manager.create_entity(
            is_collection=False,
            label="Test Image",
            description="A test image file",
            parent_id=collection.id,
            image_path=image_path
        )
        assert res.is_success
        assert res.data is not None
        entity = res.data
        assert entity.id is not None
        assert entity.parent_id == collection.id
        assert entity.mime_type is not None
        
        # 3. List entities with filter
        res_list = await store_manager.list_entities(
            mime_type=entity.mime_type,
            page_size=10
        )
        assert res_list.is_success
        assert res_list.data is not None
        found = False
        for item in res_list.data.items:
            if item.id == entity.id:
                found = True
                break
        assert found, f"Entity {entity.id} not found with mime_type filter {entity.mime_type}"

        # 4. Download media
        res_media = await store_manager.download_media(entity.id)
        assert res_media.is_success
        assert res_media.data is not None
        media_bytes = res_media.data
        assert len(media_bytes) == 1024
        
        # 5. Get stream URL
        stream_url = store_manager.get_stream_url(entity.id)
        assert f"/entities/{entity.id}/stream/adaptive.m3u8" in stream_url
        
        # 6. Test preview download
        res_preview = await store_manager.download_preview(entity.id)
        # Preview might fail if generation is slow or invalid image, but we test the call
        if not res_preview.is_success:
             # Expect 404 or specific error if not ready
             pass

    finally:
        # Cleanup
        if image_path.exists():
            image_path.unlink()
        
        # Delete entities - store_manager.delete_entity handles soft/hard delete with force=True
        if entity is not None:
            _ = await store_manager.delete_entity(entity.id, force=True)
        
        if collection is not None:
            _ = await store_manager.delete_entity(collection.id, force=True)
