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
        logger.info("Testing image similarity search...")
        # Self-search should return the image itself as top result
        sim_images = await store_manager.search_similar_images(entity.id, limit=5)
        assert sim_images.is_success
        results = sim_images.value_or_throw().results
        assert len(results) > 0
        # Check if our entity is in results (likely with score ~1.0)
        assert any(r.image_id == entity.id for r in results), "Self not found in similar images"

        # 3. Test Face Similarity Search
        logger.info("Testing face similarity search...")
        sim_faces = await store_manager.search_similar_faces(face_id, limit=5)
        assert sim_faces.is_success
        f_results = sim_faces.value_or_throw().results
        assert len(f_results) > 0
        # Self face might not be returned depending on Qdrant/Server logic often, 
        # but let's check basic response structure validity
        assert f_results[0].face_id is not None
        
        # 4. Test Face Matches
        logger.info("Testing face matches...")
        matches_res = await store_manager.get_face_matches(face_id)
        assert matches_res.is_success
        matches = matches_res.value_or_throw()
        assert isinstance(matches, list)
        
        # 5. Test Person Management
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
