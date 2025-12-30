"""Plugin clients for compute service tasks."""

from .base import BasePluginClient
from .clip_embedding import ClipEmbeddingClient
from .dino_embedding import DinoEmbeddingClient
from .exif import ExifClient
from .face_detection import FaceDetectionClient
from .face_embedding import FaceEmbeddingClient
from .hash import HashClient
from .hls_streaming import HlsStreamingClient
from .image_conversion import ImageConversionClient
from .media_thumbnail import MediaThumbnailClient

__all__ = [
    "BasePluginClient",
    "ClipEmbeddingClient",
    "DinoEmbeddingClient",
    "ExifClient",
    "FaceDetectionClient",
    "FaceEmbeddingClient",
    "HashClient",
    "HlsStreamingClient",
    "ImageConversionClient",
    "MediaThumbnailClient",
]
