"""Self-consistency 5회 — 흑석동 DSM 누적 그림자 안정성 검증.

강의자료 40p 권장: 동일 입력에 대해 5회 반복 평가 → 평균 + 표준편차.

CV-DSM 모듈이 사용하는 태양위치(고도·방위)를 ±미세 변동시켜 5회 ray-cast 수행.
각 격자별로:
  - mean: 5회 누적 그림자 비율 평균
  - std: 표준편차 (예측 안정성, 작을수록 신뢰도 ↑)
  - ci95: 95% 신뢰구간 폭 (≈ 2×std)

산출물:
  data/processed/grid_heukseok_consistency.csv
    grid_idx, lat, lon, mean, std, ci95_low, ci95_high
"""
from __future__ import annotations
from math import radians, sin, cos, tan
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from .config import (DATA_RAW, DATA_PROCESSED, CRS_WGS84,
                      SUN_ALTITUDE_DEG, SUN_AZIMUTH_DEG)


# 5회 변동: 기본 위치 + (±15분 시각, ±5° 방위) 조합
# 시각 ±15분 ≈ 고도 ±3.75° (지구 자전 1시간 15° 기준)
SUN_VARIATIONS = [
    ("base",      0.0,  0.0),   # 기준점
    ("early_lo",  +3.5, -5.0),  # 15분 일찍, 방위 동쪽
    ("early_hi",  +3.5, +5.0),  # 15분 일찍, 방위 서쪽
    ("late_lo",   -3.5, -5.0),  # 15분 늦게, 방위 동쪽
    ("late_hi",   -3.5, +5.0),  # 15분 늦게, 방위 서쪽
]


def _ray_cast_shadow(ndsm: np.ndarray, transform,
                      alt_deg: float, az_deg: float,
                      step_m: float = 2.0,
                      max_dist_m: float = 200.0) -> np.ndarray:
    """cv_dsm_heukseok._ray_cast_shadow_mask 와 동일 구현 (단일 시점)."""
    alt = radians(alt_deg)
    az = radians(az_deg)
    H, W = ndsm.shape
    px_x = transform.a
    px_y = -transform.e
    drow_sun = sin(az) * step_m / px_y
    dcol_sun = -(-sin(az)) * step_m / px_x  # = sin(az)*step_m/px_x  (간단화 위해 풀어쓰기 X)
    dcol_sun = sin(az) * step_m / px_x
    drow_sun = cos(az) * step_m / px_y  # 북쪽으로 row 감소 → cos(az)*step_m/px_y

    n_steps = int(max_dist_m / step_m)
    rows, cols = np.indices(ndsm.shape)
    shadow = np.zeros_like(ndsm, dtype=bool)
    for k in range(1, n_steps + 1):
        rr = (rows + drow_sun * k).astype(np.int32)
        cc = (cols + dcol_sun * k).astype(np.int32)
        valid = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        ray_h = k * step_m * tan(alt)
        rr_c = np.where(valid, rr, 0)
        cc_c = np.where(valid, cc, 0)
        blocker = (ndsm[rr_c, cc_c] > ray_h) & valid
        shadow |= blocker
    return shadow


def compute_consistency(dsm_path: Path, dem_path: Path) -> np.ndarray:
    """5회 변동 평균 + 표준편차 래스터 반환.

    Returns:
        np.stack([mean, std], axis=0) — shape (2, H, W)
    """
    with rasterio.open(dsm_path) as ds_dsm, rasterio.open(dem_path) as ds_dem:
        dsm = ds_dsm.read(1).astype(np.float32)
        dem = ds_dem.read(1).astype(np.float32)
        transform = ds_dsm.transform
        meta = ds_dsm.meta.copy()
    dsm = np.where(dsm < -100, np.nan, dsm)
    dem = np.where(dem < -100, np.nan, dem)
    ndsm = np.clip(np.nan_to_num(dsm - dem, nan=0.0), 0, 200)

    samples = []
    for label, d_alt, d_az in SUN_VARIATIONS:
        alt = SUN_ALTITUDE_DEG + d_alt
        az = SUN_AZIMUTH_DEG + d_az
        # 한 시점 = 4 가상시점(10·12·14·16) ray-cast union 의 단순화 버전 (계산비용 ↓):
        # 본 모듈은 "오후 3시 ± 미세변동" 5회를 누적 — Self-consistency 본질.
        s = _ray_cast_shadow(ndsm, transform, alt, az).astype(np.float32)
        samples.append(s)
        print(f"  [SC] {label}: alt={alt:.1f}, az={az:.1f}, "
              f"mean shadow={s.mean():.3f}")

    stack = np.stack(samples, axis=0)  # (5, H, W)
    mean = stack.mean(axis=0)
    std = stack.std(axis=0)
    return np.stack([mean, std], axis=0), meta


def aggregate_to_grid(mean_std: np.ndarray, meta: dict,
                       grid: gpd.GeoDataFrame) -> pd.DataFrame:
    """5회 평균/표준편차 래스터 → 격자별 통계."""
    mean = mean_std[0]
    std = mean_std[1]
    transform = meta['transform']
    raster_crs = meta['crs']
    H, W = mean.shape

    grid_proj = grid.to_crs(raster_crs)
    inv = ~transform
    rows = []
    for idx, row in grid_proj.iterrows():
        c = row.geometry.centroid
        col_f, row_f = inv * (c.x, c.y)
        col, r = int(col_f), int(row_f)
        if 0 <= r < H and 0 <= col < W:
            m, sd = float(mean[r, col]), float(std[r, col])
            rows.append({
                "grid_idx": int(idx),
                "lat": float(grid.loc[idx, 'geometry'].centroid.y)
                       if grid.crs == CRS_WGS84 else None,
                "lon": float(grid.loc[idx, 'geometry'].centroid.x)
                       if grid.crs == CRS_WGS84 else None,
                "shadow_mean": m,
                "shadow_std": sd,
                "ci95_low": max(0.0, m - 2 * sd),
                "ci95_high": min(1.0, m + 2 * sd),
            })
    df = pd.DataFrame(rows)
    return df


def run(grid: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    print("[SC] Self-consistency 5회 (흑석동 DSM 누적 그림자 안정성)")
    dsm_path = DATA_RAW / "heukseok" / "basic_dsm_ortho" / "흑석동_dsm.tif"
    dem_path = DATA_RAW / "heukseok" / "ngii_dem" / "흑석동_dem.tif"
    if not (dsm_path.exists() and dem_path.exists()):
        print("  [skip] 흑석동 DSM/DEM 없음")
        return pd.DataFrame()

    mean_std, meta = compute_consistency(dsm_path, dem_path)

    if grid is None:
        from .grid import build_grid
        grid = build_grid().to_crs(CRS_WGS84)
    elif grid.crs != CRS_WGS84:
        grid = grid.to_crs(CRS_WGS84)

    df = aggregate_to_grid(mean_std, meta, grid)
    out = DATA_PROCESSED / "grid_heukseok_consistency.csv"
    df.to_csv(out, index=False)
    print(f"  [SC] {out}  ({len(df)} 격자, "
          f"평균 mean={df['shadow_mean'].mean():.3f}, "
          f"평균 std={df['shadow_std'].mean():.3f})")
    return df


if __name__ == "__main__":
    run()
