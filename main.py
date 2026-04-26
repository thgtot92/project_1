"""동작구 그늘막 입지 추천 파이프라인 엔트리포인트.

사용:
    python -X utf8 main.py

CV 단계는 산출물(buildings.geojson, grid_streetview.csv) 캐시가 있으면 자동 skip.
처음 실행 시: V-World 항공사진 다운로드 + SAM 건물 추출 + Mapillary 거리뷰 + SegFormer.
"""
from __future__ import annotations
import json
from src.grid import build_grid
from src.scoring import compute_scores
from src.filtering import pick_candidates, filter_candidates
from src.visualization import build_map
from src.llm_rationale import generate_rationale
from src.scenarios import (run_scenarios, comparison_table,
                            overlap_summary, build_comparison_map)
from src.validation import validate_against_focus_areas, print_report
from src.config import OUTPUT, DATA_RAW, DATA_PROCESSED


def _maybe_run_cv_buildings():
    """data/raw/buildings.geojson 없으면 CV-A 실행."""
    if (DATA_RAW / "buildings.geojson").exists():
        print("  [CV-A] buildings.geojson 캐시 사용")
        return
    print("  [CV-A] V-World 항공사진 + SAM 건물 추출 (1회 실행)")
    try:
        from src import cv_buildings
        cv_buildings.run()
    except Exception as e:
        print(f"  [CV-A] 실패 → 더미 건물 사용: {e}")


def _maybe_run_cv_streetview(prelim_candidates):
    """data/processed/grid_streetview.csv 없으면 CV-B 실행."""
    if (DATA_PROCESSED / "grid_streetview.csv").exists():
        print("  [CV-B] grid_streetview.csv 캐시 사용")
        return
    print(f"  [CV-B] Mapillary 거리뷰 + SegFormer ({len(prelim_candidates)} 후보)")
    try:
        from src import cv_streetview
        cv_streetview.run_for_top_candidates(prelim_candidates, per_point=3)
    except Exception as e:
        print(f"  [CV-B] 실패 → streetview_deficit=0 으로 진행: {e}")


def run():
    print("[1/8] 격자 생성 중...")
    grid = build_grid()
    print(f"  → {len(grid):,} cells")

    print("[2/8] CV-A: 위성 항공사진 + SAM 건물 추출")
    _maybe_run_cv_buildings()

    print("[3/8] 1차 필요도 스코어 산출 (CV-B 캐시 없으면 sv_deficit=0)...")
    scored = compute_scores(grid)
    print(f"  → score range: {scored['score'].min():.3f} ~ {scored['score'].max():.3f}")

    print("[4/8] CV-B: 1차 후보풀(보행로 통과) 거리뷰 분석")
    prelim = filter_candidates(scored, verbose=False)
    print(f"  → 후보 풀 {len(prelim)} 격자")
    _maybe_run_cv_streetview(prelim)

    print("[5/8] streetview_deficit 반영 재스코어링...")
    scored = compute_scores(grid)
    print(f"  → score range: {scored['score'].min():.3f} ~ {scored['score'].max():.3f}")

    print("[6/8] 후보지 최종 필터링 + TOP K...")
    top = pick_candidates(scored)
    print(f"  → TOP {len(top)} 선정")

    print("[7/8] 기본 지도 생성 중...")
    map_path = build_map(scored.to_crs("EPSG:4326"), top)
    print(f"  → {map_path}")

    print("[8/8] 시나리오 분석 + 검증 + LLM 근거")
    scenario_results = run_scenarios(scored)

    cmp_df = comparison_table(scenario_results)
    cmp_path = OUTPUT / "scenarios_comparison.csv"
    cmp_df.to_csv(cmp_path, index=False, encoding="utf-8-sig")
    print(f"  → {cmp_path}")

    overlap = overlap_summary(scenario_results)
    overlap_path = OUTPUT / "scenarios_overlap.json"
    overlap_path.write_text(json.dumps(overlap, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"  → {overlap_path}")

    cmp_map = build_comparison_map(scenario_results, scored)
    print(f"  → {cmp_map}")

    print("\n  [시나리오별 유니크 추천 수]")
    for name, cnt in overlap["시나리오별_유니크"].items():
        print(f"    {name:15s} : {cnt}곳 독점")
    print(f"    모든 시나리오 공통     : {overlap['모든_시나리오_공통']}곳")

    validation = validate_against_focus_areas(top)
    vpath = OUTPUT / "focus_areas_validation.json"
    vpath.write_text(json.dumps(validation, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"  → {vpath}")
    print_report(validation)

    print("  LLM 설치 근거 생성 중...")
    rationales = generate_rationale(top)
    rpath = OUTPUT / "rationales.json"
    rpath.write_text(json.dumps(rationales, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"  → {rpath}")

    if "sv_deficit" in top.columns:
        avg_sv = float(top["sv_deficit"].mean())
        print(f"\n  [CV] TOP10 평균 streetview_deficit: {avg_sv:.3f}")

    print("\n[완료] output/ 디렉토리를 확인하세요.")


if __name__ == "__main__":
    run()
