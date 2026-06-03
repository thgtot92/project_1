"""STEP 4 — 예산 제약 배낭 최적화 (Budget-Constrained Knapsack).

다기준 의사결정(MCDA) Score 산출 후, 실제 정책 의사결정에 직접 답하는 단계:
  "예산 N원 = 그늘막 K개 = 어디?"

PuLP 정수 선형계획법(ILP):
  목표: max  Σ score_i × x_i
  제약:
    Σ cost_i × x_i ≤ BUDGET                (예산)
    Σ x_i ≤ MAX_INSTALL                    (개수 한도, 선택)
    x_i + x_j ≤ 1  if dist(i,j) < MIN_SEP  (공간 분산: 가까운 후보 동시 선택 금지)
    x_i ∈ {0, 1}

비용 가정 (더미, 실제 단가 확보 시 교체):
  - 고정형 그늘막: 800만원
  - 스마트형 그늘막: 1,500만원
  본 모듈은 고정형 800만원 단일 단가로 가정 → 예산 = 개수 × 800만원

산출물:
  output/budget_optimal.json     선정된 격자 좌표 + 점수 + 총 비용
  output/budget_optimal.html     선정 결과 지도 시각화
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from .config import OUTPUT, CRS_KOREA


# 비용 가정 (만원 단위)
COST_PER_SHADE = 800
# 공간 분산: 최소 이격 거리 (m)
DEFAULT_MIN_SEPARATION = 200
# 후보 풀 크기 (필터 통과 격자 중 상위)
DEFAULT_CANDIDATE_POOL = 50


def optimize_budget_knapsack(
    candidates: gpd.GeoDataFrame,
    budget_manwon: int = 4000,        # 4,000만원 = 5개 가능
    min_separation_m: float = DEFAULT_MIN_SEPARATION,
    max_install: int | None = None,
    pool_size: int = DEFAULT_CANDIDATE_POOL,
    cost_per_shade: int = COST_PER_SHADE,
    # NEW: 흑석동 한정 + 기존 그늘막 회피
    region_boundary: gpd.GeoDataFrame | None = None,
    existing_shades: gpd.GeoDataFrame | None = None,
    avoid_existing_m: float = 50.0,
) -> dict:
    """예산·공간분산 제약 하에서 총 score 최대화하는 그늘막 위치 선정.

    Args:
        candidates: filter_candidates 통과한 격자 GeoDataFrame (lon/lat/score 컬럼)
        budget_manwon: 예산 (만원)
        min_separation_m: 선정 격자 간 최소 이격 거리 (m)
        max_install: 설치 개수 상한 (None 이면 예산만 제약)
        pool_size: 후보 풀 크기 (전체 격자 중 score 상위 N)
        cost_per_shade: 그늘막 1개당 비용 (만원)

    Returns:
        dict: {selected, total_score, total_cost, budget, n_selected, ...}
    """
    import pulp

    # === 신규: 흑석동 경계 안 격자만 통과 (region_boundary 지정 시) ===
    filtered = candidates.copy()
    if region_boundary is not None and not region_boundary.empty:
        boundary_wgs = region_boundary.to_crs("EPSG:4326")
        bgeom = boundary_wgs.geometry.iloc[0]
        candidates_wgs = filtered.to_crs("EPSG:4326")
        mask = candidates_wgs.geometry.centroid.within(bgeom)
        filtered = filtered.loc[mask.values]
        print(f"  [OPT] 영역 필터: {len(candidates)} → {len(filtered)} 격자")

    # === 신규: 기존 그늘막 N m 이내 격자 제외 (신규 위치만) ===
    if (existing_shades is not None and not existing_shades.empty
            and avoid_existing_m > 0):
        shades_m = existing_shades.to_crs(CRS_KOREA)
        filtered_m = filtered.to_crs(CRS_KOREA)
        union_buffer = shades_m.buffer(avoid_existing_m).unary_union
        keep_mask = ~filtered_m.geometry.centroid.within(union_buffer)
        before = len(filtered)
        filtered = filtered.loc[keep_mask.values]
        print(f"  [OPT] 기존 그늘막 {avoid_existing_m:.0f}m 회피: "
              f"{before} → {len(filtered)}")

    # 후보 풀: score 상위 N개만 (전체 격자에 대해 ILP 돌리면 너무 큼)
    pool = filtered.nlargest(pool_size, 'score').reset_index(drop=True)
    n = len(pool)
    if n == 0:
        return {"selected": [], "total_score": 0.0, "total_cost": 0,
                "budget": budget_manwon, "n_selected": 0,
                "n_candidates": 0, "message": "후보 풀 비어 있음"}

    # 미터 좌표로 변환 (분산 제약 계산용)
    pool_m = pool.to_crs(CRS_KOREA)
    coords_m = np.array([(g.centroid.x, g.centroid.y) for g in pool_m.geometry])

    # 거리 매트릭스 (n x n)
    dist = np.sqrt(((coords_m[:, None, :] - coords_m[None, :, :]) ** 2).sum(-1))

    # PuLP 모델
    prob = pulp.LpProblem("ShadeKnapsack", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    scores = pool['score'].to_numpy()

    # 목표: 총 score 최대화
    prob += pulp.lpSum(scores[i] * x[i] for i in range(n))

    # 제약 1: 예산
    n_max_by_budget = budget_manwon // cost_per_shade
    prob += pulp.lpSum(x[i] for i in range(n)) <= n_max_by_budget, "budget"

    # 제약 2: 개수 상한 (옵션)
    if max_install is not None:
        prob += pulp.lpSum(x[i] for i in range(n)) <= max_install, "max_install"

    # 제약 3: 공간 분산 — i,j 가 min_separation_m 이내면 동시 선택 금지
    pair_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] < min_separation_m:
                prob += x[i] + x[j] <= 1, f"sep_{i}_{j}"
                pair_count += 1

    # 솔버 (CBC 무료 솔버, PuLP 기본)
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=30)
    status = prob.solve(solver)
    status_name = pulp.LpStatus[status]

    # 결과 추출
    selected_idx = [i for i in range(n) if x[i].value() and x[i].value() > 0.5]
    selected = pool.iloc[selected_idx].copy()
    selected['cost_manwon'] = cost_per_shade
    total_score = float(selected['score'].sum())
    total_cost = int(len(selected) * cost_per_shade)

    result = {
        "status": status_name,
        "region": ("흑석동" if region_boundary is not None
                    and not region_boundary.empty else "동작구 전체"),
        "avoid_existing_m": float(avoid_existing_m) if existing_shades is not None else 0.0,
        "budget_manwon": budget_manwon,
        "cost_per_shade_manwon": cost_per_shade,
        "n_max_by_budget": int(n_max_by_budget),
        "min_separation_m": min_separation_m,
        "candidate_pool_size": int(n),
        "spatial_separation_pairs": int(pair_count),
        "n_selected": int(len(selected)),
        "total_score": round(total_score, 3),
        "total_cost_manwon": total_cost,
        "remaining_budget_manwon": int(budget_manwon - total_cost),
        "selected": [
            {
                "rank": rank,
                "lat": round(float(row['lat']), 5),
                "lon": round(float(row['lon']), 5),
                "score": round(float(row['score']), 3),
                "cost_manwon": cost_per_shade,
            }
            for rank, (_, row) in enumerate(selected.iterrows(), 1)
        ],
    }
    return result


def render_budget_map(result: dict, candidates: gpd.GeoDataFrame,
                       out_path: Path) -> Path:
    """선정 결과 지도 시각화 (선정 vs 미선정 후보 비교)."""
    import folium
    from .config import DONGJAK_CENTER
    from . import data_loader

    m = folium.Map(location=DONGJAK_CENTER, zoom_start=14,
                    tiles="CartoDB positron")

    # 기존 그늘막 (있으면)
    try:
        shades = data_loader.load_existing_shades()
        fg = folium.FeatureGroup(name=f"기존 그늘막 ({len(shades)})", show=True)
        for _, row in shades.iterrows():
            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                icon=folium.Icon(color="black", icon="umbrella", prefix="fa"),
                tooltip="기존 그늘막",
            ).add_to(fg)
        fg.add_to(m)
    except Exception:
        pass

    # 미선정 후보 (회색)
    selected_keys = {(s['lat'], s['lon']) for s in result['selected']}
    cand_wgs = candidates.to_crs("EPSG:4326")
    fg = folium.FeatureGroup(name=f"미선정 후보 ({len(cand_wgs) - len(selected_keys)})",
                              show=True)
    for _, row in cand_wgs.iterrows():
        key = (round(float(row['lat']), 5), round(float(row['lon']), 5))
        if key in selected_keys:
            continue
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4, color="#999", fill=True,
            fillColor="#bbb", fillOpacity=0.5, weight=1,
            tooltip=f"미선정 score {row['score']:.3f}",
        ).add_to(fg)
    fg.add_to(m)

    # 선정된 격자 (빨간 큰 원)
    fg = folium.FeatureGroup(
        name=f"🎯 선정 ({result['n_selected']}개, "
             f"예산 {result['total_cost_manwon']:,}만원)",
        show=True,
    )
    for sel in result['selected']:
        folium.CircleMarker(
            location=[sel['lat'], sel['lon']],
            radius=12, color="#d81b60", fill=True,
            fillColor="#d81b60", fillOpacity=0.85, weight=3,
            popup=folium.Popup(
                f"<b>선정 #{sel['rank']}</b><br>"
                f"좌표: {sel['lat']:.5f}, {sel['lon']:.5f}<br>"
                f"score: {sel['score']:.3f}<br>"
                f"비용: {sel['cost_manwon']:,}만원",
                max_width=240,
            ),
            tooltip=f"#{sel['rank']} score {sel['score']:.2f}",
        ).add_to(fg)
    fg.add_to(m)

    # 범례
    legend = f"""
    <div style="position:fixed; bottom:30px; left:30px; z-index:9999;
                background:white; padding:10px 14px; border-radius:6px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2); font-size:12px;
                font-family:'Malgun Gothic',sans-serif; max-width:420px;">
      <b>예산 제약 최적화 결과</b><br>
      예산: {result['budget_manwon']:,}만원
      / 그늘막 단가: {result['cost_per_shade_manwon']:,}만원
      / 최대 {result['n_max_by_budget']}개<br>
      <b>선정 {result['n_selected']}개</b>
      · 총 score {result['total_score']:.3f}
      · 총 비용 {result['total_cost_manwon']:,}만원
      · 잔여 {result['remaining_budget_manwon']:,}만원<br>
      <small>제약: 공간 이격 {result['min_separation_m']:.0f}m 이상
      / 후보 풀 {result['candidate_pool_size']}개
      / 분산 제약 쌍 {result['spatial_separation_pairs']}개</small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out_path))
    return out_path


def run(candidates: gpd.GeoDataFrame,
        budget_manwon: int = 4000,
        region: str | None = "heukseok",
        avoid_existing_m: float = 50.0) -> dict:
    """엔트리포인트: 후보 GeoDataFrame + 예산 → 최적화 + 저장.

    region: "heukseok" 이면 흑석동 경계 안 + 실측 그늘막 회피.
    """
    from . import data_loader
    region_gdf = None
    existing_shades_gdf = None
    if region == "heukseok":
        boundary_path = (Path(__file__).resolve().parent.parent
                           / "data" / "raw" / "heukseok" / "ngii_data"
                           / "흑석동_경계5186.shp")
        if boundary_path.exists():
            region_gdf = gpd.read_file(boundary_path).to_crs("EPSG:4326")
            existing_shades_gdf = data_loader.load_existing_shades()
            print(f"[OPT] 흑석동 한정 모드: 경계 안 + 기존 그늘막 "
                  f"{int(avoid_existing_m)}m 회피 (실측 "
                  f"{len(existing_shades_gdf)}개)")
        else:
            print("[OPT] 흑석동 경계 데이터 없음 → 동작구 전체 모드")

    print(f"[OPT] 예산 제약 최적화: {budget_manwon:,}만원")
    result = optimize_budget_knapsack(
        candidates, budget_manwon=budget_manwon,
        region_boundary=region_gdf,
        existing_shades=existing_shades_gdf,
        avoid_existing_m=avoid_existing_m,
    )
    print(f"  [OPT] status={result['status']}, "
          f"region={result.get('region', '?')}, "
          f"선정 {result['n_selected']}개, "
          f"총 score {result['total_score']:.3f}, "
          f"비용 {result['total_cost_manwon']:,}만원")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "budget_optimal.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"  [OPT] {json_path}")

    # 시각화 후보: 영역 필터 적용 후 결과로 그리기 위해 동일 후보 전달
    map_candidates = candidates
    if region_gdf is not None and not region_gdf.empty:
        bgeom = region_gdf.geometry.iloc[0]
        cand_wgs = candidates.to_crs("EPSG:4326")
        map_candidates = candidates.loc[
            cand_wgs.geometry.centroid.within(bgeom).values
        ]
    map_path = OUTPUT / "budget_optimal.html"
    render_budget_map(result, map_candidates, map_path)
    print(f"  [OPT] {map_path}")

    return result


if __name__ == "__main__":
    # CLI: 메인 파이프라인 후보로 실행
    from .grid import build_grid
    from .scoring import compute_scores
    from .filtering import filter_candidates
    grid = build_grid()
    scored = compute_scores(grid)
    cand = filter_candidates(scored, verbose=True)
    run(cand, budget_manwon=4000)
