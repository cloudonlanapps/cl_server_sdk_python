from pathlib import Path

def create_unique_copy(source_path: Path, dest_path: Path, offset: int = 0):
    """Create a unique copy of an image by appending random bytes to the file end.
    
    This preserves the original image content (including Exif) and avoids re-encoding errors
    or quality loss that occurs with PIL.save(). Appended bytes are ignored by decoders.
    """
    import shutil
    import os
    
    # 1. Copy the file (preserves content, metadata, etc.)
    shutil.copy2(source_path, dest_path)
    
    # 2. Append random bytes to ensure unique MD5
    # The 'offset' arg is kept for compatibility but not used for pixel mod anymore
    with open(dest_path, "ab") as f:
        # Write enough bytes to ensure uniqueness even if random data collides (unlikely)
        f.write(os.urandom(16 + (offset % 16)))
