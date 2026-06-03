"""STEP CV-DSM — 흑석동 DSM 기반 정밀 자연그늘 (Deep Umbra 영감, 시간 누적).

PDF 강의자료 13p 추천 논문:
  Deep Umbra: A Generative Approach for Sunlight Access Computation
  in Urban Spaces (http://evl.uic.edu/shadows/)

본 모듈은 풀 GAN 학습 대신, **DSM 실측 높이 + 4시점(오전 10·정오·오후 2·오후 4)
하지 태양위치 ray casting** 으로 시간 누적 그림자(shadow accumulation) 맵을 산출.

흑석동에 한정 — 동작구 다른 영역은 기존 SAM+오후3시 단일 그림자 유지.

입력:
  data/raw/heukseok/basic_dsm_ortho/흑석동_dsm.tif    표면 모델 (m, EPSG:5186)
  data/raw/heukseok/ngii_dem/흑석동_dem.tif            지표 고도 (m, EPSG:5186)
  data/raw/heukseok/ngii_data/흑석동_경계5186.shp     흑석동 경계 (BBOX)

산출물:
  data/processed/heukseok_shadow_accum.tif    누적 그림자 비율 [0,1] 래스터
  data/processed/grid_heukseok_natural.csv    흑석동 격자 자연그늘 (덮어쓰기용)
  output/cv_dsm_overlay.png                    DSM + 누적 그림자 시각화

실행:
    python -X utf8 -m src.cv_dsm_heukseok
"""
from __future__ import annotations
from math import radians, sin, cos, tan
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import xy as rio_xy
from .config import DATA_RAW, DATA_PROCESSED, OUTPUT, CRS_KOREA, CRS_WGS84


# 서울 하지(6/21) 9시점 태양위치 — 오전 9시~오후 5시 1시간 간격
# (시각, altitude_deg, azimuth_deg from N CW)
# 4시점에서 9시점으로 확장 — 시간 누적 그림자 정밀도 ↑ (Deep Umbra 원논문 정신 강화)
SUN_TIMES = [
    ("09:00", 50.0,  95.0),   # 동쪽, 낮은 고도
    ("10:00", 60.0, 110.0),   # 동남
    ("11:00", 68.0, 135.0),   # 남동
    ("12:00", 75.0, 175.0),   # 정오, 남쪽 천정
    ("13:00", 73.0, 210.0),   # 남서로 기울기 시작
    ("14:00", 65.0, 235.0),   # 남서
    ("15:00", 55.0, 250.0),   # 서남서
    ("16:00", 45.0, 260.0),   # 서쪽, 그림자 길어짐
    ("17:00", 33.0, 268.0),   # 서쪽, 매우 낮음
]


def _compute_ndsm(dsm_path: Path, dem_path: Path) -> tuple[np.ndarray, dict]:
    """nDSM = DSM − DEM (객체 높이 모델), 메타와 함께 반환."""
    with rasterio.open(dsm_path) as ds_dsm, rasterio.open(dem_path) as ds_dem:
        dsm = ds_dsm.read(1).astype(np.float32)
        dem = ds_dem.read(1).astype(np.float32)
        if dsm.shape != dem.shape:
            raise RuntimeError(
                f"DSM/DEM 모양 불일치: {dsm.shape} vs {dem.shape}"
            )
        meta = ds_dsm.meta.copy()

    # nodata 처리
    dsm = np.where(dsm < -100, np.nan, dsm)
    dem = np.where(dem < -100, np.nan, dem)
    ndsm = dsm - dem
    ndsm = np.clip(ndsm, 0, 200)  # 음수 제거 + 200m 상한 (이상치 컷)
    ndsm = np.nan_to_num(ndsm, nan=0.0)
    return ndsm, meta


def _ray_cast_shadow_mask(ndsm: np.ndarray, transform, crs_proj,
                            alt_deg: float, az_deg: float,
                            step_m: float = 2.0,
                            max_dist_m: float = 200.0) -> np.ndarray:
    """단일 태양위치에서 ndsm 기준 그림자 마스크 (True=그림자) 산출.

    각 픽셀 (i,j) 에서 태양 반대 방향으로 step_m 씩 전진하며,
    그 지점의 nDSM 높이가 (현재 픽셀 높이 + 직선 거리 × tan(alt)) 보다 크면
    그림자 안으로 판정. 단순화: 픽셀 해상도 그대로 사용, GPU 없이 CPU 루프.
    """
    alt = radians(alt_deg)
    az = radians(az_deg)
    # 태양 반대 방향 (그림자가 뻗어나가는 방향): (-sin az, -cos az)
    dx_m = -sin(az)
    dy_m = -cos(az)

    H, W = ndsm.shape
    # 픽셀 크기 (m): transform.a (x scale), transform.e (y scale, 음수)
    px_x = transform.a
    px_y = -transform.e
    dx_px = dx_m * step_m / px_x
    dy_px = dy_m * step_m / px_y  # 이미지 y는 아래로 + 이지만, 5186 좌표는 위로+
    # rasterio transform: y는 위로+ → 픽셀 내려갈수록 y 감소
    # 그러므로 row 증분 = -dy_m * step_m / px_y (이미지 row)
    drow = -dy_m * step_m / px_y
    dcol = dx_m * step_m / px_x

    n_steps = int(max_dist_m / step_m)
    rise_per_step = tan(alt) * step_m  # 태양 반대 방향 step 당 ray 높이 상승은 없음
    # 그림자 판정: 어떤 광선이 픽셀 (i,j) 에 도달하려면, 그 광선의 출발지(태양 방향)에서
    # 통과한 다른 픽셀의 높이가 광선 높이보다 낮아야 함.
    # 단순화: 각 픽셀에 대해 태양 방향으로 walk → 더 높은 nDSM 발견 시 그림자.
    # 태양 방향 = -dx_m, -dy_m (드림자 반대)
    drow_sun = -drow
    dcol_sun = -dcol

    shadow = np.zeros_like(ndsm, dtype=bool)
    rows, cols = np.indices(ndsm.shape)
    # 각 시작 픽셀 (i,j) 에서 N step 까지 태양 방향 광선 sampling
    for k in range(1, n_steps + 1):
        rr = (rows + drow_sun * k).astype(np.int32)
        cc = (cols + dcol_sun * k).astype(np.int32)
        valid = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        # 광선 높이 = 시작 nDSM + (광선이 태양방향으로 진행한 거리) × tan(alt)
        # 시작 nDSM 은 0(지면) 이라 가정 → 광선 높이 = k*step_m * tan(alt)
        ray_h = k * step_m * tan(alt)
        # 통과 지점의 nDSM 이 광선보다 높으면 시작 픽셀은 그림자
        rr_c = np.where(valid, rr, 0)
        cc_c = np.where(valid, cc, 0)
        blocker = (ndsm[rr_c, cc_c] > ray_h) & valid
        shadow |= blocker
    return shadow


def compute_accumulated_shadow(dsm_path: Path, dem_path: Path,
                                 out_path: Path) -> np.ndarray:
    """4시점 그림자 union → 누적 그림자 비율 [0,1] 저장 + 반환.

    각 픽셀의 값 = (그림자였던 시점 수) / 총 시점 수.
    """
    ndsm, meta = _compute_ndsm(dsm_path, dem_path)
    print(f"  [DSM] nDSM shape={ndsm.shape}, max height={ndsm.max():.1f}m")

    with rasterio.open(dsm_path) as src:
        transform = src.transform
        crs_proj = src.crs

    accum = np.zeros_like(ndsm, dtype=np.float32)
    for label, alt, az in SUN_TIMES:
        print(f"  [DSM] ray-cast {label} (alt={alt}, az={az})")
        shadow = _ray_cast_shadow_mask(ndsm, transform, crs_proj, alt, az)
        accum += shadow.astype(np.float32)
    accum /= len(SUN_TIMES)  # [0,1]

    # GeoTIFF 저장
    out_meta = meta.copy()
    out_meta.update(dtype="float32", count=1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(accum.astype(np.float32), 1)
    print(f"  [DSM] 누적 그림자 → {out_path} (mean={accum.mean():.3f})")
    return accum


def aggregate_to_grid(accum_path: Path,
                       grid: gpd.GeoDataFrame) -> pd.Series:
    """누적 그림자 래스터를 격자별 평균값으로 집계 (흑석동 격자만 의미있음).

    반환: 인덱스가 grid 와 동일한 pd.Series (이름=heukseok_shadow_accum).
    """
    with rasterio.open(accum_path) as src:
        accum = src.read(1)
        transform = src.transform
        raster_crs = src.crs
        H, W = accum.shape

    # 격자 → 래스터 CRS 로 변환
    grid_proj = grid.to_crs(raster_crs)
    vals = np.full(len(grid), np.nan, dtype=np.float32)

    inv_transform = ~transform
    for i, (idx, row) in enumerate(grid_proj.iterrows()):
        c = row.geometry.centroid
        col_f, row_f = inv_transform * (c.x, c.y)
        col, r = int(col_f), int(row_f)
        if 0 <= r < H and 0 <= col < W:
            vals[i] = accum[r, col]
    return pd.Series(vals, name="heukseok_shadow_accum")


def run(grid: gpd.GeoDataFrame | None = None) -> pd.Series | None:
    print("[CV-DSM] 흑석동 DSM 기반 누적 그림자 (Deep Umbra 영감)")
    dsm_path = DATA_RAW / "heukseok" / "basic_dsm_ortho" / "흑석동_dsm.tif"
    dem_path = DATA_RAW / "heukseok" / "ngii_dem" / "흑석동_dem.tif"
    if not (dsm_path.exists() and dem_path.exists()):
        print("  [skip] 흑석동 DSM/DEM 없음")
        return None

    accum_path = DATA_PROCESSED / "heukseok_shadow_accum.tif"
    if not accum_path.exists():
        compute_accumulated_shadow(dsm_path, dem_path, accum_path)
    else:
        print(f"  [skip] {accum_path} 캐시 사용")

    if grid is None:
        # CLI 단독 실행 시 격자 생성
        from .grid import build_grid
        grid = build_grid()

    sv = aggregate_to_grid(accum_path, grid)
    valid_n = int((~sv.isna()).sum())
    print(f"  [CV-DSM] 격자 {valid_n}/{len(sv)}개 매칭 (흑석동 영역)")

    out_csv = DATA_PROCESSED / "grid_heukseok_natural.csv"
    pd.DataFrame({
        "heukseok_shadow_accum": sv.values,
    }).to_csv(out_csv, index=False)
    print(f"  [CV-DSM] {out_csv}")
    return sv


if __name__ == "__main__":
    run()
