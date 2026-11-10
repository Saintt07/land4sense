import base64
from io import BytesIO
from pathlib import Path

import h5py
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, db, security
from app.main import MODELS_DIR, app
from app.services.inference import load_rf, load_unet
from app.services.preprocess import load_stats

SAMPLE = Path(__file__).parent / "fixtures" / "unet" / "luzon_0150_r1920_c2304.h5"
HAS_MODELS = (MODELS_DIR / "rf_landslide_model.joblib").exists() and (MODELS_DIR / "unet_landslide.pth").exists()
KEYS = {"status", "risk_level", "risk_color", "landslide_pixels", "landslide_area_m2", "landslide_pct",
        "rf_confidence", "rgb_preview_b64", "mask_overlay_b64", "patch_id"}


class FakeCursor:
    def __init__(self, log):
        self.log, self.lastrowid, self._sql = log, 42, ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def execute(self, sql, params=None):
        self._sql = sql
        self.log.append((sql, params))

    def fetchone(self):
        return {"model_id": 1} if "dim_model" in self._sql else None


class FakeConn:
    def __init__(self):
        self.log = []

    def cursor(self):
        return FakeCursor(self.log)


def fact_inserts(conn):
    return [p for s, p in conn.log if s.startswith("INSERT INTO fact_landslide_detections")]


@pytest.fixture
def fake():
    security._hits.clear()
    conn = FakeConn()

    def _get_db():
        yield conn

    app.dependency_overrides[db.get_db] = _get_db
    app.dependency_overrides[auth.get_current_user] = lambda: {
        "user_id": 1,
        "email": "test@example.com",
        "created_at": None,
    }

    yield TestClient(app), conn
    app.dependency_overrides.clear()


def h5_bytes(img):
    buf = BytesIO()
    with h5py.File(buf, "w") as f:
        f["img"] = img
    return buf.getvalue()


def post(client, content, name="patch.h5", **form):
    return client.post("/api/predict", files={"file": (name, content)}, data=form)


@pytest.mark.parametrize("content,code", [
    (b"\0" * (5 * 1024 * 1024 + 1), 413),
    (b"just some text, renamed to .h5", 400),
    (h5_bytes(np.ones((64, 64, 14), np.float32)), 400),
    (h5_bytes(np.dstack([np.ones((128, 128, 9)), np.full((128, 128, 1), 5.0), np.ones((128, 128, 4))])), 400),
])
def test_bad_upload_rejected_nothing_logged(fake, content, code):
    client, conn = fake
    r = post(client, content)
    assert r.status_code == code
    assert r.json()["status"] == "error" and r.json()["error"]
    assert conn.log == []


def test_bad_latitude_400_error_shape(fake):
    client, conn = fake
    r = post(client, b"x", latitude="200")
    assert r.status_code == 400 and r.json()["status"] == "error" and "latitude" in r.json()["error"]
    assert conn.log == []


@pytest.fixture(scope="module")
def models():
    if not HAS_MODELS:
        pytest.skip("models not in backend/models")
    app.state.mean, app.state.std = load_stats(MODELS_DIR)
    app.state.rf, app.state.unet = load_rf(MODELS_DIR), load_unet(MODELS_DIR)


def test_predict_success_logs_one_fact(models, fake):
    client, conn = fake
    r = post(client, SAMPLE.read_bytes(), name=SAMPLE.name, region_name="Luzon", latitude="16.4", longitude="120.6")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == KEYS and body["status"] == "success"
    for key, mode in (("rgb_preview_b64", "RGB"), ("mask_overlay_b64", "RGBA")):
        im = Image.open(BytesIO(base64.b64decode(body[key])))
        assert im.size == (128, 128) and im.mode == mode
    (row,) = fact_inserts(conn)
    assert row[3] == body["patch_id"] and row[4] == SAMPLE.name and row[6] == body["landslide_pixels"]
    assert any(s.startswith("INSERT INTO dim_location") and p == ("Luzon", 16.4, 120.6) for s, p in conn.log)


def _fact_count():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM fact_landslide_detections")
            return cur.fetchone()["n"]
    finally:
        conn.close()


def test_real_db_one_row_per_success_none_on_error(models):
    """Integration: needs XAMPP MySQL + seeded schema; leaves one real fact row behind."""
    try:
        before = _fact_count()
    except Exception:
        pytest.skip("MySQL not reachable")
    security._hits.clear()
    client = TestClient(app)
    assert post(client, b"not hdf5").status_code == 400
    assert _fact_count() == before
    assert post(client, SAMPLE.read_bytes(), name=SAMPLE.name).status_code == 200
    assert _fact_count() == before + 1
