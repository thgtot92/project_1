"""가중치 자동 튜닝 — Bayesian Optimization with 실측 그늘막 18개 (역-라벨).

가설 (사용자 정정):
  "이미 그늘막이 설치된 위치는 (이미 충분히 커버되므로) score 가 낮아야 한다"
  → 학습된 가중치는 자동으로 shade 페널티가 강해지고, 사각지대 우선순위 ↑

손실 함수:
  loss = mean( score(기존 그늘막 18개 근접 격자) )    ← minimize
        + λ × constraint_penalty

solver:
  scikit-optimize gp_minimize (Bayesian Optimization, GP surrogate)

탐색 공간 (7 피처 가중치):
  popdens, lst, vuln ∈ [0.05, 0.40]
  shade           ∈ [-0.40, -0.05]
  natural         ∈ [-0.20, 0.00]
  streetview_deficit ∈ [0.00, 0.25]
  intersection_density ∈ [0.00, 0.30]

산출물:
  output/weights_tuned.json    학습 가중치 + 손실 추이 + 수동 vs 학습 비교
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from .config import OUTPUT, WEIGHTS, CRS_KOREA, CRS_WGS84
from . import data_loader


# 탐색 공간 (절댓값으로 정의 후 부호 부여)
SEARCH_SPACE = [
    ("popdens",              0.05, 0.40),
    ("lst",                  0.05, 0.40),
    ("vuln",                 0.05, 0.40),
    ("shade_abs",            0.05, 0.40),  # 음수
    ("natural_abs",          0.00, 0.20),  # 음수
    ("streetview_deficit",   0.00, 0.25),
    ("intersection_density", 0.00, 0.30),
]


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo + 1e-9)


def _score_with_weights(scored_features: pd.DataFrame, w: dict) -> np.ndarray:
    """이미 계산된 피처 위에 가중치 적용 → score numpy array."""
    nrm = pd.DataFrame({
        "popdens":              _minmax(scored_features["pop"]),
        "lst":                  _minmax(scored_features["lst_c"]),
        "vuln":                 _minmax(scored_features["vuln_ratio"]),
        "shade":                _minmax(scored_features["shade_cov"]),
        "natural":              _minmax(scored_features["natural"]),
        "streetview_deficit":   _minmax(scored_features.get("sv_deficit",
                                          pd.Series(np.zeros(len(scored_features))))),
        "intersection_density": _minmax(scored_features.get("inter_density",
                                          pd.Series(np.zeros(len(scored_features))))),
    })
    return (
        w["popdens"]              * nrm["popdens"].values
        + w["lst"]                * nrm["lst"].values
        + w["vuln"]               * nrm["vuln"].values
        + w["shade"]              * nrm["shade"].values
        + w["natural"]            * nrm["natural"].values
        + w["streetview_deficit"] * nrm["streetview_deficit"].values
        + w["intersection_density"] * nrm["intersection_density"].values
    )


def _nearest_grid_for_shades(shades: gpd.GeoDataFrame,
                                scored: gpd.GeoDataFrame,
                                radius_m: float = 80.0) -> list[int]:
    """각 실측 그늘막에 가장 가까운 격자 인덱스 (radius_m 이내)."""
    shades_m = shades.to_crs(CRS_KOREA)
    grid_m = scored.to_crs(CRS_KOREA)
    centroids_m = grid_m.geometry.centroid

    from scipy.spatial import cKDTree
    coords = np.array([(c.x, c.y) for c in centroids_m])
    tree = cKDTree(coords)
    indices = []
    for _, srow in shades_m.iterrows():
        d, i = tree.query([srow.geometry.x, srow.geometry.y], k=1)
        if d <= radius_m:
            indices.append(int(scored.index[i]))
    return indices


def make_objective(scored_features: pd.DataFrame, target_indices: list[int]):
    """Bayesian Opt 용 목적함수: 기존 그늘막 근접 격자의 평균 score 최소화.

    sum_pos = popdens + lst + vuln + streetview_deficit + intersection_density
    sum_neg = |shade| + |natural|
    제약 (penalty): sum_pos - sum_neg 가 [0.4, 1.0] 범위 밖이면 페널티 가산.
    """
    from skopt.space import Real
    space = [Real(low, high, name=name) for name, low, high in SEARCH_SPACE]

    def objective(x):
        # x = [popdens, lst, vuln, shade_abs, natural_abs, sv, inter]
        w = {
            "popdens": x[0],
            "lst": x[1],
            "vuln": x[2],
            "shade": -x[3],
            "natural": -x[4],
            "streetview_deficit": x[5],
            "intersection_density": x[6],
        }
        scores = _score_with_weights(scored_features, w)
        if not target_indices:
            return 0.0
        # target_indices 는 scored.index 의 값 → 위치 인덱스로 변환
        loc = scored_features.index.get_indexer(target_indices)
        loc = loc[loc >= 0]
        if len(loc) == 0:
            return 0.0
        target_score_mean = float(np.mean(scores[loc]))

        # 가중치 합 제약: 양수 합 - 음수 합 ∈ [0.4, 1.0]
        pos = x[0] + x[1] + x[2] + x[5] + x[6]
        neg = x[3] + x[4]
        net = pos - neg
        penalty = 0.0
        if net < 0.4:
            penalty += 5 * (0.4 - net)
        elif net > 1.0:
            penalty += 5 * (net - 1.0)

        return target_score_mean + penalty

    return objective, space


def tune(scored: gpd.GeoDataFrame,
         n_calls: int = 60,
         random_state: int = 42) -> dict:
    """Bayesian Optimization 실행 + 학습 가중치 vs 수동 가중치 비교."""
    from skopt import gp_minimize

    print(f"[BO] Bayesian Optimization 가중치 튜닝 (n_calls={n_calls})")
    shades = data_loader.load_existing_shades()
    target_idx = _nearest_grid_for_shades(shades, scored)
    print(f"  [BO] 실측 그늘막 {len(shades)} → 80m 이내 매칭 격자 {len(target_idx)}개")

    if not target_idx:
        return {"status": "skip", "reason": "no nearest grids"}

    objective, space = make_objective(scored.copy(), target_idx)
    result = gp_minimize(objective, space, n_calls=n_calls,
                          random_state=random_state, verbose=False)

    tuned = {
        "popdens": float(result.x[0]),
        "lst": float(result.x[1]),
        "vuln": float(result.x[2]),
        "shade": float(-result.x[3]),
        "natural": float(-result.x[4]),
        "streetview_deficit": float(result.x[5]),
        "intersection_density": float(result.x[6]),
    }
    # 비교: 기존 가중치 vs 학습 가중치로 기존 그늘막 격자 점수
    manual_scores = _score_with_weights(scored, WEIGHTS)
    tuned_scores = _score_with_weights(scored, tuned)
    loc = scored.index.get_indexer(target_idx)
    loc = loc[loc >= 0]
    manual_target_mean = float(np.mean(manual_scores[loc]))
    tuned_target_mean = float(np.mean(tuned_scores[loc]))
    overall_manual_mean = float(manual_scores.mean())
    overall_tuned_mean = float(tuned_scores.mean())

    out = {
        "n_calls": n_calls,
        "best_loss": float(result.fun),
        "n_target_grids": len(target_idx),
        "weights_manual": {k: round(v, 3) for k, v in WEIGHTS.items()},
        "weights_tuned": {k: round(v, 3) for k, v in tuned.items()},
        "verification": {
            "manual_target_mean_score": round(manual_target_mean, 4),
            "tuned_target_mean_score": round(tuned_target_mean, 4),
            "delta_at_target": round(tuned_target_mean - manual_target_mean, 4),
            "manual_overall_mean": round(overall_manual_mean, 4),
            "tuned_overall_mean": round(overall_tuned_mean, 4),
            "interpretation": (
                "tuned_target_mean_score < manual_target_mean_score 이면 "
                "학습된 가중치가 실측 위치를 '덜 추천'하도록 조정됨 — "
                "사용자 가설(이미 설치된 곳은 score 낮춰야)에 부합."
            ),
        },
    }
    return out


def run(scored: gpd.GeoDataFrame | None = None) -> dict:
    if scored is None:
        from .grid import build_grid
        from .scoring import compute_scores
        scored = compute_scores(build_grid())

    result = tune(scored, n_calls=60)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT / "weights_tuned.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"  [BO] {out_path}")
    if "verification" in result:
        v = result["verification"]
        print(f"  [BO] 수동 가중치 target 평균: {v['manual_target_mean_score']:.4f}")
        print(f"  [BO] 학습 가중치 target 평균: {v['tuned_target_mean_score']:.4f}")
        print(f"  [BO] Δ = {v['delta_at_target']:+.4f} "
              f"(음수 = 학습이 실측 위치를 덜 추천)")
    return result


if __name__ == "__main__":
    run()
