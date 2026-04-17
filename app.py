"""동작구 그늘막 입지 — 가중치 슬라이더 대시보드 (Streamlit).

실행:
    streamlit run app.py

격자·기본 피처는 1회 캐싱하고, 가중치만 바꿔 실시간 재스코어링.
"""
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from src.grid import build_grid
from src.scoring import compute_scores, rescore_from_features
from src.filtering import pick_candidates
from src.visualization import build_map
from src.config import SCENARIOS, WEIGHTS, OUTPUT


st.set_page_config(page_title="동작구 그늘막 대시보드",
                    layout="wide",
                    initial_sidebar_state="expanded")
st.title("☀️ 동작구 여름 그늘막 입지 대시보드")
st.caption("가중치 슬라이더를 움직이면 TOP 10 추천이 실시간 재계산됩니다. "
           "(피처는 1회 캐싱 → 슬라이더 반응은 가중합 재계산만)")


@st.cache_resource(show_spinner="격자 + 기본 피처 산출 중...")
def _load_base():
    """격자 + 기본 스코어(피처 캐시용)는 1회만 계산."""
    grid = build_grid()
    scored = compute_scores(grid)
    return scored


scored_base = _load_base()

# ─────────────────────────────────────────────────────────────
# 사이드바: 시나리오 프리셋 + 가중치 슬라이더
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 시나리오 프리셋")
    preset_names = ["사용자 지정"] + list(SCENARIOS.keys())
    preset = st.selectbox("프리셋 선택", preset_names, index=1,
                           help="프리셋 선택 시 슬라이더 기본값이 갱신됩니다.")
    defaults = SCENARIOS[preset] if preset != "사용자 지정" else WEIGHTS

    st.header("🎚 가중치")
    st.caption("양수: 클수록 우선 / 음수: 페널티")
    w_pop = st.slider("유동인구 (popdens)",
                      0.0, 0.8, float(defaults["popdens"]), 0.05)
    w_lst = st.slider("지표온도 (lst)",
                      0.0, 0.8, float(defaults["lst"]), 0.05)
    w_vuln = st.slider("취약계층 (vuln)",
                       0.0, 0.8, float(defaults["vuln"]), 0.05)
    w_shade = st.slider("기존그늘막 페널티 (shade)",
                        -0.4, 0.0, float(defaults["shade"]), 0.05)
    w_nat = st.slider("자연그늘 페널티 (natural)",
                      -0.4, 0.0, float(defaults["natural"]), 0.05)

    weights = {"popdens": w_pop, "lst": w_lst, "vuln": w_vuln,
               "shade": w_shade, "natural": w_nat}
    total = sum(weights.values())
    st.metric("가중치 합", f"{total:+.2f}",
              help="권장: 양수 합계 ≈ 0.8, 합계 ≈ 0.6 ~ 0.8")

# ─────────────────────────────────────────────────────────────
# 본문: 재스코어링 → TOP 후보 → 지도 + 표
# ─────────────────────────────────────────────────────────────
rescored = rescore_from_features(scored_base, weights)
top = pick_candidates(rescored)

col_map, col_tbl = st.columns([5, 4])

with col_map:
    st.subheader(f"🗺 TOP {len(top)} 추천 지도")
    map_path = build_map(rescored.to_crs("EPSG:4326"), top,
                          filename="dashboard_map.html")
    with open(map_path, "r", encoding="utf-8") as f:
        components.html(f.read(), height=620, scrolling=False)

with col_tbl:
    st.subheader("📊 TOP 10 표")
    if len(top) == 0:
        st.warning("필터 통과 후보가 없습니다. 가중치를 조정해 주세요.")
    else:
        df = top[["lat", "lon", "score", "pop", "lst_c",
                  "vuln_ratio", "natural"]].copy()
        df.insert(0, "rank", range(1, len(df) + 1))
        df["score"] = df["score"].round(3)
        df["pop"] = df["pop"].round(0).astype(int)
        df["lst_c"] = df["lst_c"].round(1)
        df["vuln_ratio"] = (df["vuln_ratio"] * 100).round(1)
        df["natural"] = df["natural"].round(2)
        df = df.rename(columns={
            "lat": "위도", "lon": "경도", "score": "점수",
            "pop": "유동인구", "lst_c": "LST(℃)",
            "vuln_ratio": "취약(%)", "natural": "자연그늘",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 현재 가중치")
    st.json(weights)

    if len(top) > 0:
        st.markdown("#### 통계")
        c1, c2, c3 = st.columns(3)
        c1.metric("최고 점수", f"{top['score'].max():.3f}")
        c2.metric("평균 LST", f"{top['lst_c'].mean():.1f}℃")
        c3.metric("평균 유동", f"{top['pop'].mean():.0f}")

st.markdown("---")
st.caption(
    "산출물 디렉토리: " + str(OUTPUT)
    + "  ·  지도 파일: dashboard_map.html (매 조작 시 갱신)"
)
