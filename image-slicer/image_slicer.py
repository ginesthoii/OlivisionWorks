from PIL import Image
import os

# Settings
SOURCE_IMAGE = "x_sign.png"   # example  image
OUTPUT_DIR = "nine-pieces"
GRID_SIZE = 3                    # 3x3 = 9 tiles 

def make_output_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def crop_to_center_square(img: Image.Image) -> Image.Image:
    """Crop the image to a centered square (min(width, height))."""
    w, h = img.size
    side = min(w, h)
    left   = (w - side) // 2
    top    = (h - side) // 2
    right  = left + side
    bottom = top + side
    return img.crop((left, top, right, bottom))

def slice_image_to_tiles():
    # Load image
    img = Image.open(SOURCE_IMAGE).convert("RGB")

    # Crop to a centered square so tiles are perfect squares
    img = crop_to_center_square(img)
    w, h = img.size

    tile_w = w // GRID_SIZE
    tile_h = h // GRID_SIZE

    make_output_dir(OUTPUT_DIR)

    tile_id = 0
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            left   = col * tile_w
            upper  = row * tile_h
            right  = left + tile_w
            lower  = upper + tile_h

            tile = img.crop((left, upper, right, lower))
            out_path = os.path.join(OUTPUT_DIR, f"{tile_id}.jpg")
            tile.save(out_path, "JPEG", quality=95)
            print(f"Saved {out_path}")
            tile_id += 1

    print("Done! Tiles are in:", OUTPUT_DIR)

if __name__ == "__main__":
    slice_image_to_tiles()
