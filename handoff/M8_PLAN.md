# M8 — `POST /api/predict` end-to-end + logging (plan)

**Status: ✅ Done 2026-11-10** — automated + manual checks below all passed (see `SESSION_2026-11-09.md`).

## Context
M1, M3–M7 are done. M8 is the milestone that turns the pieces into the product: the website uploads a `.h5`, gets the risk JSON + two PNGs, and one fact row is logged in MySQL (PROJECT_PLAN §3, §4, M8).

**Can it be fully completed now? No — two prerequisites fail today (checked read-only just now):**
1. **M2 DB login is broken:** `db.connect()` as `l4s_app` → `1045 Access denied`. M8's acceptance test is about DB rows (1 new fact row on success, count unchanged on every error), so it can't pass until M2 passes.
2. **Not enough memory to load the RF:** `joblib.load(rf)` fails with `MemoryError` even in a bare process (~2 GB free commit). The server lifespan loads RF + U-Net, so `uvicorn` startup (and the Postman test) fails until memory is freed.

Nothing from Member 1 blocks M8. `rf_confidence` (mean over all 16,384 pixels) and `risk_color` (hex: Low `#2ECC71`, Moderate `#F39C12`, High `#E74C3C`) are confirmed and implemented.

## Step 0 — Prerequisites (you, before any M8 code is "done")
**P1. Fix M2** (PROJECT_PLAN M2) — as MySQL80 root:
1. Pick an ASCII-only password → `DB_PASSWORD=` in `backend/.env` (never in `.env.example` / `03_app_user.sql`).
2. `SELECT user FROM mysql.user; SHOW DATABASES;` → if schema/user missing, run `sql/01_schema.sql` → `02_seed.sql` → `03_app_user.sql`; otherwise `ALTER USER 'l4s_app'@'localhost' IDENTIFIED BY '<pw>';`
3. Verify: `/health` → `"db":"ok"`; `SHOW GRANTS FOR 'l4s_app'@'localhost'` = SELECT + 3 INSERTs only; as `l4s_app`, `DELETE FROM dim_model` → denied; `net stop MySQL80` → `/health` `"db":"error"` (no crash), then `net start MySQL80`.

**P2. Free RAM** — close extra VS Code windows/apps until `.\venv\Scripts\python -c "import joblib; joblib.load('models/rf_landslide_model.joblib')"` succeeds, then `pytest -q` → 32 passed (incl. `test_rf_mask_and_probs`).

M8 code can be written in parallel with P1/P2; it just can't be verified until both pass.

## What M8 must do (contract, PROJECT_PLAN §3)
`POST /api/predict`, public, multipart: `file` (.h5, required), `region_name`, `latitude`, `longitude` (optional).
- 200 → `{status:"success", risk_level, risk_color, landslide_pixels, landslide_area_m2, landslide_pct, rf_confidence, rgb_preview_b64, mask_overlay_b64, patch_id}`
- Errors → `{"status":"error","error":"<msg>"}`: 413 (>5 MB), 400 (not HDF5 / missing `img` / bad shape / NaN-Inf / cloud cover / bad form fields), 429 (rate limit).
- **Nothing written to DB on any error.** Images not stored.

## How (files)

### `app/routers/predict.py` (new)
`router = APIRouter()`; `@router.post("/api/predict", response_model=PredictOut, responses={400/413/429: ErrorOut}, dependencies=[Depends(rate_limit)])`. Plain `def` (CPU-bound → FastAPI threadpool).
Params: `request: Request`, `file: UploadFile = File(...)`, `region_name: str | None = Form(None, max_length=100)`, `latitude: float | None = Form(None, ge=-90, le=90)`, `longitude: float | None = Form(None, ge=-180, le=180)`, `conn = Depends(get_db)`.
Flow (reuse everything existing):
1. `data = file.file.read(MAX_BYTES + 1)`; `len > 5 MB` → `HTTPException(413)`.
2. `img = load_patch(data)` (`services/preprocess.py`); `ValueError` → `HTTPException(400, str(e))`.
3. Exactly one of lat/lon given → 400 "latitude and longitude must be given together".
4. `img17 = add_indices(img)`; `norm = normalize(img17, request.app.state.mean, .std)`.
5. `rf_mask, rf_conf = run_rf(state.rf, norm)`; `unet_mask, _ = run_unet(state.unet, norm)` (`services/inference.py`).
6. `stats = risk_stats(unet_mask)`; `rf_confidence(rf_conf)` rounded 4 dp.
7. `rgb_preview_b64(img)`, `mask_overlay_b64(unet_mask)` (`services/imaging.py`).
8. `patch_id = f"upload_{uuid4().hex[:8]}"`; `insert_detection(conn, …)` with `mean_ndvi = img17[:,:,14].mean()` (pre-norm), `mean_slope = img[:,:,12].mean()`, `cirrus_mean(img)`, `client_ip = request.client.host`, `file_name = (file.filename or "upload.h5")[:255]`.
9. Return the handoff dict. `get_db` commits after return; any exception (incl. the HTTPExceptions above) → rollback, so errors never write.

### `app/services/detections.py` (new — all SQL, parameterized `%s` only)
- `time_id(cur, d)`: `INSERT IGNORE INTO dim_time (...)` with `YYYYMMDD`, year, quarter, month, day, isoweekday → return id.
- `location_id(cur, region, lat, lon)`: all None → 1 ('Unknown'). Else region defaults to 'Unknown'; `SELECT location_id … WHERE region_name=%s AND latitude <=> %s AND longitude <=> %s` (null-safe, because UNIQUE allows duplicate NULLs) → else `INSERT` → `cur.lastrowid`. Only SELECT+INSERT → fits `l4s_app` grants.
- `unet_model_id(cur)`: `SELECT model_id FROM dim_model WHERE model_name='U-Net' AND version='v1'`; missing → `RuntimeError` (500, seed not run).
- `insert_detection(conn, **fields) -> detection_id`: the three lookups + `INSERT INTO fact_landslide_detections` in one cursor; transaction owned by `get_db`.

### `app/schemas.py` (new)
`PredictOut` (fields above, `status: Literal["success"]`) and `ErrorOut` (`status: Literal["error"]`, `error: str`) — for `/docs` + response validation.

### `app/main.py`
- `app.include_router(predict.router)`.
- `RequestValidationError` handler → 400 `{"status":"error","error": "<field>: <msg>"}` (otherwise missing `file` / bad latitude return FastAPI's 422 `{"detail":…}`, breaking the single error shape).
- `pymysql.MySQLError` handler → 503 `{"status":"error","error":"Database unavailable"}`, details only in the server log (same pattern as `/health`).

## Verification

### Automated — `tests/test_api.py` (new)
Setup (module fixture): real `mean/std` (`load_stats`) + real U-Net (`load_unet`) put on `app.state`; **RF = tiny real `RandomForestClassifier(n_estimators=2)` fitted on random 17-feature data** (keeps API tests off the 1.5 GB model; real RF is already covered by `test_inference.py`). `security._hits.clear()` per test.
DB: real MySQL as `l4s_app` (proves the real grants). `app.dependency_overrides[get_db]` yields **one shared connection that is rolled back at teardown** → tests see their inserts but leave no rows behind (`l4s_app` can't DELETE). Skip with a clear reason if the DB is unreachable — M8 is not verified while that skip shows.
Tests:
1. Success with `fixtures/unet/luzon_0155_r1536_c2048.h5` + `region_name=Benguet, latitude, longitude` → 200; exact key set; `landslide_pixels == 0` (Member 1's JSON); both b64 decode to 128×128 PNG (RGB / RGBA); fact count +1; fact row has `patch_id`, `client_ip='testclient'`, `risk_level`; today's `dim_time` row exists; location row created.
2. Same region/coords again → same `location_id` (get-or-create, no duplicate).
3. No location fields → `location_id = 1`.
4. `handoff_member2/sample_patches/sample_patch_1.h5` (float64) → 200 (copy into `tests/fixtures/`).
5. Errors, each asserting error shape **and fact count unchanged**: 6 MB body → 413; random bytes named `.h5` → 400; synthetic patch with cirrus = 5.0 → 400; `.h5` without `img` → 400; latitude only → 400; latitude = 999 → 400; no `file` field → 400.
6. 11th request in a minute → 429 (end-to-end on the real route).

Run: `cd backend; .\venv\Scripts\python -m pytest -q -rs` → all pass, **no skips**.

### Manual (PROJECT_PLAN M8 ✅)
1. `.\venv\Scripts\python -m uvicorn app.main:app` → starts (both models load).
2. Postman `POST http://127.0.0.1:8000/api/predict`, form-data `file` = a fixture `.h5` (+ region/lat/lon) → 200 with every handoff key; paste `data:image/png;base64,<rgb_preview_b64>` in a browser tab.
3. phpMyAdmin: 1 new `fact_landslide_detections` row, today's `dim_time` row, the location row.
4. 6 MB file → 413; `.txt` renamed `.h5` → 400; cloudy synthetic → 400; fact row count unchanged after each.

Then mark M2 + M8 ✅ in `PROJECT_PLAN.md` and `handoff/SESSION_2026-11-09.md`.

## Out of scope
Band 1 guardrail, cloud DB (M9), smaller RF, login/dashboard (§7).
