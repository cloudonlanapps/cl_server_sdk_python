# Test Media Setup Guide

## Overview

Tests require pre-provided media files in `cl_client_test_media/` directory.
This directory is **NOT in git** and must be set up separately.

## Quick Setup

1. Create media directory:
   ```bash
   mkdir -p cl_client_test_media/images
   mkdir -p cl_client_test_media/videos
   ```

2. Set environment variable (optional):
   ```bash
   export CL_CLIENT_TEST_MEDIA=/path/to/cl_client_test_media
   ```
   Default: `../cl_client_test_media/` relative to test directory

3. Provide test media files (see requirements below)

## Required Media Files

### Images (5 files required)

#### 1. `images/test_image_1920x1080.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080
- **Purpose**: Standard HD image testing
- **Source**: Any HD photo (Unsplash, Pexels, or personal)

#### 2. `images/test_image_800x600.png`
- **Format**: PNG
- **Resolution**: 800x600
- **Purpose**: Smaller image, PNG format testing
- **Source**: Any medium-size photo converted to PNG

#### 3. `images/test_face_single.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080+
- **Purpose**: Face detection with 1 clear face
- **Requirements**:
  - 1 human face, front-facing
  - Good lighting
  - Face size >200px
- **Source**: Portrait photo (stock or personal)

#### 4. `images/test_face_multiple.jpg`
- **Format**: JPEG
- **Resolution**: 1920x1080+
- **Purpose**: Face detection with multiple faces
- **Requirements**:
  - 3-5 human faces
  - Various angles acceptable
- **Source**: Group photo (stock or personal)

#### 5. `images/test_exif_rich.jpg`
- **Format**: JPEG with EXIF
- **Resolution**: Any
- **Purpose**: EXIF metadata extraction
- **Requirements**:
  - Must have EXIF data (camera model, date, GPS if possible)
  - NOT a screenshot or edited image
- **Source**: Direct camera photo with EXIF preserved

### Videos (2 files required)

#### 1. `videos/test_video_1080p_10s.mp4`
- **Format**: MP4 (H.264)
- **Resolution**: 1920x1080
- **Duration**: 10 seconds
- **Purpose**: HLS streaming, thumbnail generation
- **Source**: Any 1080p video (stock or screen recording)

#### 2. `videos/test_video_720p_5s.mp4`
- **Format**: MP4 (H.264)
- **Resolution**: 1280x720
- **Duration**: 5 seconds
- **Purpose**: Video processing tests
- **Source**: Any 720p video

## Recommended Sources

### Free Stock Media (CC0/Public Domain)
- **Pexels**: https://www.pexels.com/
- **Unsplash**: https://unsplash.com/
- **Pixabay**: https://pixabay.com/

### Generating Test Media

You can generate synthetic media using:
- **Images**: PIL/Pillow (gradients, patterns)
- **Videos**: ffmpeg (test patterns, color bars)

Example - Generate test pattern image:
```python
from PIL import Image, ImageDraw
img = Image.new('RGB', (1920, 1080), color=(73, 109, 137))
draw = ImageDraw.Draw(img)
# Add patterns...
img.save('test_image_1920x1080.jpg')
```

## Validation

Run this to check media setup:
```bash
pytest tests/test_client/test_media_validation.py -v
```

This test checks:
- All required files exist
- Correct formats and resolutions
- Files are readable

## Using Existing Test Media

If you have access to existing test media (e.g., `/Users/anandasarangaram/Work/test_media`), you can symlink or copy:

```bash
# Option 1: Symlink
ln -s /Users/anandasarangaram/Work/test_media/images cl_client_test_media/images
ln -s /Users/anandasarangaram/Work/test_media/videos cl_client_test_media/videos

# Option 2: Copy
cp -r /Users/anandasarangaram/Work/test_media/* cl_client_test_media/
```

## Troubleshooting

### Tests fail with "Media not found"

1. Check environment variable is set correctly
2. Verify directory structure matches requirements
3. Run validation tests to identify missing files

### Tests fail with "Invalid format"

1. Check file extensions match requirements
2. Verify image/video dimensions
3. Ensure EXIF data exists (for test_exif_rich.jpg)
