"""Batch integration test for MInsight intelligence tracking."""

import asyncio
import sys
import time
import uuid
from pathlib import Path as PathlibPath

import pytest
from tests.test_utils import create_unique_copy

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import AuthConfig, should_succeed





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
    
    # Check if worker is running or idle (both mean it's online)
    status = status_result.data
    assert status and status.get("status") in ["running", "idle"], f"MInsight worker not online. Status: {status}"
    
    # 2. Upload 30 unique images in parallel
    NUM_IMAGES = 30
    print(f"\nUploading {NUM_IMAGES} unique images...")
    
    tasks = []
    entity_ids = []
    
    for i in range(NUM_IMAGES):
        unique_path = tmp_path / f"batch_{i}_{uuid.uuid4().hex[:6]}.jpg"
        create_unique_copy(test_image, unique_path, offset=i)
        
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
        # Check intelligence status for each pending entity
        for entity_id in list(pending_ids):
            intel_result = await store_manager.get_entity_intelligence(entity_id)

            if intel_result.is_success and intel_result.data:
                # We accept any state that indicates MInsight has at least acknowledged/picked up the image
                status = intel_result.data.overall_status
                if status in ["queued", "processing", "completed"]:
                    pending_ids.remove(entity_id)

        if pending_ids:
            print(f"  {len(pending_ids)} images still not picked up by MInsight...")
            await asyncio.sleep(2)
            
    # Final check
    if pending_ids:
        # Get details for failures
        failed_details = []
        for pid in pending_ids:
            intel_res = await store_manager.get_entity_intelligence(pid)
            if intel_res.is_success and intel_res.data:
                status = intel_res.data.overall_status
            else:
                status = "no intelligence data"
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
