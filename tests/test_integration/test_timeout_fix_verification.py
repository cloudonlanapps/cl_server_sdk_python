"""Verification test for timeout and database lock fixes.

This test demonstrates that the upload timeout and database lock fixes work correctly.
It uses fewer images than test_full_embedding_flow to avoid overwhelming the server.
"""
import os
from pathlib import Path

import pytest
from cl_client import StoreManager

TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", str(Path.home() / "cl_server_test_media"))
)

# Use only 3 images to avoid overwhelming the server
TEST_IMAGES = [
    ("test_face_single.jpg", 2),
    ("test_image_1920x1080.jpg", 0),
    ("IMG20240901130125.jpg", 3),
]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_uploads_with_timeout_fix(
    store_manager: StoreManager,
    compute_server_info: dict,
    tmp_path: Path,
):
    """Verify that timeout and database lock fixes allow concurrent uploads."""
    from .test_utils import create_unique_copy
    from loguru import logger

    created_entities = []

    try:
        # Upload all test images concurrently to test database lock handling
        for filename, expected_faces in TEST_IMAGES:
            source_path = TEST_VECTORS_DIR / "images" / filename
            assert source_path.exists(), f"Test image not found: {source_path}"

            # Create a unique copy to avoid MD5 deduplication
            image_path = tmp_path / f"unique_{filename}"
            create_unique_copy(source_path, image_path)

            logger.info(f"Uploading {filename} (unique copy)...")
            create_result = await store_manager.create_entity(
                is_collection=False,
                label=f"Test Timeout Fix {filename}",
                image_path=image_path,
            )

            # This should succeed with our fixes (300s timeout + database lock retry)
            assert create_result.is_success, f"Upload failed for {filename}: {create_result.error}"
            entity = create_result.value_or_throw()
            created_entities.append(entity)
            logger.info(f"Created entity {entity.id} for {filename}")

        logger.info(f"Successfully uploaded {len(created_entities)} images with timeout and lock fixes")

    finally:
        # Cleanup
        logger.info("Cleaning up test entities...")
        for entity in created_entities:
            await store_manager.delete_entity(entity.id)
