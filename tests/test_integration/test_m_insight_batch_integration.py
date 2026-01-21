"""Batch integration test for MInsight intelligence tracking."""

import asyncio
import sys
import time
import uuid
from pathlib import Path as PathlibPath

import pytest
from PIL import Image

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import AuthConfig, should_succeed


def create_unique_image(base_image: PathlibPath, output_path: PathlibPath, index: int):
    """Create a unique copy of an image by modifying a pixel."""
    with Image.open(base_image) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        pixels = img.load()
        if pixels:
            r, g, b = pixels[0, 0] # type: ignore
            # Modify pixel based on index to ensure uniqueness
            pixels[0, 0] = (r, g, (b + index + 1) % 256) # type: ignore
        img.save(output_path)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.intelligence
@pytest.mark.admin_only
async def test_m_insight_batch_upload_and_queue(
    store_manager, 
    test_image: PathlibPath, 
    tmp_path: PathlibPath,
    auth_config: AuthConfig
):
    """Test uploading 30 unique images and waiting for them to be queued by MInsight."""
    
    # 0. Check if we have required permissions (needs admin for MInsight status and write for upload)
    if not should_succeed(auth_config, "admin") or not should_succeed(auth_config, "store_write"):
        pytest.skip("Test requires admin and store_write permissions")

    # 1. Verify MInsight worker is online
    status_result = await store_manager.get_m_insight_status()
    assert status_result.is_success, f"Failed to get MInsight status: {status_result.error}"
    
    # Check for any online worker
    statuses = status_result.data or {}
    online_workers = [p for p, s in statuses.items() if s.get("status") == "running"]
    assert online_workers, "No MInsight workers reported 'running' status. Ensure MInsight process is started with MQTT enabled."
    
    # 2. Upload 30 unique images in parallel
    NUM_IMAGES = 30
    print(f"\nUploading {NUM_IMAGES} unique images...")
    
    tasks = []
    entity_ids = []
    
    for i in range(NUM_IMAGES):
        unique_path = tmp_path / f"batch_{i}_{uuid.uuid4().hex[:6]}.jpg"
        create_unique_image(test_image, unique_path, i)
        
        # We wrap in a coroutine to capture the resulting ID
        async def upload_task(path, idx):
            res = await store_manager.create_entity(
                label=f"Batch_Test_{idx}",
                is_collection=False,
                image_path=path
            )
            return res
            
        tasks.append(upload_task(unique_path, i))
    
    results = await asyncio.gather(*tasks)
    
    for r in results:
        assert r.is_success, f"Upload failed: {r.error}"
        entity_ids.append(r.data.id)
        
    print(f"Successfully uploaded {len(entity_ids)} images.")
    
    # 3. Poll for intelligence_status == "queued"
    # We use a per-image timeout budget of 5s, min 60s total
    TIMEOUT = max(60, NUM_IMAGES * 5)
    start_time = time.time()
    pending_ids = set(entity_ids)
    
    print(f"Waiting for MInsight to queue images (timeout: {TIMEOUT}s)...")
    
    while pending_ids and (time.time() - start_time < TIMEOUT):
        # We can poll in batches or one by one. Batch is better.
        list_result = await store_manager.list_entities(page_size=100)
        assert list_result.is_success
        
        for item in list_result.data.items:
            if item.id in pending_ids and item.intelligence_status == "queued":
                pending_ids.remove(item.id)
        
        if pending_ids:
            print(f"  {len(pending_ids)} images still pending...")
            await asyncio.sleep(2)
            
    # Final check
    if pending_ids:
        # Get details for failures
        failed_details = []
        for pid in pending_ids:
            item_res = await store_manager.read_entity(pid)
            status = item_res.data.intelligence_status if item_res.is_success else "unknown"
            failed_details.append(f"ID {pid}: status={status}")
            
        pytest.fail(
            f"Timed out waiting for {len(pending_ids)} images to be queued.\n"
            f"Failures: {', '.join(failed_details)}"
        )
    
    print("All images successfully queued by MInsight!")
    
    # 4. Cleanup
    print("Cleaning up test entities...")
    cleanup_tasks = [store_manager.delete_entity(eid) for eid in entity_ids]
    await asyncio.gather(*cleanup_tasks)
