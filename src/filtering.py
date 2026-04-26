"""STEP 2 — 후보지 공간 필터링.

조건:
  1) 보행로/횡단보도 20m 이내 (필수)
  2) 인도 폭 ≥ 2m
  3) 기존 그늘막 반경 150m 외
  4) 상위 TOP_K (점수 내림차순)
"""
from __future__ import annotations
import geopandas as gpd
from .config import CRS_KOREA, CRS_WGS84, FILTER
from . import data_loader


def _filter_by_pedestrian(candidates: gpd.GeoDataFrame,
                          buffer_m: float = 20.0,
                          min_width: float = 2.0) -> gpd.GeoDataFrame:
    """보행로/횡단보도에서 buffer_m 이내 격자만 통과 (핵심 제약)."""
    ped = data_loader.load_pedestrian_network()
    if ped is None or ped.empty:
        return candidates
    ped = ped[ped.get("width", 0) >= min_width]
    if ped.empty:
        return candidates
    ped_m = ped.to_crs(CRS_KOREA)
    buf = ped_m.buffer(buffer_m).unary_union
    cand_m = candidates.to_crs(CRS_KOREA)
    mask = cand_m.geometry.centroid.intersects(buf)
    return candidates.loc[mask.values]


def _filter_by_shades(candidates: gpd.GeoDataFrame,
                      radius_m: float) -> gpd.GeoDataFrame:
    shades = data_loader.load_existing_shades().to_crs(CRS_KOREA)
    if shades.empty:
        return candidates
    union = shades.buffer(radius_m).unary_union
    cand_m = candidates.to_crs(CRS_KOREA)
    mask = ~cand_m.geometry.centroid.within(union)
    return candidates.loc[mask.values]


def filter_candidates(scored_grid: gpd.GeoDataFrame,
                       verbose: bool = True) -> gpd.GeoDataFrame:
    """필터만 적용 (TOP K 안 자름) — 1차 후보 풀(약 19개) 산출용."""
    g = scored_grid.sort_values("score", ascending=False).copy()
    g = g.to_crs(CRS_WGS84) if g.crs != CRS_WGS84 else g

    before = len(g)
    g = _filter_by_pedestrian(g,
                              buffer_m=20.0,
                              min_width=FILTER["min_sidewalk_width_m"])
    if verbose:
        print(f"    보행로 필터: {before} → {len(g)}")

    before = len(g)
    g = _filter_by_shades(g, FILTER["exclusion_radius_m"])
    if verbose:
        print(f"    기존그늘막 필터: {before} → {len(g)}")

    return g.reset_index(drop=True)


def pick_candidates(scored_grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """score 부착 grid → 보행로 제약 + 기존그늘막 제외 + TOP_K."""
    g = filter_candidates(scored_grid)
    return g.head(FILTER["top_k"]).reset_index(drop=True)
