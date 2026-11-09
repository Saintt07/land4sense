-- Run as root. Creates the Landslide4Sense star-schema data mart.
CREATE DATABASE IF NOT EXISTS landslide4sense
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE landslide4sense;

CREATE TABLE IF NOT EXISTS dim_time (
  time_id     INT      NOT NULL PRIMARY KEY,          -- YYYYMMDD
  full_date   DATE     NOT NULL UNIQUE,
  year        SMALLINT NOT NULL,
  quarter     TINYINT  NOT NULL,
  month       TINYINT  NOT NULL,
  day         TINYINT  NOT NULL,
  day_of_week TINYINT  NOT NULL                       -- 1=Mon .. 7=Sun
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_location (
  location_id INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
  region_name VARCHAR(100) NOT NULL,
  latitude    DECIMAL(9,6) NULL,
  longitude   DECIMAL(9,6) NULL,
  UNIQUE KEY uq_location (region_name, latitude, longitude)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_model (
  model_id      INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
  model_name    VARCHAR(50)  NOT NULL,
  model_type    VARCHAR(30)  NOT NULL,
  version       VARCHAR(20)  NOT NULL,
  artifact_file VARCHAR(255) NOT NULL,
  f1_score      DECIMAL(5,4) NULL,
  roc_auc       DECIMAL(5,4) NULL,
  iou           DECIMAL(5,4) NULL,
  UNIQUE KEY uq_model (model_name, version)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fact_landslide_detections (
  detection_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  time_id           INT             NOT NULL,
  location_id       INT             NOT NULL,
  model_id          INT             NOT NULL,
  patch_id          VARCHAR(64)     NOT NULL,
  file_name         VARCHAR(255)    NOT NULL,
  client_ip         VARCHAR(45)     NOT NULL,
  landslide_pixels  INT UNSIGNED    NOT NULL,
  landslide_area_m2 INT UNSIGNED    NOT NULL,
  landslide_pct     DECIMAL(5,2)    NOT NULL,
  risk_level        ENUM('Low','Moderate','High') NOT NULL,
  rf_confidence     DECIMAL(5,4)    NOT NULL,
  mean_ndvi         DECIMAL(6,4)    NOT NULL,
  mean_slope        DECIMAL(8,4)    NOT NULL,
  cirrus_mean       DECIMAL(8,4)    NOT NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_fact_time     FOREIGN KEY (time_id)     REFERENCES dim_time(time_id)         ON DELETE RESTRICT,
  CONSTRAINT fk_fact_location FOREIGN KEY (location_id) REFERENCES dim_location(location_id) ON DELETE RESTRICT,
  CONSTRAINT fk_fact_model    FOREIGN KEY (model_id)    REFERENCES dim_model(model_id)       ON DELETE RESTRICT
) ENGINE=InnoDB;
