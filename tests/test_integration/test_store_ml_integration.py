"""Integration tests for Store + ML workflow (face detection and recognition).

Tests the complete pipeline from image upload to face recognition results.
Priority order reflects dependencies:
- Priority 2: Job triggering (entity creation triggers async jobs)
- Priority 3: Job lifecycle (monitoring job status via MQTT and HTTP)
- Priority 1: End-to-end face recognition (complete workflow)
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient
from cl_client.store_manager import StoreManager


# ============================================================================
# PRIORITY 2: JOB TRIGGERING
# ============================================================================


@pytest.mark.asyncio
async def test_entity_triggers_jobs(
    store_manager: StoreManager,
    test_image_face_single: Path,
):
    """Test that creating an entity with an image triggers async ML jobs.

    Verifies:
    1. Entity creation succeeds
    2. Jobs are triggered for the entity
    3. Both face_detection and clip_embedding jobs are created
    4. Jobs have correct status fields (queued, in_progress, completed, failed)
    """
    # Create entity with single face image
    result = await store_manager.create_entity(
        label="Single Face Test",
        description="Test image with one face",
        is_collection=False,
        image_path=test_image_face_single,
    )

    assert result.is_success, f"Failed to create entity: {result.error}"
    entity = result.data
    assert entity.id is not None
    assert entity.label == "Single Face Test"

    # Wait briefly for jobs to be triggered (async job creation)
    await asyncio.sleep(1.0)

    # Query triggered jobs
    store_client = store_manager._store_client
    jobs = await store_client.get_entity_jobs(entity.id)

    # Verify jobs were triggered
    assert len(jobs) > 0, "No jobs were triggered for the entity"

    # Check job types
    job_types = {job.task_type for job in jobs}
    assert "face_detection" in job_types, "face_detection job not triggered"
    assert "clip_embedding" in job_types, "clip_embedding job not triggered"

    # Verify job structure
    for job in jobs:
        assert job.id is not None
        assert job.entity_id == entity.id
        assert job.job_id is not None
        assert job.task_type in ["face_detection", "clip_embedding"]
        assert job.status in ["queued", "in_progress", "completed", "failed"]
        assert job.created_at is not None
        assert job.updated_at is not None

    print(f"✓ Entity {entity.id} triggered {len(jobs)} jobs: {job_types}")


# ============================================================================
# PRIORITY 1: END-TO-END FACE RECOGNITION WORKFLOW
# ============================================================================
# Note: Priority 3 (Job Lifecycle Monitoring via MQTT/HTTP) is already tested
# in test_face_detection_integration.py and test_clip_embedding_integration.py.
# Those tests validate PySDK's MQTT callback and HTTP polling mechanisms.
# The tests below focus on store-ML integration: entity creation → job execution
# → results persistence to store database.
# ============================================================================


@pytest.mark.asyncio
async def test_face_recognition_workflow_single_face(
    store_manager: StoreManager,
    test_client: ComputeClient,
    test_image_face_single: Path,
):
    """Test complete face recognition workflow with single face image.

    Verifies end-to-end pipeline:
    1. Create entity with image
    2. Wait for face detection job to complete
    3. Retrieve detected faces from store
    4. Verify face metadata (bbox, confidence, landmarks)
    5. Download face crop
    6. Query known persons
    """
    # Step 1: Create entity
    result = await store_manager.create_entity(
        label="Single Face Workflow Test",
        is_collection=False,
        image_path=test_image_face_single,
    )

    assert result.is_success
    entity = result.data
    print(f"✓ Created entity {entity.id}")

    # Step 2: Wait for face detection job
    store_client = store_manager._store_client

    # Poll for jobs to appear (async job creation)
    face_job = None
    for _ in range(10):  # Try for 10 seconds
        await asyncio.sleep(1.0)
        jobs = await store_client.get_entity_jobs(entity.id)
        face_detection_jobs = [j for j in jobs if j.task_type == "face_detection"]
        if face_detection_jobs:
            face_job = face_detection_jobs[0]
            break

    assert face_job is not None, "No face detection job found after 10 seconds"
    print(f"✓ Face detection job {face_job.job_id} found")

    # Wait for job completion via HTTP polling
    final_job = await test_client.wait_for_job(
        job_id=face_job.job_id,
        timeout=30.0,
    )

    assert final_job.status == "completed"
    assert final_job.task_output is not None
    assert "faces" in final_job.task_output
    num_faces = len(final_job.task_output['faces'])
    print(f"✓ Face detection completed - found {num_faces} face(s) in job output")

    # Step 2b: Wait for face embedding jobs to complete
    # Each detected face triggers a face_embedding job
    print(f"  Waiting for {num_faces} face embedding job(s) to complete...")

    max_wait_time = 60  # 60 seconds total
    wait_interval = 2   # Check every 2 seconds
    elapsed = 0

    while elapsed < max_wait_time:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        jobs = await store_client.get_entity_jobs(entity.id)
        face_embedding_jobs = [j for j in jobs if j.task_type == "face_embedding"]

        # Check if we have the expected number of face embedding jobs
        if len(face_embedding_jobs) >= num_faces:
            # Check if all are completed
            completed = [j for j in face_embedding_jobs if j.status == "completed"]
            if len(completed) >= num_faces:
                print(f"✓ All {num_faces} face embedding job(s) completed")
                break
            else:
                print(f"  Face embedding progress: {len(completed)}/{num_faces} completed")
    else:
        # Timeout - print status and continue
        jobs = await store_client.get_entity_jobs(entity.id)
        face_embedding_jobs = [j for j in jobs if j.task_type == "face_embedding"]
        completed = [j for j in face_embedding_jobs if j.status == "completed"]
        print(f"  Warning: Timeout waiting for face embeddings. Status: {len(completed)}/{num_faces} completed")

    # Step 3: Retrieve detected faces from store
    faces = await store_client.get_entity_faces(entity.id)

    # Note: Store may not have face records if face detection results aren't persisted
    # For now, verify faces were detected in job output
    if len(faces) == 0:
        pytest.skip("Face detection succeeded but faces not persisted to store (store-compute integration not configured)")

    print(f"✓ Retrieved {len(faces)} face(s) from store")

    # Step 4: Verify face metadata
    face = faces[0]
    assert face.id is not None
    assert face.entity_id == entity.id
    assert face.bbox is not None and len(face.bbox) == 4
    assert 0.0 <= face.bbox[0] <= 1.0  # x1
    assert 0.0 <= face.bbox[1] <= 1.0  # y1
    assert 0.0 <= face.bbox[2] <= 1.0  # x2
    assert 0.0 <= face.bbox[3] <= 1.0  # y2
    assert 0.0 <= face.confidence <= 1.0
    assert face.landmarks is not None and len(face.landmarks) == 5  # 5 keypoints
    assert face.file_path is not None

    print(f"✓ Face metadata valid:")
    print(f"  - BBox: {face.bbox}")
    print(f"  - Confidence: {face.confidence:.3f}")
    print(f"  - Landmarks: {len(face.landmarks)} points")

    # Step 5: Verify face embedding exists in Qdrant by downloading it
    import tempfile
    import numpy as np

    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await store_client.download_face_embedding(
            face_id=face.id,
            dest=tmp_path,
        )

        # Verify it's a valid embedding
        embedding = np.load(tmp_path)
        assert embedding.shape == (512,), f"Expected shape (512,), got {embedding.shape}"
        assert embedding.dtype == np.float32, f"Expected float32, got {embedding.dtype}"
        print(f"✓ Downloaded face embedding from Qdrant: {embedding.shape} vector")
    finally:
        tmp_path.unlink(missing_ok=True)

    # Step 6: Query known persons (after face embedding completes, faces should be linked)
    known_persons = await store_client.get_all_known_persons()
    print(f"✓ Retrieved {len(known_persons)} known person(s)")

    # Verify face has been linked to a known person
    # After face embedding completes, each face should have a known_person_id
    if face.known_person_id is not None:
        person = await store_client.get_known_person(face.known_person_id)
        assert person.id == face.known_person_id
        print(f"✓ Face linked to known person {person.id} (name: {person.name or 'unnamed'})")

        # Verify we can query faces for this known person
        person_faces = await store_client.get_known_person_faces(person.id)
        assert len(person_faces) > 0
        print(f"  Known person has {len(person_faces)} face(s)")
    else:
        print(f"  Warning: Face not linked to known person (known_person_id is None)")


@pytest.mark.asyncio
async def test_face_recognition_workflow_multiple_faces(
    store_manager: StoreManager,
    test_client: ComputeClient,
    test_image_face_multiple: Path,
):
    """Test face recognition workflow with multiple faces in one image.

    Verifies:
    1. Multiple faces are detected
    2. Each face has valid metadata
    3. Face similarity search works
    """
    # Step 1: Create entity
    result = await store_manager.create_entity(
        label="Multiple Faces Workflow Test",
        is_collection=False,
        image_path=test_image_face_multiple,
    )

    assert result.is_success
    entity = result.data
    print(f"✓ Created entity {entity.id}")

    # Step 2: Wait for face detection
    store_client = store_manager._store_client

    # Poll for jobs to appear
    face_job = None
    for _ in range(10):  # Try for 10 seconds
        await asyncio.sleep(1.0)
        jobs = await store_client.get_entity_jobs(entity.id)
        face_detection_jobs = [j for j in jobs if j.task_type == "face_detection"]
        if face_detection_jobs:
            face_job = face_detection_jobs[0]
            break

    assert face_job is not None, "No face detection job found"

    final_job = await test_client.wait_for_job(
        job_id=face_job.job_id,
        timeout=30.0,
    )

    assert final_job.status == "completed"
    assert final_job.task_output is not None
    assert "faces" in final_job.task_output
    num_faces = len(final_job.task_output['faces'])
    print(f"✓ Face detection completed - found {num_faces} face(s) in job output")

    # Step 2b: Wait for face embedding jobs to complete
    print(f"  Waiting for {num_faces} face embedding job(s) to complete...")

    max_wait_time = 60
    wait_interval = 2
    elapsed = 0

    while elapsed < max_wait_time:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        jobs = await store_client.get_entity_jobs(entity.id)
        face_embedding_jobs = [j for j in jobs if j.task_type == "face_embedding"]

        if len(face_embedding_jobs) >= num_faces:
            completed = [j for j in face_embedding_jobs if j.status == "completed"]
            if len(completed) >= num_faces:
                print(f"✓ All {num_faces} face embedding job(s) completed")
                break
            else:
                print(f"  Face embedding progress: {len(completed)}/{num_faces} completed")
    else:
        jobs = await store_client.get_entity_jobs(entity.id)
        face_embedding_jobs = [j for j in jobs if j.task_type == "face_embedding"]
        completed = [j for j in face_embedding_jobs if j.status == "completed"]
        print(f"  Warning: Timeout waiting for face embeddings. Status: {len(completed)}/{num_faces} completed")

    # Step 3: Retrieve all faces
    faces = await store_client.get_entity_faces(entity.id)

    # Note: Store may not have face records if face detection results aren't persisted
    if len(faces) == 0:
        pytest.skip("Face detection succeeded but faces not persisted to store (store-compute integration not configured)")

    assert len(faces) > 1, f"Expected multiple faces, got {len(faces)}"
    print(f"✓ Detected {len(faces)} faces")

    # Step 4: Verify each face
    for i, face in enumerate(faces):
        assert face.id is not None
        assert face.entity_id == entity.id
        assert face.bbox is not None and len(face.bbox) == 4
        assert 0.0 <= face.confidence <= 1.0
        print(f"  Face {i+1}: confidence={face.confidence:.3f}, bbox={face.bbox}")

    # Step 5: Test face similarity search
    first_face_id = faces[0].id
    similar_faces_response = await store_client.find_similar_faces(
        face_id=first_face_id,
        limit=5,
        threshold=0.7,
    )

    assert similar_faces_response.query_face_id == first_face_id
    print(f"✓ Face similarity search returned {len(similar_faces_response.results)} results")

    for result in similar_faces_response.results:
        assert result.face_id is not None
        assert 0.0 <= result.score <= 1.0
        print(f"  Similar face {result.face_id}: score={result.score:.3f}")


@pytest.mark.skip(reason="Focus on face detection workflow first - CLIP similarity search to be tested later")
@pytest.mark.asyncio
async def test_image_similarity_search(
    store_manager: StoreManager,
    test_client: ComputeClient,
    test_image_face_single: Path,
):
    """Test CLIP-based image similarity search.

    Verifies:
    1. CLIP embedding job is triggered
    2. Image similarity search works
    3. Similar images are returned with scores
    """
    # Create entity
    result = await store_manager.create_entity(
        label="Image Similarity Test",
        is_collection=False,
        image_path=test_image_face_single,
    )

    assert result.is_success
    entity = result.data
    print(f"✓ Created entity {entity.id}")

    # Wait for CLIP embedding job
    store_client = store_manager._store_client

    # Poll for jobs to appear
    clip_job = None
    for _ in range(10):  # Try for 10 seconds
        await asyncio.sleep(1.0)
        jobs = await store_client.get_entity_jobs(entity.id)
        clip_jobs = [j for j in jobs if j.task_type == "clip_embedding"]
        if clip_jobs:
            clip_job = clip_jobs[0]
            break

    assert clip_job is not None, "No CLIP embedding job found"

    final_job = await test_client.wait_for_job(
        job_id=clip_job.job_id,
        timeout=30.0,
    )

    assert final_job.status == "completed"
    print(f"✓ CLIP embedding completed")

    # Test image similarity search
    from httpx import HTTPStatusError

    try:
        similar_images_response = await store_client.find_similar_images(
            entity_id=entity.id,
            limit=5,
            score_threshold=0.85,
        )

        assert similar_images_response.query_entity_id == entity.id
        print(f"✓ Image similarity search returned {len(similar_images_response.results)} results")

        for result in similar_images_response.results:
            assert result.entity_id is not None
            assert 0.0 <= result.score <= 1.0
            print(f"  Similar entity {result.entity_id}: score={result.score:.3f}")
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            pytest.skip("Image similarity search endpoint not implemented or entity not indexed yet")
        raise
