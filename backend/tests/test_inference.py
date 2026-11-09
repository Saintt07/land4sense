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


@pytest.mark.parametrize("pct,expected", [
    (0, ("Low", "#2ECC71")),
    (4.99, ("Low", "#2ECC71")),
    (5, ("Moderate", "#F39C12")),
    (19.99, ("Moderate", "#F39C12")),
    (20, ("High", "#E74C3C")),
    (100, ("High", "#E74C3C")),
])
def test_risk_thresholds(pct, expected):
    assert risk_level(pct) == expected


def test_risk_stats():
    mask = np.zeros((128, 128), np.uint8)
    mask.ravel()[:820] = 1  # 820/16384 = 5.0049 % → Moderate
    assert risk_stats(mask) == {"landslide_pixels": 820, "landslide_area_m2": 82000,
                                "landslide_pct": 5.0, "risk_level": "Moderate", "risk_color": "#F39C12"}
