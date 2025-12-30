# Python Client Library (`cl_client`) - Implementation Tasks

## Progress Overview
- **Phase**: 1 - Core Client Library (Week 1)
- **Current Focus**: Day 3 - MQTT Monitor (Primary Workflow)
- **Completed**: Days 1-2 (Setup, Models, Exceptions, Auth)

---

## Server Prerequisites

### File Download Endpoint Implementation
- [x] ~~Add GET /jobs/{job_id}/files/{file_path:path} endpoint to server~~
  - [x] ~~Add route in server's routes.py~~
  - [x] ~~Implement file serving with security validation~~
  - [x] ~~Type check passes (basedpyright)~~
  - [x] ~~Test endpoint with actual job outputs (verified with media_thumbnail)~~
- [x] ~~Restart server after endpoint addition (tested in no-auth mode)~~

**Server endpoint implementation COMPLETED** ✅
- Endpoint: `GET /jobs/{job_id}/files/{file_path:path}`
- Security: Path traversal protection, job verification
- Tested: Successfully downloaded thumbnail.jpg (19KB JPEG, 256x250px)
- Ready for client integration

---

## Phase 1: Core Client Library (Week 1)

### Day 1: Project Setup & Configuration
- [x] ~~Create `cl_client/` package structure~~
- [x] ~~Set up `pyproject.toml` (mirror compute service structure)~~
  - [x] ~~Configure pytest, coverage, ruff (same as server)~~
  - [x] ~~Add CLI dependencies (click, rich)~~
  - [x] ~~Add CLI entry point in [project.scripts]~~
  - [x] ~~Match server's naming, order, and structure~~
- [x] ~~Create `pyrightconfig.json` (separate file, NOT in pyproject.toml)~~
  - [x] ~~Mirror server's pyrightconfig.json structure~~
  - [x] ~~Strict type checking mode~~
  - [x] ~~reportAny = "error" (NO Any types allowed)~~
- [x] ~~Implement `config.py` with `ComputeClientConfig` class~~
  - [x] ~~All endpoints, hosts, ports as class variables~~
  - [x] ~~NO hardcoded values elsewhere~~
  - [x] ~~Type-safe (basedpyright compatible)~~
- [x] ~~Create documentation skeletons:~~
  - [x] ~~README.md (user docs)~~
  - [x] ~~INTERNALS.md (developer docs)~~
  - [x] ~~tests/README.md (testing docs)~~
  - [x] ~~tests/media/MEDIA_SETUP.md (media setup)~~
- [x] ~~Run `uv run basedpyright` to verify strict mode setup~~ ✅ 0 errors

**Day 1 COMPLETED** ✅

### Day 2: Models & Exceptions
- [x] ~~Define models in `models.py` (mirror server schemas)~~
  - [x] ~~Use JSONObject type alias (NO Any types)~~
  - [x] ~~JobResponse, WorkerCapabilitiesResponse, WorkerCapability~~
  - [x] ~~All fields with type hints and descriptions~~
- [x] ~~Implement custom exceptions in `exceptions.py`~~
  - [x] ~~ComputeClientError, JobNotFoundError, JobFailedError~~
  - [x] ~~AuthenticationError, PermissionError~~
  - [x] ~~WorkerUnavailableError (for capability validation)~~
- [x] ~~Implement modular auth in `auth.py` (FastAPI Depends-style)~~
  - [x] ~~AuthProvider abstract base class~~
  - [x] ~~NoAuthProvider (Phase 1 default)~~
  - [x] ~~JWTAuthProvider stub (Phase 2 future)~~
  - [x] ~~Injectable auth providers for testability~~
- [x] ~~Write unit tests for models, exceptions, auth~~
- [x] ~~Run `uv run basedpyright` to verify (zero errors)~~ ✅ 0 errors, 100% coverage

**Day 2 COMPLETED** ✅

### Day 3: MQTT Monitor (Primary Workflow)
- [x] ~~Implement `MQTTJobMonitor` using paho-mqtt~~
  - [x] ~~Job status subscription with unique subscription IDs (supports multiple callbacks per job)~~
  - [x] ~~Two-callback system: on_progress and on_complete~~
  - [x] ~~subscribe_job_updates() returns subscription ID~~
  - [x] ~~unsubscribe(subscription_id) uses ID, not job_id~~
  - [x] ~~Worker capability subscription and parsing~~
  - [x] ~~In-memory worker state tracking~~
  - [x] ~~wait_for_capability() method (for test validation)~~
- [x] ~~All configuration from `ComputeClientConfig` (NO hardcoding)~~
- [x] ~~Write integration tests for MQTT (test both callbacks)~~ ✅ 15 tests passing
- [x] ~~Run `uv run basedpyright` to verify~~ ✅ 0 errors

**Day 3 COMPLETED** ✅

### Day 4: Core Client
- [x] ~~Implement `ComputeClient` class~~
  - [x] ~~REST API methods (get_job, delete_job, get_capabilities)~~
  - [x] ~~MQTT callback registration with two-callback system (on_progress, on_complete)~~
  - [x] ~~subscribe_job_updates() returns subscription ID~~
  - [x] ~~unsubscribe(subscription_id) method~~
  - [x] ~~Optional HTTP polling (wait_for_job, secondary workflow)~~
  - [x] ~~Worker validation (wait_for_workers)~~
  - [x] ~~Injectable auth_provider (modular auth)~~
  - [x] ~~File download method (download_job_file)~~
- [x] ~~All defaults from `ComputeClientConfig`~~
- [x] ~~Internal MQTT monitor instance~~
- [x] ~~Write unit tests for client core~~ ✅ 16 tests passing
- [x] ~~Run `uv run basedpyright` to verify~~ ✅ 0 errors

**Day 4 COMPLETED** ✅

### Day 5: Plugin System & CLI
- [x] ~~Implement `BasePluginClient`~~
  - [x] ~~Endpoint lookup from config (NO hardcoding)~~
  - [x] ~~submit_job() as stub (NotImplementedError) for future file-less plugins~~
  - [x] ~~submit_with_files() fully implemented (primary method)~~
  - [x] ~~Two-callback system (on_progress, on_complete)~~
  - [x] ~~Support MQTT callback (primary) and polling (secondary via wait=True)~~
  - [x] ~~File upload mechanism (multipart/form-data)~~
- [x] ~~Create all 9 plugin client classes (separate files, modular)~~ **[9/9 COMPLETED]** ✅
  - [x] ~~clip_embedding.py~~ ✅
  - [x] ~~dino_embedding.py~~ ✅
  - [x] ~~exif.py~~ ✅
  - [x] ~~face_detection.py~~ ✅
  - [x] ~~face_embedding.py~~ ✅
  - [x] ~~hash.py~~ ✅
  - [x] ~~hls_streaming.py~~ ✅
  - [x] ~~image_conversion.py~~ ✅
  - [x] ~~media_thumbnail.py~~ ✅
- [x] ~~Add lazy-loading properties to `ComputeClient`~~ **[9/9 COMPLETED]** ✅
  - [x] ~~All 9 plugin properties added~~ ✅
- [x] ~~Fix file upload field names (all plugins use "file")~~ ✅
- [x] ~~Create integration tests for all 9 plugins~~ ✅
  - [x] ~~HTTP polling tests~~
  - [x] ~~MQTT callback tests~~
  - [x] ~~File download tests (clip_embedding verified)~~
  - [x] ~~Worker capability tests~~
- [ ] Implement CLI tool (`cli.py`)
  - [ ] Use click for command framework
  - [ ] Use rich for terminal output
  - [ ] Subcommands for each plugin
  - [ ] Real-time progress via MQTT callbacks
  - [ ] File download using new server endpoint
- [ ] Write unit tests for plugin clients
- [x] ~~Run `uv run basedpyright`~~ ✅ 0 errors, 0 warnings

**Day 5 COMPLETED (except CLI tool)** ✅
- **All 9 plugins implemented** with consistent "file" field naming
- **All integration tests created** (HTTP polling + MQTT callbacks + file download)
- **Tests verified passing**: clip_embedding (5/5), exif (2/2), hash (2/2), media_thumbnail (5/5)
- **Type checking**: 0 errors, strict mode enforced
- **Remaining**: CLI tool implementation (deferred)

---

## Phase 2: Test Suite (Week 2)

### Day 1: Test Infrastructure
- [ ] Create test directory structure
- [ ] Implement `conftest.py` with all fixtures
- [ ] Write `tests/media/MEDIA_SETUP.md` documentation
- [ ] Create media validation tests
- [ ] Run `uv run basedpyright` and `uv run pytest` to verify

### Day 2-3: Plugin Tests (1-6) - MQTT Primary
- [ ] test_clip_embedding.py
- [ ] test_dino_embedding.py
- [ ] test_exif.py
- [ ] test_face_detection.py
- [ ] test_face_embedding.py
- [ ] test_hash.py
- [ ] All tests clean up jobs after completion
- [ ] Run `uv run pytest` to verify

### Day 4: Plugin Tests (7-9)
- [ ] test_hls_streaming.py
- [ ] test_image_conversion.py
- [ ] test_media_thumbnail.py
- [ ] All tests validate worker availability
- [ ] Run `uv run pytest` to verify

### Day 5: Workflow Tests (Parallel MQTT Pattern)
- [ ] test_image_processing_workflow.py
- [ ] test_video_processing_workflow.py
- [ ] Run full test suite
- [ ] Verify ≥90% coverage

---

## Phase 3: Documentation & Polish (Week 3)

### Day 1-2: Documentation
- [ ] Complete README.md (user-facing)
- [ ] Complete INTERNALS.md (developer-facing)
- [ ] Complete tests/README.md (testing-specific)
- [ ] Complete tests/media/MEDIA_SETUP.md
- [ ] API reference docstrings (all public methods)

### Day 3-4: Test Media & Validation
- [ ] Acquire/create test media
- [ ] Validate all media files
- [ ] Run full test suite with worker validation
- [ ] Fix any integration issues

### Day 5: Final Polish & Quality Checks
- [ ] Code review and cleanup
- [ ] Verify type hints on all public APIs
- [ ] Run quality checks (basedpyright, ruff, pytest)
- [ ] Verify ≥90% coverage
- [ ] Final documentation review
- [ ] Ready for Phase 2 (JWT auth integration)

---

## Notes
- Mark tasks with `[x]` when completed
- Update this file before moving to next task
- Run type checks (`uv run basedpyright`) after each major change
- Commit frequently with descriptive messages
