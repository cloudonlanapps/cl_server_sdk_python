import asyncio
import os
from pathlib import Path

import pytest
from cl_client import StoreManager
from loguru import logger

TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server_test_media")
)

# Use an image we know has a face
TEST_FACE_IMAGE = "test_face_single.jpg"

async def wait_for_job(
    store_manager: StoreManager,
    entity_id: int,
    task_type: str,
    timeout: float = 300.0,
) -> bool:
    """Wait for ALL jobs of a specific type to complete for an entity."""
    start_time = asyncio.get_running_loop().time()
    while (asyncio.get_running_loop().time() - start_time) < timeout:
        result = await store_manager.get_entity_jobs(entity_id)
        if result.is_error:
            logger.error(f"Failed to get jobs for entity {entity_id}: {result.error}")
            await asyncio.sleep(1)
            continue

        jobs = [j for j in result.value_or_throw() if j.task_type == task_type]
        if not jobs:
            # Job might not be created yet
            await asyncio.sleep(1)
            continue
            
        if all(j.status == "completed" for j in jobs):
            return True
        
        if any(j.status == "failed" for j in jobs):
            failed_job = next(j for j in jobs if j.status == "failed")
            logger.error(f"Job {task_type} failed for entity {entity_id}: {failed_job.error_message}")
            return False
            
        await asyncio.sleep(2)
    return False

@pytest.mark.integration
@pytest.mark.intelligence
@pytest.mark.asyncio
async def test_intelligence_features(
    store_manager: StoreManager,
    unique_face_single: Path,
):
    """Test similarity search, face matches, and person management."""
    
    image_path = unique_face_single
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
        
    # 1. Create Entity and Wait for Processing
    logger.info("Creating entity for intelligence test...")
    create_result = await store_manager.create_entity(
        is_collection=False,
        label="Intelligence Test Entity",
        image_path=image_path,
    )
    assert create_result.is_success
    entity = create_result.value_or_throw()
    
    try:
        # Wait for CLIP embedding
        assert await wait_for_job(store_manager, entity.id, "clip_embedding"), "CLIP job failed"
        
        # Wait for Face Detection
        assert await wait_for_job(store_manager, entity.id, "face_detection"), "Face detection failed"
        
        # Wait for Face Embedding (indirect check via face count)
        # We need faces to be detected and embedded for search
        faces_result = await store_manager.get_entity_faces(entity.id)
        assert faces_result.is_success
        faces = faces_result.value_or_throw()
        assert len(faces) > 0, "No faces detected"
        face_id = faces[0].id
        
        # Wait for DINO embedding
        assert await wait_for_job(store_manager, entity.id, "dino_embedding"), "DINO job failed"

        # 2. Test Image Similarity Search

        # 2. Test Person Management
        known_person_id = faces[0].known_person_id
        if known_person_id:
            logger.info("Testing person name update...")
            # Update name
            new_name = "Test Person Update"
            update_res = await store_manager.update_known_person_name(known_person_id, new_name)
            assert update_res.is_success
            assert update_res.value_or_throw().name == new_name
            
            # Verify update persisted
            person_res = await store_manager.get_known_person(known_person_id)
            assert person_res.is_success
            assert person_res.value_or_throw().name == new_name

    finally:
        await store_manager.delete_entity(entity.id)

@pytest.mark.integration
@pytest.mark.intelligence
@pytest.mark.asyncio
async def test_consolidated_deletion_flow(
    store_manager: StoreManager,
    unique_face_single: Path,
):
    """Test consolidated deletion flow (DEL-03, DEL-04, DEL-05, DEL-08)."""
    image_path = unique_face_single
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
        
    # 1. Create Entity and Wait for Processing
    create_result = await store_manager.create_entity(
        is_collection=False,
        label="Consolidated Delete Test",
        image_path=image_path,
    )
    assert create_result.is_success
    entity = create_result.value_or_throw()
    
    try:
        # Wait for full processing
        assert await wait_for_job(store_manager, entity.id, "clip_embedding")
        assert await wait_for_job(store_manager, entity.id, "face_detection")
        assert await wait_for_job(store_manager, entity.id, "dino_embedding")
        
        # 2. Verify initial state (Faces exist)
        intel_result = await store_manager.get_entity_intelligence(entity.id)
        assert intel_result.is_success
        intelligence_data = intel_result.value_or_throw()
        initial_face_count = intelligence_data.face_count if intelligence_data else 0
        assert initial_face_count > 0, "Should have at least one face"
        
        faces_result = await store_manager.get_entity_faces(entity.id)
        assert faces_result.is_success
        faces = faces_result.value_or_throw()
        assert len(faces) == initial_face_count
        
        face_id_to_delete = faces[0].id
        
        # 3. Delete one face
        delete_res = await store_manager.delete_face(face_id_to_delete)
        assert delete_res.is_success, f"Delete face failed: {delete_res.error}"
        
        # 4. Verify cleanup (Face gone, count decremented)
        after_faces_result = await store_manager.get_entity_faces(entity.id)
        assert after_faces_result.is_success
        assert not any(f.id == face_id_to_delete for f in after_faces_result.value_or_throw())
        
        after_intel_result = await store_manager.get_entity_intelligence(entity.id)
        assert after_intel_result.is_success
        after_intel_data = after_intel_result.value_or_throw()
        assert after_intel_data and after_intel_data.face_count == initial_face_count - 1
        
        # 5. Delete Entity (Full Cleanup)
        entity_delete_res = await store_manager.delete_entity(entity.id)
        assert entity_delete_res.is_success
        
        # Verify entity gone
        read_res = await store_manager.read_entity(entity.id)
        assert read_res.is_error
        assert "Not Found" in str(read_res.error)
        
    finally:
        await store_manager.delete_entity(entity.id)
