"""Model inference (RF + U-Net) + risk logic (Member 1's recipe)."""
from pathlib import Path

import joblib
import numpy as np
import torch

from app.ml.unet import UNet

PIXEL_AREA_M2 = 100  # 10 m × 10 m Sentinel-2 pixel
UNET_THRESHOLD = 0.8461  # Member 1's tuned optimum (not the handoff's 0.5)


def load_rf(models_dir: Path):
    return joblib.load(models_dir / "rf_landslide_model.joblib")


def run_rf(rf, img17_norm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Normalized (128,128,17) → (rf_mask uint8 {0,1}, rf_conf float in [0,1]), both (128,128)."""
    h, w, c = img17_norm.shape
    X = img17_norm.reshape(-1, c)
    probs = rf.predict_proba(X)[:, list(rf.classes_).index(1)]
    # same as rf.predict(X) for sorted binary classes [0,1] (ties → 0), without running the forest twice
    labels = (probs > 0.5).astype(np.uint8)
    return labels.reshape(h, w), probs.reshape(h, w)


def load_unet(models_dir: Path) -> UNet:
    model = UNet(in_channels=17)
    # weights_only=True: a state_dict needs no pickle code execution
    state = torch.load(models_dir / "unet_landslide.pth", map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    return model.eval()


def run_unet(model: UNet, img17_norm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Normalized (128,128,17) → (unet_mask uint8 {0,1}, probs float32 in [0,1]), both (128,128)."""
    x = torch.from_numpy(np.ascontiguousarray(img17_norm.transpose(2, 0, 1), dtype=np.float32)).unsqueeze(0)
    with torch.inference_mode():
        probs = torch.sigmoid(model(x)).squeeze().numpy()
    return (probs > UNET_THRESHOLD).astype(np.uint8), probs


def rf_confidence(rf_conf: np.ndarray) -> float:
    """Mean RF probability over all 16,384 pixels (Member 1's definition)."""
    return float(rf_conf.mean())


def risk_level(pct: float) -> tuple[str, str]:
    if pct < 5:
        return "Low", "#2ECC71"
    if pct < 20:
        return "Moderate", "#F39C12"
    return "High", "#E74C3C"


def risk_stats(mask: np.ndarray) -> dict:
    pixels = int(mask.sum())
    pct = pixels / mask.size * 100
    level, color = risk_level(pct)
    return {
        "landslide_pixels": pixels,
        "landslide_area_m2": pixels * PIXEL_AREA_M2,
        "landslide_pct": round(pct, 2),
        "risk_level": level,
        "risk_color": color,
    }
