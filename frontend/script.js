const DATA_URL = "./data/ph_4areas_hazard.geojson";
const FALLBACK_COLORS = {Low:"#2ECC71", Moderate:"#F39C12", High:"#E74C3C"};
const RISK_OPACITY = {Low:0.20, Moderate:0.60, High:0.75};
const METRO_MANILA_BOUNDS = L.latLngBounds([[14.2899,120.8799],[14.8301,121.4201]]);
const DEFAULT_CENTER = [12.8, 122.8];
const DEFAULT_ZOOM = 5.2;

const map = L.map("map", {preferCanvas:true, zoomControl:false}).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
const philippinesBounds = L.latLngBounds(
  [4.0, 116.0],
  [21.5, 127.0]
);

map.setMaxBounds(philippinesBounds);
map.setMinZoom(5);
L.control.zoom({position:"topleft"}).addTo(map);

const streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);
const satelliteLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
  maxZoom:19, attribution:"Tiles &copy; Esri"
});
// Optional local Sentinel-2 tiles. Copy your generated tiles_fixed folder here:
// tiles/metro_manila/{z}/{x}/{y}.png
const metroManilaSatelliteLayer = L.tileLayer("./tiles/metro_manila/{z}/{x}/{y}.png", {
  minZoom:8, maxZoom:19, maxNativeZoom:15, tileSize:256, noWrap:true,
  bounds:METRO_MANILA_BOUNDS, opacity:1,
  attribution:"Sentinel-2 imagery processed by the project team"
});

let allFeatures = [];
let geoLayer = null;
let selectedLayer = null;
let activeArea = "All";
let visibleRisks = new Set(["Low","Moderate","High"]);
let overlayOpacity = 0.65;

const $ = id => document.getElementById(id);
const number = value => Number(value || 0).toLocaleString("en-PH");
const confidenceText = value => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "Not available";
  return `${(n <= 1 ? n * 100 : n).toFixed(1)}%`;
};

function featuresForCurrentArea() {
  return allFeatures.filter(f => {
    const p = f.properties || {};
    return (activeArea === "All" || p.area === activeArea) && visibleRisks.has(p.risk_level);
  });
}
function featureColor(feature) {
  const p = feature.properties || {};
  return p.risk_color || FALLBACK_COLORS[p.risk_level] || "#718078";
}
function styleFeature(feature) {
  const risk = feature.properties?.risk_level || "Low";
  return {
    color:featureColor(feature),
    weight:risk === "High" ? 0.8 : 0.35,
    opacity:0.9,
    fillColor:featureColor(feature),
    fillOpacity:overlayOpacity * (RISK_OPACITY[risk] ?? 0.2)
  };
}
function updateCounts() {
  const areaFeatures = allFeatures.filter(f => activeArea === "All" || f.properties?.area === activeArea);
  const counts = {Low:0,Moderate:0,High:0};
  areaFeatures.forEach(f => { const r=f.properties?.risk_level; if (counts[r] !== undefined) counts[r]++; });
  $("lowCount").textContent = number(counts.Low);
  $("moderateCount").textContent = number(counts.Moderate);
  $("highCount").textContent = number(counts.High);
  $("totalCount").textContent = number(areaFeatures.length);
  $("highMetric").textContent = number(counts.High);
  $("areaCount").textContent = activeArea === "All" ? new Set(allFeatures.map(f=>f.properties?.area)).size : "1";
  $("areaLabel").textContent = activeArea === "All" ? "All areas" : activeArea;
}
function renderLayer() {
  if (geoLayer) map.removeLayer(geoLayer);
  const filtered = featuresForCurrentArea();
  geoLayer = L.geoJSON({type:"FeatureCollection",features:filtered}, {
    style:styleFeature,
    onEachFeature:(feature,layer)=>{
      layer.on("click",()=>showFeature(feature,layer));
      layer.bindTooltip(`${feature.properties?.area || "Area"} · ${feature.properties?.risk_level || "Unclassified"}`, {sticky:true});
    }
  }).addTo(map);
  updateCounts();
  if (selectedLayer) { selectedLayer = null; clearFeature(); }
}
function showFeature(feature, layer) {
  if (selectedLayer && geoLayer) geoLayer.resetStyle(selectedLayer);
  selectedLayer = layer;
  const p = feature.properties || {};
  const risk = p.risk_level || "Unclassified";
  layer.setStyle({color:"#20332b",weight:2.2,fillOpacity:Math.min(1,overlayOpacity * (RISK_OPACITY[risk] ?? 0.2) + 0.18)});
  $("featureDetails").hidden = true;
  $("featureInfo").hidden = false;
  $("featureSwatch").className = `swatch ${risk.toLowerCase()}`;
  $("featureRisk").textContent = `${risk} hazard`;
  $("featureArea").textContent = p.area || "Not available";
  $("featurePixels").textContent = number(p.landslide_pixels);
  $("featurePct").textContent = `${Number(p.landslide_pct || 0).toFixed(4)}%`;
  $("featureConfidence").textContent = confidenceText(p.rf_confidence);
  $("featureAffectedArea").textContent = `${number(p.area_m2)} m² (${(Number(p.area_m2 || 0) / 10000).toFixed(2)} ha)`;
  $("featureCoords").textContent = `${Number(p.lat).toFixed(5)}, ${Number(p.lon).toFixed(5)}`;
  $("featureTile").textContent = p.tile || "Not available";
  const popup = `<div class="hazard-popup"><span class="popup-risk" style="color:${featureColor(feature)}">${risk} risk</span><br><b>${p.area || "Unknown area"}</b><hr><b>Affected area:</b> ${number(p.area_m2)} m² (${(Number(p.area_m2 || 0) / 10000).toFixed(2)} ha)<br><b>Landslide pixels:</b> ${number(p.landslide_pixels)}<br><b>Patch coverage:</b> ${Number(p.landslide_pct || 0).toFixed(2)}%<br><b>RF confidence:</b> ${confidenceText(p.rf_confidence)}<br><b>RF pixels:</b> ${number(p.rf_pixels)}<br><small>Center: ${Number(p.lat).toFixed(5)}, ${Number(p.lon).toFixed(5)}</small></div>`;
  layer.bindPopup(popup).openPopup();
}
function clearFeature() {
  $("featureDetails").hidden = false;
  $("featureInfo").hidden = true;
}
function areaBounds(area) {
  const selected = allFeatures.filter(f => area === "All" || f.properties?.area === area);
  if (!selected.length) return null;
  const bounds = L.latLngBounds([]);
  selected.forEach(f => {
    const lat = Number(f.properties?.lat), lon = Number(f.properties?.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon)) bounds.extend([lat,lon]);
    else if (f.geometry) {
      L.geoJSON(f).eachLayer(layer => bounds.extend(layer.getBounds()));
    }
  });
  return bounds.isValid() ? bounds : null;
}
function focusArea(area) {
  const bounds = areaBounds(area);
  if (bounds) map.fitBounds(bounds.pad(0.12), {maxZoom:11,animate:true});
}
function setArea(area) {
  activeArea = area;
  $("areaFilter").value = area;
  renderLayer();
  focusArea(area);
}
function showMessage(message, isError=false) {
  const box = $("loadMessage");
  box.textContent = message;
  box.classList.toggle("error",isError);
  box.hidden = false;
  if (!isError) setTimeout(()=>box.hidden=true,3500);
}

$("areaFilter").addEventListener("change",e=>setArea(e.target.value));
document.querySelectorAll(".risk-filter").forEach(input=>{
  input.addEventListener("change",()=>{
    if(input.checked) visibleRisks.add(input.value); else visibleRisks.delete(input.value);
    renderLayer();
  });
});
$("opacityRange").addEventListener("input",e=>{
  overlayOpacity=Number(e.target.value)/100;
  $("opacityValue").textContent=`${e.target.value}%`;
  if(geoLayer) geoLayer.setStyle(styleFeature);
});
$("searchForm").addEventListener("submit",e=>{
  e.preventDefault();
  const query=$("searchInput").value.trim().toLowerCase();
  if(!query) return;
  const areas=[...new Set(allFeatures.map(f=>f.properties?.area).filter(Boolean))];
  const match=areas.find(a=>a.toLowerCase()===query) || areas.find(a=>a.toLowerCase().includes(query));
  if(match) setArea(match);
  else showMessage("No matching area in the current test dataset.",true);
});
$("resetView").addEventListener("click",()=>{
  setArea("All");
  map.setView(DEFAULT_CENTER,DEFAULT_ZOOM);
});
$("locateMe").addEventListener("click",()=>{
  if(!navigator.geolocation){showMessage("Location is not supported by this browser.",true);return;}
  showMessage("Requesting location permission…");
  navigator.geolocation.getCurrentPosition(pos=>{
    map.flyTo([pos.coords.latitude,pos.coords.longitude],12);
    showMessage("Map centered on your current location.");
  },()=>showMessage("Location permission was not granted.",true),{enableHighAccuracy:true,timeout:10000});
});
$("panelToggle").addEventListener("click",()=>{
  const panel=$("sidePanel");
  const collapsed=panel.classList.toggle("collapsed");
  $("panelToggle").textContent=collapsed?"‹":"›";
  $("panelToggle").setAttribute("aria-label",collapsed?"Expand side panel":"Collapse side panel");
  setTimeout(()=>map.invalidateSize(),280);
});

const baseMaps = {"Street":streetLayer,"Satellite (Esri)":satelliteLayer,"Metro Manila (local Sentinel-2)":metroManilaSatelliteLayer};
L.control.layers(baseMaps, null, {position:"topleft",collapsed:true}).addTo(map);

fetch(DATA_URL)
  .then(response=>{if(!response.ok) throw new Error(`HTTP ${response.status}`); return response.json();})
  .then(data=>{
    if(data.type!=="FeatureCollection" || !Array.isArray(data.features)) throw new Error("The file is not a valid GeoJSON FeatureCollection.");
    allFeatures=data.features;
    const metadata = data.metadata || {};
    renderLayer();
    const declaredTotal = Number(metadata.total_patches || allFeatures.length);
    showMessage(`${number(allFeatures.length)} hazard patches loaded${declaredTotal !== allFeatures.length ? " (metadata count differs)" : ""}.`);
})
  .catch(error=>{
    console.error(error);
    showMessage("Could not load GeoJSON. Run this site through a local server (not file://).",true);
    $("totalCount").textContent="Load failed";
  });
