import asyncio
import os
from pathlib import Path

import pytest
from cl_client import ComputeClient, StoreManager
from loguru import logger

TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server_test_media")
)


# Define test cases: (image_filename, expected_face_count)
TEST_IMAGES = [
    ("test_face_single.jpg", 2),
    ("test_image_1920x1080.jpg", 0),  # No face
    ("IMG20240901130125.jpg", 3),
    ("IMG20240901202523.jpg", 5),
    ("IMG20240901194834.jpg", 3),
    # ("IMG20240901193819.jpg", 9), # Takes too long often
    ("IMG20240901153107.jpg", 1),
]


async def wait_for_job(
    store_manager: StoreManager,
    entity_id: int,
    task_type: str,
    timeout: float = 60.0,
) -> bool:
    """Wait for a specific job type to complete for an entity."""
    start_time = asyncio.get_running_loop().time()
    while (asyncio.get_running_loop().time() - start_time) < timeout:
        result = await store_manager.get_entity_jobs(entity_id)
        if result.is_error:
            logger.error(f"Failed to get jobs for entity {entity_id}: {result.error}")
            await asyncio.sleep(1)
            continue

        jobs = result.value_or_throw()
        for job in jobs:
            if job.task_type == task_type:
                if job.status == "completed":
                    return True
                if job.status == "failed":
                    logger.error(f"Job {task_type} failed for entity {entity_id}: {job.error_message}")
                    return False
        
        await asyncio.sleep(1)
    
    logger.error(f"Timeout waiting for {task_type} for entity {entity_id}")
    # Print all jobs for debugging
    result = await store_manager.get_entity_jobs(entity_id)
    if result.is_success:
        jobs = result.value_or_throw()
        logger.error(f"Current jobs for entity {entity_id}: {[j.model_dump() for j in jobs]}")
    return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_embedding_flow(
    store_manager: StoreManager,
    compute_server_info: dict,  # Wait for compute to be ready
):
    """Verify that uploaded images get all embeddings and face processing."""
    
    # Increase timeout for heavy models cold start
    TIMEOUT = 300.0
    
    created_entities = []

    try:
        # 1. Upload all test images
        for filename, expected_faces in TEST_IMAGES:
            image_path = TEST_VECTORS_DIR / "images" / filename
            assert image_path.exists(), f"Test image not found: {image_path}"

            logger.info(f"Uploading {filename}...")
            create_result = await store_manager.create_entity(
                is_collection=False,
                label=f"Test Integration {filename}",
                image_path=image_path,
            )
            assert create_result.is_success
            entity = create_result.value_or_throw()
            created_entities.append((entity, expected_faces))
            logger.info(f"Created entity {entity.id} for {filename}")

        # 2. Verify processing for each entity
        for entity, expected_faces in created_entities:
            logger.info(f"Verifying processing for entity {entity.id} ({entity.label})")

            # A. Verify Face Detection Job
            assert await wait_for_job(store_manager, entity.id, "face_detection", timeout=TIMEOUT), \
                f"Face detection job failed or timed out for {entity.id}"

            # B. Verify Face Count
            faces_result = await store_manager.get_entity_faces(entity.id)
            assert faces_result.is_success
            faces = faces_result.value_or_throw()
            assert len(faces) == expected_faces, \
                f"Expected {expected_faces} faces, found {len(faces)} for {entity.label}"

            # C. Verify CLIP Embedding
            assert await wait_for_job(store_manager, entity.id, "clip_embedding", timeout=TIMEOUT), \
                f"CLIP embedding job failed or timed out for {entity.id}"
            
            # Verify we can download the embedding
            embedding_result = await store_manager.download_entity_embedding(entity.id)
            assert embedding_result.is_success, "Failed to download CLIP embedding"
            assert len(embedding_result.value_or_throw()) > 0, "Empty CLIP embedding downloaded"

            # D. Verify DINO Embedding
            assert await wait_for_job(store_manager, entity.id, "dino_embedding", timeout=TIMEOUT), \
                f"DINO embedding job failed or timed out for {entity.id}"

            # E. If faces detected, verify Face Embeddings and Person Assignment
            if expected_faces > 0:
                # Wait for face embedding jobs (one per face, mapped to parent entity)
                # Note: "face_embedding" jobs are tracked on the parent entity
                assert await wait_for_job(store_manager, entity.id, "face_embedding", timeout=TIMEOUT), \
                    f"Face embedding job failed for {entity.id}"

                # Verify each face has a known person or embedding
                for face in faces:
                    # Check if face embedding can be downloaded
                    face_emb_result = await store_manager.download_face_embedding(face.id)
                    assert face_emb_result.is_success, f"Failed to download embedding for face {face.id}"
                    
                    # Verify person assignment (might be None if new person, but field should exist)
                    # Note: We don't enforce *which* person, just that the data structure is valid
                    logger.info(f"Face {face.id} assigned to person: {face.known_person_id}")

    finally:
        # Cleanup
        logger.info("Cleaning up test entities...")
        for entity, _ in created_entities:
            await store_manager.delete_entity(entity.id)
