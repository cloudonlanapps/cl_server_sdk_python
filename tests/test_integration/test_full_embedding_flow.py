import asyncio
import os
from pathlib import Path

import pytest
from cl_client import StoreManager
from loguru import logger

TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server_test_media")
)


# Define test cases: (image_filename, expected_face_count)
# Reduced to 3 images to avoid overwhelming the single worker during testing
# Full test with 6 images would require ~24 concurrent jobs which exceeds worker capacity
TEST_IMAGES = [
    ("test_face_single.jpg", 2),
    ("test_image_1920x1080.jpg", 0),  # No face
    ("IMG20240901130125.jpg", 3),
    # ("IMG20240901202523.jpg", 5),
    # ("IMG20240901194834.jpg", 3),
    # ("IMG20240901193819.jpg", 9), # Takes too long often
    # ("IMG20240901153107.jpg", 1),
]


@pytest.mark.integration
@pytest.mark.asyncio
#@pytest.mark.skip(reason="Skipping temporarily as this test is expeected to hang")
async def test_full_embedding_flow(
    store_manager: StoreManager,
    compute_server_info: dict[str, object],  # Wait for compute to be ready
    tmp_path: Path,
):
    """Verify that uploaded images get all embeddings and face processing."""
    from .test_utils import create_unique_copy
    
    # Increase timeout for heavy models cold start
    TIMEOUT = 300.0
    
    # Store pending verifications: (entity, expected_faces, wait_task)
    pending_verifications = []

    try:
        # 1. Upload all test images and start monitoring immediately
        for filename, expected_faces in TEST_IMAGES:
            source_path = TEST_VECTORS_DIR / "images" / filename
            assert source_path.exists(), f"Test image not found: {source_path}"
            
            # Create a unique copy to avoid MD5 deduplication issues in group tests
            image_path = tmp_path / f"unique_{filename}"
            create_unique_copy(source_path, image_path)

            logger.info(f"Uploading {filename} (unique copy)...")
            create_result = await store_manager.create_entity(
                is_collection=False,
                label=f"Test Integration {filename}",
                image_path=image_path,
            )
            assert create_result.is_success
            entity = create_result.value_or_throw()
            
            logger.info(f"Created entity {entity.id} for {filename}")
            
            # Start monitoring waiting immediately to catch early status updates
            logger.info(f"Starting status monitor for entity {entity.id}...")
            wait_task = asyncio.create_task(store_manager.wait_for_entity_status(
                entity_id=entity.id,
                target_status="completed",
                timeout=TIMEOUT
            ))
            pending_verifications.append((entity, expected_faces, wait_task))

        # 2. Verify processing for each entity
        for entity, expected_faces, wait_task in pending_verifications:
            logger.info(f"Waiting for entity {entity.id} ({entity.label}) to complete processing...")
            
            # Await the pre-created task
            try:
                status_payload = await wait_task
                logger.info(f"Entity {entity.id} completed with final status: {status_payload}")
            except Exception as e:
                pytest.fail(f"Entity {entity.id} failed to complete: {e}")

            # Verify all artifacts are present
            logger.info(f"Verifying artifacts for entity {entity.id}...")

            # B. Verify Face Count
            faces_result = await store_manager.get_entity_faces(entity.id)
            assert faces_result.is_success
            faces = faces_result.value_or_throw()
            assert len(faces) == expected_faces, \
                f"Expected {expected_faces} faces, found {len(faces)} for {entity.label}"

            # C. Verify CLIP Embedding
            embedding_result = await store_manager.download_entity_clip_embedding(entity.id)
            assert embedding_result.is_success, "Failed to download CLIP embedding"
            assert len(embedding_result.value_or_throw()) > 0, "Empty CLIP embedding downloaded"

            # D. Verify DINO Embedding
            dino_result = await store_manager.download_entity_dino_embedding(entity.id)
            assert dino_result.is_success, "Failed to download DINO embedding"
            assert len(dino_result.value_or_throw()) > 0, "Empty DINO embedding downloaded"

            # E. If faces detected, verify Face Embeddings and Person Assignment
            if expected_faces > 0:
                # Verify each face has a known person or embedding
                for face in faces:
                    # Check if face embedding can be downloaded
                    face_emb_result = await store_manager.download_face_embedding(face.id)
                    assert face_emb_result.is_success, f"Failed to download embedding for face {face.id}"
                    
                    # Verify person assignment (might be None if new person, but field should exist)
                    logger.info(f"Face {face.id} assigned to person: {face.known_person_id}")

    finally:
        # Cleanup
        logger.info("Cleaning up test entities...")
        # Since we might have crashed before populating all pending_verifications, use whatever we have
        for entity_data in pending_verifications:
            # Unpack tuple
            if len(entity_data) >= 1:
                entity = entity_data[0]
                await store_manager.delete_entity(entity.id)
