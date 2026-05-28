"""흑석동 focus map v8: Self-consistency + 학습 가중치 TOP 비교."""
import json
import folium
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from src.grid import build_grid
from src.scoring import compute_scores
from src.filtering import (_filter_by_pedestrian, _filter_by_buildings,
                              _filter_by_focus_proximity)
from src.config import FILTER, CRS_WGS84
from src import data_loader

boundary = gpd.read_file("data/raw/heukseok/ngii_data/흑석동_경계5186.shp").to_crs("EPSG:4326")
bld = gpd.read_file("data/raw/heukseok/ngii_data/흑석동_건물5186.shp").to_crs("EPSG:4326")
inter = gpd.read_file("data/processed/osm_intersections.geojson").to_crs("EPSG:4326")
edges = gpd.read_file("data/processed/osm_walkable_edges.geojson").to_crs("EPSG:4326")
crossings = gpd.read_file("data/processed/osm_crossings.geojson").to_crs("EPSG:4326")
shades = data_loader.load_existing_shades()
consistency = pd.read_csv("data/processed/grid_heukseok_consistency.csv")
W_TUNED = json.load(open("output/weights_tuned.json", encoding="utf-8"))["weights_tuned"]

grid = build_grid()
scored = compute_scores(grid)
g = scored.to_crs(CRS_WGS84).sort_values("score", ascending=False)
g = _filter_by_pedestrian(g, buffer_m=10.0, min_width=FILTER["min_sidewalk_width_m"])
g = _filter_by_buildings(g, inset_m=5.0)
g = _filter_by_focus_proximity(g, max_dist_m=80.0)
filtered = g.reset_index(drop=True).to_crs("EPSG:4326")
b_geom = boundary.iloc[0].geometry
hk_filt = filtered[filtered.geometry.centroid.within(b_geom)]
top_manual = hk_filt.nlargest(min(10, len(hk_filt)), 'score').reset_index(drop=True)

# 학습 가중치 score
def _minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo + 1e-9)
sv_col = hk_filt["sv_deficit"] if "sv_deficit" in hk_filt.columns else pd.Series(
    np.zeros(len(hk_filt)), index=hk_filt.index)
in_col = hk_filt["inter_density"] if "inter_density" in hk_filt.columns else pd.Series(
    np.zeros(len(hk_filt)), index=hk_filt.index)
nrm = pd.DataFrame({
    "popdens": _minmax(hk_filt["pop"]), "lst": _minmax(hk_filt["lst_c"]),
    "vuln": _minmax(hk_filt["vuln_ratio"]), "shade": _minmax(hk_filt["shade_cov"]),
    "natural": _minmax(hk_filt["natural"]),
    "sv": _minmax(sv_col), "inter": _minmax(in_col),
})
hk_tuned = hk_filt.copy()
hk_tuned["score_tuned"] = (
    W_TUNED["popdens"] * nrm["popdens"].values
    + W_TUNED["lst"] * nrm["lst"].values
    + W_TUNED["vuln"] * nrm["vuln"].values
    + W_TUNED["shade"] * nrm["shade"].values
    + W_TUNED["natural"] * nrm["natural"].values
    + W_TUNED["streetview_deficit"] * nrm["sv"].values
    + W_TUNED["intersection_density"] * nrm["inter"].values
)
top_tuned = hk_tuned.nlargest(min(10, len(hk_tuned)), 'score_tuned').reset_index(drop=True)

# 실측 그늘막 최단거리
shades_proj = shades.to_crs("EPSG:5179")
def nearest(top):
    proj = top.to_crs("EPSG:5179")
    return [round(float(shades_proj.geometry.distance(r.geometry.centroid).min()), 1)
            for _, r in proj.iterrows()]
top_manual['nearest_shade_m'] = nearest(top_manual)
top_tuned['nearest_shade_m'] = nearest(top_tuned)

# 지도
cen = [(b_geom.bounds[1]+b_geom.bounds[3])/2, (b_geom.bounds[0]+b_geom.bounds[2])/2]
m = folium.Map(location=cen, zoom_start=15, tiles="CartoDB positron")
folium.GeoJson(boundary.__geo_interface__, name="흑석동 경계",
    style_function=lambda f: {"color":"#1565c0","weight":3,"fillColor":"#1565c0","fillOpacity":0.05}).add_to(m)

fg = folium.FeatureGroup(name="OSMnx 보행 도로", show=True)
for _, r in edges[edges.geometry.intersects(b_geom)].iterrows():
    folium.PolyLine([(la,lo) for lo,la in r.geometry.coords],
        color="#00897b", weight=2, opacity=0.55).add_to(fg)
fg.add_to(m)

fg = folium.FeatureGroup(name=f"NGII 건물 {len(bld)}", show=True)
def bc(n):
    if n>=15: return "#b71c1c"
    if n>=10: return "#e53935"
    if n>=5: return "#fb8c00"
    if n>=3: return "#43a047"
    return "#90a4ae"
for _, r in bld.iterrows():
    folium.GeoJson(r.geometry.__geo_interface__,
        style_function=lambda f,c=bc(r['NMLY']):{"fillColor":c,"color":c,"weight":0.3,"fillOpacity":0.5},
        tooltip=f"{int(r['NMLY'])}층 {r['HEGT']:.1f}m").add_to(fg)
fg.add_to(m)

fg = folium.FeatureGroup(name="교차로", show=False)
for _, r in inter[inter.geometry.within(b_geom)].iterrows():
    folium.CircleMarker([r.geometry.y, r.geometry.x], radius=4,
        color="#00838f", fill=True, fillColor="#00838f", fillOpacity=0.85, weight=1).add_to(fg)
fg.add_to(m)
fg = folium.FeatureGroup(name="횡단보도", show=False)
for _, r in crossings[crossings.geometry.within(b_geom)].iterrows():
    folium.CircleMarker([r.geometry.y, r.geometry.x], radius=6,
        color="#f57f17", fill=True, fillColor="#ffeb3b", fillOpacity=0.95, weight=2).add_to(fg)
fg.add_to(m)

hk_shades = shades[shades.geometry.within(b_geom)]
fg = folium.FeatureGroup(name=f"기존 그늘막 {len(hk_shades)}", show=True)
for _, r in hk_shades.iterrows():
    ic = "darkblue" if r.get('type')=="스마트형" else "black"
    folium.Marker([r.geometry.y, r.geometry.x],
        icon=folium.Icon(color=ic, icon="umbrella", prefix="fa"),
        popup=folium.Popup(
            f"<b>{r.get('type','?')}</b><br>{r.get('location','?')}<br>"
            f"{r.get('address','?')}<br>설치일: {r.get('installed','?')}",
            max_width=240)).add_to(fg)
fg.add_to(m)

# 수동 TOP
fg_m = folium.FeatureGroup(name=f"수동 가중치 TOP {len(top_manual)}", show=True)
for i, (_, r) in enumerate(top_manual.iterrows(), 1):
    is_blind = r['nearest_shade_m'] > 150
    is_close = r['nearest_shade_m'] < 60
    color = "#d81b60" if is_blind else ("#7e57c2" if is_close else "#e91e63")
    folium.CircleMarker([r['lat'], r['lon']], radius=18-i*0.7, color=color, fill=True,
        fillColor=color, fillOpacity=0.85, weight=3,
        popup=folium.Popup(
            f"<b>수동 TOP {i}</b> score={r['score']:+.3f}<br>"
            f"가까운 그늘막: <b>{r['nearest_shade_m']}m</b>",
            max_width=260),
        tooltip=f"수동 TOP{i} {r['score']:+.2f}").add_to(fg_m)
fg_m.add_to(m)

# 학습 TOP (별 모양)
fg_t = folium.FeatureGroup(name=f"학습(BayesOpt) 가중치 TOP {len(top_tuned)}", show=True)
for i, (_, r) in enumerate(top_tuned.iterrows(), 1):
    folium.RegularPolygonMarker([r['lat'], r['lon']],
        number_of_sides=5, radius=12-i*0.5,
        color="#1565c0", fill=True, fill_color="#42a5f5", fill_opacity=0.9, weight=2.5,
        popup=folium.Popup(
            f"<b>학습 TOP {i}</b><br>"
            f"수동 score: {r['score']:+.3f}<br>"
            f"학습 score: {r['score_tuned']:+.3f}<br>"
            f"가까운 그늘막: {r['nearest_shade_m']}m",
            max_width=240),
        tooltip=f"학습 TOP{i} {r['score_tuned']:+.2f}").add_to(fg_t)
fg_t.add_to(m)

# 신뢰구간
fg_ci = folium.FeatureGroup(name="그림자 std (Self-consistency 5회)", show=False)
for _, r in consistency.dropna(subset=['shadow_std']).iterrows():
    if not b_geom.contains(Point(r['lon'], r['lat'])):
        continue
    opacity = min(1.0, float(r['shadow_std']) * 20)
    folium.CircleMarker([r['lat'], r['lon']], radius=3,
        color="#8e24aa", fill=True, fillColor="#8e24aa", fillOpacity=opacity, weight=1,
        tooltip=f"mean {r['shadow_mean']:.3f} ± {2*r['shadow_std']:.3f}").add_to(fg_ci)
fg_ci.add_to(m)

legend = """
<div style="position:fixed;bottom:30px;left:30px;z-index:9999;
            background:white;padding:10px 14px;border-radius:6px;
            box-shadow:0 2px 8px rgba(0,0,0,0.2);font-size:12px;
            font-family:'Malgun Gothic',sans-serif;max-width:440px;">
  <b>흑석동 v8 — Self-consistency + 학습 가중치 비교</b><br>
  <span style="display:inline-block;width:14px;height:14px;background:#d81b60;border-radius:50%;"></span>
  수동 가중치 TOP10 <br>
  <span style="color:#1565c0;font-size:18px;">★</span>
  학습 가중치 TOP10 (BayesOpt, n=60, 실측 그늘막 18개 역-라벨)<br>
  <span style="color:#000;">⛱</span> 기존 그늘막 18개<br>
  <span style="display:inline-block;width:10px;height:10px;background:#8e24aa;border-radius:50%;"></span>
  그림자 표준편차 (Self-consistency 5회 · 진할수록 변동 큼)<br>
  <small>학습 결과: shade -0.15→-0.30, natural -0.05→-0.18 (페널티 강화)<br>
  실측위치 평균 score: 0.087→-0.122 (Δ -0.21, 가설 부합)</small>
</div>
"""
m.get_root().html.add_child(folium.Element(legend))
folium.LayerControl(collapsed=False).add_to(m)
m.save("output/heukseok_focus.html")
print(f"saved: output/heukseok_focus.html")
print(f"수동 TOP10 vs 학습 TOP10 vs 신뢰구간 309격자")
