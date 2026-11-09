-- Run as root after 01_schema.sql. Safe to re-run.
USE landslide4sense;

INSERT IGNORE INTO dim_model (model_name, model_type, version, artifact_file) VALUES
  ('U-Net',         'segmentation',     'v1', 'unet_landslide.pth'),
  ('Random Forest', 'pixel-classifier', 'v1', 'rf_landslide_model.joblib');

-- Step 8 test-set metrics from Member 1 (handoff_member2/model_evaluation_metrics.md)
UPDATE dim_model SET f1_score = 0.7178, roc_auc = 0.9945, iou = 0.5599
  WHERE model_name = 'U-Net' AND version = 'v1';
UPDATE dim_model SET f1_score = 0.7929, roc_auc = 0.9814, iou = 0.6568
  WHERE model_name = 'Random Forest' AND version = 'v1';

-- location_id 1 = fallback when the upload has no region/coordinates
INSERT IGNORE INTO dim_location (location_id, region_name, latitude, longitude)
VALUES (1, 'Unknown', NULL, NULL);
