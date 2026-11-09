import base64
from io import BytesIO

import numpy as np
from PIL import Image

from app.services.imaging import mask_overlay_b64, rgb_preview_b64


def decode(s: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(s)))


def test_rgb_preview_shape_and_mode():
    img = decode(rgb_preview_b64(np.random.default_rng(0).uniform(0, 2, (128, 128, 14))))
    assert img.size == (128, 128) and img.mode == "RGB"


def test_rgb_preview_constant_patch_no_div_by_zero():
    with np.errstate(all="raise"):
        img = decode(rgb_preview_b64(np.full((128, 128, 14), 0.7)))
    assert img.mode == "RGB" and img.getextrema() == ((0, 0), (0, 0), (0, 0))


def test_mask_overlay_pixels():
    mask = np.zeros((128, 128), np.uint8)
    mask[:10, :10] = 1
    img = decode(mask_overlay_b64(mask))
    assert img.size == (128, 128) and img.mode == "RGBA"
    assert img.getpixel((0, 0)) == (255, 0, 0, 180)
    assert img.getpixel((50, 50))[3] == 0


def test_mask_overlay_all_zero_is_transparent():
    img = decode(mask_overlay_b64(np.zeros((128, 128), np.uint8)))
    assert img.getchannel("A").getextrema() == (0, 0)
