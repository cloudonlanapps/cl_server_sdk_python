from pathlib import Path

import uuid
from PIL import Image
from loguru import logger

def create_unique_copy(source_path: Path, dest_path: Path, offset: int = 0) -> None:
    """
    Create a unique copy of the image by modifying the last few pixels.
    This ensures server-side hashing sees it as a new image while preserving EXIF.
    
    Args:
        source_path: Path to source image
        dest_path: Path to destination image
        offset: Unused legacy parameter, kept for compatibility
    """
    try:
        with Image.open(source_path) as img:
            # Force load to ensure we can access pixels
            img.load()
            
            # Generate unique identifier
            unique_id = uuid.uuid4().bytes

            # Modify LAST 16 pixels (bottom-right) using the UUID bytes
            if img.mode == 'RGB' or img.mode == 'RGBA':
                width, height = img.size
                total_pixels = width * height
                
                for i, byte in enumerate(unique_id):
                    idx = total_pixels - 1 - i
                    if idx < 0: break # Safety check for very small images
                    
                    x = idx % width
                    y = idx // width
                    
                    pixel = list(img.getpixel((x, y)))
                    pixel[0] = byte 
                    
                    if img.mode == 'RGBA':
                        img.putpixel((x, y), tuple(pixel))
                    else:
                        img.putpixel((x, y), tuple(pixel[:3]))
            
            # Save to new path with EXIF
            exif_data = img.getexif()
            img.save(dest_path, exif=exif_data, quality=95)
            
    except Exception as e:
        logger.error(f"Error preparing unique image {source_path}: {e}")
        # Fallback to simple copy + append if PIL fails (e.g. not an image)
        import shutil
        import os
        shutil.copy2(source_path, dest_path)
        with open(dest_path, "ab") as f:
            f.write(os.urandom(16))
