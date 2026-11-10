from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import logging

from app import config, db
from app.routers import auth, predict
from app.services.inference import load_rf, load_unet
from app.services.preprocess import load_stats

log = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"



@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models_loaded = False

    try:
        app.state.mean, app.state.std = load_stats(MODELS_DIR)
        app.state.rf = load_rf(MODELS_DIR)
        app.state.unet = load_unet(MODELS_DIR)

        app.state.models_loaded = True
        log.info("Models loaded successfully")

    except FileNotFoundError as e:
        log.warning("Model files missing. Prediction is disabled: %s", e)

    yield



app = FastAPI(title="Landslide4Sense API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    # one error shape for the frontend: {"status":"error","error":...}
    return JSONResponse({"status": "error", "error": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # bad/missing form fields → same 400 error shape instead of FastAPI's 422
    e = exc.errors()[0]
    return JSONResponse({"status": "error", "error": f"{e['loc'][-1]}: {e['msg']}"}, status_code=400)


app.include_router(auth.router)
app.include_router(predict.router)


@app.get("/health")
def health():
    try:
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        db_status = "ok"
    except Exception as e:
        log.warning("health: db check failed: %s", e)  # details stay in the server log, not the response
        db_status = "error"
    return {"status": "ok", "db": db_status}
