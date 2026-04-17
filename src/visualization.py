"""Folium 지도 시각화."""
from __future__ import annotations
import folium
from folium.plugins import HeatMap
import geopandas as gpd
import branca.colormap as cm
from .config import DONGJAK_CENTER, OUTPUT
from . import data_loader


def build_map(scored_grid: gpd.GeoDataFrame,
              top_candidates: gpd.GeoDataFrame,
              filename: str = "shade_map.html") -> str:
    m = folium.Map(location=DONGJAK_CENTER, zoom_start=14, tiles="CartoDB positron")

    # 1) 격자 스코어 히트맵
    heat = scored_grid[["lat", "lon", "score"]].dropna().values.tolist()
    HeatMap(heat, radius=14, blur=20, min_opacity=0.3,
            gradient={"0.2": "blue", "0.5": "orange", "0.8": "red"},
            name="필요도 히트맵").add_to(m)

    # 2) 보행로 / 횡단보도 오버레이
    ped = data_loader.load_pedestrian_network()
    if ped is not None and not ped.empty:
        ped_fg = folium.FeatureGroup(name="보행로 / 횡단보도", show=True)
        for _, row in ped.iterrows():
            is_cw = (row.get("type") == "crosswalk")
            color = "#ff6b00" if is_cw else "#00897b"
            weight = 5 if is_cw else 3
            tooltip = f"{'횡단보도' if is_cw else '보행로'} (폭 {row.get('width', 2):.1f}m)"
            folium.PolyLine(
                locations=[(lat, lon) for lon, lat in row.geometry.coords],
                color=color, weight=weight, opacity=0.8,
                tooltip=tooltip,
            ).add_to(ped_fg)
        ped_fg.add_to(m)

    # 3) 기존 그늘막 (검은 원)
    shades = data_loader.load_existing_shades()
    if not shades.empty:
        shade_fg = folium.FeatureGroup(name="기존 그늘막", show=True)
        for _, row in shades.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=5, color="#333", fill=True, fillColor="#333",
                fillOpacity=0.8, tooltip="기존 그늘막",
            ).add_to(shade_fg)
        shade_fg.add_to(m)

    # 4) TOP 후보지 별 마커
    top_fg = folium.FeatureGroup(name="추천 TOP 10", show=True)
    for i, row in top_candidates.iterrows():
        popup = folium.Popup(
            html=f"<b>TOP {i+1}</b><br>"
                 f"Score: {row['score']:.3f}<br>"
                 f"유동인구: {row['pop']:.0f}<br>"
                 f"지표온도: {row['lst_c']:.1f}℃<br>"
                 f"취약계층: {row['vuln_ratio']*100:.1f}%",
            max_width=250,
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=popup,
            tooltip=f"TOP {i+1} (score {row['score']:.2f})",
            icon=folium.Icon(color="red", icon="star", prefix="fa"),
        ).add_to(top_fg)
    top_fg.add_to(m)

    # 5) 범례 + 레이어 컨트롤
    cmap = cm.LinearColormap(["blue", "orange", "red"],
                             vmin=float(scored_grid["score"].min()),
                             vmax=float(scored_grid["score"].max()),
                             caption="설치 필요도 점수")
    cmap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT / filename
    m.save(str(out_path))
    return str(out_path)
