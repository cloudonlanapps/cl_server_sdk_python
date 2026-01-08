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
async def cleanup_store_entities(
    request: Any,
    auth_config: dict[str, Any],
):
    """Clean up all store entities before store integration tests run.

    Runs only for test_store_integration.py.
    Uses CLI-provided auth credentials.
    """

    # Only run for store integration tests
    if "test_store_integration" not in request.module.__name__:
        yield
        return

    # Skip cleanup if no auth (cannot delete entities)
    if not auth_config["username"]:
        yield
        return

    # Cleanup requires admin
    if not auth_config["is_admin"]:
        pytest.skip("Store cleanup requires admin credentials")

    import httpx

    store_url = auth_config["store_url"]
    auth_url = auth_config["auth_url"]
    username = auth_config["username"]
    password = auth_config["password"]

    try:
        async with httpx.AsyncClient() as client:
            # Login
            token_resp = await client.post(
                f"{auth_url}/auth/token",
                data={
                    "username": username,
                    "password": password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=5.0,
            )

            if token_resp.status_code != 200:
                pytest.fail("Failed to authenticate admin for store cleanup")

            token = token_resp.json()["access_token"]

            # Fetch entities
            resp = await client.get(
                f"{store_url}/entities?page=1&page_size=1000",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )

            if resp.status_code != 200:
                yield
                return

            entities = resp.json().get("items", [])

            # Delete all
            for entity in entities:
                await client.delete(
                    f"{store_url}/entities/{entity['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )

    except Exception:
        # Non-fatal cleanup failure
        pass

    yield
