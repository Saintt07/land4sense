"""RGB preview + mask overlay as base64 PNGs (Member 1's recipe, with a zero-range guard)."""
import base64
from io import BytesIO

import numpy as np
from PIL import Image


def _png_b64(arr: np.ndarray) -> str:
    buf = BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")  # uint8 HxWx3 → RGB, HxWx4 → RGBA
    return base64.b64encode(buf.getvalue()).decode()


def rgb_preview_b64(img: np.ndarray) -> str:
    """Raw (128,128,14) patch → true-colour PNG (B4,B3,B2), min-max scaled."""
    rgb = img[:, :, [3, 2, 1]].astype(np.float32)
    lo, rng = rgb.min(), rgb.max() - rgb.min()
    norm = (rgb - lo) / rng if rng > 0 else np.zeros_like(rgb)  # constant patch → black, not NaN
    return _png_b64((norm * 255).astype(np.uint8))


def mask_overlay_b64(mask: np.ndarray) -> str:
    """(128,128) {0,1} mask → RGBA PNG: landslide red (alpha 180), background transparent."""
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[mask == 1] = (255, 0, 0, 180)
    return _png_b64(rgba)
