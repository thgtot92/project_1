"""STEP OSM — 동작구 highway/보행 네트워크에서 교차로 추출.

OSMnx 로 동작구 BBOX 도로 그래프를 받아 노드 중 street_count >= 3 (교차로)을
GeoDataFrame 으로 저장. 격자별 "교차로 밀도" 피처 산출 → 보행자가 모이는
교차로 인근을 그늘막 추천에서 우선시.

산출물:
    data/processed/osm_intersections.geojson    교차로 노드 (WGS84)
    data/processed/grid_intersection.csv         격자별 intersection_density

실행:
    python -X utf8 -m src.osm_intersections
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from .config import (DATA_PROCESSED, DONGJAK_BBOX, CRS_WGS84, CRS_KOREA)


# 보행자 그늘막 관점에서 의미 있는 highway 태그
# (motorway·trunk는 차도 위주라 제외 가능하지만 인근 보도 존재 → 포함)
WALKABLE_HIGHWAYS = [
    "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street",
    "footway", "pedestrian", "path", "steps",
    "primary_link", "secondary_link", "tertiary_link",
]


def fetch_osm_intersections(force: bool = False) -> gpd.GeoDataFrame:
    """동작구 BBOX 안의 교차로(노드 street_count >= 3) GeoDataFrame.

    캐시: data/processed/osm_intersections.geojson (있으면 재사용).
    """
    out_path = DATA_PROCESSED / "osm_intersections.geojson"
    if out_path.exists() and not force:
        return gpd.read_file(out_path).to_crs(CRS_WGS84)

    import osmnx as ox
    bbox = DONGJAK_BBOX
    print(f"  [OSMnx] 동작구 BBOX 도로 그래프 다운로드 중...")

    # OSMnx 2.x 시그니처: bbox = (left, bottom, right, top)
    bbox_tuple = (bbox["min_lon"], bbox["min_lat"],
                   bbox["max_lon"], bbox["max_lat"])
    custom_filter = '["highway"~"' + "|".join(WALKABLE_HIGHWAYS) + '"]'
    try:
        G = ox.graph_from_bbox(bbox=bbox_tuple, network_type="walk",
                                 custom_filter=custom_filter, simplify=True)
    except TypeError:
        # OSMnx 1.x fallback (north/south/east/west)
        G = ox.graph_from_bbox(north=bbox["max_lat"], south=bbox["min_lat"],
                                 east=bbox["max_lon"], west=bbox["min_lon"],
                                 network_type="walk",
                                 custom_filter=custom_filter, simplify=True)

    nodes_gdf, _ = ox.graph_to_gdfs(G)
    nodes_gdf = nodes_gdf.to_crs(CRS_WGS84)

    # 교차로: street_count >= 3 (T자·교차로). 막다른 길(1)·중간점(2) 제외
    if "street_count" not in nodes_gdf.columns:
        # OSMnx 일부 버전에서 noticeable count
        nodes_gdf = nodes_gdf.assign(
            street_count=ox.stats.count_streets_per_node(G).values
        )
    intersections = nodes_gdf[nodes_gdf["street_count"] >= 3].copy()
    intersections = intersections.reset_index()[["osmid", "street_count",
                                                    "highway", "geometry"]]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    intersections.to_file(out_path, driver="GeoJSON")
    print(f"  [OSMnx] {len(intersections)} 교차로 → {out_path}")
    return intersections


def compute_intersection_density(grid: gpd.GeoDataFrame,
                                   radius_m: float = 80.0,
                                   force: bool = False) -> pd.Series:
    """각 격자 중심 기준 radius_m 내 교차로 개수.

    반환: pd.Series(이름=intersection_density, 원시 정수).
    """
    cache_path = DATA_PROCESSED / "grid_intersection.csv"
    if cache_path.exists() and not force:
        cached = pd.read_csv(cache_path)
        if len(cached) == len(grid):
            return pd.Series(cached["intersection_density"].values,
                              name="intersection_density")

    intersections = fetch_osm_intersections()
    if intersections.empty:
        return pd.Series(np.zeros(len(grid)), name="intersection_density")

    inter_m = intersections.to_crs(CRS_KOREA)
    grid_m = grid if grid.crs == CRS_KOREA else grid.to_crs(CRS_KOREA)

    # 격자 중심에서 radius_m 버퍼 → 교차로 점과 intersects 카운트
    from shapely.strtree import STRtree
    tree = STRtree(list(inter_m.geometry.values))
    counts = []
    for cell in grid_m.geometry.centroid:
        buf = cell.buffer(radius_m)
        idxs = tree.query(buf)
        # STRtree.query: 후보 idx 배열 → 정확 검사
        hit = 0
        for idx in idxs:
            if inter_m.geometry.iloc[int(idx)].within(buf):
                hit += 1
        counts.append(hit)

    cached = pd.DataFrame({"intersection_density": counts})
    cached.to_csv(cache_path, index=False)
    print(f"  [OSMnx] 격자별 교차로 밀도 (radius={radius_m}m) → {cache_path}")
    return pd.Series(counts, name="intersection_density")


def render_overlay():
    """디버그용: 교차로 오버레이 + 격자 카운트 지도."""
    import folium
    from .config import OUTPUT, DONGJAK_CENTER

    intersections = fetch_osm_intersections()
    m = folium.Map(location=DONGJAK_CENTER, zoom_start=14,
                    tiles="CartoDB positron")
    for _, row in intersections.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3, color="#1565c0", fill=True,
            fillColor="#1565c0", fillOpacity=0.7,
            tooltip=f"deg={row.get('street_count', '?')}",
        ).add_to(m)
    out = OUTPUT / "osm_intersections_overlay.html"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    print(f"  [OSMnx] overlay → {out}")
    return out


if __name__ == "__main__":
    fetch_osm_intersections(force=True)
    render_overlay()
