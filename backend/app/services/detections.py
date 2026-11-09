"""Log one prediction into the star schema (parameterized SQL, runs as l4s_app)."""
from datetime import date

UNKNOWN_LOCATION_ID = 1  # seeded in 02_seed.sql


def _time_id(cur, today: date) -> int:
    tid = int(today.strftime("%Y%m%d"))
    cur.execute(
        "INSERT IGNORE INTO dim_time (time_id, full_date, year, quarter, month, day, day_of_week) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (tid, today, today.year, (today.month - 1) // 3 + 1, today.month, today.day, today.isoweekday()),
    )
    return tid


def _location_id(cur, region_name: str | None, latitude: float | None, longitude: float | None) -> int:
    region = (region_name or "").strip() or "Unknown"
    if region == "Unknown" and latitude is None and longitude is None:
        return UNKNOWN_LOCATION_ID
    lat = None if latitude is None else round(latitude, 6)
    lon = None if longitude is None else round(longitude, 6)
    # <=> is NULL-safe: the UNIQUE key alone doesn't dedupe rows with NULL coordinates
    cur.execute(
        "SELECT location_id FROM dim_location WHERE region_name = %s AND latitude <=> %s AND longitude <=> %s",
        (region, lat, lon),
    )
    row = cur.fetchone()
    if row:
        return row["location_id"]
    cur.execute("INSERT INTO dim_location (region_name, latitude, longitude) VALUES (%s, %s, %s)", (region, lat, lon))
    return cur.lastrowid


def log_detection(conn, *, region_name, latitude, longitude, patch_id, file_name, client_ip,
                  stats: dict, rf_conf: float, mean_ndvi: float, mean_slope: float, cirrus: float) -> int:
    """Insert dims as needed + one fact row; caller (db.get_db) commits. Returns detection_id."""
    with conn.cursor() as cur:
        time_id = _time_id(cur, date.today())
        location_id = _location_id(cur, region_name, latitude, longitude)
        cur.execute("SELECT model_id FROM dim_model WHERE model_name = 'U-Net' AND version = 'v1'")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("dim_model has no U-Net v1 row; run sql/02_seed.sql")
        cur.execute(
            "INSERT INTO fact_landslide_detections (time_id, location_id, model_id, patch_id, file_name, client_ip, "
            "landslide_pixels, landslide_area_m2, landslide_pct, risk_level, rf_confidence, mean_ndvi, mean_slope, "
            "cirrus_mean) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (time_id, location_id, row["model_id"], patch_id, file_name, client_ip,
             stats["landslide_pixels"], stats["landslide_area_m2"], stats["landslide_pct"], stats["risk_level"],
             round(rf_conf, 4), round(mean_ndvi, 4), round(mean_slope, 4), round(cirrus, 4)),
        )
        return cur.lastrowid
