# Landslide4Sense — Backend Handoff to Member 3 (Frontend)

**From:** Member 2 (Backend, Database & Security) · **Date:** 2026-11-10 · **Backend status:** done and tested (M1–M8)

Everything you need to connect the website to the backend is in this file. Every request, response and error message below was copied from the running API, not written from memory.

**Files that come with this guide** (in `handoff/member3/`):

| File | What it is |
|---|---|
| `sample_response_moderate.json` | A real success response (Moderate risk, red mask visible). Use it as a mock while building the UI. |
| `sample_response_low_empty_mask.json` | A real success response with **0 landslide pixels**, so the mask is fully transparent. Use it to test the "nothing found" case. |
| `sample_patches/sample_patch_1.h5`, `_2.h5`, `_5.h5` | Valid upload files for testing. |
| `sample_patches/invalid_processed_patch.h5` | An `.h5` the API **rejects**. Use it to show error handling in the demo. |

---

## Contents
0. [TL;DR](#0-tldr)
1. [How to reach the API (3 options)](#1-how-to-reach-the-api)
2. [Endpoint reference: `POST /api/predict`](#2-endpoint-reference-post-apipredict)
3. [Errors](#3-errors)
4. [Showing the result on the map](#4-showing-the-result-on-the-map)
5. [Suggested upload flow + UX checklist](#5-suggested-upload-flow--ux-checklist)
6. [Test files and what they return](#6-test-files-and-what-they-return)
7. [What the backend does NOT provide](#7-what-the-backend-does-not-provide)
8. [Model facts for an About/Info panel](#8-model-facts-for-an-aboutinfo-panel)
9. [Troubleshooting](#9-troubleshooting)
10. [Open items](#10-open-items)

---

## 0. TL;DR

- **One endpoint:** `POST {API_URL}/api/predict`, `multipart/form-data`, **no login, no auth header**.
- Send the `.h5` file (plus optional location fields) → get JSON back with a risk level, numbers, and **two base64 PNGs** (satellite preview + red landslide mask) to place on the map.
- Errors always look like `{"status": "error", "error": "<message you can show the user>"}`.
- Health check: `GET {API_URL}/health` → `{"status":"ok","db":"ok"}`. Interactive docs: `{API_URL}/docs`.
- Limits: **5 MB per file**, **10 requests per minute per computer**.

```js
const form = new FormData();
form.append('file', fileInput.files[0]);          // the .h5 file
form.append('latitude', '15.731791');             // optional
form.append('longitude', '121.632743');           // optional
form.append('region_name', 'Aurora');             // optional
const res = await fetch('http://localhost:8000/api/predict', { method: 'POST', body: form });
const data = await res.json();
if (data.status === 'success') console.log(data.risk_level, data.landslide_pct);
else console.error(data.error);
```

---

## 1. How to reach the API

Pick **one**. Option A or C is enough for building the UI. Use A for the demo.

### Option A: Member 2 runs the backend, you connect over the same Wi-Fi (recommended)
You don't install Python, MySQL or the 540 MB models.

**Member 2 does:**
```powershell
cd land4sense\backend
.\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
ipconfig        # note the "IPv4 Address", e.g. 192.168.1.23
```
On the first run Windows asks to allow Python through the firewall: tick **Private networks** → Allow.

**You do:** create `.env.local` in your Vite project:
```
VITE_API_URL=http://192.168.1.23:8000
```
Open `http://192.168.1.23:8000/health` in your browser. You should see `{"status":"ok","db":"ok"}`.

> CORS checks the address of **your page**, not your IP. The API allows pages served from `http://localhost:5173` (Vite's default), so you need no changes **as long as you open the site at exactly `http://localhost:5173`**. See [§9](#9-troubleshooting) if you use another port or `127.0.0.1`.

### Option B: run the backend on your own laptop
Needs: **Python 3.11**, **MySQL 8**, about **1.5 GB of free RAM** (the Random Forest is large), about 3 GB of disk.

1. Get the model files **from Member 2 directly** (git doesn't store them) and put them in `backend/models/`:
   `rf_landslide_model.joblib` (512 MB), `unet_landslide.pth`, `channel_mean.npy`, `channel_std.npy`.
2. Install:
   ```powershell
   cd land4sense\backend
   py -3.11 -m venv venv
   .\venv\Scripts\python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
   .\venv\Scripts\python -m pip install -r requirements.txt
   copy .env.example .env
   ```
3. Edit `.env`: set `DB_PASSWORD` to a password of your choice. Use **plain ASCII letters and digits only**, no quotes or special characters (a non-ASCII password caused `1045 Access denied`).
4. Database: in MySQL Workbench (or phpMyAdmin) **as root**, run in order:
   `sql/01_schema.sql` → `sql/02_seed.sql` → `sql/03_app_user.sql`.
   Before running `03`, replace `CHANGE_ME` in it with the same password as in `.env`. **Don't commit that change.**
5. Start the server:
   ```powershell
   .\venv\Scripts\python -m uvicorn app.main:app --reload
   ```
   Startup takes about **10–15 s** while the models load. Wait for `Application startup complete.`
6. Check `http://localhost:8000/health` → `{"status":"ok","db":"ok"}`. Your `VITE_API_URL` is `http://localhost:8000`.

### Option C: no backend at all (mock mode)
Build the whole UI against the sample JSON files and switch to the real API later. See [§5, mock mode](#mock-mode).

---

## 2. Endpoint reference: `POST /api/predict`

### Request
`Content-Type: multipart/form-data`. **Don't set this header yourself**: when you pass a `FormData` body, the browser sets it and adds the required boundary. No auth header, no cookies.

| Field | Required | Type / rules | Notes |
|---|---|---|---|
| `file` | **yes** | `.h5` file, **max 5 MB** | Must be an HDF5 file with a dataset named `img` of shape **128 × 128 × 14** (a raw Sentinel-2 patch), no NaN/Infinity values, and not too cloudy (see §3). |
| `latitude` | no | number, **−90 … 90** | Usually the dropped pin. |
| `longitude` | no | number, **−180 … 180** | |
| `region_name` | no | text, **max 100 chars** | e.g. province or place name from your search box. |

If you leave out all three location fields, the upload is saved under the location "Unknown". Location fields only affect the database log; they **don't change the prediction**.

### Success response: HTTP 200
Real values from `sample_patch_2.h5` (full file: `sample_response_moderate.json`):
```json
{
  "status": "success",
  "risk_level": "Moderate",
  "risk_color": "#F39C12",
  "landslide_pixels": 938,
  "landslide_area_m2": 93800,
  "landslide_pct": 5.73,
  "rf_confidence": 0.1851,
  "rgb_preview_b64": "iVBORw0KGgoA… (≈33 000 chars)",
  "mask_overlay_b64": "iVBORw0KGgoA…",
  "patch_id": "upload_56be7915"
}
```

| Key | Type | Meaning | How to use it |
|---|---|---|---|
| `status` | `"success"` | Always `"success"` on 200. | Branch on this. |
| `risk_level` | `"Low"` \| `"Moderate"` \| `"High"` | Based on `landslide_pct` (table below). | Badge text. |
| `risk_color` | hex string | `#2ECC71` (Low, green) · `#F39C12` (Moderate, orange) · `#E74C3C` (High, red) | Badge or marker colour, legend. ⚠️ It's a **hex code**, not the word "Green/Yellow/Red" from Member 1's old notes. |
| `landslide_pixels` | integer, 0–16384 | Pixels the U-Net marked as landslide. | Detail text. |
| `landslide_area_m2` | integer | `landslide_pixels × 100` (each pixel is 10 m × 10 m). | Show as m², or ÷10 000 for hectares, or ÷1 000 000 for km². |
| `landslide_pct` | number, 2 decimals | % of the patch covered by landslide. | Main number in the popup. |
| `rf_confidence` | number 0–1, 4 decimals | Random Forest's **average** landslide probability over the patch. It's a second opinion, **not** the confidence of the risk level, and is usually low (≈0.1–0.2) because most of a patch is not landslide. | Optional "RF score" line; label it clearly. |
| `rgb_preview_b64` | string | **PNG, 128×128, RGB**: true-colour satellite preview. Base64 **without** the `data:` prefix. | `"data:image/png;base64," + value` |
| `mask_overlay_b64` | string | **PNG, 128×128, RGBA**: landslide pixels red (`255,0,0`) at alpha 180, everything else **fully transparent**. Same format. | Draw **on top of** the RGB preview. |
| `patch_id` | string | `upload_` + 8 hex chars, unique per upload. | Show as a reference ID or use as a React key. |

**Risk thresholds** (from Member 1):

| `landslide_pct` | `risk_level` | `risk_color` |
|---|---|---|
| < 5 % | Low | `#2ECC71` |
| 5 % – < 20 % | Moderate | `#F39C12` |
| ≥ 20 % | High | `#E74C3C` |

**Facts you'll need:**
- One patch = 128 × 128 pixels × 10 m = **1.28 km × 1.28 km** on the ground (1.6384 km²).
- The API **doesn't return a date, coordinates or region**. For the popup, use your own pin coordinates and `new Date()`.
- Each request takes about **0.25–0.4 s** on Member 2's laptop. Over Wi-Fi, allow ~1 s. Show a spinner anyway.

### `GET /health`
`{"status":"ok","db":"ok"}`. If MySQL is down you still get **200** but `"db":"error"`; uploads will then fail (see §3, 500).

---

## 3. Errors

Every handled error has the **same shape**, and `error` is a short message that's safe to show the user as is:
```json
{"status": "error", "error": "Invalid file: not an HDF5 file"}
```

| HTTP | Exact `error` text | When |
|---|---|---|
| 400 | `Invalid file: not an HDF5 file` | Not an HDF5 file, e.g. a `.txt` renamed to `.h5`. |
| 400 | `Invalid file: missing 'img' dataset` | HDF5 without an `img` dataset, e.g. Member 1's *processed* `*_proc.h5` files (they hold `img17`). |
| 400 | `Invalid format: expected shape (128, 128, 14), got (…)` | Wrong size or band count. |
| 400 | `Invalid file: contains NaN or infinite values` | Corrupt pixel values. |
| 400 | `Excessive cloud cover` | Cirrus band mean > 2.5 (too cloudy to analyse). |
| 400 | `file: Field required` | No `file` field in the form. |
| 400 | `latitude: Input should be less than or equal to 90` | Out-of-range coordinate. The same pattern applies to `longitude` and `greater than or equal to`. |
| 400 | `latitude: Input should be a valid number, unable to parse string as a number` | Non-numeric coordinate (e.g. empty text typed into the field; just don't append empty fields). |
| 400 | `region_name: String should have at most 100 characters` | Region name too long. |
| 413 | `File too large: max 5 MB` | File over 5 MB. |
| 429 | `Rate limit exceeded: 10 requests/minute` | More than 10 uploads in 60 s from the same computer. Wait a minute. |
| 500 | *(no JSON, see below)* | Server-side failure, e.g. MySQL not running. |

**About 500s:** unexpected server errors come back **without CORS headers**, so the browser hides the response and `fetch()` **throws a `TypeError: Failed to fetch`**, exactly as if the server were off. Treat a thrown `fetch` as *"Can't reach the server, please try again later."*

**Nothing is saved to the database when a request fails.**

### Recommended API helper (`src/api.js`)
```js
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const MAX_BYTES = 5 * 1024 * 1024;

/** Upload an .h5 patch. Resolves with the success JSON, throws Error(message) otherwise. */
export async function predict(file, { regionName, lat, lng } = {}) {
  // Same checks as the server, done first so the user gets instant feedback
  if (!file) throw new Error('Please choose a .h5 file.');
  if (!file.name.toLowerCase().endsWith('.h5')) throw new Error('Only .h5 files are supported.');
  if (file.size > MAX_BYTES) throw new Error('File too large: max 5 MB');

  const form = new FormData();
  form.append('file', file);
  if (regionName?.trim()) form.append('region_name', regionName.trim().slice(0, 100));
  if (lat != null && lng != null) {
    form.append('latitude', String(lat));
    form.append('longitude', String(lng));
  }

  let res;
  try {
    res = await fetch(`${API_URL}/api/predict`, { method: 'POST', body: form }); // no Content-Type header!
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }

  let body;
  try {
    body = await res.json();
  } catch {
    throw new Error(`Server error (${res.status}). Please try again.`);
  }
  if (!res.ok || body.status !== 'success') {
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return body;
}

export const pngUrl = (b64) => `data:image/png;base64,${b64}`;
```

---

## 4. Showing the result on the map

### Where to put the overlay
The `.h5` file **contains no coordinates**. The backend can't tell where on Earth the patch is, so **you place it**: centre a **1.28 km × 1.28 km** square, north-up, on the user's pin (or on the known coordinates of a sample, see §6). It's an approximate placement; say so in the UI ("Approximate footprint").

```js
/** Square of ±640 m around a point → bounds in degrees. */
export function patchBounds(lat, lng, halfSizeM = 640) {
  const dLat = halfSizeM / 111320;                                      // metres per degree of latitude
  const dLng = halfSizeM / (111320 * Math.cos((lat * Math.PI) / 180));  // shrinks toward the poles
  return { north: lat + dLat, south: lat - dLat, east: lng + dLng, west: lng - dLng };
}
```

Draw **two layers**: the RGB preview first, then the mask on top (the mask is transparent where there's no landslide).

### If you use Mapbox GL JS
```js
import { pngUrl } from './api';
import { patchBounds } from './geo';

export function showPrediction(map, result, lat, lng) {
  const b = patchBounds(lat, lng);
  // Mapbox image corners: top-left, top-right, bottom-right, bottom-left, each [lng, lat]
  const coordinates = [[b.west, b.north], [b.east, b.north], [b.east, b.south], [b.west, b.south]];

  for (const id of ['l4s-mask', 'l4s-rgb']) {             // remove the previous result
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  }
  map.addSource('l4s-rgb',  { type: 'image', url: pngUrl(result.rgb_preview_b64),  coordinates });
  map.addSource('l4s-mask', { type: 'image', url: pngUrl(result.mask_overlay_b64), coordinates });
  map.addLayer({ id: 'l4s-rgb',  type: 'raster', source: 'l4s-rgb',
                 paint: { 'raster-opacity': 0.9, 'raster-resampling': 'nearest' } });
  map.addLayer({ id: 'l4s-mask', type: 'raster', source: 'l4s-mask',
                 paint: { 'raster-opacity': 1.0, 'raster-resampling': 'nearest' } });

  map.fitBounds([[b.west, b.south], [b.east, b.north]], { padding: 80 });
}
// Opacity slider: map.setPaintProperty('l4s-mask', 'raster-opacity', value)
// Toggle: map.setLayoutProperty('l4s-mask', 'visibility', on ? 'visible' : 'none')
```

### If you use Leaflet
```js
import L from 'leaflet';
import { pngUrl } from './api';
import { patchBounds } from './geo';

let rgbLayer, maskLayer;
export function showPrediction(map, result, lat, lng) {
  const b = patchBounds(lat, lng);
  const bounds = [[b.south, b.west], [b.north, b.east]];   // Leaflet: [[lat, lng], [lat, lng]]
  rgbLayer?.remove();
  maskLayer?.remove();
  rgbLayer  = L.imageOverlay(pngUrl(result.rgb_preview_b64),  bounds, { opacity: 0.9 }).addTo(map);
  maskLayer = L.imageOverlay(pngUrl(result.mask_overlay_b64), bounds, { opacity: 1.0 }).addTo(map);
  map.fitBounds(bounds);
}
// Opacity slider: maskLayer.setOpacity(value)
```
```css
/* 128×128 images get blurry when stretched; keep pixels crisp */
.leaflet-image-layer { image-rendering: pixelated; }
```

### Popup / side panel content
These cover the feature list's "popup shows risk level, affected area, coordinates, date" and "RGB preview + mask inside the popup":
```html
<div class="l4s-popup">
  <span class="badge" style="background: ${r.risk_color}">${r.risk_level} risk</span>
  <div class="thumb">                                      <!-- stack mask over preview -->
    <img src="${pngUrl(r.rgb_preview_b64)}"  alt="Satellite preview of the uploaded patch">
    <img src="${pngUrl(r.mask_overlay_b64)}" alt="Detected landslide pixels in red">
  </div>
  <dl>
    <dt>Landslide area</dt><dd>${r.landslide_area_m2.toLocaleString()} m² (${r.landslide_pct}% of patch)</dd>
    <dt>Coordinates</dt><dd>${lat.toFixed(5)}, ${lng.toFixed(5)}</dd>
    <dt>Analysed</dt><dd>${new Date().toLocaleString()}</dd>
    <dt>Reference</dt><dd>${r.patch_id}</dd>
  </dl>
</div>
```
```css
.l4s-popup .thumb { position: relative; width: 192px; height: 192px; }
.l4s-popup .thumb img { position: absolute; inset: 0; width: 100%; height: 100%; image-rendering: pixelated; }
```
> If you build this as an HTML string, escape any user-typed text (e.g. `region_name`) before inserting it. Values from the API are numbers or fixed strings and are safe.

### Legend (bottom right)
Use the same three colours as the API: Low `#2ECC71`, Moderate `#F39C12`, High `#E74C3C`, plus "Detected landslide" in red (`rgba(255,0,0,0.7)`).

---

## 5. Suggested upload flow + UX checklist

1. User drops a pin, or searches a place → you have `lat`, `lng` (+ maybe `region_name`).
2. User picks a `.h5` file (file input with `accept=".h5"` or drag-and-drop).
3. Check it on your side (extension, ≤ 5 MB), then call `predict()`.
4. While waiting: disable the button, show a spinner.
5. Success → `showPrediction(...)`, open the popup or panel, fly to the patch.
6. Error → show `error.message` in a toast or inline (it's already user-friendly). Keep the previous result on the map.

**Checklist**
- [ ] Upload button disabled while a request is running (prevents double submits and hitting the 429 limit).
- [ ] Don't send a pin that hasn't been set: either require a pin first, or allow "no location" and centre the overlay on the current map view.
- [ ] "No landslide detected" state when `landslide_pixels === 0` (the mask image is fully transparent, which is correct, not a bug).
- [ ] Label `rf_confidence` as a secondary model score, not "confidence of this result".
- [ ] Error messages shown as returned; `Failed to fetch` mapped to "server unreachable".
- [ ] Images have `alt` text; the risk badge also shows the word (Low/Moderate/High), not colour alone.

### Mock mode
Build everything without the backend, then flip one variable:
```js
// src/api.js (add at the top of predict())
import mockResult from './mocks/sample_response_moderate.json';
if (import.meta.env.VITE_USE_MOCK === 'true') {
  return new Promise((resolve) => setTimeout(() => resolve(mockResult), 600)); // fake latency
}
```
Copy `handoff/member3/sample_response_moderate.json` into `src/mocks/`. To preview **High** risk styling, make a copy and change `risk_level` to `"High"`, `risk_color` to `"#E74C3C"` and `landslide_pct` to e.g. `23.5`. **No real sample file produces High**, so this is the only way to show it. (Images stay the same; that's fine for UI work.)

---

## 6. Test files and what they return

Results captured from the real API on 2026-11-10:

| File | Result | Known location (use as the pin) |
|---|---|---|
| `handoff/member3/sample_patches/sample_patch_2.h5` | ✅ **Moderate**, 5.73 %, 938 px, red mask visible | unknown, pick any point (e.g. Benguet 16.40, 120.60) |
| `handoff/member3/sample_patches/sample_patch_1.h5` | ✅ Low, 2.33 %, 381 px | unknown |
| `handoff/member3/sample_patches/sample_patch_5.h5` | ✅ Low, 0.65 %, 107 px | unknown |
| `backend/tests/fixtures/unet/luzon_0150_r1920_c2304.h5` | ✅ Low, 0 %, **empty mask** | Aurora · **15.731791, 121.632743** |
| `backend/tests/fixtures/unet/luzon_0155_r1536_c2048.h5` | ✅ Low, 0 %, empty mask | Mountain Province · **17.116275, 121.609746** |
| `handoff/member3/sample_patches/invalid_processed_patch.h5` | ❌ 400 `Invalid file: missing 'img' dataset` | — |
| any `.txt` renamed to `.h5` | ❌ 400 `Invalid file: not an HDF5 file` | — |

**Demo script suggestion:** (1) upload `sample_patch_2.h5` on a pin → orange Moderate result with red mask; (2) upload `luzon_0150…h5` at Aurora → Low, nothing detected; (3) upload `invalid_processed_patch.h5` → clean error message.

---

## 7. What the backend does NOT provide

These features from `landslide4sense_feature_list.md` have **no API**. Do them purely in the frontend, or leave them out:

| Feature | Status / suggestion |
|---|---|
| Login button / accounts | **No auth exists.** Hide the button or make it say "coming soon". |
| Pre-computed hazard zones (Low/Moderate/High layer) | No endpoint. Use a **static GeoJSON** bundled with the site. Member 1's export files in `backend/tests/fixtures/unet/*.json` have `area`, `lat`, `lon`, `risk_level`, `risk_color` for 6 Luzon patches and can seed it. |
| Upload history / dashboard | Uploads are logged in MySQL but there is **no read endpoint**. Keep a "recent results" list in the browser (`localStorage`) if needed. |
| Place search, suggestions, geocoding | Use your map library's geocoder (Mapbox Geocoding) or Nominatim. |
| Province / municipality boundaries | Static GeoJSON (e.g. from PSA/NAMRIA or GADM). |
| Current location | Browser `navigator.geolocation`, no backend needed. |

If any of these must come from the backend, tell Member 2 early; each is a new endpoint.

---

## 8. Model facts for an About/Info panel

From Member 1's evaluation (Step 8, test set):

| Model | Role | F1 | ROC-AUC | IoU | Precision | Recall |
|---|---|---|---|---|---|---|
| **U-Net** | Produces the mask + risk level | 0.7178 | 0.9945 | 0.5599 | 0.6069 | 0.8785 |
| Random Forest | Second opinion (`rf_confidence`) | 0.7929 | 0.9814 | 0.6568 | 0.7356 | 0.8599 |

- Input: Sentinel-2 patch, 14 bands (incl. slope/DEM), 128 × 128 px at 10 m. The backend adds NDVI, NDWI and BSI → 17 features.
- U-Net marks a pixel as landslide when its probability > **0.8461** (Member 1's tuned threshold).
- Uploads that are too cloudy are rejected (Cirrus band check).

---

## 9. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Browser console: *"blocked by CORS policy"* | Your page address isn't on the allowed list. The API allows only `http://localhost:5173`. `http://127.0.0.1:5173`, port `5174`, or a LAN address count as **different** origins. Fix: open the site at `http://localhost:5173`, **or** ask Member 2 to add your origin to `CORS_ORIGINS` in `backend/.env` (comma-separated) and restart the server. |
| `TypeError: Failed to fetch` | Server off, wrong `VITE_API_URL`, firewall blocking (Option A), or a 500 (e.g. MySQL down). Open `{API_URL}/health` in the browser to see which. |
| `/health` shows `"db":"error"` | MySQL isn't running on the server machine. Start the `MySQL80` Windows service. |
| 429 while testing | You sent more than 10 uploads in a minute. Wait 60 s. The limit resets when the server restarts. |
| 400 `latitude: …` with an empty input | You appended an empty string. Only append coordinates when both are set. |
| 400 `file: Field required` | The form field must be named exactly `file`. |
| Changed `VITE_API_URL` but nothing changed | Restart `npm run dev`; Vite reads `.env*` files only at startup. |
| Overlay is in the wrong place | Mapbox wants `[lng, lat]`, Leaflet wants `[lat, lng]`. Check the order. |
| Overlay looks blurry | Add `raster-resampling: 'nearest'` (Mapbox) or `image-rendering: pixelated` (Leaflet/`<img>`). |
| Server takes long to start (Option B) | Normal: the 512 MB Random Forest loads at startup (~10–15 s, ~1.5 GB RAM). A `MemoryError` means not enough free RAM. Close other apps. |

---

## 10. Open items

- **Map library:** Mapbox GL JS (feature list) vs Leaflet (earlier plan) is still undecided. This guide covers both, and the API is the same either way. Mapbox needs a free access token; Leaflet doesn't.
- **Extra cloud check (Band 1):** waiting on Member 1's threshold. When added, it may reject a few more cloudy uploads with a new 400 message. Your error display needs no change.
- **Cloud hosting:** not planned for the demo. The demo runs on Member 2's laptop (Option A), or everything on one laptop.
- **Questions / new endpoints:** ask Member 2. The full backend spec is in `PROJECT_PLAN.md` §3 (endpoint contract).
