"""시나리오 분석 — 가중치 프리셋별 TOP 10 비교.

각 시나리오를 동일한 피처셋 위에서 가중치만 바꿔 재스코어링 → 민감도 비교.
"""
from __future__ import annotations
import json
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm
from .config import SCENARIOS, DONGJAK_CENTER, OUTPUT
from .scoring import rescore_from_features
from .filtering import pick_candidates
from . import data_loader


# 시나리오별 대표 색상 (지도 마커용)
SCENARIO_COLORS = {
    "기본":         "#e53935",   # red
    "고령자_중시":  "#8e24aa",   # purple
    "폭염_중시":    "#fb8c00",   # orange
    "유동인구_중시":"#1e88e5",   # blue
}


def run_scenarios(base_scored: gpd.GeoDataFrame) -> dict:
    """모든 시나리오 실행. 반환: {name: top_candidates_gdf}"""
    results = {}
    for name, weights in SCENARIOS.items():
        rescored = rescore_from_features(base_scored, weights)
        top = pick_candidates(rescored)
        results[name] = top
        print(f"  [{name}] TOP {len(top)} 선정, 최고 score {top['score'].max():.3f}")
    return results


def comparison_table(scenario_results: dict) -> pd.DataFrame:
    """시나리오별 TOP 10 좌표 집합을 비교 테이블로 변환."""
    rows = []
    for name, top in scenario_results.items():
        for i, r in top.iterrows():
            rows.append({
                "scenario": name,
                "rank": i + 1,
                "lat": round(r["lat"], 5),
                "lon": round(r["lon"], 5),
                "score": round(float(r["score"]), 3),
                "pop": round(float(r["pop"]), 0),
                "lst_c": round(float(r["lst_c"]), 1),
                "vuln_ratio": round(float(r["vuln_ratio"]), 3),
            })
    return pd.DataFrame(rows)


def overlap_summary(scenario_results: dict) -> dict:
    """시나리오 간 TOP 10 중복 지점 분석 (격자 ID 기준 근사)."""
    # 격자 중심 좌표를 소수점 4자리로 반올림해 키로 사용
    def _key(r):
        return (round(r["lat"], 4), round(r["lon"], 4))

    sets = {name: set(_key(r) for _, r in top.iterrows())
            for name, top in scenario_results.items()}

    # 모든 시나리오에 공통으로 들어간 지점
    common_all = set.intersection(*sets.values()) if sets else set()

    # 쌍 간 중복 개수
    pairs = {}
    names = list(sets.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            pairs[f"{a} ∩ {b}"] = len(sets[a] & sets[b])

    return {
        "모든_시나리오_공통": len(common_all),
        "공통_좌표": [list(c) for c in common_all],
        "쌍별_중복": pairs,
        "시나리오별_유니크": {
            name: len(s - set.union(*[v for k, v in sets.items() if k != name]))
            for name, s in sets.items()
        },
    }


def build_comparison_map(scenario_results: dict,
                         base_scored: gpd.GeoDataFrame,
                         filename: str = "scenarios_map.html") -> str:
    """레이어 컨트롤로 시나리오 토글 가능한 지도."""
    m = folium.Map(location=DONGJAK_CENTER, zoom_start=14, tiles="CartoDB positron")

    # 보행로 항상 표시
    ped = data_loader.load_pedestrian_network()
    if ped is not None and not ped.empty:
        ped_fg = folium.FeatureGroup(name="보행로/횡단보도", show=True)
        for _, row in ped.iterrows():
            is_cw = row.get("type") == "crosswalk"
            folium.PolyLine(
                locations=[(lat, lon) for lon, lat in row.geometry.coords],
                color="#ff6b00" if is_cw else "#00897b",
                weight=5 if is_cw else 3, opacity=0.7,
            ).add_to(ped_fg)
        ped_fg.add_to(m)

    # 기존 그늘막
    shades = data_loader.load_existing_shades()
    shade_fg = folium.FeatureGroup(name="기존 그늘막", show=True)
    for _, row in shades.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=5, color="#333", fill=True,
            fillColor="#333", fillOpacity=0.8,
        ).add_to(shade_fg)
    shade_fg.add_to(m)

    # 시나리오별 TOP 10
    for name, top in scenario_results.items():
        color = SCENARIO_COLORS.get(name, "#666")
        fg = folium.FeatureGroup(name=f"TOP10 · {name}",
                                  show=(name == "기본"))
        for i, row in top.iterrows():
            popup = folium.Popup(
                html=f"<b>[{name}] TOP {i+1}</b><br>"
                     f"Score: {row['score']:.3f}<br>"
                     f"유동인구: {row['pop']:.0f}<br>"
                     f"지표온도: {row['lst_c']:.1f}℃<br>"
                     f"취약계층: {row['vuln_ratio']*100:.1f}%",
                max_width=260,
            )
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=8 + (10 - i) * 0.4,  # 상위일수록 큰 원
                color=color, fill=True, fillColor=color,
                fillOpacity=0.75, weight=2,
                popup=popup,
                tooltip=f"[{name}] TOP{i+1} · {row['score']:.2f}",
            ).add_to(fg)
        fg.add_to(m)

    # 범례
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 12px 16px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 13px;">
      <b>시나리오 범례</b><br>
    """
    for name, color in SCENARIO_COLORS.items():
        legend_html += (
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{color};border-radius:50%;margin-right:6px;'
            f'vertical-align:middle;"></span>{name}<br>'
        )
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT / filename
    m.save(str(out_path))
    return str(out_path)
