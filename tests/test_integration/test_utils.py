from pathlib import Path

def create_unique_copy(source_path: Path, dest_path: Path, offset: int = 0):
    """Create a unique copy of an image by modifying a pixel and adding random bytes."""
    from PIL import Image
    import random
    import os
    with Image.open(source_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        pixels = img.load()
        if pixels:
            r, g, b = pixels[0, 0] # type: ignore
            pixels[0, 0] = (r, g, (b + 11 + offset) % 256) # type: ignore
        img.save(dest_path)
    
    # Append random bytes to ensure unique MD5 regardless of pixel modification
    with open(dest_path, "ab") as f:
        f.write(os.urandom(16))
