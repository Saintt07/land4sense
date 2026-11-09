# Landslide4Sense — Member 2 Backend Plan (FastAPI + MySQL)

## Context
You are Member 2 (Backend, Database & Security Lead) for CS333 Landslide4Sense. Member 1 handed off a trained Random Forest (`rf_landslide_model.joblib`, scikit-learn 1.6.1), U-Net weights (`unet_landslide.pth`), and normalization stats (`channel_mean.npy`, `channel_std.npy`, `normalization_stats.json`), plus the preprocessing/inference recipe (`handoff_member2/HANDOFF_NOTES.txt`). Scope: a MySQL star-schema data mart, one public prediction endpoint, and a security layer — built as small testable milestones. Budget $0.

The product is a **website**: a browser-based web app (Member 3, Vite + map library) calls this API. There is no mobile/native app. **The website has no login/signup page and no dashboard yet**, so the API is public and has a single business endpoint: `POST /api/predict`.

**Not included:** login/signup, JWT, user accounts, dashboard endpoint (all deferred — see §7), password reset, roles, ORM/migrations tool, Docker, async job queue, file storage of uploads, frontend (Member 3), mobile/native app.

---

## 0. Status of Member 1 handoff
**Received** (`handoff_member2/`): RF `.joblib` (`rf_landslide_model_compressed.joblib`, 512 MB joblib-compressed — identical model to the earlier 1.56 GB file; copied to `backend/models/rf_landslide_model.joblib`. ~12 s load, ~1.5 GB RAM), `unet_landslide.pth`, `channel_mean.npy`, `channel_std.npy` (17 values each), `normalization_stats.json`, `HANDOFF_NOTES.txt`.

**Confirmed by Member 1 (2026-11-09):** U-Net mask threshold = **0.8461** (sigmoid prob > 0.8461), replacing the handoff's 0.5. RF stays at 0.5 (= sklearn `predict`).

**Still missing:**
1. **The exact `UNet` class source** — needed for U-Net inference (M7). State_dict keys (`downs.0-3`, `bottleneck`, `ups.0-7`, `final`) match the common DoubleConv U-Net, so a draft is possible, but the real class must confirm it.
2. **2–3 sample `.h5` patches** + Member 1's U-Net landslide pixel count for one of them (regression check).
3. **Their `torch` version** (low risk; state_dicts are portable).
4. **Band 1 (Coastal Aerosol) threshold.** Until given, guardrail uses Cirrus only (`img[:,:,9].mean() > 2.5`).
5. Step 8 metrics (F1 / ROC-AUC / IoU) — seeded as NULL, filled with one `UPDATE` later.
6. ~~Ask whether a smaller RF is acceptable~~ — got a 512 MB compressed file (2026-11-09); same forest, so RAM is still ~1.5 GB (still a concern for free hosting).

---

## 1. Directory structure
```
land4sense/backend/
├── app/
│   ├── main.py            # FastAPI app, lifespan (load models once), CORS, router include, /health
│   ├── config.py          # reads .env via python-dotenv (DB creds, CORS origins)
│   ├── db.py              # PyMySQL connection dependency (get_db), DictCursor, commit/rollback
│   ├── security.py        # in-memory per-IP rate limiter
│   ├── schemas.py         # Pydantic response models (PredictOut, ErrorOut)
│   ├── routers/
│   │   └── predict.py     # POST /api/predict
│   ├── services/
│   │   ├── preprocess.py  # Stage 0 guardrail, 14→17 channels, normalize
│   │   ├── inference.py   # load RF + U-Net, run both, risk level, rf_confidence
│   │   ├── imaging.py     # RGB preview PNG b64, RGBA mask PNG b64
│   │   └── detections.py  # all SQL: get-or-create dims, insert fact
│   └── ml/
│       └── unet.py        # UNet class from Member 1 (verbatim)
├── models/                # .joblib, .pth, .npy, normalization_stats.json  (gitignored)
├── sql/
│   ├── 01_schema.sql      # CREATE DATABASE + tables
│   ├── 02_seed.sql        # dim_model rows, 'Unknown' location
│   └── 03_app_user.sql    # least-privilege service account
├── tests/
│   ├── fixtures/          # sample .h5 from Member 1 (+ synthetic files generated in tests)
│   ├── test_preprocess.py
│   ├── test_inference.py
│   ├── test_imaging.py
│   └── test_api.py        # FastAPI TestClient end-to-end
├── .env.example           # committed; .env is gitignored
├── .gitignore
└── requirements.txt
```
**requirements.txt:** `fastapi uvicorn[standard] python-multipart pymysql python-dotenv h5py numpy scikit-learn==1.6.1 joblib torch==<M1's, CPU> pillow pytest httpx`.

Design choices: raw parameterized SQL via PyMySQL (`cursor.execute(sql, params)`), no ORM. Models loaded once at startup into `app.state`.

---

## 2. Database schema (`landslide4sense`, InnoDB, utf8mb4)

**dim_time** — one row per calendar day, smart key, inserted on demand (`INSERT IGNORE`)
| column | type | notes |
|---|---|---|
| time_id | INT PK | `YYYYMMDD`, e.g. 20261105 |
| full_date | DATE NOT NULL UNIQUE | |
| year | SMALLINT NOT NULL | |
| quarter | TINYINT NOT NULL | 1–4 |
| month | TINYINT NOT NULL | |
| day | TINYINT NOT NULL | |
| day_of_week | TINYINT NOT NULL | 1=Mon … 7=Sun |

**dim_location** — get-or-create from optional upload form fields
| column | type | notes |
|---|---|---|
| location_id | INT AUTO_INCREMENT PK | id 1 = seeded 'Unknown' |
| region_name | VARCHAR(100) NOT NULL | |
| latitude | DECIMAL(9,6) NULL | |
| longitude | DECIMAL(9,6) NULL | |
| | UNIQUE(region_name, latitude, longitude) | |

**dim_model** — seeded with 2 rows (U-Net, Random Forest)
| column | type | notes |
|---|---|---|
| model_id | INT AUTO_INCREMENT PK | |
| model_name | VARCHAR(50) NOT NULL | 'U-Net', 'Random Forest' |
| model_type | VARCHAR(30) NOT NULL | 'segmentation' / 'pixel-classifier' |
| version | VARCHAR(20) NOT NULL | 'v1' |
| artifact_file | VARCHAR(255) NOT NULL | 'unet_landslide.pth' |
| f1_score | DECIMAL(5,4) NULL | from Step 8 |
| roc_auc | DECIMAL(5,4) NULL | |
| iou | DECIMAL(5,4) NULL | |
| | UNIQUE(model_name, version) | |

**fact_landslide_detections** — one row per successful `/api/predict`
| column | type | notes |
|---|---|---|
| detection_id | BIGINT UNSIGNED AUTO_INCREMENT PK | |
| time_id | INT NOT NULL | FK → dim_time |
| location_id | INT NOT NULL | FK → dim_location |
| model_id | INT NOT NULL | FK → dim_model (the U-Net row) |
| patch_id | VARCHAR(64) NOT NULL | e.g. `upload_<uuid8>` |
| file_name | VARCHAR(255) NOT NULL | original filename |
| client_ip | VARCHAR(45) NOT NULL | audit (no user accounts) |
| landslide_pixels | INT UNSIGNED NOT NULL | |
| landslide_area_m2 | INT UNSIGNED NOT NULL | pixels × 100 |
| landslide_pct | DECIMAL(5,2) NOT NULL | |
| risk_level | ENUM('Low','Moderate','High') NOT NULL | |
| rf_confidence | DECIMAL(5,4) NOT NULL | |
| mean_ndvi | DECIMAL(6,4) NOT NULL | pre-normalization |
| mean_slope | DECIMAL(8,4) NOT NULL | raw channel index 12 |
| cirrus_mean | DECIMAL(8,4) NOT NULL | guardrail value, for audit |
| created_at | DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP | |

FKs all `ON DELETE RESTRICT`. Images (base64) are **not** stored — returned only. The fact table keeps logging so a future dashboard has data.

**Least-privilege account (`03_app_user.sql`)** — schema created by `root` in phpMyAdmin; the API only uses `l4s_app`:
```
CREATE USER 'l4s_app'@'localhost' IDENTIFIED BY '<from .env>';
GRANT SELECT ON landslide4sense.* TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.fact_landslide_detections TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.dim_time      TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.dim_location  TO 'l4s_app'@'localhost';
```
No UPDATE/DELETE/DDL.

---

## 3. Endpoint contract

**POST /api/predict** (public, multipart) — fields: `file` (.h5, required), `region_name`, `latitude`, `longitude` (optional → 'Unknown' location). Rate limit 10/min/IP. Success = exact handoff JSON shape (`status, risk_level, risk_color, landslide_pixels, landslide_area_m2, landslide_pct, rf_confidence, rgb_preview_b64, mask_overlay_b64, patch_id`). Errors: `{"status":"error","error":"<msg>"}` with 413 (>5 MB), 400 (not HDF5 / missing `img` / bad shape / NaN-Inf / excessive cloud cover), 429 (rate limit). Nothing is written to DB on error.

`rf_confidence` definition (confirmed by Member 1): mean RF probability over all 16,384 pixels.

**GET /health** → `{"status":"ok","db":"ok"}`.

---

## 4. Architecture flow (upload → MySQL)
```
Web frontend in browser (Member 3) ── multipart POST /api/predict
   │
   ▼
[CORS whitelist] → [rate limiter (IP)]   ─ fail → 429
   │
   ▼
routers/predict.py: read ≤5 MB+1 bytes ─ too big → 413
   │
   ▼
services/preprocess.py
   Stage 0: h5py.File(BytesIO) → f["img"] → shape (128,128,14)? finite? cirrus(idx 9) mean ≤ 2.5? [B1 check when threshold known]
            ─ fail → 400 {"status":"error"}
   Step 1:  NDVI, NDWI, BSI → img17 (128,128,17) float32
   Step 2:  (img17 − mean) / std   (from models/*.npy)
   │
   ▼
services/inference.py  (models preloaded in app.state at startup)
   RF:    img17.reshape(-1,17) → predict / predict_proba → rf_mask, rf_conf → rf_confidence
   U-Net: (1,17,128,128) → sigmoid → >0.8461 → unet_mask   (Member 1's tuned optimum, not 0.5)
   Risk:  pixels, area_m2 = pixels×100, pct → Low <5 / Moderate <20 / High
   │
   ▼
services/imaging.py
   raw img bands [3,2,1] → min-max (guard zero range) → RGB PNG → base64
   unet_mask → RGBA (255,0,0,180 / transparent) → PNG → base64
   │
   ▼
services/detections.py  (one transaction, parameterized SQL, as l4s_app)
   INSERT IGNORE dim_time(today) → get-or-create dim_location → SELECT U-Net model_id
   → INSERT fact_landslide_detections(... client_ip ...) → COMMIT
   │
   ▼
200 JSON (handoff shape) → Member 3 overlays mask_overlay_b64 on rgb_preview_b64 on the map
```

---

## 5. Milestones (each ends with a test; don't start the next until it passes)

### Achievable now
**M1 — Skeleton & health.** venv, `requirements.txt`, `app/main.py` with `GET /health`, `config.py`, `.env.example`, `.gitignore` (`.env`, `models/`, `venv/`, `__pycache__/`).
✅ Test: `uvicorn app.main:app --reload` → `GET http://127.0.0.1:8000/health` returns `{"status":"ok"}`; `/docs` loads.

**M2 — Database & least-privilege connection. ✅ Done 2026-11-10** Run `01_schema.sql`, `02_seed.sql`, `03_app_user.sql` in phpMyAdmin as root. `db.py` connects as `l4s_app`; `/health` adds `SELECT 1` → `"db":"ok"`.
✅ Test: `/health` shows `"db":"ok"`; `SHOW GRANTS FOR 'l4s_app'@'localhost'` lists only SELECT + 3 INSERTs; as `l4s_app`, `DELETE FROM dim_model` → *command denied*. Stop XAMPP MySQL → `/health` reports db error (not a crash).

**M3 — Preprocessing (pure functions).** `services/preprocess.py`.
✅ Test (`pytest tests/test_preprocess.py`) with **synthetic** `.h5` files: valid random `(128,128,14)` → output `(128,128,17)`, float32, all finite; rejected: wrong shape `(64,64,14)`, missing `img` key, random bytes (not HDF5), NaN-filled, cirrus channel set to 5.0. Add a real-patch case once Member 1 sends samples.

**M4 — Random Forest inference + risk logic.** RF loading in lifespan, RF part of `services/inference.py`, risk-level function.
✅ Test (`pytest tests/test_inference.py`): RF mask `(128,128)` ⊆ {0,1}; probs in [0,1]; `rf_confidence` = 0.0 on an all-background mask; risk thresholds correct at 4.99 / 5 / 19.99 / 20 %.

**M5 — Image generation.** `services/imaging.py`.
✅ Test: decode both b64 strings with PIL → 128×128, modes RGB and RGBA; all-zero mask → fully transparent PNG; constant-value RGB patch doesn't divide by zero. Visual check: paste `data:image/png;base64,<str>` in a browser tab. (Visual check done 2026-11-10: real patch preview shows terrain; empty mask is transparent.)

**M6 — Security hardening.** CORS `allow_origins` from `.env` (`CORS_ORIGINS=http://localhost:5173,...`), rate limiter dependency on predict, secrets audit.
✅ Test: 11th predict within a minute → 429; `curl -H "Origin: http://evil.com" -I .../health` → no `Access-Control-Allow-Origin` header, whitelisted origin gets one; `grep -rnE "execute\(f\"|execute\(.*%[^s]|\.format\(" app/` returns nothing; `git check-ignore .env` prints `.env`.
Rate limiter is an in-memory per-IP sliding window — `shortcut: per-process memory, resets on restart and isn't shared across workers; switch to slowapi+Redis if you run >1 worker`.

### Blocked (waiting on Member 1)
**M7 — U-Net inference. ✅ Done 2026-11-09** (`tests/test_unet.py` 7 pass on torch 2.14.1: strict load; draft class reproduces Member 1's export JSONs — pixel counts at 0.8461 + max prob — on processed and raw→pipeline fixtures in `tests/fixtures/unet/`. Real class still to be confirmed by Member 1, non-blocking.) `ml/unet.py` + U-Net part of `services/inference.py`.
✅ Test: `load_state_dict(strict=True)` succeeds; mask `(128,128)` ⊆ {0,1}; **U-Net landslide pixel count on the reference patch equals Member 1's notebook number**.

**M8 — `/api/predict` end-to-end + logging. ✅ Done 2026-11-10** (`tests/test_api.py` 7 pass incl. real MySQL, no skips. Manual via curl + MySQL Workbench: 200 with all keys, `rf_confidence` 0.1004 = Member 1; +1 fact row per success, today's `dim_time`; location get-or-create reuses rows for same/lowercase/rounded/NULL coords; 6 MB → 413, bad files + form fields → 400, 11th request → 429, fact count unchanged on every error.) `routers/predict.py`, fact insert in `services/detections.py`. Needs M7. (Error paths can be built early.)
✅ Test (Postman form-data): sample `.h5` → 200 with every handoff key; phpMyAdmin shows 1 new fact row, today's `dim_time` row, location row. 6 MB file → 413; `.txt` renamed `.h5` → 400; cloudy synthetic → 400; **fact row count unchanged after each error.** `pytest tests/test_api.py` covers the same.

### Later
**M9 — Cloud DB.** Pick a free MySQL host, run the 3 SQL files there, change `.env` only. MySQL 8 hosts use `caching_sha2_password` → add `cryptography`; most require SSL (`ssl={"ca": ...}` in `db.py`).
✅ Test: `/health` → `"db":"ok"` against the cloud host; repeat M8 upload.

---

## 6. Handoff fixes / notes to share with the team
- Handoff RGB snippet divides by `max-min` — guard zero range (handled in M5).
- `mean_ndvi` / `mean_slope` are stored from **pre-normalization** values (real units).
- Tell Member 3 the error shape `{"status":"error","error":...}`, the 429 on rate limit, and to upload the `.h5` with a browser `FormData` POST (no auth header needed).
- Map library: `landslide4sense_feature_list.md` says Mapbox GL JS, earlier plan said Leaflet — team to agree (doesn't affect the API).
- Fill Step 8 metrics with `UPDATE dim_model SET f1_score=…, roc_auc=…, iou=… WHERE model_name=…` (as root).

## 7. Deferred (re-add when the website gets login and a dashboard)
- `users` table, `fact.user_id` FK, `POST /api/auth/login` (bcrypt + JWT, 5/min rate limit), JWT guard on predict, `scripts/hash_password.py`.
- `GET /api/dashboard-stats` (KPIs, quarterly detections, slope-vs-NDVI, model metrics) — the fact/dim tables already hold the data it needs.
