"""Integration tests for face_detection plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in multiple auth modes: admin, user-with-permission, user-no-permission, no-auth.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from cl_client import ComputeClient
from httpx import HTTPStatusError

import sys
from pathlib import Path as PathlibPath
sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import get_expected_error, should_succeed




@pytest.mark.integration
@pytest.mark.asyncio
async def test_face_detection_http_polling(
    test_image_face_multiple: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test face detection with HTTP polling (secondary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        job = await client.face_detection.detect(
            image=test_image_face_multiple,
            wait=True,
            timeout=30.0,
        )

        # Verify completion
        assert job.status == "completed"
        assert job.task_output is not None

        # Should have faces list with at least one face
        assert "faces" in job.task_output
        assert isinstance(job.task_output["faces"], list)
        assert len(job.task_output["faces"]) > 0, "Should detect at least one face"

        # Validate new schema fields for each detected face
        for i, face in enumerate(job.task_output["faces"]):
            # Validate bbox structure and normalized coordinates
            assert "bbox" in face, f"Face {i}: Missing bbox"
            bbox = face["bbox"]
            assert all(k in bbox for k in ["x1", "y1", "x2", "y2"])
            assert 0.0 <= bbox["x1"] <= 1.0
            assert 0.0 <= bbox["y1"] <= 1.0
            assert 0.0 <= bbox["x2"] <= 1.0
            assert 0.0 <= bbox["y2"] <= 1.0

            # Validate confidence
            assert "confidence" in face
            assert 0.0 <= face["confidence"] <= 1.0

            # Validate landmarks structure and normalized coordinates
            assert "landmarks" in face, f"Face {i}: Missing landmarks"
            landmarks = face["landmarks"]
            required_landmarks = ["right_eye", "left_eye", "nose_tip", "mouth_right", "mouth_left"]
            for landmark_name in required_landmarks:
                assert landmark_name in landmarks
                landmark = landmarks[landmark_name]
                assert isinstance(landmark, (list, tuple)) and len(landmark) == 2
                x, y = landmark
                assert 0.0 <= x <= 1.0, f"Face {i}: {landmark_name}.x not normalized"
                assert 0.0 <= y <= 1.0, f"Face {i}: {landmark_name}.y not normalized"

            # Validate file_path field
            assert "file_path" in face
            assert isinstance(face["file_path"], str) and len(face["file_path"]) > 0

        # Test downloading cropped face image
        import tempfile
        from PIL import Image

        first_face = job.task_output["faces"][0]
        crop_path = first_face["file_path"]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        await client.download_job_file(job.job_id, crop_path, tmp_path)

        assert tmp_path.exists()
        assert tmp_path.stat().st_size > 0

        # Verify it's a valid image
        img = Image.open(tmp_path)
        assert img.width > 0 and img.height > 0
        img.close()
        tmp_path.unlink()

        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.face_detection.detect(
                image=test_image_face_multiple,
                wait=True,
                timeout=30.0,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_face_detection_mqtt_callbacks(
    test_image_face_multiple: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test face detection with MQTT callbacks (primary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        assert client._mqtt._connected, "MQTT not connected"

        completion_event = asyncio.Event()
        final_job = None

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        job = await client.face_detection.detect(
            image=test_image_face_multiple,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        assert final_job is not None
        assert final_job.status == "completed"

        # MQTT callbacks don't include task_output, fetch via HTTP
        full_job = await client.get_job(job.job_id)
        assert "faces" in full_job.task_output
        assert len(full_job.task_output["faces"]) > 0, "Should detect at least one face"

        # Validate new schema fields for each detected face
        for i, face in enumerate(full_job.task_output["faces"]):
            # Validate bbox structure and normalized coordinates
            assert "bbox" in face, f"Face {i}: Missing bbox"
            bbox = face["bbox"]
            assert all(k in bbox for k in ["x1", "y1", "x2", "y2"])
            assert 0.0 <= bbox["x1"] <= 1.0
            assert 0.0 <= bbox["y1"] <= 1.0
            assert 0.0 <= bbox["x2"] <= 1.0
            assert 0.0 <= bbox["y2"] <= 1.0

            # Validate confidence
            assert "confidence" in face
            assert 0.0 <= face["confidence"] <= 1.0

            # Validate landmarks structure and normalized coordinates
            assert "landmarks" in face, f"Face {i}: Missing landmarks"
            landmarks = face["landmarks"]
            required_landmarks = ["right_eye", "left_eye", "nose_tip", "mouth_right", "mouth_left"]
            for landmark_name in required_landmarks:
                assert landmark_name in landmarks
                landmark = landmarks[landmark_name]
                assert isinstance(landmark, (list, tuple)) and len(landmark) == 2
                x, y = landmark
                assert 0.0 <= x <= 1.0, f"Face {i}: {landmark_name}.x not normalized"
                assert 0.0 <= y <= 1.0, f"Face {i}: {landmark_name}.y not normalized"

            # Validate file_path field
            assert "file_path" in face
            assert isinstance(face["file_path"], str) and len(face["file_path"]) > 0

        # Test downloading cropped face image
        import tempfile
        from PIL import Image

        first_face = full_job.task_output["faces"][0]
        crop_path = first_face["file_path"]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        await client.download_job_file(job.job_id, crop_path, tmp_path)

        assert tmp_path.exists()
        assert tmp_path.stat().st_size > 0

        # Verify it's a valid image
        img = Image.open(tmp_path)
        assert img.width > 0 and img.height > 0
        img.close()
        tmp_path.unlink()

        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.face_detection.detect(
                image=test_image_face_multiple,
                on_complete=lambda job: None,
            )
        assert exc_info.value.response.status_code == expected_code
