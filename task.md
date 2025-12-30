# Python Client Library (`cl_client`) - Implementation Tasks

## Progress Overview
- **Phase**: 2 - Test Suite (Week 2)
- **Current Focus**: Phase 2 Complete - All Integration Tests Passing
- **Completed**: Phase 1 (Days 1-5), Phase 2 (Days 1-4)

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
- [x] ~~Create integration tests for all 9 plugins~~ ✅ **[25/25 tests PASSING]**
  - [x] ~~HTTP polling tests~~
  - [x] ~~MQTT callback tests~~
  - [x] ~~File download tests (clip_embedding verified)~~
  - [x] ~~Worker capability tests~~
  - [x] ~~Fix metadata field checks (embedding_dim vs embedding, master_playlist vs manifest_path)~~
  - [x] ~~Fix MQTT callback tests to fetch full job details via HTTP~~
  - [x] ~~Fix image_conversion to check params instead of task_output~~
- [ ] Implement CLI tool (`cli.py`) **[DEFERRED]**
  - [ ] Use click for command framework
  - [ ] Use rich for terminal output
  - [ ] Subcommands for each plugin
  - [ ] Real-time progress via MQTT callbacks
  - [ ] File download using new server endpoint
- [ ] Write unit tests for plugin clients **[DEFERRED]**
- [x] ~~Run `uv run basedpyright`~~ ✅ 0 errors, 0 warnings

**Day 5 COMPLETED** ✅
- **All 9 plugins implemented** with consistent "file" field naming
- **All 25 integration tests PASSING** (100% success rate)
  - clip_embedding: 5/5 ✅
  - dino_embedding: 2/2 ✅
  - exif: 2/2 ✅
  - face_detection: 2/2 ✅
  - face_embedding: 2/2 ✅
  - hash: 2/2 ✅
  - hls_streaming: 2/2 ✅
  - image_conversion: 3/3 ✅
  - media_thumbnail: 5/5 ✅
- **Type checking**: 0 errors, strict mode enforced
- **Code coverage**: 80.83% (will improve with unit tests)
- **Remaining**: CLI tool and unit tests (deferred to future phase)

---

## Phase 2: Test Suite (Week 2)

### Day 1: Test Infrastructure
- [x] ~~Create test directory structure~~ ✅
- [x] ~~Implement `conftest.py` with all fixtures~~ ✅
  - [x] ~~Media directory fixture (tests/media/)~~
  - [x] ~~All image fixtures (test_image, test_image_png, test_face_single, etc.)~~
  - [x] ~~All video fixtures (test_video_1080p, test_video_720p)~~
- [x] ~~Write `tests/media/MEDIA_SETUP.md` documentation~~ ✅ (already existed)
- [x] ~~User provided test media files~~ ✅
- [x] ~~Run `uv run basedpyright` and `uv run pytest` to verify~~ ✅

**Day 1 COMPLETED** ✅

### Day 2-3: Plugin Tests (1-6) - MQTT Primary
- [x] ~~test_clip_embedding.py~~ ✅ (5 tests)
- [x] ~~test_dino_embedding.py~~ ✅ (2 tests)
- [x] ~~test_exif.py~~ ✅ (2 tests)
- [x] ~~test_face_detection.py~~ ✅ (2 tests)
- [x] ~~test_face_embedding.py~~ ✅ (2 tests)
- [x] ~~test_hash.py~~ ✅ (2 tests)
- [x] ~~All tests clean up jobs after completion~~ ✅
- [x] ~~Run `uv run pytest` to verify~~ ✅ All passing

**Day 2-3 COMPLETED** ✅

### Day 4: Plugin Tests (7-9)
- [x] ~~test_hls_streaming.py~~ ✅ (2 tests)
- [x] ~~test_image_conversion.py~~ ✅ (3 tests)
- [x] ~~test_media_thumbnail.py~~ ✅ (5 tests)
- [x] ~~All tests validate worker availability~~ ✅ (via MQTT connection check)
- [x] ~~Run `uv run pytest` to verify~~ ✅ **25/25 tests passing**

**Day 4 COMPLETED** ✅

### Day 5: Workflow Tests (Parallel MQTT Pattern)
- [ ] test_image_processing_workflow.py **[DEFERRED]**
- [ ] test_video_processing_workflow.py **[DEFERRED]**
- [x] ~~Run full test suite~~ ✅ **25/25 tests passing**
- [ ] Verify ≥90% coverage (80.83% - will improve with unit tests) **[PENDING]**

**Day 5 PARTIALLY COMPLETED** ⚠️
- All integration tests passing
- Workflow tests deferred to future phase
- Coverage at 80.83% (unit tests needed for 90%)

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

## Current Status Summary

### ✅ COMPLETED
1. **Core Client Library** (Phase 1)
   - All 9 plugin clients implemented
   - MQTT monitoring with two-callback system
   - HTTP polling (secondary workflow)
   - File download support
   - Modular authentication (NoAuthProvider)
   - Strict type checking (0 errors)

2. **Integration Tests** (Phase 2, Days 1-4)
   - 25/25 tests PASSING (100% success rate)
   - All plugins tested: HTTP polling + MQTT callbacks
   - Worker capability validation
   - File download verified
   - Test media provided by user

### 🔄 IN PROGRESS / PENDING
1. **Unit Tests** (80.83% coverage → need 90%+)
   - Plugin unit tests needed
   - Core client unit tests exist (16 tests)
   - MQTT monitor coverage needs improvement

2. **Documentation** (Phase 3)
   - README.md needs completion
   - INTERNALS.md needs completion
   - API reference docstrings

### ⏸️ DEFERRED
1. **CLI Tool** - Interactive command-line interface
2. **Workflow Tests** - Multi-plugin integration workflows
3. **JWT Authentication** - Will require auth server integration

---

## What's Next?

### Priority 1: Improve Code Coverage (to meet 90% requirement)
- Write unit tests for uncovered code paths
- Focus on mqtt_monitor.py (62.94% → 90%+)
- Focus on exceptions.py (60.87% → 90%+)
- Focus on auth.py (75% → 90%+)

### Priority 2: Complete Documentation
- User-facing README.md with examples
- Developer INTERNALS.md with architecture
- API reference for all public methods

### Priority 3: Optional Enhancements
- CLI tool for interactive usage
- Workflow tests for multi-plugin scenarios
- Additional integration tests

---

## Notes
- Mark tasks with `[x]` when completed
- Update this file before moving to next task
- Run type checks (`uv run basedpyright`) after each major change
- Commit frequently with descriptive messages
