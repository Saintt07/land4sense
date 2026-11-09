# Message to Member 1 — Remaining Backend Questions (2026-11-09)

Hi! Thanks for the sample patches, the demo pipeline, and the U-Net threshold (0.8461). Quick update, then the few things I still need.

## What I already confirmed from your files
- Your U-Net class loads `unet_landslide.pth` with `strict=True` and matches your export JSONs on **24/24** processed patches (same `landslide_pixels` at 0.8461 and same `unet_max_prob`).
- `processed_patches/*_proc.h5` holds **normalized** `img17`. My raw → indices → normalize pipeline matches it to within 2e-6, and 7/7 raw patches give your exact pixel counts end to end.

So the U-Net side is working. Here's what's left, most urgent first:

## Can the RF model be smaller?
The "light" RF file is still 1.56 GB. It takes about 1.5 GB of RAM, and today it failed to load on my laptop with a `MemoryError`. Free hosting usually gives 512 MB–1 GB. Could you retrain with fewer or shallower trees (e.g. `n_estimators=50, max_depth=15`), or save it compressed (`joblib.dump(rf, path, compress=3)`)? Is a small drop in accuracy acceptable?

---

Not urgent. Thanks!
