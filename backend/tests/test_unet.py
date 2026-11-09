"""M7: U-Net inference must reproduce Member 1's exported results (demo_pipeline/export/*.json)."""
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from app.services.inference import load_unet, risk_stats, run_unet
from app.services.preprocess import add_indices, load_patch, load_stats, normalize

MODELS = Path(__file__).resolve().parents[1] / "models"
FIX = Path(__file__).parent / "fixtures" / "unet"
pytestmark = pytest.mark.skipif(not (MODELS / "unet_landslide.pth").exists(),
                                reason="U-Net weights not in backend/models")

PROCESSED = ["luzon_0123_r1152_c0768", "luzon_0149_r0128_c1024",
             "luzon_0154_r2816_c1664", "luzon_0173_r2048_c1536"]  # all contain landslide pixels
RAW = ["luzon_0155_r1536_c2048",   # max prob 0.73: positive at 0.5, negative at 0.8461
       "luzon_0150_r1920_c2304"]


@pytest.fixture(scope="module")
def unet():
    return load_unet(MODELS)  # strict=True inside: fails if the class doesn't match the weights


def expected(name):
    return json.loads((FIX / f"{name}.json").read_text())


def test_mask_shape_and_values(unet):
    x = np.random.default_rng(0).standard_normal((128, 128, 17)).astype(np.float32)
    mask, probs = run_unet(unet, x)
    assert mask.shape == probs.shape == (128, 128)
    assert set(np.unique(mask)) <= {0, 1}
    assert probs.min() >= 0 and probs.max() <= 1


@pytest.mark.parametrize("name", PROCESSED)
def test_matches_member1_processed(unet, name):
    with h5py.File(FIX / f"{name}_proc.h5") as f:
        img17_norm = f["img17"][()]  # Member 1's already-normalized input
    mask, probs = run_unet(unet, img17_norm)
    exp = expected(name)
    assert int(mask.sum()) == exp["landslide_pixels"]
    assert probs.max() == pytest.approx(exp["unet_max_prob"], abs=1e-3)
    assert risk_stats(mask)["landslide_area_m2"] == exp["area_m2"]


@pytest.mark.parametrize("name", RAW)
def test_matches_member1_raw_end_to_end(unet, name):
    # same path the API will use: raw upload bytes → guardrail → indices → normalize → U-Net
    img = load_patch((FIX / f"{name}.h5").read_bytes())
    mean, std = load_stats(MODELS)
    mask, probs = run_unet(unet, normalize(add_indices(img), mean, std))
    exp = expected(name)
    assert int(mask.sum()) == exp["landslide_pixels"]
    assert probs.max() == pytest.approx(exp["unet_max_prob"], abs=1e-3)
