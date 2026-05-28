# 동작구 여름 그늘막 최적 입지 추천 시스템 — 작업 로그

> 최종 업데이트: 2026-04-16
> 작성자: 한영재 (인공지능융합대학원 / 2025961227)
> 수업: 데이터기반 도시설계 — 기말 프로젝트
> **발표용 요약은 [RESULTS.md](RESULTS.md) 참고**

---

## 1. 프로젝트 정체성

- **주제**: 동작구 여름 그늘막 **최적 입지 추천 시스템**
- **관점**: 다기준 의사결정(MCDA) + 컴퓨터비전 + GIS 통합한 데이터 기반 입지 추천
- **핵심 질문**: *어느 위치에 설치할 것인가?* (민원·직관이 아닌 데이터 파이프라인으로 해결)
- **1차 발표**: [도시설계_1차_발표자료.pdf](도시설계_1차_발표자료.pdf)

---

## 2. 현재까지 진행 상태 ✅

### 완료
- [x] 프로젝트 디렉토리 및 의존성 골격
- [x] 동작구 100m 격자 생성기 (3,672 cells)
- [x] 5종 데이터 로더 — 실데이터 ↔ 더미 데이터 자동 스위칭
- [x] STEP 1. 필요도 스코어링 (가중합 + MinMax 정규화)
- [x] STEP 2. GIS 공간 필터링
- [x] STEP 3. LLM 자연어 근거 생성 (OpenAI 키 없으면 룰베이스)
- [x] Folium 히트맵 + TOP 10 마커 지도 + 레이어 컨트롤
- [x] **더미 데이터를 동작구 실제 거점(역세권·시장·주거축) 기반으로 고정**
- [x] **보행로·횡단보도 LineString 네트워크 + 20m 이내 강제 제약** — 강변·건물 후보 원천 제외
- [x] **시간대 가중 스코어링** (9~18시 HOUR_WEIGHTS, 오후 1~3시 피크)
- [x] **역세권(출퇴근)·시장(오후 피크) 프로파일 분리**
- [x] **LST 시간대 가중 평균** (오후 피크 반영)
- [x] **시나리오 분석** — 4개 프리셋 (기본/고령자/폭염/유동인구)
- [x] **강건 입지 (robust location) 식별** — 시나리오 불변 N곳
- [x] **발표자료 3대 집중구역 일치도 검증** (사당-이수 2곳, 상도로 3곳 일치)
- [x] **발표용 요약 RESULTS.md 생성**
- [x] **자연 그늘 활성화** — 동작구 주요 건물군 + 오후 3시(고도 52°/방위 252°) 그림자 시뮬레이션 → 격자별 커버 비율로 `natural` 페널티 부여
- [x] **Streamlit 대시보드** — 가중치 슬라이더 + 시나리오 프리셋 → TOP 10 실시간 재계산 (`app.py`)
- [x] **최종 발표자료** — PPTX(12장, 16:9) + reveal.js HTML 두 종 (`presentation/`)
- [x] **CV-A: V-World 항공사진 + Mobile-SAM** — 동작구 BBOX z15 48타일 → SAM zero-shot → 실측 건물 30동 추출 → `data/raw/buildings.geojson` (자연그늘 시뮬레이션 입력 자동 교체)
- [x] **CV-B: Mapillary 거리뷰 + SegFormer (CityScapes 19 classes)** — 동작구 1,302장 거리뷰 → 19개 후보 격자 매핑 → `shade_deficit = walkable × (1 − building − vegetation)` 산출 → Score 식 6번째 피처
- [x] **NGII 흑석동 실측 건물 3,775동 통합** — `data_loader.load_buildings()` 가 SAM 30동(동작구) + NGII 3,775동(흑석동) 자동 union
- [x] **CV-DSM 흑석동 정밀 그림자 (Deep Umbra 영감)** — DSM−DEM=nDSM + 4시점(10·12·14·16시) ray-cast 누적 그림자 → 흑석동 309격자에 적용
- [x] **OSMnx 교차로 추출** — 동작구 walkable highway 그래프 → 교차로 노드 GeoJSON → 격자 반경 80m 내 교차로 밀도 (격자 평균 2.02개, max 27) → Score 식 7번째 피처
- [x] **시나리오 6개로 확장** — `보행환경_중시` + `교차로_중시` 신규
- [x] **보행로 필터를 OSMnx walkable edges 로 교체** (더미 14개 라인 → OSMnx 수천 edges + 더미 union, buffer 20m → **5m**)
- [x] **NGII 건물 안 centroid 컷 필터 신설** — 100m 격자 중심이 건물(또는 5m inset) 안이면 자동 제외 → "건물 위 추천" 시각적 오류 차단
- [x] **OSMnx 횡단보도(highway=crossing) 통합** — `osm_crossings.geojson`
- [x] **교차로 + 횡단보도 union → "보행자 결집 지점"** 으로 통합 사용 (밀도 피처 + 50m 근접 필터)
- [x] **교차로/횡단보도 50m 근접 필터** 신설 — 격자 centroid 가 결집지점 50m 이내만 통과
- [x] **`intersection_density` 가중치 0.10 → 0.20** (보행자 결집 강조), 다른 양수 항목 재배분
- [x] **결과**: 노량진역-수산시장 ✓ (TOP6 진입, 이전 △ 1521m → 291m), 사당-이수 4곳, 동작구 후보 풀 434 → **330** 격자
- [x] heukseok_focus.html v3 — 보행 도로·교차로·횡단보도·기존그늘막·TOP5 한 화면
- [x] **흑석동 실측 그늘막 18개 통합** — 사용자 제공, `data/raw/existing_shades.csv`
  (고정형 13 + 스마트형 5, 2019~2023 설치, 좌표·주소·설치일)
- [x] **횡단보도 다중 태그 검색** — 한국 OSM은 `footway=crossing` 우세
  → `highway/footway/crossing` 3종 통합 후 중복 제거 (동작구 306개)
- [x] **흑석동 focus map v7** — TOP 10 + 4종 카테고리(사각지대/보강/중간) +
  실측 그늘막 18개 + 최단거리 popup
- [x] **발표자료 PPTX/reveal.js v2** — 15장 새 구조
  (CV-DSM·NGII·OSMnx·횡단보도·흑석동실측 5개 슬라이드 신규/갱신)

### 실행 결과 (필터 보강 후: OSMnx 보행로 5m + 건물 컷)
- 격자 수: **3,672 cells**
  → 보행로 필터(OSMnx 5m) **449** → 그늘막 제외 446 → 건물 안 컷 **434**
- 시나리오별 최고 Score:
   - 기본 **0.551**, 고령자 0.518, 폭염 0.607, 유동인구 0.657,
   - 보행환경 0.600, 교차로 0.474
- 시나리오 유니크: 기본 0 / 고령자 8 / 폭염 0 / 유동인구 0 / 보행환경 0 / 교차로 1
- 모든 6개 시나리오 공통 강건 입지: **0곳**
  (필터 후보 풀이 5배 늘어나며 시나리오 간 추천 다양성 ↑)
- TOP10 평균 streetview_deficit: **0.259**
- 사당-이수 축: **7곳** (TOP1~5,8,10 모두 반경 400m 안)
- 상도로 / 노량진: TOP10 진입 못 함 (사당-이수 우세)
- 흑석동: 9격자 통과 (이전 155 → 9, 보행로+건물 컷)
- 산출물:
  - `output/shade_map.html` — 기본 TOP 10 지도
  - `output/scenarios_map.html` — 4개 시나리오 토글 비교
  - `output/scenarios_comparison.csv` — 40행 비교표
  - `output/scenarios_overlap.json` — 중복/유니크 분석
  - `output/focus_areas_validation.json` — 발표 구역 검증
  - `output/rationales.json` — LLM 설치 근거

---

## 3. 디렉토리 구조

```
project_1/
├── main.py                       # 6단계 파이프라인
├── app.py                        # Streamlit 대시보드 (가중치 슬라이더)
├── requirements.txt              # 의존성
├── WORKLOG.md                    # (이 파일)
├── RESULTS.md                    # 발표용 결과 요약
├── 가이드.txt                    # 과제 가이드
├── 도시설계_1차_발표자료.pdf    # 1차 발표
├── src/
│   ├── config.py                 # bbox, WEIGHTS, HOUR_WEIGHTS,
│   │                              SCENARIOS, FOCUS_AREAS, FILTER,
│   │                              SUN_ALTITUDE_DEG, SUN_AZIMUTH_DEG
│   ├── grid.py                   # 100m 격자 생성 (EPSG:5179)
│   ├── data_loader.py            # 5종 데이터 로더 + 시간 프로파일
│   │                              + 보행로·횡단보도 네트워크
│   │                              + 건물 footprint (SAM + NGII 흑석동 union)
│   │                              + 자연그늘 / streetview / intersection
│   │                              / 흑석동 DSM 누적 그림자 로더
│   ├── cv_buildings.py           # CV-A: V-World 항공사진 + Mobile-SAM
│   ├── cv_streetview.py          # CV-B: Mapillary + SegFormer (CityScapes)
│   ├── cv_dsm_heukseok.py        # CV-DSM: 흑석동 DSM-DEM 4시점 ray-cast (Deep Umbra 영감)
│   ├── osm_intersections.py      # OSMnx 교차로 추출 + 격자 밀도
│   ├── scoring.py                # STEP 1: compute_scores + rescore_from_features
│   ├── filtering.py              # STEP 2: 보행로 20m + 기존그늘막 150m 제외
│   ├── visualization.py          # Folium (레이어 컨트롤, 보행로·그늘막 오버레이)
│   ├── scenarios.py              # 4개 시나리오 실행·비교 + 비교 지도
│   ├── validation.py             # 발표 3대 구역 정량 검증
│   └── llm_rationale.py          # STEP 3: LLM 근거 (룰베이스 fallback)
├── presentation/                 # 최종 발표자료
│   ├── generate_pptx.py          # PPTX 자동 생성 스크립트
│   ├── 동작구_그늘막_최종발표.pptx  # 학교 제출용 (12장, 16:9)
│   └── slides.html               # reveal.js 슬라이드
│                                   (output/*.html iframe 임베드)
├── data/
│   ├── raw/                      # ← 실데이터 배치 위치
│   └── processed/
└── output/
    ├── shade_map.html            # 기본 시나리오 TOP 10 지도
    ├── scenarios_map.html        # 4개 시나리오 토글 비교 지도
    ├── scenarios_comparison.csv  # 시나리오×TOP10 비교표 (40행)
    ├── scenarios_overlap.json    # 중복/유니크 분석
    ├── focus_areas_validation.json  # 3대 구역 검증
    └── rationales.json           # LLM 설치 근거
```

---

## 4. 데이터 파이프라인 (5종)

| # | 데이터 | 출처 | 배치 파일명 | 필수 컬럼 | 현재 |
|---|---|---|---|---|---|
| 1 | 생활인구(시간대별) | 서울 열린데이터광장 SKT | `data/raw/living_pop_dongjak.csv` | `lon, lat, pop` | 더미 |
| 2 | 지표면 온도(LST) | 서울연구원 Landsat | `data/raw/lst_dongjak.csv` | `lon, lat, lst_c` | 더미 |
| 3 | 취약계층 비율 | KOSIS 동작구 연령별 | `data/raw/vuln_dongjak.csv` | `lon, lat, vuln_ratio` | 더미 |
| 4 | 기존 그늘막 위치 | 서울 열린데이터광장 | `data/raw/existing_shades.csv` | `lon, lat` | 더미 |
| 5 | 인도 공간정보 | 국가공간정보포털 | `data/raw/sidewalks.geojson` | `geometry, width` | 미확보 |

> **중요**: 위 파일명·컬럼만 맞춰 `data/raw/`에 넣으면 `data_loader.py`가 자동으로 실데이터로 전환합니다.

---

## 5. AI 알고리즘 (CV-A/B + DSM + OSMnx + NGII 통합)

```
CV-A: V-World 항공사진(z15 48타일) + Mobile-SAM zero-shot
        → buildings.geojson (실측 건물 30동, 동작구 전역)

CV-B: Mapillary 거리뷰(동작구 1,302장) + SegFormer (CityScapes 19 classes)
        → 후보 격자별 shade_deficit = walkable × (1 − building − vegetation)

CV-DSM (NEW, Deep Umbra 영감 — 강의자료 13p 추천 논문):
        흑석동 DSM−DEM=nDSM + 4시점(10·12·14·16시) ray-cast
        → 격자별 시간 누적 그림자 비율 (흑석동 한정)

OSMnx (NEW): 동작구 walkable highway → 교차로 노드(degree≥3) 추출
        → 격자 반경 80m 내 교차로 밀도 (보행자 결집)

NGII (NEW): 흑석동 실측 건물 3,775동(층수·HEGT)
        → CV-A SAM 30동과 union 후 자연그늘 입력으로 사용

STEP 1 — 7 피처 필요도 스코어
  Score = 0.22·pop + 0.22·lst + 0.18·vuln
        − 0.15·shadeCov − 0.05·natural (CV-A + DSM 결합)
        + 0.13·streetview_deficit         (CV-B)
        + 0.10·intersection_density       (OSMnx, NEW)
        (각 피처 MinMax 정규화 후 가중합)

STEP 2 — 공간 필터링
  · 보행로·횡단보도 20m 이내, 폭 ≥ 2m
  · 기존 그늘막 반경 150m 외
  · 상위 TOP 10

STEP 3 — 시나리오 6종 + LLM 근거
  · 기본 / 고령자 / 폭염 / 유동인구 / 보행환경 / 교차로(NEW)
  · OPENAI_API_KEY 있으면 gpt-4o-mini, 없으면 룰베이스
```

가중치는 `src/config.py` 의 `WEIGHTS` / `SCENARIOS` 에서 조정.

---

## 6. 실행 방법

```bash
# 1회만
pip install -r requirements.txt

# 실행 (Windows 콘솔에서 한글 출력)
python -X utf8 main.py

# 인터랙티브 대시보드 (가중치 슬라이더로 실시간 재계산)
streamlit run app.py
# → 브라우저에서 http://localhost:8501 자동 열림

# 최종 발표자료 생성 (PPTX, 12장 16:9)
python -X utf8 presentation/generate_pptx.py
# → presentation/동작구_그늘막_최종발표.pptx

# reveal.js 슬라이드 (iframe으로 output/*.html 임베드 → 정적 서버 필요)
python -m http.server 8000
# → http://localhost:8000/presentation/slides.html

# OpenAI 연동 시
set OPENAI_API_KEY=sk-...        # cmd
$env:OPENAI_API_KEY="sk-..."     # powershell
python -X utf8 main.py
```

산출물: `output/shade_map.html` (지도), `output/rationales.json` (근거)

---

## 7. 다음에 할 작업 (TODO)

### P0 — 실데이터 연결 (필수)
- [ ] 서울 열린데이터광장 **SKT 생활인구** → `data/raw/living_pop_dongjak.csv`
     (컬럼 `hour` 포함 시 시간 가중 자동 적용)
- [ ] 서울연구원 **Landsat LST** 타일 → `lst_dongjak.csv`
- [ ] 서울 열린데이터광장 **기존 그늘막 위치** → `existing_shades.csv`
- [ ] KOSIS **동작구 동별 65세↑·어린이 비율** → `vuln_dongjak.csv`
- [ ] 국가공간정보포털 **도로·보도 shp** → `pedestrian.geojson`
     (실제 보행로·횡단보도 LineString + width 속성)

### P1 — 알고리즘 고도화
- [x] ~~시간대별 인구 가중 (오후 1~3시 가중치 ↑)~~ 완료
- [x] ~~가중치 민감도 분석 (WEIGHTS 변경 시 TOP 10 변화 추적)~~ 완료
- [x] ~~**자연 그늘** 반영~~ 완료 → CV-A로 진화 (실측 건물 30동)
- [x] ~~**CV-A: SAM 건물 추출**~~ 완료 — V-World z15 + Mobile-SAM
- [x] ~~**CV-B: 거리뷰 segmentation**~~ 완료 — Mapillary + SegFormer CityScapes
- [ ] 격자 스코어 캐싱 (parquet 저장 → 재실행 속도 ↑)
- [ ] CV-B 매핑 거리 임계값(500m) 튜닝 — 더 많은 격자에 deficit 부여

### P2 — 발표·검증
- [x] ~~3대 집중구역 검증~~ 완료 (사당-이수 2곳, 상도로 3곳 일치)
- [x] ~~시나리오 분석: 고령자/폭염/유동인구 중시~~ 완료
- [x] ~~발표용 요약 (RESULTS.md)~~ 완료
- [x] ~~최종 발표자료 생성 (PPTX + reveal.js)~~ 완료 — `presentation/`
- [ ] PPTX placeholder 3곳에 실제 스크린샷 배치
     (shade_map / 건물-그림자 / Streamlit 대시보드)
- [ ] 현재 동작구 실제 그늘막과 TOP 10 비교 맵 (실데이터 연결 후)

### P3 — 확장 (선택)
- [x] ~~Streamlit 대시보드 (가중치 슬라이더 → 실시간 TOP 10 갱신)~~ 완료 (`streamlit run app.py`)
- [ ] 타 자치구 확장 (BBOX 만 바꾸면 재사용 가능)
- [ ] 예산 제약 하 최적화 (K개 중 예산 내 최적 조합 — 배낭 문제)

---

## 8. 재개 프롬프트 (Claude Code 재진입용)

> 아래 블록을 그대로 Claude Code 에 붙여 넣으면 작업을 이어받을 수 있습니다.

```
나는 동작구 여름 그늘막 최적 입지 추천 시스템을 개발 중이야 (수업: 데이터기반 도시설계 기말 프로젝트).
현재 디렉토리는 c:\Users\hanyoungjae\myPycode\myPycode\project_1 이고,
WORKLOG.md 에 프로젝트 개요·구조·진행 상태·TODO,
RESULTS.md 에 발표용 결과 요약이 있다.

작업 재개 전에 다음을 수행해줘:
1. WORKLOG.md 와 RESULTS.md 를 읽고 전체 맥락을 파악한다.
2. src/config.py, main.py, src/scoring.py, src/filtering.py, src/scenarios.py 를
   훑어 현재 알고리즘 상태(시간 가중·보행로 제약·시나리오 4종)를 확인한다.
3. data/raw/ 를 확인해 실데이터가 추가됐는지 체크한다.
4. python -X utf8 main.py 가 정상 동작하는지 한 번 실행해 확인한다.
5. 확인 후 "현재 진행 상태 요약 + 오늘 가능한 다음 작업 후보 3개"를 제시한다.
   사용자 선택 후에만 실제 코드 수정을 시작한다.

현재 완료된 핵심:
- 동작구 100m 격자 (3,672) → 보행로·횡단보도 20m 필터 → 19 후보 → TOP 10
- 시간대 가중 스코어링 (9~18시, 오후 1~3시 피크 1.0)
- 역세권(출퇴근)·시장(오후) 프로파일 분리, LST 오후 피크 반영
- 4개 시나리오 (기본/고령자/폭염/유동인구) + 강건 입지 3곳 식별
- 발표자료 3대 집중구역 정량 검증 (사당-이수 2곳, 상도로 3곳 일치)
- 자연그늘 시뮬레이션 활성화 (건물 footprint + 오후 3시 태양위치)
- Streamlit 대시보드 (`app.py`, 가중치 슬라이더 + 시나리오 프리셋)

원칙:
- MCDA 프레임 유지: pop/lst/vuln(+) - shade/natural(-) + sv/intersection(+) 가중합.
- 좌표계: 분석용 EPSG:5179 ↔ 시각화용 EPSG:4326.
- 실데이터가 data/raw/ 에 있으면 자동 사용, 없으면 data_loader.py 의
  동작구 실제 거점(역세권·시장·주거축) 기반 더미 데이터로 파이프라인 유지.
- 추천 후보는 반드시 보행로·횡단보도 위에만 — 강변/건물 위 금지.
- 한국어 주석/출력. Windows 콘솔에서는 python -X utf8 main.py 로 실행.
- 긴 파일 전체 재작성보다는 작은 Edit 을 선호 (사용자가 변경을 검토하기 쉽도록).

작업 후에는 WORKLOG.md 의 "7. 다음에 할 작업" 과
"2. 현재까지 진행 상태" 를 업데이트해 다음 세션에서 이어갈 수 있게 해줘.
```

---

## 9. 참고 링크

- 서울 열린데이터광장: https://data.seoul.go.kr
- 국가공간정보포털: https://www.nsdi.go.kr
- KOSIS 국가통계포털: https://kosis.kr
- 서울연구원 Landsat LST 자료 (검색 키워드: "서울 도시열섬 Landsat")
