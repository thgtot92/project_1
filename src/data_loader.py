"""데이터 로더.

실제 공공데이터가 data/raw 에 존재하면 그것을 사용하고,
없으면 재현 가능한 더미 데이터를 생성합니다 (MVP 파이프라인 검증용).

실제 데이터 배치 규칙:
- data/raw/living_pop_dongjak.csv   (col: lon, lat, pop)
- data/raw/lst_dongjak.csv          (col: lon, lat, lst_c)
- data/raw/vuln_dongjak.csv         (col: lon, lat, vuln_ratio)
- data/raw/existing_shades.csv      (col: lon, lat)
- data/raw/sidewalks.geojson        (LineString, attr: width)
"""
from __future__ import annotations
from math import radians, sin, cos, tan
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.affinity import translate
from shapely.ops import unary_union
from .config import (DATA_RAW, CRS_WGS84, CRS_KOREA, HOUR_WEIGHTS,
                      SUN_ALTITUDE_DEG, SUN_AZIMUTH_DEG)


# 동작구 실제 거점 기반 핫스팟 (lon, lat, sigma)
# 시간대별 상대 강도: (역세권 출퇴근 피크 vs 시장/상업 오후 피크)
_POP_HOURLY_PROFILE = {
    # 역세권: 아침·저녁 출퇴근 피크, 낮에는 낮음
    "transit": {9: 0.8, 10: 0.5, 11: 0.5, 12: 0.6, 13: 0.6,
                14: 0.6, 15: 0.6, 16: 0.7, 17: 0.9, 18: 1.0},
    # 시장/상업: 오후에 피크
    "market":  {9: 0.4, 10: 0.6, 11: 0.8, 12: 1.0, 13: 1.0,
                14: 1.0, 15: 1.0, 16: 0.9, 17: 0.7, 18: 0.5},
}
_HOTSPOTS = {
    "pop": [
        # (lon, lat, sigma, category)
        (126.9410, 37.5131, 0.005, "market"),    # 노량진 수산시장 (시장)
        (126.9530, 37.5020, 0.004, "transit"),   # 장승배기역
        (126.9683, 37.4855, 0.005, "transit"),   # 사당역
        (126.9637, 37.4920, 0.004, "transit"),   # 이수역
        (126.9177, 37.4940, 0.004, "transit"),   # 신대방역
        (126.9243, 37.5090, 0.003, "transit"),   # 대방역
    ],
    "lst": [
        (126.9410, 37.5100, 0.006),   # 노량진 상업지구
        (126.9683, 37.4870, 0.005),   # 사당 교차로
        (126.9637, 37.4900, 0.005),   # 이수역 대로변
        (126.9350, 37.4987, 0.004),   # 상도동 주거밀집
    ],
    "vuln": [
        (126.9350, 37.4987, 0.006),   # 상도3동 (노후 주거)
        (126.9573, 37.5072, 0.005),   # 흑석동
        (126.9813, 37.4840, 0.005),   # 사당5동
    ],
}


# 동작구 주요 건물군 (자연 그늘 시뮬레이션용 더미)
# (lon, lat, footprint_radius_m, height_m)
# 역세권 상업빌딩 + 주거 밀집지 아파트 — TOP 후보 격자 주변에 의도적으로 배치
_BUILDINGS = [
    # 노량진역·수산시장 일대 상업빌딩
    (126.9412, 37.5118, 25, 45),
    (126.9398, 37.5128, 22, 40),
    (126.9425, 37.5108, 20, 35),
    # 사당역 교차로 빌딩군
    (126.9685, 37.4868, 28, 50),
    (126.9670, 37.4862, 22, 40),
    (126.9692, 37.4878, 20, 35),
    # 이수역 일대
    (126.9645, 37.4915, 25, 45),
    (126.9632, 37.4925, 22, 40),
    # 상도3동 주거 밀집 (아파트군)
    (126.9345, 37.4985, 18, 42),
    (126.9358, 37.4978, 18, 42),
    (126.9342, 37.4972, 18, 42),
    (126.9362, 37.4992, 18, 42),
    # 장승배기역
    (126.9528, 37.5022, 22, 38),
    (126.9540, 37.5015, 20, 35),
    # 흑석동 한강변 아파트
    (126.9573, 37.5072, 25, 50),
    (126.9588, 37.5078, 22, 45),
    # 사당5동
    (126.9810, 37.4840, 22, 38),
    # 신대방·대방
    (126.9180, 37.4940, 20, 35),
    (126.9240, 37.5088, 22, 40),
]


# 동작구 주요 보행로 / 횡단보도 (실제 도로 축 기반 더미)
_PEDESTRIAN_ROUTES = [
    # 노량진역 ~ 수산시장 보행로 / 횡단보도
    {"coords": [(126.9390, 37.5140), (126.9405, 37.5131), (126.9425, 37.5120),
                (126.9440, 37.5108)], "type": "sidewalk", "width": 3.0},
    {"coords": [(126.9405, 37.5135), (126.9412, 37.5128)],
     "type": "crosswalk", "width": 4.0},
    # 장승배기역
    {"coords": [(126.9510, 37.5030), (126.9525, 37.5022), (126.9540, 37.5015),
                (126.9555, 37.5005)], "type": "sidewalk", "width": 2.5},
    {"coords": [(126.9528, 37.5025), (126.9535, 37.5018)],
     "type": "crosswalk", "width": 4.0},
    # 사당역 ~ 이수역 (동작대로)
    {"coords": [(126.9670, 37.4865), (126.9678, 37.4878), (126.9685, 37.4890),
                (126.9640, 37.4910), (126.9635, 37.4925)], "type": "sidewalk", "width": 3.5},
    {"coords": [(126.9675, 37.4858), (126.9690, 37.4852)],
     "type": "crosswalk", "width": 5.0},
    {"coords": [(126.9630, 37.4918), (126.9645, 37.4922)],
     "type": "crosswalk", "width": 4.0},
    # 상도로
    {"coords": [(126.9330, 37.4970), (126.9345, 37.4980), (126.9360, 37.4990),
                (126.9380, 37.5000), (126.9400, 37.5010)], "type": "sidewalk", "width": 2.5},
    {"coords": [(126.9348, 37.4983), (126.9355, 37.4977)],
     "type": "crosswalk", "width": 3.5},
    # 흑석로
    {"coords": [(126.9550, 37.5060), (126.9565, 37.5068), (126.9580, 37.5075),
                (126.9595, 37.5080)], "type": "sidewalk", "width": 2.0},
    # 신대방역
    {"coords": [(126.9160, 37.4945), (126.9175, 37.4940), (126.9195, 37.4935),
                (126.9210, 37.4930)], "type": "sidewalk", "width": 2.5},
    # 대방역
    {"coords": [(126.9225, 37.5095), (126.9240, 37.5088), (126.9258, 37.5082)],
     "type": "sidewalk", "width": 2.0},
    # 사당5동
    {"coords": [(126.9795, 37.4845), (126.9810, 37.4838), (126.9825, 37.4832)],
     "type": "sidewalk", "width": 2.0},
    # 남성대로 (사당3동)
    {"coords": [(126.9680, 37.4910), (126.9690, 37.4925), (126.9695, 37.4940),
                (126.9700, 37.4955)], "type": "sidewalk", "width": 3.0},
]


def _gaussian_field(df: pd.DataFrame, centers, base=1.0, peak=20.0) -> np.ndarray:
    """centers: (lon, lat, sigma) 또는 (lon, lat, sigma, category) 튜플 리스트."""
    vals = np.full(len(df), base)
    for c in centers:
        cx, cy, s = c[0], c[1], c[2]
        d2 = (df["lon"] - cx) ** 2 + (df["lat"] - cy) ** 2
        vals = vals + peak * np.exp(-d2 / (2 * s ** 2))
    return vals


def _pop_at_hour(sample_points: pd.DataFrame, hour: int,
                 base: float = 50, peak: float = 800) -> np.ndarray:
    """특정 시간대의 유동인구 필드. 역세권/시장 카테고리별 시간 프로파일 반영."""
    vals = np.full(len(sample_points), base)
    for cx, cy, s, cat in _HOTSPOTS["pop"]:
        profile = _POP_HOURLY_PROFILE.get(cat, _POP_HOURLY_PROFILE["market"])
        intensity = profile.get(hour, 0.5)
        d2 = (sample_points["lon"] - cx) ** 2 + (sample_points["lat"] - cy) ** 2
        vals = vals + (peak * intensity) * np.exp(-d2 / (2 * s ** 2))
    return vals


def load_living_pop(sample_points: pd.DataFrame) -> pd.Series:
    """시간대 가중 유동인구 (오후 1~3시 피크 가중).

    실데이터: CSV 에 `hour` 컬럼이 있으면 시간 가중 평균, 없으면 단순 평균.
    더미: 역세권/시장 카테고리별 시간 프로파일에 HOUR_WEIGHTS 적용.
    """
    fp = DATA_RAW / "living_pop_dongjak.csv"
    if fp.exists():
        real = pd.read_csv(fp)
        if "hour" in real.columns:
            # 시간별 그룹핑 후 HOUR_WEIGHTS 가중 평균
            w_total, v_total = 0.0, None
            for h, w in HOUR_WEIGHTS.items():
                hr = real[real["hour"] == h]
                if hr.empty:
                    continue
                v = _nearest_value(sample_points, hr, "pop").values
                v_total = v * w if v_total is None else v_total + v * w
                w_total += w
            if v_total is not None and w_total > 0:
                return pd.Series(v_total / w_total, name="pop")
        return _nearest_value(sample_points, real, "pop")

    # 더미: 각 시간대 필드 생성 → HOUR_WEIGHTS 가중 평균
    w_sum = 0.0
    acc = np.zeros(len(sample_points))
    for h, w in HOUR_WEIGHTS.items():
        acc += w * _pop_at_hour(sample_points, h)
        w_sum += w
    return pd.Series(acc / w_sum, name="pop")


# LST 일중 변동 프로파일 (오후 1~3시 최고)
_LST_HOURLY_PROFILE = {
     9: 0.5, 10: 0.65, 11: 0.8, 12: 0.9,
    13: 1.0, 14: 1.0, 15: 0.95, 16: 0.85,
    17: 0.7, 18: 0.55,
}


def load_lst(sample_points: pd.DataFrame) -> pd.Series:
    """지표면 온도 (°C). 오후 피크 시간대 가중 평균으로 폭염 취약 지점 부각."""
    fp = DATA_RAW / "lst_dongjak.csv"
    if fp.exists():
        real = pd.read_csv(fp)
        return _nearest_value(sample_points, real, "lst_c")

    # 더미: base = 32°C 기준, 시간별 peak 변동
    base = 32.0
    peak_max = 6.0
    w_sum = 0.0
    acc = np.zeros(len(sample_points))
    for h, w in HOUR_WEIGHTS.items():
        intensity = _LST_HOURLY_PROFILE.get(h, 0.7)
        field = _gaussian_field(sample_points, _HOTSPOTS["lst"],
                                base=base, peak=peak_max * intensity)
        acc += w * field
        w_sum += w
    return pd.Series(acc / w_sum, name="lst_c")


def load_vuln_ratio(sample_points: pd.DataFrame) -> pd.Series:
    """취약계층 비율 (0~1). 동 단위 더미."""
    fp = DATA_RAW / "vuln_dongjak.csv"
    if fp.exists():
        real = pd.read_csv(fp)
        return _nearest_value(sample_points, real, "vuln_ratio")
    raw = _gaussian_field(sample_points, _HOTSPOTS["vuln"], base=0.10, peak=0.15)
    return pd.Series(np.clip(raw, 0, 1), name="vuln_ratio")


def load_existing_shades() -> gpd.GeoDataFrame:
    """기존 그늘막 포인트. 더미는 보행로 위 중간지점에 배치."""
    fp = DATA_RAW / "existing_shades.csv"
    if fp.exists():
        df = pd.read_csv(fp)
    else:
        coords = []
        for route in _PEDESTRIAN_ROUTES[:6]:
            c = route["coords"]
            mid = c[len(c) // 2]
            coords.append({"lon": mid[0], "lat": mid[1]})
        df = pd.DataFrame(coords)
    geom = [Point(xy) for xy in zip(df["lon"], df["lat"])]
    return gpd.GeoDataFrame(df, geometry=geom, crs=CRS_WGS84)


def load_buildings() -> gpd.GeoDataFrame:
    """건물 footprint + 높이. 자연 그늘 시뮬레이션용.

    실데이터: data/raw/buildings.geojson (Polygon, attr: height_m)
    더미: 동작구 주요 건물군을 원형 footprint로 근사.
    """
    fp = DATA_RAW / "buildings.geojson"
    if fp.exists():
        return gpd.read_file(fp).to_crs(CRS_WGS84)

    # 더미: 미터 단위 buffer 를 위해 일단 WGS84 점 → EPSG:5179 변환 → buffer → WGS84 복귀
    pts_wgs = gpd.GeoSeries(
        [Point(lon, lat) for lon, lat, _r, _h in _BUILDINGS],
        crs=CRS_WGS84,
    )
    pts_m = pts_wgs.to_crs(CRS_KOREA)
    polys_m = [pt.buffer(r) for pt, (_, _, r, _) in zip(pts_m, _BUILDINGS)]
    polys_wgs = gpd.GeoSeries(polys_m, crs=CRS_KOREA).to_crs(CRS_WGS84)
    return gpd.GeoDataFrame(
        {"height_m": [h for _l, _t, _r, h in _BUILDINGS]},
        geometry=list(polys_wgs.values),
        crs=CRS_WGS84,
    )


def load_natural_shade(grid: gpd.GeoDataFrame) -> pd.Series:
    """각 격자 셀의 자연 그늘 커버 비율 [0,1].

    오후 폭염 피크(SUN_ALTITUDE_DEG / SUN_AZIMUTH_DEG) 기준으로
    건물 footprint 를 태양 반대 방향으로 평행이동 + convex hull → 그림자 영역.
    셀 polygon 과의 intersection 면적 / 셀 면적.
    """
    buildings = load_buildings()
    if buildings.empty:
        return pd.Series(np.zeros(len(grid)), name="natural")

    buildings_m = buildings.to_crs(CRS_KOREA)
    alt = radians(SUN_ALTITUDE_DEG)
    az = radians(SUN_AZIMUTH_DEG)

    # 그림자 변위: 태양 방위 반대 방향, 길이 = h / tan(alt)
    # 격자 평면(EPSG:5179): x=동쪽+, y=북쪽+. 방위 az(북=0, 시계방향).
    # 태양 반대 방향 단위벡터 = (-sin(az), -cos(az))
    inv_tan_alt = 1.0 / tan(alt)
    shadows = []
    for _, b in buildings_m.iterrows():
        h = float(b["height_m"])
        L = h * inv_tan_alt
        dx = -sin(az) * L
        dy = -cos(az) * L
        translated = translate(b.geometry, xoff=dx, yoff=dy)
        shadows.append(unary_union([b.geometry, translated]).convex_hull)

    shadow_union = unary_union(shadows)
    grid_m = grid if grid.crs == CRS_KOREA else grid.to_crs(CRS_KOREA)
    inter = grid_m.geometry.intersection(shadow_union).area
    cover = (inter / grid_m.geometry.area).clip(0, 1)
    return pd.Series(cover.values, name="natural")


def load_pedestrian_network() -> gpd.GeoDataFrame:
    """보행로 + 횡단보도 네트워크 (LineString)."""
    fp = DATA_RAW / "pedestrian.geojson"
    if fp.exists():
        return gpd.read_file(fp).to_crs(CRS_WGS84)
    lines = [{
        "geometry": LineString(r["coords"]),
        "type": r["type"],
        "width": r["width"],
    } for r in _PEDESTRIAN_ROUTES]
    return gpd.GeoDataFrame(lines, crs=CRS_WGS84)


def load_sidewalks() -> gpd.GeoDataFrame | None:
    """하위 호환 — pedestrian_network 반환."""
    return load_pedestrian_network()


def _nearest_value(sample_points: pd.DataFrame, real: pd.DataFrame, col: str) -> pd.Series:
    """샘플 포인트별로 실데이터 중 가장 가까운 행의 값을 할당 (간이 NN)."""
    from scipy.spatial import cKDTree
    tree = cKDTree(real[["lon", "lat"]].to_numpy())
    _, idx = tree.query(sample_points[["lon", "lat"]].to_numpy(), k=1)
    return pd.Series(real[col].to_numpy()[idx], name=col)
