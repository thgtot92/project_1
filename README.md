# 동작구 여름 그늘막 설치 최적화

> 채권 트레이더의 다변수 최적화 방법론을 도시 공간 데이터에 이식한
> **그늘막 최적 입지 추천 시스템**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

데이터기반 도시설계 기말 프로젝트. 동작구를 100m 격자 3,672개로 나누고,
다변수 가중합 · 공간 필터 · 시나리오 민감도 · 자연그늘 시뮬레이션을 거쳐
**TOP 10 최적 입지**와 **정책 관점 불변 강건 입지 3곳**을 도출합니다.

---

## 한 줄 요약

> 데이터의 논리로, 어떤 정책 관점을 취하든 그늘막이 반드시 필요한 **3곳**을 찾아냈다.

---

## 핵심 결과

### 강건 입지 (Robust Location) — 4개 시나리오 공통 추천

| # | 좌표 (lat, lon) | 구역 |
|---|---|---|
| 1 | 37.4977, 126.9341 | 상도로 (상도3동 주거밀집) |
| 2 | 37.4986, 126.9353 | 상도로 (상도3동 주거밀집) |
| 3 | 37.4907, 126.9647 | 동작대로 사당-이수 축 |

### 시나리오 민감도 (가중치 프리셋 4종)

| 시나리오 | 강조 | 최고 Score | 유니크 추천 |
|---|---|---|---|
| 기본 | 균형 (30/30/20) | 0.574 | 0곳 |
| 고령자 중시 | `vuln 0.45` | **0.567** | 4곳 독점 |
| 폭염 중시 | `lst 0.45` | 0.617 | 0곳 |
| 유동인구 중시 | `pop 0.45` | 0.633 | 3곳 독점 |

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
Score = 0.30·popdens + 0.30·lst + 0.20·vuln − 0.15·shade − 0.05·natural
        (각 피처 MinMax 정규화 후 가중합)
```

| 피처 | 의미 | 시간 프로파일 |
|---|---|---|
| `popdens` (+) | 유동인구 | 9~18시, 오후 1~3시 피크 1.0 |
| `lst` (+) | 지표면 온도 | 오후 피크 가중 평균 |
| `vuln` (+) | 취약계층 비율 | 상수 (연령 구조) |
| `shade` (−) | 기존 그늘막 커버리지 | 반경 150m 내 개수 |
| `natural` (−) | 자연 그늘 (건물 그림자) | 오후 3시 기준 시뮬레이션 |

### 사용한 기법 (MCDA 기반, 딥러닝 사용 X)

- **선형 가중합** (Linear Weighted Sum, MCDA)
- **Min-Max 정규화** [0, 1]
- **공간 버퍼 + 교집합** (보행로 20m 이내 + 기존그늘막 150m 외)
- **시간대별 가중 평균** (역세권=출퇴근 / 시장=오후 피크 프로파일 분리)
- **기하학적 그림자 시뮬레이션** (`shapely.affinity.translate` + convex hull,
  서울 7월 말 오후 3시 태양위치 고도 52° · 방위 252°)
- **파라미터 스윕** (가중치 프리셋 4종 × 동일 피처셋)
- **집합 교집합** (∩ across scenarios → 강건 입지 식별)

> 설명가능성·반사실(counterfactual) 질문 대응이 중요해 의도적으로 선형 모델 채택.

---

## 파이프라인

```
[동작구 100m 격자 3,672개]
        │
        ▼   시간대별(9~18시) × 역세권/시장 프로파일 × HOUR_WEIGHTS
  STEP 1  필요도 스코어 (pop·lst·vuln · −shade·−natural)
        │
        ▼   보행로/횡단보도 20m 이내 · 기존 그늘막 150m 외
  STEP 2  공간 필터   3,672 → 23 → 19
        │
        ▼   4개 시나리오 (기본·고령자·폭염·유동인구)
  STEP 3  TOP 10 × 시나리오 + LLM 설치 근거 자동 생성
```

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

### OpenAI 연동 (선택)

```bash
# cmd
set OPENAI_API_KEY=sk-...
# powershell
$env:OPENAI_API_KEY="sk-..."
python -X utf8 main.py
```

키가 없으면 룰베이스 템플릿 fallback으로 자동 전환.

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
