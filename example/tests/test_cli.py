"""Unit tests for CLI commands."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from cl_client.models import JobResponse
from cl_client_cli.main import cli


class TestClipEmbedding:
    """Tests for clip-embedding commands."""

    def test_embed_polling_mode(self, mock_compute_client, temp_image_file, completed_job):
        """Test clip-embedding embed in polling mode."""
        # Configure mock
        mock_compute_client.clip_embedding.embed_image = AsyncMock(return_value=completed_job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["clip-embedding", "embed", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "test-job-123" in result.output
        assert "completed" in result.output.lower()
        mock_compute_client.clip_embedding.embed_image.assert_called_once()

    def test_embed_watch_mode(self, mock_compute_client, temp_image_file, completed_job):
        """Test clip-embedding embed with --watch flag."""
        # Configure mock to simulate immediate completion via callback
        async def mock_embed_image(**kwargs):
            # Simulate immediate callback
            if "on_complete" in kwargs:
                kwargs["on_complete"](completed_job)
            return completed_job

        mock_compute_client.clip_embedding.embed_image = AsyncMock(side_effect=mock_embed_image)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["clip-embedding", "embed", "--watch", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        mock_compute_client.clip_embedding.embed_image.assert_called_once()

    def test_embed_missing_file(self, mock_compute_client):
        """Test clip-embedding embed with missing file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["clip-embedding", "embed", "/nonexistent/file.jpg"])

        # Should fail validation before calling API
        assert result.exit_code != 0


class TestDinoEmbedding:
    """Tests for dino-embedding commands."""

    def test_embed_polling_mode(self, mock_compute_client, temp_image_file, completed_job):
        """Test dino-embedding embed in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-456",
            task_type="dino_embedding",
            status="completed",
            progress=100,
            params={},
            task_output={"embedding": [0.1] * 384},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.dino_embedding.embed_image = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["dino-embedding", "embed", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "test-job-456" in result.output
        mock_compute_client.dino_embedding.embed_image.assert_called_once()


class TestExif:
    """Tests for exif commands."""

    def test_extract_polling_mode(self, mock_compute_client, temp_image_file):
        """Test exif extract in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-789",
            task_type="exif",
            status="completed",
            progress=100,
            params={},
            task_output={
                "make": "Canon",
                "model": "EOS 5D Mark IV",
                "datetime": "2024:01:15 10:30:00",
            },
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.exif.extract = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["exif", "extract", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "Canon" in result.output
        assert "EOS 5D Mark IV" in result.output
        mock_compute_client.exif.extract.assert_called_once()


class TestFaceDetection:
    """Tests for face-detection commands."""

    def test_detect_polling_mode(self, mock_compute_client, temp_image_file):
        """Test face-detection detect in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-abc",
            task_type="face_detection",
            status="completed",
            progress=100,
            params={},
            task_output={
                "faces": [
                    {"x": 100, "y": 150, "width": 200, "height": 250, "confidence": 0.99},
                    {"x": 400, "y": 200, "width": 180, "height": 220, "confidence": 0.95},
                ]
            },
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.face_detection.detect = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["face-detection", "detect", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "test-job-abc" in result.output
        assert "completed" in result.output.lower()
        mock_compute_client.face_detection.detect.assert_called_once()


class TestFaceEmbedding:
    """Tests for face-embedding commands."""

    def test_embed_polling_mode(self, mock_compute_client, temp_image_file):
        """Test face-embedding embed in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-def",
            task_type="face_embedding",
            status="completed",
            progress=100,
            params={},
            task_output={"embeddings": [[0.1] * 128]},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.face_embedding.embed_faces = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["face-embedding", "embed", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "test-job-def" in result.output
        mock_compute_client.face_embedding.embed_faces.assert_called_once()


class TestHash:
    """Tests for hash commands."""

    def test_compute_polling_mode(self, mock_compute_client, temp_image_file):
        """Test hash compute in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-ghi",
            task_type="hash",
            status="completed",
            progress=100,
            params={},
            task_output={
                "phash": "abcdef1234567890",
                "dhash": "fedcba0987654321",
            },
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.hash.compute = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["hash", "compute", str(temp_image_file)])

        # Verify
        assert result.exit_code == 0
        assert "abcdef1234567890" in result.output
        assert "fedcba0987654321" in result.output
        mock_compute_client.hash.compute.assert_called_once()


class TestHlsStreaming:
    """Tests for hls-streaming commands."""

    def test_generate_manifest_polling_mode(self, mock_compute_client, temp_video_file):
        """Test hls-streaming generate-manifest in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-jkl",
            task_type="hls_streaming",
            status="completed",
            progress=100,
            params={},
            task_output={
                "manifest_url": "/output/manifest.m3u8",
                "segments": 10,
            },
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.hls_streaming.generate_manifest = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["hls-streaming", "generate-manifest", str(temp_video_file)])

        # Verify
        assert result.exit_code == 0
        assert "manifest.m3u8" in result.output
        mock_compute_client.hls_streaming.generate_manifest.assert_called_once()


class TestImageConversion:
    """Tests for image-conversion commands."""

    def test_convert_polling_mode(self, mock_compute_client, temp_image_file):
        """Test image-conversion convert in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-mno",
            task_type="image_conversion",
            status="completed",
            progress=100,
            params={},
            task_output={"output_path": "/output/image.png"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.image_conversion.convert = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(
            cli, ["image-conversion", "convert", str(temp_image_file), "--format", "png"]
        )

        # Verify
        assert result.exit_code == 0
        assert "test-job-mno" in result.output
        mock_compute_client.image_conversion.convert.assert_called_once()

    def test_convert_with_quality(self, mock_compute_client, temp_image_file):
        """Test image-conversion convert with quality parameter."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-pqr",
            task_type="image_conversion",
            status="completed",
            progress=100,
            params={},
            task_output={"output_path": "/output/image.jpg"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.image_conversion.convert = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "image-conversion",
                "convert",
                str(temp_image_file),
                "--format",
                "jpg",
                "--quality",
                "90",
            ],
        )

        # Verify
        assert result.exit_code == 0
        # Check that convert was called with quality parameter
        call_kwargs = mock_compute_client.image_conversion.convert.call_args[1]
        assert call_kwargs["quality"] == 90


class TestMediaThumbnail:
    """Tests for media-thumbnail commands."""

    def test_generate_polling_mode(self, mock_compute_client, temp_image_file):
        """Test media-thumbnail generate in polling mode."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-stu",
            task_type="media_thumbnail",
            status="completed",
            progress=100,
            params={},
            task_output={"thumbnail_path": "/output/thumb.jpg"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.media_thumbnail.generate = AsyncMock(return_value=job)

        # Run command with required width and height options
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["media-thumbnail", "generate", str(temp_image_file), "--width", "256", "--height", "256"],
        )

        # Verify
        assert result.exit_code == 0
        assert "test-job-stu" in result.output
        mock_compute_client.media_thumbnail.generate.assert_called_once()

    def test_generate_with_size(self, mock_compute_client, temp_image_file):
        """Test media-thumbnail generate with size parameters."""
        # Configure mock
        job = JobResponse(
            job_id="test-job-vwx",
            task_type="media_thumbnail",
            status="completed",
            progress=100,
            params={},
            task_output={"thumbnail_path": "/output/thumb.jpg"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.media_thumbnail.generate = AsyncMock(return_value=job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "media-thumbnail",
                "generate",
                str(temp_image_file),
                "--width",
                "256",
                "--height",
                "256",
            ],
        )

        # Verify
        assert result.exit_code == 0
        # Check that generate was called with width/height parameters
        call_kwargs = mock_compute_client.media_thumbnail.generate.call_args[1]
        assert call_kwargs["width"] == 256
        assert call_kwargs["height"] == 256


class TestErrorHandling:
    """Tests for error handling."""

    def test_failed_job(self, mock_compute_client, temp_image_file):
        """Test handling of failed jobs."""
        # Configure mock to return failed job
        failed_job = JobResponse(
            job_id="test-job-fail",
            task_type="clip_embedding",
            status="failed",
            progress=50,
            params={},
            error_message="Processing error",
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )
        mock_compute_client.clip_embedding.embed_image = AsyncMock(return_value=failed_job)

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["clip-embedding", "embed", str(temp_image_file)])

        # Should show error but may exit 0 (depends on implementation)
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_timeout_parameter(self, mock_compute_client, temp_image_file, completed_job):
        """Test timeout parameter is passed correctly."""
        mock_compute_client.clip_embedding.embed_image = AsyncMock(return_value=completed_job)

        # Run command with custom timeout
        runner = CliRunner()
        result = runner.invoke(
            cli, ["clip-embedding", "embed", "--timeout", "120", str(temp_image_file)]
        )

        # Verify timeout was passed
        assert result.exit_code == 0
        call_kwargs = mock_compute_client.clip_embedding.embed_image.call_args[1]
        assert call_kwargs["timeout"] == 120.0


class TestAdditionalCommands:
    """Additional tests for better coverage."""

    def test_dino_watch_mode(self, mock_compute_client, temp_image_file):
        """Test dino-embedding with watch mode."""
        job = JobResponse(
            job_id="test-job-watch",
            task_type="dino_embedding",
            status="completed",
            progress=100,
            params={},
            task_output={"embedding": [0.1] * 384},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_embed(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.dino_embedding.embed_image = AsyncMock(side_effect=mock_embed)

        runner = CliRunner()
        result = runner.invoke(cli, ["dino-embedding", "embed", "--watch", str(temp_image_file)])

        assert result.exit_code == 0
        mock_compute_client.dino_embedding.embed_image.assert_called_once()

    def test_exif_watch_mode(self, mock_compute_client, temp_image_file):
        """Test exif extract with watch mode."""
        job = JobResponse(
            job_id="test-job-exif-watch",
            task_type="exif",
            status="completed",
            progress=100,
            params={},
            task_output={"make": "Canon", "model": "EOS 5D"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_extract(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.exif.extract = AsyncMock(side_effect=mock_extract)

        runner = CliRunner()
        result = runner.invoke(cli, ["exif", "extract", "--watch", str(temp_image_file)])

        assert result.exit_code == 0
        mock_compute_client.exif.extract.assert_called_once()

    def test_hash_watch_mode(self, mock_compute_client, temp_image_file):
        """Test hash compute with watch mode."""
        job = JobResponse(
            job_id="test-job-hash-watch",
            task_type="hash",
            status="completed",
            progress=100,
            params={},
            task_output={"phash": "abc123", "dhash": "def456"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_compute(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.hash.compute = AsyncMock(side_effect=mock_compute)

        runner = CliRunner()
        result = runner.invoke(cli, ["hash", "compute", "--watch", str(temp_image_file)])

        assert result.exit_code == 0
        mock_compute_client.hash.compute.assert_called_once()

    def test_face_detection_watch_mode(self, mock_compute_client, temp_image_file):
        """Test face-detection detect with watch mode."""
        job = JobResponse(
            job_id="test-job-face-watch",
            task_type="face_detection",
            status="completed",
            progress=100,
            params={},
            task_output={"faces": []},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_detect(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.face_detection.detect = AsyncMock(side_effect=mock_detect)

        runner = CliRunner()
        result = runner.invoke(cli, ["face-detection", "detect", "--watch", str(temp_image_file)])

        assert result.exit_code == 0
        mock_compute_client.face_detection.detect.assert_called_once()

    def test_image_conversion_watch_mode(self, mock_compute_client, temp_image_file):
        """Test image-conversion convert with watch mode."""
        job = JobResponse(
            job_id="test-job-convert-watch",
            task_type="image_conversion",
            status="completed",
            progress=100,
            params={},
            task_output={"output_path": "/output/image.png"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_convert(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.image_conversion.convert = AsyncMock(side_effect=mock_convert)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["image-conversion", "convert", "--watch", str(temp_image_file), "--format", "png"],
        )

        assert result.exit_code == 0
        mock_compute_client.image_conversion.convert.assert_called_once()

    def test_media_thumbnail_watch_mode(self, mock_compute_client, temp_image_file):
        """Test media-thumbnail generate with watch mode."""
        job = JobResponse(
            job_id="test-job-thumb-watch",
            task_type="media_thumbnail",
            status="completed",
            progress=100,
            params={},
            task_output={"thumbnail_path": "/output/thumb.jpg"},
            priority=5,
            created_at=1234567890000,
            completed_at=1234567891000,
        )

        async def mock_generate(**kwargs):
            if "on_complete" in kwargs:
                kwargs["on_complete"](job)
            return job

        mock_compute_client.media_thumbnail.generate = AsyncMock(side_effect=mock_generate)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "media-thumbnail",
                "generate",
                "--watch",
                str(temp_image_file),
                "--width",
                "256",
                "--height",
                "256",
            ],
        )

        assert result.exit_code == 0
        mock_compute_client.media_thumbnail.generate.assert_called_once()
