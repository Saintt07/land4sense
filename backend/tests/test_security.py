from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import security
from app.main import app, http_error

# no `with TestClient(...)`: the lifespan (RF load, ~1.5 GB RAM) never runs


def _limited_client():
    mini = FastAPI()
    mini.add_exception_handler(HTTPException, http_error)

    @mini.post("/limited", dependencies=[Depends(security.rate_limit)])
    def limited():
        return {"status": "ok"}

    return TestClient(mini)


def test_rate_limit_11th_request_429_then_window_expires(monkeypatch):
    security._hits.clear()
    now = [1000.0]
    monkeypatch.setattr(security.time, "monotonic", lambda: now[0])
    client = _limited_client()

    for _ in range(10):
        assert client.post("/limited").status_code == 200
    r = client.post("/limited")
    assert r.status_code == 429
    assert r.json() == {"status": "error", "error": "Rate limit exceeded: 10 requests/minute"}

    now[0] += 61
    assert client.post("/limited").status_code == 200
    assert len(security._hits["testclient"]) == 1  # expired timestamps pruned


def test_cors_blocks_unlisted_origin():
    r = TestClient(app).get("/health", headers={"Origin": "http://evil.com"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_allows_whitelisted_origin():
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    pre = client.options(
        "/api/predict",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == "http://localhost:5173"
