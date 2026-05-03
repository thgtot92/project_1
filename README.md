# 동작구 여름 그늘막 설치 최적화

> 채권 트레이더의 다변수 최적화 방법론을 도시 공간 데이터에 이식한
> **그늘막 최적 입지 추천 시스템**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

데이터기반 도시설계 기말 프로젝트. 동작구를 100m 격자 3,672개로 나누고,
다변수 가중합 · 공간 필터 · 시나리오 민감도 · 자연그늘 시뮬레이션 + **2종 컴퓨터 비전**
(항공사진 SAM 건물 추출 + 거리뷰 SegFormer segmentation)을 거쳐
**TOP 10 최적 입지**와 **5개 정책 관점 모두에서 살아남는 강건 입지 3곳**을 도출합니다.

---

## 한 줄 요약

> 항공사진과 거리뷰까지 컴퓨터 비전으로 읽어내, 5가지 정책 관점 모두에서 살아남는
> 그늘막 강건 입지 **3곳**을 찾아냈다.

---

## 핵심 결과

### 강건 입지 (Robust Location) — 5개 시나리오 공통 추천

| # | 좌표 (lat, lon) | 구역 |
|---|---|---|
| 1 | 37.4907, 126.9647 | 동작대로 사당-이수 축 |
| 2 | 37.4898, 126.9670 | 동작대로 사당역 인근 |
| 3 | 37.5068, 126.9567 | **흑석동** (한강변 주거밀집) |

### 시나리오 민감도 (가중치 프리셋 5종)

| 시나리오 | 강조 | 최고 Score | 유니크 추천 |
|---|---|---|---|
| 기본 | 균형 (25/25/20) | 0.620 | 0곳 |
| 고령자 중시 | `vuln 0.40` | 0.585 | 0곳 |
| 폭염 중시 | `lst 0.40` | 0.664 | 1곳 독점 |
| 유동인구 중시 | `pop 0.40` | **0.726** | 3곳 독점 |
| **보행환경 중시 (NEW)** | `streetview_deficit 0.40` | 0.665 | 0곳 |

### 1차 발표 3대 집중구역 정량 검증

| 구역 | 판정 | 반경 내 TOP | 최근접 거리 |
|---|---|---|---|
| 노량진역-수산시장 | △ | 0곳 | 1,355m |
| 사당역-이수역 축 | ✓ | 2곳 (TOP1·TOP2) | 167m |
| 상도로 주거축 | ✓ | 3곳 (TOP5~7) | 66m |

> 노량진 "0곳"은 실패가 아님 — 기존 그늘막 150m 제약이 의도대로 작동한 결과.

---

## 알고리즘

```
Score = 0.25·popdens + 0.25·lst + 0.20·vuln
      − 0.15·shade − 0.05·natural          (CV-A 활성)
      + 0.15·streetview_deficit            (CV-B 활성, NEW)
        (모든 피처 MinMax 정규화 후 가중합)
```

| 피처 | 의미 | 산출 방법 |
|---|---|---|
| `popdens` (+) | 유동인구 | 시간대 가중 평균 (9~18시, 오후 피크 1.0) |
| `lst` (+) | 지표면 온도 | 오후 피크 가중 |
| `vuln` (+) | 취약계층 비율 | 상수 (연령 구조) |
| `shade` (−) | 기존 그늘막 커버리지 | 반경 150m 내 개수 |
| `natural` (−) | 자연 그늘 (건물 그림자) | **CV-A** SAM 추출 건물 + 오후 3시 태양위치 |
| `streetview_deficit` (+) | 거리뷰 그늘 결핍 | **CV-B** SegFormer 19-class · `walkable × (1−building−vegetation)` |

### 사용한 기법

**기존 MCDA 코어**
- 선형 가중합 (Linear Weighted Sum) + Min-Max 정규화
- 공간 버퍼 + 교집합 (보행로 20m + 그늘막 150m 외)
- 파라미터 스윕 (5개 시나리오 × 동일 피처셋)
- 집합 교집합 (∩ across scenarios → 강건 입지)

**CV 통합 (NEW)**
- **CV-A — Mobile-SAM** (Meta, 2023): V-World z15 항공사진 48타일 합성 →
  zero-shot segmentation → 면적·종횡비·밝기 필터로 건물 30동 자동 추출
- **CV-B — SegFormer** (NVIDIA, 2021, CityScapes pretrained):
  Mapillary 거리뷰 동작구 1,249장 → 19-class segmentation →
  보행 공간 비율 × (1 − 그늘 자원 비율)
- **기하학적 그림자 시뮬레이션** (`shapely.affinity.translate` + convex hull,
  서울 7월 말 오후 3시: 고도 52° · 방위 252°)

> MCDA 코어는 설명가능성을 위해 선형 유지, 데이터 품질만 컴퓨터 비전으로 끌어올림.

---

## 파이프라인

```
[CV-A] V-World 항공사진(z15) + Mobile-SAM
        → 실측 건물 30동 → 자연그늘 시뮬레이션 입력 자동 교체
        │
[동작구 100m 격자 3,672개]
        │
        ▼   시간대별(9~18시) × 역세권/시장 프로파일 × HOUR_WEIGHTS
  STEP 1  필요도 스코어 (5 피처)
        │
        ▼   보행로/횡단보도 20m 이내 · 기존 그늘막 150m 외
  STEP 2  공간 필터   3,672 → 23 → 19
        │
[CV-B] Mapillary 거리뷰(1,249장) + SegFormer (CityScapes)
        → 19개 후보 격자 매핑 → shade_deficit 산출
        → 6번째 피처로 Score 식 통합 (재스코어링)
        │
        ▼   5개 시나리오 (기본·고령자·폭염·유동인구·보행환경)
  STEP 3  TOP 10 × 시나리오 + LLM 설치 근거 자동 생성
```

**처음 실행 시** CV-A·CV-B가 자동 실행되어 캐시 생성.
이후 실행은 `data/raw/buildings.geojson` + `data/processed/grid_streetview.csv`
캐시를 사용하므로 빠릅니다.

---

## 실행 방법

```bash
# 1회만
pip install -r requirements.txt

# 기본 파이프라인 실행 (Windows 콘솔 한글 출력)
python -X utf8 main.py
# → output/shade_map.html, scenarios_map.html, rationales.json 등 생성

# 인터랙티브 대시보드 (가중치 슬라이더로 TOP 10 실시간 재계산)
streamlit run app.py
# → http://localhost:8501

# 최종 발표자료 PPTX 재생성
python -X utf8 presentation/generate_pptx.py

# reveal.js 슬라이드 (iframe으로 지도 임베드 → 정적 서버 필요)
python -m http.server 8000
# → http://localhost:8000/presentation/slides.html
```

### 외부 API 키 (선택)

`.env` 파일에 다음 키들을 두면 CV·LLM 단계가 활성화됩니다 (없어도 더미 fallback).

```bash
# .env (gitignore 처리됨)
VWORLD_API_KEY=...      # V-World 항공사진 (CV-A) - 무료, vworld.kr
MAPILLARY_TOKEN=MLY|... # Mapillary 거리뷰 (CV-B) - 무료, mapillary.com/dashboard/developers
OPENAI_API_KEY=sk-...   # GPT-4o-mini LLM 근거 (선택)
```

---

## 디렉토리 구조

```
project_1/
├── main.py                       # 6단계 파이프라인 엔트리포인트
├── app.py                        # Streamlit 대시보드
├── requirements.txt
├── README.md
├── RESULTS.md                    # 결과 요약 (슬라이드용)
├── WORKLOG.md                    # 전체 작업 로그 · TODO · 재개 프롬프트
├── src/
│   ├── config.py                 # bbox, WEIGHTS, HOUR_WEIGHTS, SCENARIOS,
│   │                              FOCUS_AREAS, FILTER, SUN_ALTITUDE/AZIMUTH
│   ├── grid.py                   # 100m 격자 생성 (EPSG:5179)
│   ├── data_loader.py            # 5종 데이터 로더 + 시간 프로파일
│   │                              + 보행로 네트워크 + 건물 footprint
│   │                              + streetview_deficit 로더 (CV-B)
│   ├── cv_buildings.py           # CV-A: V-World 항공사진 + Mobile-SAM
│   ├── cv_streetview.py          # CV-B: Mapillary + SegFormer (CityScapes)
│   ├── scoring.py                # STEP 1: compute_scores + rescore_from_features
│   ├── filtering.py              # STEP 2: 보행로 20m + 기존그늘막 150m 제외
│   ├── visualization.py          # Folium 지도
│   ├── scenarios.py              # 시나리오 4개 실행·비교 + 비교 지도
│   ├── validation.py             # 발표 3대 구역 정량 검증
│   └── llm_rationale.py          # STEP 3: LLM 근거 (룰베이스 fallback)
├── presentation/
│   ├── generate_pptx.py          # PPTX 자동 생성 스크립트
│   ├── slides.html               # reveal.js 슬라이드 (iframe 지도 임베드)
│   └── 동작구_그늘막_최종발표.pptx  # 12장, 16:9
├── data/
│   ├── raw/                      # 실데이터 배치 위치 (*.csv, *.geojson)
│   └── processed/
└── output/
    ├── shade_map.html            # 기본 시나리오 TOP 10 지도
    ├── scenarios_map.html        # 4개 시나리오 토글 비교 지도
    ├── scenarios_comparison.csv  # 시나리오×TOP10 비교표
    ├── scenarios_overlap.json    # 중복/유니크 분석
    ├── focus_areas_validation.json  # 3대 구역 검증
    └── rationales.json           # LLM 설치 근거
```

---

## 데이터 (5종)

| # | 데이터 | 출처 | 배치 파일 | 현재 |
|---|---|---|---|---|
| 1 | 생활인구 (시간대별) | 서울 열린데이터광장 SKT | `data/raw/living_pop_dongjak.csv` | 더미 |
| 2 | 지표면 온도 LST | 서울연구원 Landsat | `data/raw/lst_dongjak.csv` | 더미 |
| 3 | 취약계층 비율 | KOSIS 동작구 | `data/raw/vuln_dongjak.csv` | 더미 |
| 4 | 기존 그늘막 위치 | 서울 열린데이터광장 | `data/raw/existing_shades.csv` | 더미 |
| 5 | 인도·횡단보도 | 국가공간정보포털 | `data/raw/pedestrian.geojson` | 더미 |

> `data/raw/` 에 실데이터를 넣으면 `data_loader.py` 가 자동으로 전환.
> 현재 더미 데이터는 동작구 실제 거점(역세권·시장·주거축) 기반으로 재현 가능하게 생성.

---

## 한계와 다음 단계

| 한계 | 해결 방향 |
|---|---|
| 5종 데이터 모두 더미 | 서울 열린데이터광장 API 연결 |
| LST 래스터 미연결 | Landsat 8 Level-2 ST_B10 밴드 |
| 건물 footprint 더미 19개 | 국가공간정보포털 건물shp 교체 |
| 인도 폭 정보 부재 | 도로대장 shp |
| 예산 제약 미반영 | 배낭 최적화 (K개 예산 내 최적 조합) |

---

## 작성자

- 한영재 (`thgtot92@naver.com`)
- 인공지능융합대학원 인공지능컴퓨팅 · 2025961227
- 수업: 데이터기반 도시설계 (2026 봄학기 기말 프로젝트)

## License

[MIT](LICENSE)

## 참고

- 서울 열린데이터광장: <https://data.seoul.go.kr>
- 국가공간정보포털: <https://www.nsdi.go.kr>
- KOSIS 국가통계포털: <https://kosis.kr>
