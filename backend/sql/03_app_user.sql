-- Run as root after 02_seed.sql.
-- Replace CHANGE_ME with the same value as DB_PASSWORD in backend/.env (never commit the real password).
CREATE USER IF NOT EXISTS 'l4s_app'@'localhost' IDENTIFIED BY 'CHANGE_ME';

-- Read everything; insert only into the tables /api/predict writes. No UPDATE/DELETE/DDL.
GRANT SELECT ON landslide4sense.* TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.fact_landslide_detections TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.dim_time     TO 'l4s_app'@'localhost';
GRANT INSERT ON landslide4sense.dim_location TO 'l4s_app'@'localhost';
FLUSH PRIVILEGES;
