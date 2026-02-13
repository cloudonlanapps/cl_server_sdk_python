from pathlib import Path
from pydantic import BaseModel
import uuid
from PIL import Image
from loguru import logger

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CliConfig(BaseModel):
    """CLI configuration from pytest arguments."""
    auth_url: str
    compute_url: str
    store_url: str
    mqtt_url: str
    username: str | None
    password: str | None


class ServerRootResponse(BaseModel):
    """Server root endpoint response (health check)."""
    status: str
    service: str
    version: str
    guestMode: str = "off"  # "on" or "off"
    auth_required: bool = True  # Only from compute service


class ComputeServerInfo(BaseModel):
    """Compute server capability information."""
    auth_required: bool = True
    guest_mode: bool = False  # Converted from "on"/"off" string


class StoreServerInfo(BaseModel):
    """Store server capability information."""
    guest_mode: bool = False  # Converted from "on"/"off" string


class UserInfo(BaseModel):
    """Current user information from /users/me."""
    id: int
    username: str
    is_admin: bool
    is_active: bool
    permissions: list[str]


class AuthConfig(BaseModel):
    """Complete auth configuration for tests."""
    mode: str  # "auth" or "no-auth"
    auth_url: str
    compute_url: str
    store_url: str
    mqtt_url: str
    compute_auth_required: bool
    compute_guest_mode: bool
    store_guest_mode: bool
    username: str | None
    password: str | None
    user_info: UserInfo | None
    
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
        # Check if source exists
        if not source_path.exists():
            raise FileNotFoundError(f"Source image not found: {source_path}")

        # Try to open with PIL to modify pixels
        try:
            with Image.open(source_path) as img:
                # Force load to ensure we can access pixels
                img.load()
                
                # Create a copy to modify
                img_copy = img.copy()
                
                # Generate unique identifier
                unique_id = uuid.uuid4().bytes

                # Modify LAST 16 pixels (bottom-right) using the UUID bytes
                # Only if image has pixels
                if img_copy.width > 0 and img_copy.height > 0:
                    width, height = img_copy.size
                    total_pixels = width * height
                    
                    # Convert to mode that supports putpixel if needed/possible
                    if img_copy.mode not in ('RGB', 'RGBA', 'L'):
                         # Skip pixel modification for complex modes, fallback to metadata change or just copy
                         pass
                    else:
                        for i, byte in enumerate(unique_id):
                            idx = total_pixels - 1 - i
                            if idx < 0: break # Safety check for very small images
                            
                            x = idx % width
                            y = idx // width
                            
                            try:
                                # Get pixel value - format depends on mode
                                pixel_val = img_copy.getpixel((x, y))
                                
                                if isinstance(pixel_val, tuple):
                                    # RGB or RGBA
                                    pixel = list(pixel_val)
                                    # Modify first channel
                                    # Use modulo 256 to ensure valid range although byte is already 0-255
                                    pixel[0] = (pixel[0] +byte) % 256
                                    img_copy.putpixel((x, y), tuple(pixel))
                                elif isinstance(pixel_val, int):
                                    # L (grayscale)
                                    new_val = (pixel_val + byte) % 256
                                    img_copy.putpixel((x, y), new_val)
                            except Exception:
                                # Start ignore pixel modification errors
                                pass
                
                # Save to new path with EXIF
                exif_data = img.getexif()
                img_copy.save(dest_path, exif=exif_data, quality=95)
                return

        except Exception as e:
            logger.warning(f"PIL modification failed for {source_path}: {e}")
            # Fallback will execute below
            
    except Exception as e:
        logger.error(f"Error preparing unique image {source_path}: {e}")
        
    # Fallback to simple copy
    import shutil
    shutil.copy2(source_path, dest_path)
