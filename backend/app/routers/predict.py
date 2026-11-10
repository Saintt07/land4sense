from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app import auth, db, security
from app.services.detections import log_detection
from app.services.imaging import mask_overlay_b64, rgb_preview_b64
from app.services.inference import rf_confidence, risk_stats, run_rf, run_unet
from app.services.preprocess import add_indices, cirrus_mean, load_patch, normalize

MAX_BYTES = 5 * 1024 * 1024

router = APIRouter()


@router.post(
    "/api/predict",
    dependencies=[
        Depends(security.rate_limit),
        Depends(auth.get_current_user),
    ],
)
def predict(
    request: Request,
    file: UploadFile = File(...),
    region_name: str | None = Form(None, max_length=100),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
    conn=Depends(db.get_db),
):
    # sync def: inference is CPU-bound, FastAPI runs it in the threadpool
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large: max 5 MB")

    try:
        img = load_patch(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not getattr(request.app.state, "models_loaded", False):
        raise HTTPException(503, "Prediction models are not available")

    state = request.app.state
    img17 = add_indices(img)
    img17_norm = normalize(img17, state.mean, state.std)
    _, rf_probs = run_rf(state.rf, img17_norm)
    unet_mask, _ = run_unet(state.unet, img17_norm)
    stats = risk_stats(unet_mask, region_name)
    rf_conf = rf_confidence(rf_probs)
    patch_id = f"upload_{uuid4().hex[:8]}"

    log_detection(
        conn, region_name=region_name, latitude=latitude, longitude=longitude, patch_id=patch_id,
        file_name=(file.filename or "upload.h5")[:255], client_ip=request.client.host if request.client else "unknown",
        stats=stats, rf_conf=rf_conf,
        mean_ndvi=float(img17[:, :, 14].mean()),  # pre-normalization = real units
        mean_slope=float(img[:, :, 12].mean()), cirrus=cirrus_mean(img),
    )
    return {
        "status": "success",
        "risk_level": stats["risk_level"],
        "risk_color": stats["risk_color"],
        "landslide_pixels": stats["landslide_pixels"],
        "landslide_area_m2": stats["landslide_area_m2"],
        "landslide_pct": stats["landslide_pct"],
        "rf_confidence": round(rf_conf, 4),
        "rgb_preview_b64": rgb_preview_b64(img),
        "mask_overlay_b64": mask_overlay_b64(unet_mask),
        "patch_id": patch_id,
    }
