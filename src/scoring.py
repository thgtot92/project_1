"""STEP 1 — 필요도 스코어 산출.

Score = w_pop*pop + w_lst*lst + w_vuln*vuln - w_shade*shadeCov - w_nat*natShade

각 피처는 [0,1] 로 Min-Max 정규화 후 가중합.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from .config import WEIGHTS, CRS_WGS84, CRS_KOREA, FILTER
from . import data_loader


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo + 1e-9)


def _shade_coverage(points_wgs: gpd.GeoDataFrame,
                    shades_wgs: gpd.GeoDataFrame,
                    radius_m: float = 150.0) -> pd.Series:
    """각 격자 중심에서 radius_m 내 기존 그늘막 개수 → 정규화."""
    p_m = points_wgs.to_crs(CRS_KOREA)
    s_m = shades_wgs.to_crs(CRS_KOREA)
    buf = p_m.buffer(radius_m)
    count = np.array([s_m.intersects(b).sum() for b in buf])
    return pd.Series(count, index=points_wgs.index, name="shade_cov")


def compute_scores(grid: gpd.GeoDataFrame,
                   weights: dict | None = None) -> gpd.GeoDataFrame:
    """grid(EPSG:5179, geometry=polygon) 에 스코어 컬럼 부착하여 반환.

    Args:
        grid: 격자 GeoDataFrame
        weights: 사용자 지정 가중치 (없으면 config.WEIGHTS 사용)
    """
    W = weights if weights is not None else WEIGHTS
    centroids_m = grid.geometry.centroid
    centroids_wgs = gpd.GeoSeries(centroids_m, crs=CRS_KOREA).to_crs(CRS_WGS84)
    pts = pd.DataFrame({
        "lon": centroids_wgs.x.values,
        "lat": centroids_wgs.y.values,
    })

    pop = data_loader.load_living_pop(pts)
    lst = data_loader.load_lst(pts)
    vuln = data_loader.load_vuln_ratio(pts)

    shades = data_loader.load_existing_shades()
    cent_gdf = gpd.GeoDataFrame(
        geometry=[Point(xy) for xy in zip(pts["lon"], pts["lat"])],
        crs=CRS_WGS84,
    )
    shade_cov = _shade_coverage(cent_gdf, shades,
                                radius_m=FILTER["exclusion_radius_m"])

    # 자연 그늘 (CV-A): 건물 footprint + 오후 피크 태양 위치로 그림자 시뮬레이션
    nat = data_loader.load_natural_shade(grid)

    # 거리뷰 그늘 결핍 (CV-B): grid_streetview.csv 가 있으면 nearest 매칭, 없으면 0
    sv_deficit = data_loader.load_streetview_deficit(pts)

    out = grid.copy()
    out["lon"] = pts["lon"].values
    out["lat"] = pts["lat"].values
    out["pop"] = pop.values
    out["lst_c"] = lst.values
    out["vuln_ratio"] = vuln.values
    out["shade_cov"] = shade_cov.values
    out["natural"] = nat.values
    out["sv_deficit"] = sv_deficit.values

    nrm = pd.DataFrame({
        "popdens":            _minmax(pop),
        "lst":                _minmax(lst),
        "vuln":               _minmax(vuln),
        "shade":              _minmax(shade_cov),
        "natural":            _minmax(nat),
        "streetview_deficit": _minmax(sv_deficit),
    })
    out["score"] = (
        W["popdens"]            * nrm["popdens"]
        + W["lst"]              * nrm["lst"]
        + W["vuln"]             * nrm["vuln"]
        + W["shade"]            * nrm["shade"]
        + W["natural"]          * nrm["natural"]
        + W.get("streetview_deficit", 0.0) * nrm["streetview_deficit"]
    ).values
    return out


def rescore_from_features(scored: gpd.GeoDataFrame,
                          weights: dict) -> gpd.GeoDataFrame:
    """이미 계산된 피처(pop/lst_c/...)를 재사용해서 가중치만 다시 적용.

    scenarios 여러 번 돌릴 때 데이터 재로딩 비용 절약.
    """
    sv_col = scored["sv_deficit"] if "sv_deficit" in scored.columns \
        else pd.Series(np.zeros(len(scored)), index=scored.index)
    nrm = pd.DataFrame({
        "popdens":            _minmax(scored["pop"]),
        "lst":                _minmax(scored["lst_c"]),
        "vuln":               _minmax(scored["vuln_ratio"]),
        "shade":              _minmax(scored["shade_cov"]),
        "natural":            _minmax(scored["natural"]),
        "streetview_deficit": _minmax(sv_col),
    })
    out = scored.copy()
    out["score"] = (
        weights["popdens"]            * nrm["popdens"]
        + weights["lst"]              * nrm["lst"]
        + weights["vuln"]             * nrm["vuln"]
        + weights["shade"]            * nrm["shade"]
        + weights["natural"]          * nrm["natural"]
        + weights.get("streetview_deficit", 0.0) * nrm["streetview_deficit"]
    ).values
    return out
