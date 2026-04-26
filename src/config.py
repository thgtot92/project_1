"""프로젝트 전역 설정"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"

# .env 자동 로딩 (없어도 무해)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# 외부 API 키 (없으면 None — 더미 fallback)
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
MAPILLARY_TOKEN = os.getenv("MAPILLARY_TOKEN")

# 동작구 대략 경계 (WGS84, lon/lat)
DONGJAK_BBOX = {
    "min_lon": 126.9100,
    "max_lon": 126.9900,
    "min_lat": 37.4750,
    "max_lat": 37.5200,
}
DONGJAK_CENTER = (37.5124, 126.9393)

# 좌표계
CRS_WGS84 = "EPSG:4326"
CRS_KOREA = "EPSG:5179"   # 격자 분석은 미터 단위로

# 격자 한 변 길이 (m)
GRID_SIZE_M = 100

# 스코어 가중치 (합 = 1.0 권장, 음수 항목은 페널티)
# streetview_deficit: 거리뷰 segmentation으로 산출한 그늘 결핍 지수 (CV-B)
WEIGHTS = {
    "popdens":            0.25,    # 유동인구
    "lst":                0.25,    # 지표면 온도
    "vuln":               0.20,    # 취약계층 가중치
    "shade":             -0.15,    # 기존 그늘막 커버리지 (페널티)
    "natural":           -0.05,    # 건물 자연 그늘 (CV-A)
    "streetview_deficit": 0.15,    # 거리뷰 그늘 결핍 (CV-B)
}

# 시나리오 프리셋 (정책 관점별 가중치)
SCENARIOS = {
    "기본": {
        "popdens": 0.25, "lst": 0.25, "vuln": 0.20,
        "shade": -0.15, "natural": -0.05, "streetview_deficit": 0.15,
    },
    "고령자_중시": {
        "popdens": 0.15, "lst": 0.20, "vuln": 0.40,
        "shade": -0.10, "natural": -0.05, "streetview_deficit": 0.15,
    },
    "폭염_중시": {
        "popdens": 0.15, "lst": 0.40, "vuln": 0.15,
        "shade": -0.10, "natural": -0.10, "streetview_deficit": 0.15,
    },
    "유동인구_중시": {
        "popdens": 0.40, "lst": 0.15, "vuln": 0.15,
        "shade": -0.10, "natural": -0.05, "streetview_deficit": 0.20,
    },
    "보행환경_중시": {  # CV-B 강조 신규 시나리오
        "popdens": 0.15, "lst": 0.15, "vuln": 0.15,
        "shade": -0.10, "natural": -0.05, "streetview_deficit": 0.40,
    },
}


# 시간대 가중치 (폭염 스트레스 피크: 오후 1~3시)
# 핫한 시간대의 유동인구 · LST 에 가중치를 부여하여 평균보다 더 설치 필요한 곳을 부각
HOUR_WEIGHTS = {
     9: 0.3, 10: 0.5, 11: 0.7, 12: 0.9,
    13: 1.0, 14: 1.0, 15: 0.9, 16: 0.7,
    17: 0.5, 18: 0.3,
}

# 후보지 필터링 조건
FILTER = {
    "min_sidewalk_width_m": 2.0,
    "exclusion_radius_m": 150,   # 기존 그늘막 반경
    "top_k": 10,
}

# 자연 그늘 시뮬레이션 기준 태양 위치
# 서울(37.5°N, 127°E) · 7월 말 폭염 피크 · 오후 3시 KST 기준
# altitude(고도) 낮을수록 그림자 길어짐 / azimuth(방위, 북=0° 시계방향)
SUN_ALTITUDE_DEG = 52.0
SUN_AZIMUTH_DEG = 252.0       # 남서~서 사이 (그림자는 동쪽~북동쪽)

# 발표자료의 3대 집중구역 (검증 기준점)
FOCUS_AREAS = {
    "노량진역-수산시장 보행로": {
        "center": (37.5125, 126.9410),
        "radius_m": 300,
        "reason": "수험생 유동인구 최상위, 직사광선 노출 보행 구간",
    },
    "사당역4번-이수역 축": {
        "center": (37.4885, 126.9660),
        "radius_m": 400,
        "reason": "환승 대기 인구 밀집, 오후 열스트레스 급증",
    },
    "상도로 주거축": {
        "center": (37.4985, 126.9360),
        "radius_m": 300,
        "reason": "고령자 비율 높은 주거 밀집, 대체 그늘 부족",
    },
}

# LLM
LLM_MODEL = "gpt-4o-mini"
