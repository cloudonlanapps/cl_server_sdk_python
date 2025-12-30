"""Shared fixtures for integration tests."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def media_dir() -> Path:
    """Get media directory path."""
    return Path(__file__).parent.parent / "media"


@pytest.fixture
def test_image(media_dir: Path) -> Path:
    """Get standard test image (HD JPEG)."""
    image_path = media_dir / "images" / "test_image_1920x1080.jpg"
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    return image_path


@pytest.fixture
def test_image_png(media_dir: Path) -> Path:
    """Get PNG test image."""
    image_path = media_dir / "images" / "test_image_800x600.png"
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    return image_path


@pytest.fixture
def test_image_exif(media_dir: Path) -> Path:
    """Get image with rich EXIF data."""
    image_path = media_dir / "images" / "test_exif_rich.jpg"
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    return image_path


@pytest.fixture
def test_image_face_single(media_dir: Path) -> Path:
    """Get image with single face."""
    image_path = media_dir / "images" / "test_face_single.jpg"
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    return image_path


@pytest.fixture
def test_image_face_multiple(media_dir: Path) -> Path:
    """Get image with multiple faces."""
    image_path = media_dir / "images" / "test_face_multiple.jpg"
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    return image_path


@pytest.fixture
def test_video_1080p(media_dir: Path) -> Path:
    """Get 1080p test video."""
    video_path = media_dir / "videos" / "test_video_1080p_10s.mp4"
    if not video_path.exists():
        pytest.skip(f"Test video not found: {video_path}")
    return video_path


@pytest.fixture
def test_video_720p(media_dir: Path) -> Path:
    """Get 720p test video."""
    video_path = media_dir / "videos" / "test_video_720p_5s.mp4"
    if not video_path.exists():
        pytest.skip(f"Test video not found: {video_path}")
    return video_path
