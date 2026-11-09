from io import BytesIO
from pathlib import Path

import h5py
import numpy as np
import pytest

from app.services.preprocess import add_indices, load_patch, load_stats, normalize

MODELS = Path(__file__).resolve().parents[1] / "models"


def make_h5(arr=None, key="img") -> bytes:
    buf = BytesIO()
    with h5py.File(buf, "w") as f:
        if arr is not None:
            f.create_dataset(key, data=arr)
    return buf.getvalue()


def valid_img(shape=(128, 128, 14)):
    # values in the dataset's typical range (~0.5–1.5); cirrus mean ≈ 1.0 < 2.5
    return np.random.default_rng(0).uniform(0.5, 1.5, shape).astype(np.float32)


def test_valid_patch_pipeline():
    img = load_patch(make_h5(valid_img()))
    img17 = add_indices(img)
    mean, std = load_stats(MODELS)
    out = normalize(img17, mean, std)
    assert img17.shape == out.shape == (128, 128, 17)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    # raw bands untouched, index channels appended
    assert np.allclose(img17[:, :, :14], img)
    nir, red = img[:, :, 7], img[:, :, 3]
    assert np.allclose(img17[:, :, 14], (nir - red) / (nir + red + 1e-6), atol=1e-6)


def cloudy():
    img = valid_img()
    img[:, :, 9] = 5.0
    return img


def nan_filled():
    return np.full((128, 128, 14), np.nan, dtype=np.float32)


@pytest.mark.parametrize(
    "data, msg",
    [
        (lambda: make_h5(valid_img((64, 64, 14))), "shape"),
        (lambda: make_h5(valid_img(), key="other"), "missing 'img'"),
        (lambda: make_h5(None), "missing 'img'"),
        (lambda: np.random.default_rng(1).bytes(4096), "not an HDF5"),
        (lambda: b"", "not an HDF5"),
        (lambda: make_h5(nan_filled()), "NaN"),
        (lambda: make_h5(cloudy()), "cloud"),
    ],
    ids=["wrong_shape", "wrong_key", "empty_h5", "random_bytes", "empty_bytes", "nan", "cloudy"],
)
def test_rejects_bad_files(data, msg):
    with pytest.raises(ValueError, match=msg):
        load_patch(data())
