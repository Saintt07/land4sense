
from pathlib import Path

import numpy as np
import pytest

from app.services.inference import load_rf, risk_level, risk_stats, rf_confidence, run_rf
from app.services.preprocess import add_indices, load_stats, normalize

MODELS = Path(__file__).resolve().parents[1] / "models"
HAS_RF = (MODELS / "rf_landslide_model.joblib").exists()


@pytest.fixture(scope="module")
def rf():
    return load_rf(MODELS)  # 512 MB on disk, ~1.5 GB RAM; loaded once per module


@pytest.mark.skipif(not HAS_RF, reason="RF model not in backend/models")
def test_rf_mask_and_probs(rf):
    img = np.random.default_rng(0).uniform(0.5, 1.5, (128, 128, 14)).astype(np.float32)
    mean, std = load_stats(MODELS)
    img17 = normalize(add_indices(img), mean, std)
    mask, probs = run_rf(rf, img17)
    assert mask.shape == probs.shape == (128, 128)
    assert set(np.unique(mask)) <= {0, 1}
    assert probs.min() >= 0 and probs.max() <= 1
    # the >0.5 threshold must agree with sklearn's own predict
    assert np.array_equal(mask.ravel(), rf.predict(img17.reshape(-1, 17)).astype(np.uint8))
    assert 0.0 <= rf_confidence(probs) <= 1.0


def test_rf_confidence_mean_over_all_pixels():
    conf = np.full((128, 128), 0.1)
    conf[0, :2] = [0.6, 0.8]  # nonzero even without any landslide pixels
    assert rf_confidence(conf) == pytest.approx((0.1 * 16382 + 1.4) / 16384)


@pytest.mark.parametrize("pixels,region,expected", [
    (0, None, ("Low", "#2ECC71")),
    (14, None, ("Low", "#2ECC71")),
    (15, None, ("Moderate", "#F39C12")),
    (150, None, ("Moderate", "#F39C12")),
    (151, None, ("High", "#E74C3C")),
    (245, None, ("High", "#E74C3C")),
    (16384, None, ("High", "#E74C3C")),
    (16384, "Metro Manila", ("Low", "#2ECC71")),
    (151, "Benguet", ("High", "#E74C3C")),
])
def test_risk_thresholds(pixels, region, expected):
    assert risk_level(pixels, region) == expected


def test_risk_stats():
    mask = np.zeros((128, 128), np.uint8)

    # 150 pixels = Moderate
    mask.ravel()[:150] = 1
    assert risk_stats(mask) == {
        "landslide_pixels": 150,
        "landslide_area_m2": 15000,
        "landslide_pct": 0.92,
        "risk_level": "Moderate",
        "risk_color": "#F39C12",
    }

    # 820 pixels = High
    mask.ravel()[:] = 0
    mask.ravel()[:820] = 1
    assert risk_stats(mask)["risk_level"] == "High"

    # Metro Manila exception
    assert risk_stats(mask, "Metro Manila")["risk_level"] == "Low"
