"""Stage 0 guardrail + 14→17 channel features + normalization (Member 1's recipe)."""
from io import BytesIO
from pathlib import Path

import h5py
import numpy as np

CIRRUS_IDX = 9
CIRRUS_MAX = 2.5  # TODO: add Band 1 (Coastal Aerosol) check once Member 1 sends the threshold
EPS = 1e-6


def load_patch(data: bytes) -> np.ndarray:
    """Read and validate an uploaded .h5 patch. Raises ValueError with a user-facing message."""
    try:
        with h5py.File(BytesIO(data), "r") as f:
            if "img" not in f or not isinstance(f["img"], h5py.Dataset):
                raise ValueError("Invalid file: missing 'img' dataset")
            img = f["img"][()]
    except OSError:
        raise ValueError("Invalid file: not an HDF5 file")
    if img.shape != (128, 128, 14):
        raise ValueError(f"Invalid format: expected shape (128, 128, 14), got {img.shape}")
    if not np.issubdtype(img.dtype, np.number) or not np.isfinite(img).all():
        raise ValueError("Invalid file: contains NaN or infinite values")
    if cirrus_mean(img) > CIRRUS_MAX:
        raise ValueError("Excessive cloud cover")
    return img


def cirrus_mean(img: np.ndarray) -> float:
    return float(img[:, :, CIRRUS_IDX].mean())


def add_indices(img: np.ndarray) -> np.ndarray:
    """(128,128,14) raw → (128,128,17) float32 with NDVI, NDWI, BSI appended."""
    ndvi = (img[:, :, 7] - img[:, :, 3]) / (img[:, :, 7] + img[:, :, 3] + EPS)
    ndwi = (img[:, :, 2] - img[:, :, 7]) / (img[:, :, 2] + img[:, :, 7] + EPS)
    a = img[:, :, 10] + img[:, :, 3]
    b = img[:, :, 7] + img[:, :, 1]
    bsi = (a - b) / (a + b + EPS)
    return np.dstack([img, ndvi, ndwi, bsi]).astype(np.float32)


def normalize(img17: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((img17 - mean) / std).astype(np.float32)


def load_stats(models_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    return np.load(models_dir / "channel_mean.npy"), np.load(models_dir / "channel_std.npy")
