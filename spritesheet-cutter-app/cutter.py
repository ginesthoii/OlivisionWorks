import os
import datetime
from PIL import Image, ImageTk

# Pillow 10+: use Resampling.LANCZOS instead of deprecated ANTIALIAS
RESAMPLE = Image.Resampling.LANCZOS

class ImageProcessor:
    def __init__(self, path):
        self.path = path
        self.img = Image.open(self.path)
        if self.img.mode not in ("RGB", "RGBA"):
            self.img = self.img.convert("RGBA")
        self.size = (self.img.width, self.img.height)

    def display_image(self, img=None):
        """Return a Tk PhotoImage for display and the ORIGINAL size tuple."""
        if img is None:
            img = self.img
        return ImageTk.PhotoImage(img), self.size

    def zoom_image_for_display(self, factor_percent):
        """
        Return a PhotoImage resized from the ORIGINAL for display only.
        Does NOT mutate self.img. Caller tracks scale externally.
        """
        factor_percent = max(1, int(factor_percent))
        base_w = max(1, int(self.size[0] * (factor_percent / 100.0)))
        wpercent = base_w / float(self.size[0])
        base_h = max(1, int(self.size[1] * wpercent))
        disp = self.img.resize((base_w, base_h), RESAMPLE)
        return ImageTk.PhotoImage(disp)

    def resize_image(self, width, height, save=False):
        """Destructive resize of the underlying image (rare for sprites)."""
        width = max(1, int(width))
        height = max(1, int(height))
        new_img = self.img.resize((width, height), RESAMPLE)
        if save:
            name = os.path.splitext(os.path.basename(self.path))[0]
            new_img.save(f'{name}-resized.png')
            self.img = new_img
            self.size = (width, height)
        image, size = self.display_image(new_img)
        return image, size

    def _mkdir_out(self, suffix=""):
        dt = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        stem = os.path.splitext(os.path.basename(self.path))[0]
        folder = f"{stem}_{dt}{suffix}"
        if not os.path.exists(folder):
            os.mkdir(folder)
        return folder

    def dividebytile(self, twidth, theight, include_partial=False):
        """Cut WITHOUT resizing. twidth/theight are ORIGINAL pixels."""
        img = self.img
        W, H = img.width, img.height
        if include_partial:
            cols = (W + twidth - 1) // twidth
            rows = (H + theight - 1) // theight
        else:
            cols = W // twidth
            rows = H // theight

        folder = self._mkdir_out("_tiles")
        ct = 1
        for r in range(rows):
            for c in range(cols):
                x0 = c * twidth
                y0 = r * theight
                x1 = min(x0 + twidth, W)
                y1 = min(y0 + theight, H)
                if x0 >= W or y0 >= H:
                    continue
                tile = img.crop((x0, y0, x1, y1))
                tile.save(os.path.join(folder, f"{ct:04d}.png"))
                ct += 1

    def dividebyrc(self, rows, cols, include_partial=False):
        """
        Split ORIGINAL by rows/cols. If include_partial, last row/col absorbs remainders.
        """
        img = self.img
        W, H = img.width, img.height
        rows = max(1, int(rows))
        cols = max(1, int(cols))

        cw = W // cols
        ch = H // rows

        folder = self._mkdir_out("_rc")
        ct = 1
        for r in range(rows):
            for c in range(cols):
                x0 = c * cw
                y0 = r * ch
                if include_partial:
                    x1 = (c + 1) * cw if c < cols - 1 else W
                    y1 = (r + 1) * ch if r < rows - 1 else H
                else:
                    x1 = x0 + cw
                    y1 = y0 + ch
                tile = img.crop((x0, y0, x1, y1))
                tile.save(os.path.join(folder, f"{ct:04d}.png"))
                ct += 1

    def dividecustom(self, x, y, width, height):
        """Single crop in ORIGINAL coordinates (x,y,width,height)."""
        img = self.img
        W, H = img.width, img.height
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(W, x0 + int(width))
        y1 = min(H, y0 + int(height))
        region = (x0, y0, x1, y1)
        stem = os.path.splitext(os.path.basename(self.path))[0]
        img.crop(region).save(f'{stem}-{x0}-{y0}-{x1-x0}x{y1-y0}.png')

    def dividebyrect(self, x0, y0, x1, y1):
        """Rect crop with explicit ORIGINAL endpoints."""
        img = self.img
        W, H = img.width, img.height
        x0 = max(0, int(min(x0, x1)))
        y0 = max(0, int(min(y0, y1)))
        x1 = min(W, int(max(x0, x1)))
        y1 = min(H, int(max(y0, y1)))
        stem = os.path.splitext(os.path.basename(self.path))[0]
        img.crop((x0, y0, x1, y1)).save(f'{stem}-{x0}-{y0}-{x1-x0}x{y1-y0}.png')