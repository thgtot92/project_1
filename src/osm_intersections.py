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


# 도시 보도·차도 옆 — 산책로·계단(path, steps) 제외해 녹지 산책로 컷
# 그늘막 정책 대상은 일상 보행 동선 (도시 도로 + 횡단보도 옆 보도)
WALKABLE_HIGHWAYS = [
    "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street",
    "footway", "pedestrian",          # 도시 보도·보행자 전용
    "primary_link", "secondary_link", "tertiary_link",
    # 제외: path, steps (공원 산책로·등산로·계단 → 녹지 추천 방지)
]


def _fetch_walk_graph():
    """OSMnx walkable highway 그래프 다운로드 (캐시는 osmnx 자체가 처리)."""
    import osmnx as ox
    bbox = DONGJAK_BBOX
    bbox_tuple = (bbox["min_lon"], bbox["min_lat"],
                   bbox["max_lon"], bbox["max_lat"])
    custom_filter = '["highway"~"' + "|".join(WALKABLE_HIGHWAYS) + '"]'
    try:
        G = ox.graph_from_bbox(bbox=bbox_tuple, network_type="walk",
                                 custom_filter=custom_filter, simplify=True)
    except TypeError:
        G = ox.graph_from_bbox(north=bbox["max_lat"], south=bbox["min_lat"],
                                 east=bbox["max_lon"], west=bbox["min_lon"],
                                 network_type="walk",
                                 custom_filter=custom_filter, simplify=True)
    return G, ox


def fetch_osm_intersections(force: bool = False) -> gpd.GeoDataFrame:
    """동작구 BBOX 안의 교차로(노드 street_count >= 3) GeoDataFrame.

    캐시: data/processed/osm_intersections.geojson (있으면 재사용).
    walkable edges 캐시도 같은 호출에서 함께 생성.
    """
    out_path = DATA_PROCESSED / "osm_intersections.geojson"
    edges_path = DATA_PROCESSED / "osm_walkable_edges.geojson"
    if out_path.exists() and edges_path.exists() and not force:
        return gpd.read_file(out_path).to_crs(CRS_WGS84)

    print(f"  [OSMnx] 동작구 BBOX 도로 그래프 다운로드 중...")
    G, ox = _fetch_walk_graph()

    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)
    nodes_gdf = nodes_gdf.to_crs(CRS_WGS84)
    edges_gdf = edges_gdf.to_crs(CRS_WGS84)

    # 교차로: street_count >= 3 (T자·교차로). 막다른 길(1)·중간점(2) 제외
    if "street_count" not in nodes_gdf.columns:
        nodes_gdf = nodes_gdf.assign(
            street_count=ox.stats.count_streets_per_node(G).values
        )
    intersections = nodes_gdf[nodes_gdf["street_count"] >= 3].copy()
    intersections = intersections.reset_index()[["osmid", "street_count",
                                                    "highway", "geometry"]]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    intersections.to_file(out_path, driver="GeoJSON")
    print(f"  [OSMnx] {len(intersections)} 교차로 → {out_path}")

    # walkable edges 도 동시 저장 (보행로 필터 입력)
    # highway 컬럼이 list 일 수 있으니 정규화
    edges_export = edges_gdf.copy()
    if "highway" in edges_export.columns:
        edges_export["highway"] = edges_export["highway"].astype(str)
    # name, length 만 보존 (다른 컬럼은 fiona 가 list/dict 직렬화 실패 가능)
    keep_cols = ["highway", "geometry"]
    for c in ("name", "length", "lanes", "width"):
        if c in edges_export.columns:
            edges_export[c] = edges_export[c].astype(str)
            keep_cols.append(c)
    edges_export = edges_export.reset_index(drop=True)[keep_cols]
    edges_export.to_file(edges_path, driver="GeoJSON")
    print(f"  [OSMnx] {len(edges_export)} walkable edges → {edges_path}")

    return intersections


def fetch_osm_walkable_edges(force: bool = False) -> gpd.GeoDataFrame:
    """OSMnx walkable highway edges (LineString) — 보행로 필터 입력."""
    edges_path = DATA_PROCESSED / "osm_walkable_edges.geojson"
    if edges_path.exists() and not force:
        return gpd.read_file(edges_path).to_crs(CRS_WGS84)
    fetch_osm_intersections(force=True)
    return gpd.read_file(edges_path).to_crs(CRS_WGS84)


def fetch_osm_crossings(force: bool = False) -> gpd.GeoDataFrame:
    """OSMnx 횡단보도 — 한국 OSM 매핑 관행 반영해 다중 태그 통합 검색.

    한국 OSM 에서 횡단보도는 highway=crossing 보다 footway=crossing /
    highway=footway 패턴이 흔함. 모두 함께 가져와 중복 제거.

    캐시: data/processed/osm_crossings.geojson
    """
    out_path = DATA_PROCESSED / "osm_crossings.geojson"
    if out_path.exists() and not force:
        return gpd.read_file(out_path).to_crs(CRS_WGS84)

    import osmnx as ox
    bbox = DONGJAK_BBOX
    bbox_tuple = (bbox["min_lon"], bbox["min_lat"],
                   bbox["max_lon"], bbox["max_lat"])
    print(f"  [OSMnx] 동작구 BBOX 횡단보도 다중 태그 검색 중...")

    tag_sets = [
        {"highway": "crossing"},
        {"footway": "crossing"},
        {"crossing": True},
    ]
    all_gdfs = []
    for tags in tag_sets:
        try:
            try:
                g = ox.features_from_bbox(bbox=bbox_tuple, tags=tags)
            except TypeError:
                g = ox.features_from_bbox(
                    north=bbox["max_lat"], south=bbox["min_lat"],
                    east=bbox["max_lon"], west=bbox["min_lon"], tags=tags
                )
            if g is not None and not g.empty:
                all_gdfs.append(g.to_crs(CRS_WGS84))
                print(f"    {tags}: {len(g)}개")
        except Exception as e:
            print(f"    {tags}: 실패 ({type(e).__name__})")

    if not all_gdfs:
        print("  [OSMnx] 횡단보도 0개")
        empty = gpd.GeoDataFrame(geometry=[], crs=CRS_WGS84)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        empty.to_file(out_path, driver="GeoJSON")
        return empty

    merged = gpd.GeoDataFrame(
        pd.concat(all_gdfs, ignore_index=True),
        crs=CRS_WGS84,
    )
    # LineString·Polygon 은 중심점으로 환산
    merged["geometry"] = merged.geometry.apply(
        lambda g: g.centroid if g.geom_type != "Point" else g
    )
    merged = merged[merged.geometry.geom_type == "Point"]
    # 좌표 6자리로 반올림 후 중복 제거
    merged["_k"] = merged.geometry.apply(lambda p: (round(p.x, 6), round(p.y, 6)))
    merged = merged.drop_duplicates("_k").drop(columns=["_k"]).reset_index(drop=True)

    keep = ["geometry"]
    for c in ("highway", "footway", "crossing"):
        if c in merged.columns:
            merged[c] = merged[c].astype(str)
            keep.append(c)
    out = merged[keep].reset_index(drop=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_file(out_path, driver="GeoJSON")
    print(f"  [OSMnx] {len(out)} 횡단보도(중복 제거 후) → {out_path}")
    return out


def fetch_osm_green_areas(force: bool = False) -> gpd.GeoDataFrame:
    """OSMnx 녹지·공원·산림 polygon (그늘막 추천에서 제외할 영역).

    태그: leisure=park, landuse=forest/grass/recreation_ground,
          natural=wood, boundary=protected_area (현충원 등)
    캐시: data/processed/osm_green_areas.geojson
    """
    out_path = DATA_PROCESSED / "osm_green_areas.geojson"
    if out_path.exists() and not force:
        return gpd.read_file(out_path).to_crs(CRS_WGS84)

    import osmnx as ox
    bbox = DONGJAK_BBOX
    bbox_tuple = (bbox["min_lon"], bbox["min_lat"],
                   bbox["max_lon"], bbox["max_lat"])
    print(f"  [OSMnx] 동작구 BBOX 녹지·공원·산림 다운로드 중...")

    tag_sets = [
        {"leisure": ["park", "garden", "nature_reserve"]},
        {"landuse": ["forest", "grass", "recreation_ground",
                       "cemetery", "meadow"]},
        {"natural": ["wood", "scrub", "grassland"]},
        {"boundary": "protected_area"},   # 현충원 같은 보호구역
    ]
    all_gdfs = []
    for tags in tag_sets:
        try:
            try:
                g = ox.features_from_bbox(bbox=bbox_tuple, tags=tags)
            except TypeError:
                g = ox.features_from_bbox(
                    north=bbox["max_lat"], south=bbox["min_lat"],
                    east=bbox["max_lon"], west=bbox["min_lon"], tags=tags
                )
            if g is not None and not g.empty:
                all_gdfs.append(g.to_crs(CRS_WGS84))
                print(f"    {tags}: {len(g)}개")
        except Exception as e:
            print(f"    {tags}: 실패 ({type(e).__name__})")

    if not all_gdfs:
        empty = gpd.GeoDataFrame(geometry=[], crs=CRS_WGS84)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        empty.to_file(out_path, driver="GeoJSON")
        return empty

    merged = gpd.GeoDataFrame(
        pd.concat(all_gdfs, ignore_index=True), crs=CRS_WGS84,
    )
    # Polygon/MultiPolygon 만 유지
    merged = merged[merged.geometry.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    )]
    keep = ["geometry"]
    for c in ("leisure", "landuse", "natural", "boundary", "name"):
        if c in merged.columns:
            merged[c] = merged[c].astype(str)
            keep.append(c)
    out = merged[keep].reset_index(drop=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_file(out_path, driver="GeoJSON")
    print(f"  [OSMnx] {len(out)} 녹지 영역 → {out_path}")
    return out


def fetch_pedestrian_focus_points(force: bool = False) -> gpd.GeoDataFrame:
    """교차로 + 횡단보도 union — '보행자 결집 지점' (proximity 필터·밀도 피처용)."""
    inter = fetch_osm_intersections(force=force)
    cross = fetch_osm_crossings(force=force)
    inter_pts = inter[["geometry"]].copy()
    inter_pts["kind"] = "intersection"
    cross_pts = cross[["geometry"]].copy()
    cross_pts["kind"] = "crossing"
    return gpd.GeoDataFrame(
        pd.concat([inter_pts, cross_pts], ignore_index=True),
        crs=CRS_WGS84,
    )


def compute_intersection_density(grid: gpd.GeoDataFrame,
                                   radius_m: float = 80.0,
                                   force: bool = False) -> pd.Series:
    """각 격자 중심 기준 radius_m 내 보행자 결집 지점(교차로 + 횡단보도) 개수.

    반환: pd.Series(이름=intersection_density, 원시 정수).
    """
    cache_path = DATA_PROCESSED / "grid_intersection.csv"
    if cache_path.exists() and not force:
        cached = pd.read_csv(cache_path)
        if len(cached) == len(grid):
            return pd.Series(cached["intersection_density"].values,
                              name="intersection_density")

    focus = fetch_pedestrian_focus_points()
    if focus.empty:
        return pd.Series(np.zeros(len(grid)), name="intersection_density")

    focus_m = focus.to_crs(CRS_KOREA)
    grid_m = grid if grid.crs == CRS_KOREA else grid.to_crs(CRS_KOREA)

    from shapely.strtree import STRtree
    tree = STRtree(list(focus_m.geometry.values))
    counts = []
    for cell in grid_m.geometry.centroid:
        buf = cell.buffer(radius_m)
        idxs = tree.query(buf)
        hit = 0
        for idx in idxs:
            if focus_m.geometry.iloc[int(idx)].within(buf):
                hit += 1
        counts.append(hit)

    cached = pd.DataFrame({"intersection_density": counts})
    cached.to_csv(cache_path, index=False)
    print(f"  [OSMnx] 격자별 결집지점 밀도 (교차로+횡단보도, "
          f"radius={radius_m}m) → {cache_path}")
    return pd.Series(counts, name="intersection_density")


def compute_focus_proximity_mask(grid: gpd.GeoDataFrame,
                                   max_dist_m: float = 50.0) -> np.ndarray:
    """각 격자 centroid 에서 가장 가까운 교차로/횡단보도까지 거리 ≤ max_dist_m 인지.

    반환: bool numpy array (True = 통과).
    """
    focus = fetch_pedestrian_focus_points()
    if focus.empty:
        return np.ones(len(grid), dtype=bool)

    focus_m = focus.to_crs(CRS_KOREA)
    grid_m = grid if grid.crs == CRS_KOREA else grid.to_crs(CRS_KOREA)

    # 모든 focus 점에서 단일 union → 격자 centroid 의 distance 계산
    from shapely.ops import unary_union
    focus_union = unary_union(list(focus_m.geometry.values))
    centroids = grid_m.geometry.centroid
    dists = np.array([c.distance(focus_union) for c in centroids])
    return dists <= max_dist_m


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
