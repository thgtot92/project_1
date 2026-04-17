"""동작구 그늘막 입지 추천 파이프라인 엔트리포인트.

사용:
    python -X utf8 main.py
"""
from __future__ import annotations
import json
from src.grid import build_grid
from src.scoring import compute_scores
from src.filtering import pick_candidates
from src.visualization import build_map
from src.llm_rationale import generate_rationale
from src.scenarios import (run_scenarios, comparison_table,
                            overlap_summary, build_comparison_map)
from src.validation import validate_against_focus_areas, print_report
from src.config import OUTPUT


def run():
    print("[1/6] 격자 생성 중...")
    grid = build_grid()
    print(f"  → {len(grid):,} cells")

    print("[2/6] 필요도 스코어 산출 중 (기본 가중치)...")
    scored = compute_scores(grid)
    print(f"  → score range: {scored['score'].min():.3f} ~ {scored['score'].max():.3f}")

    print("[3/6] 후보지 필터링 중...")
    top = pick_candidates(scored)
    print(f"  → TOP {len(top)} 선정")

    print("[4/6] 기본 지도 생성 중...")
    map_path = build_map(scored.to_crs("EPSG:4326"), top)
    print(f"  → {map_path}")

    print("[5/6] 시나리오 분석 (4개 프리셋)...")
    scenario_results = run_scenarios(scored)

    # 비교 테이블 저장
    cmp_df = comparison_table(scenario_results)
    cmp_path = OUTPUT / "scenarios_comparison.csv"
    cmp_df.to_csv(cmp_path, index=False, encoding="utf-8-sig")
    print(f"  → {cmp_path}")

    # 중복 분석 저장
    overlap = overlap_summary(scenario_results)
    overlap_path = OUTPUT / "scenarios_overlap.json"
    overlap_path.write_text(json.dumps(overlap, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"  → {overlap_path}")

    # 비교 지도 저장
    cmp_map = build_comparison_map(scenario_results, scored)
    print(f"  → {cmp_map}")

    # 시나리오별 유니크 추천 요약 출력
    print("\n  [시나리오별 유니크 추천 수]")
    for name, cnt in overlap["시나리오별_유니크"].items():
        print(f"    {name:15s} : {cnt}곳 독점")
    print(f"    모든 시나리오 공통     : {overlap['모든_시나리오_공통']}곳")

    # 집중구역 검증
    validation = validate_against_focus_areas(top)
    vpath = OUTPUT / "focus_areas_validation.json"
    vpath.write_text(json.dumps(validation, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"  → {vpath}")
    print_report(validation)

    print("[6/6] LLM 설치 근거 생성 중...")
    rationales = generate_rationale(top)
    rpath = OUTPUT / "rationales.json"
    rpath.write_text(json.dumps(rationales, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"  → {rpath}")

    print("\n[완료] output/ 디렉토리를 확인하세요.")


if __name__ == "__main__":
    run()
