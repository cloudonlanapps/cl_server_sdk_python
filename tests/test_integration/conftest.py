"""Shared fixtures for integration tests."""

import os
from pathlib import Path
from typing import Any

import pytest

# Test vectors base directory (can be overridden via environment variable)
TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server/test_vectors")
)


@pytest.fixture(scope="session")
def media_dir() -> Path:
    """Get media directory path."""
    return TEST_VECTORS_DIR


@pytest.fixture
def test_image(media_dir: Path) -> Path:
    """Get standard test image (HD JPEG)."""
    image_path = media_dir / "images" / "test_image_1920x1080.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_png(media_dir: Path) -> Path:
    """Get PNG test image."""
    image_path = media_dir / "images" / "test_image_800x600.png"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_exif(media_dir: Path) -> Path:
    """Get image with rich EXIF data."""
    image_path = media_dir / "images" / "test_exif_rich.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_face_single() -> Path:
    """Get image with single face."""
    image_path = TEST_VECTORS_DIR / "images" / "test_face_single.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_face_multiple() -> Path:
    """Get image with multiple faces."""
    image_path = TEST_VECTORS_DIR / "images" / "test_face_multiple.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_video_1080p(media_dir: Path) -> Path:
    """Get 1080p test video."""
    video_path = media_dir / "videos" / "test_video_1080p_10s.mp4"
    assert video_path.exists(), f"Test video not found: {video_path}"
    return video_path


@pytest.fixture
def test_video_720p(media_dir: Path) -> Path:
    """Get 720p test video."""
    video_path = media_dir / "videos" / "test_video_720p_5s.mp4"
    assert video_path.exists(), f"Test video not found: {video_path}"
    return video_path


@pytest.fixture(scope="module", autouse=True)
async def cleanup_store_entities(request: Any):
    """Clean up all store entities before store integration tests run.

    This ensures tests start with a clean database and don't interfere with each other.
    Only runs for test_store_integration.py module.
    """
    # Only run for store integration tests
    if "test_store_integration" not in request.module.__name__:
        yield
        return

    # Import here to avoid circular dependency
    import httpx
    import os
    import json
    from pathlib import Path

    # Read URLs from auth_config.json
    config_path = Path(__file__).parent.parent / "auth_config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
            store_url = config.get("store_url", "http://localhost:8001")
            auth_url = config.get("auth_url", "http://localhost:8000")
    except Exception:
        # Fallback to defaults if config not found
        store_url = "http://localhost:8001"
        auth_url = "http://localhost:8000"

    admin_password = os.getenv("TEST_ADMIN_PASSWORD", "admin")

    # Get admin token
    try:
        async with httpx.AsyncClient() as client:
            # Login as admin
            response = await client.post(
                f"{auth_url}/auth/token",
                data={"username": "admin", "password": admin_password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                token = response.json()["access_token"]

                # Get all entities
                response = await client.get(
                    f"{store_url}/entities?page=1&page_size=1000",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code == 200:
                    entities = response.json()["items"]

                    # Delete all entities
                    for entity in entities:
                        await client.delete(
                            f"{store_url}/entities/{entity['id']}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
    except Exception:
        # If cleanup fails, continue anyway - tests will handle it
        pass

    yield
