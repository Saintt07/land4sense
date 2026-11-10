LANDSLIDE4SENSE - UPDATED LEAFLET PROTOTYPE

WHAT CHANGED
- Uses each GeoJSON feature's risk_color property for polygon styling.
- Uses different opacity levels: Low 20%, Moderate 60%, High 75% (multiplied by the overlay slider).
- Feature details and map popups now show affected area in m2 and hectares, landslide pixels, patch coverage, RF confidence, RF pixels, coordinates, and source tile.
- Includes a selectable local Metro Manila Sentinel-2 tile layer. Esri satellite and OSM street layers remain available as alternatives.
- Keeps the existing Leaflet map; no Mapbox token or backend is required for this static prototype.

GEOJSON
The supplied data file is in data/ph_4areas_hazard.geojson. It contains 21,689 features and metadata for Benguet, Mountain Province, Metro Manila, and Aurora.

ADD YOUR LOCAL METRO MANILA TILES
1. Open your generated tiles_fixed folder on your computer.
2. Copy its zoom folders (8, 9, ... 15) into this project's tiles/metro_manila/ folder.
3. The final structure should be tiles/metro_manila/8/x/y.png, etc.
4. Run the website through a local HTTP server, not by opening index.html with file://.
5. In the Leaflet layer selector, choose 'Metro Manila (local Sentinel-2)'. This local layer only has coverage around Metro Manila.

RUN LOCALLY
From this project folder, run: python -m http.server 8000
Then open: http://localhost:8000

NOTES
- Local Sentinel-2 tiles are not included because they are generated on your computer and are not available in this workspace.
- The local tile layer is a separate selectable base layer, so it does not obscure the GeoJSON hazard overlay.
- This prototype presents pre-computed predictions; it does not run the AI models in the browser.
