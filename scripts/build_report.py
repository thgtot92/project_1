"""자동 실험 보고서 — 모든 산출물을 한 HTML 페이지에 통합.

산출:
    output/report.html  (~10MB, 단일 HTML, 의존성 없음)

레이아웃:
    1. 헤더 (제목·생성시각·요약 카드 4개)
    2. 시나리오 비교 (6 시나리오 표 + 강건 입지)
    3. 1차 발표 3대 구역 검증
    4. 가중치 자동 튜닝 (BayesOpt 결과)
    5. Self-consistency 5회 신뢰구간
    6. 예산 제약 배낭 최적화
    7. 모든 인터랙티브 지도 iframe (shade_map / scenarios_map / heukseok_focus / budget_optimal)
    8. 산출물 파일 목록 + 메타
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DATA_PROC = ROOT / "data" / "processed"


def _safe_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _file_size(path: Path) -> str:
    if not path.exists():
        return "—"
    n = path.stat().st_size
    if n > 1024 * 1024:
        return f"{n/1024/1024:.1f} MB"
    if n > 1024:
        return f"{n/1024:.0f} KB"
    return f"{n} B"


def build():
    # 데이터 수집
    overlap = _safe_json(OUTPUT / "scenarios_overlap.json") or {}
    valid = _safe_json(OUTPUT / "focus_areas_validation.json") or {}
    tuned = _safe_json(OUTPUT / "weights_tuned.json") or {}
    budget = _safe_json(OUTPUT / "budget_optimal.json") or {}
    rationales = _safe_json(OUTPUT / "rationales.json") or []

    # 시나리오 표
    comparison_csv = OUTPUT / "scenarios_comparison.csv"
    scenarios = {}
    if comparison_csv.exists():
        import csv
        with comparison_csv.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sc = row.get("scenario", "")
                scenarios.setdefault(sc, []).append(row)

    # 산출물 파일 목록
    artifacts = [
        ("output/shade_map.html",            "기본 TOP10 지도"),
        ("output/scenarios_map.html",        "6 시나리오 토글"),
        ("output/heukseok_focus.html",       "흑석동 정밀 + 학습 가중치 + 그림자 std"),
        ("output/budget_optimal.html",       "예산 배낭 최적화 결과 지도"),
        ("output/scenarios_comparison.csv",  "시나리오 × TOP10 비교표"),
        ("output/scenarios_overlap.json",    "강건 입지 + 중복 분석"),
        ("output/focus_areas_validation.json","1차 발표 3대 구역 검증"),
        ("output/rationales.json",           "LLM 설치 근거"),
        ("output/weights_tuned.json",        "Bayesian Opt 학습 가중치"),
        ("output/budget_optimal.json",       "배낭 최적화 선정 결과"),
        ("data/processed/heukseok_shadow_accum.tif", "DSM 9시점 누적 그림자"),
        ("data/processed/grid_heukseok_natural.csv", "흑석동 격자 자연그늘"),
        ("data/processed/grid_heukseok_consistency.csv", "Self-consistency 5회"),
        ("data/processed/grid_streetview.csv","CV-B 격자별 그늘 결핍"),
        ("data/processed/osm_intersections.geojson", "OSMnx 교차로 GeoJSON"),
        ("data/processed/osm_crossings.geojson",     "OSMnx 횡단보도 GeoJSON"),
        ("data/processed/grid_intersection.csv","격자별 결집지 밀도"),
        ("data/raw/existing_shades.csv",     "실측 그늘막 18개"),
        ("data/raw/buildings.geojson",       "CV-A SAM 30동"),
    ]

    # 시나리오 표 HTML
    sc_table_html = "<table><thead><tr><th>시나리오</th><th>최고 Score</th><th>TOP1 좌표</th></tr></thead><tbody>"
    for sc, rows in scenarios.items():
        rows = sorted(rows, key=lambda r: int(r["rank"]))
        top1 = rows[0] if rows else {}
        sc_table_html += (
            f"<tr><td><b>{sc}</b></td>"
            f"<td>{top1.get('score', '')}</td>"
            f"<td>{top1.get('lat', '')}, {top1.get('lon', '')}</td></tr>"
        )
    sc_table_html += "</tbody></table>"

    # 강건 입지 카드
    robust = overlap.get("공통_좌표", [])
    robust_html = "".join(
        f'<div class="card"><b>강건 입지 #{i+1}</b><br>'
        f'<span class="coord">{lat:.4f}, {lon:.4f}</span></div>'
        for i, (lat, lon) in enumerate(robust)
    ) if robust else "<p>강건 입지 없음</p>"

    # 가중치 비교
    tuned_html = ""
    if tuned.get("weights_manual"):
        manual = tuned["weights_manual"]
        learned = tuned["weights_tuned"]
        keys = ["popdens","lst","vuln","shade","natural","streetview_deficit","intersection_density"]
        tuned_html = "<table><thead><tr><th>피처</th><th>수동</th><th>학습 (BayesOpt)</th><th>변화</th></tr></thead><tbody>"
        for k in keys:
            m, l = manual.get(k, 0), learned.get(k, 0)
            delta = l - m
            arrow = "↑" if delta > 0.02 else ("↓" if delta < -0.02 else "≈")
            cls = "delta-up" if delta > 0.02 else ("delta-down" if delta < -0.02 else "")
            tuned_html += f"<tr><td>{k}</td><td>{m:+.3f}</td><td>{l:+.3f}</td><td class='{cls}'>{arrow} {delta:+.3f}</td></tr>"
        tuned_html += "</tbody></table>"

        v = tuned.get("verification", {})
        tuned_html += (
            f"<p class='note'>검증: 실측 위치 평균 score "
            f"<b>{v.get('manual_target_mean_score', '?')}</b> (수동) → "
            f"<b>{v.get('tuned_target_mean_score', '?')}</b> (학습) · "
            f"Δ = <b>{v.get('delta_at_target', '?')}</b> "
            f"(음수 = 가설 부합)</p>"
        )

    # 예산 결과
    budget_html = ""
    if budget.get("selected"):
        region_label = budget.get("region", "동작구 전체")
        avoid_m = budget.get("avoid_existing_m", 0)
        budget_html = (
            f"<p><span class='pass'>🎯 영역: {region_label}</span> · "
            f"기존 그늘막 <b>{avoid_m:.0f}m</b> 회피 (신규 위치만) · "
            f"예산 <b>{budget.get('budget_manwon', 0):,}만원</b> · 단가 "
            f"{budget.get('cost_per_shade_manwon', 0):,}만원/개 → "
            f"최대 {budget.get('n_max_by_budget', 0)}개</p>"
            f"<p>solver status: <b>{budget.get('status', '?')}</b> · "
            f"후보 풀 <b>{budget.get('candidate_pool_size', 0)}</b>개 · "
            f"선정 <b>{budget.get('n_selected', 0)}개</b> · "
            f"총 score <b>{budget.get('total_score', 0)}</b> · "
            f"공간 분산 {budget.get('min_separation_m', 0):.0f}m</p>"
            f"<table><thead><tr><th>#</th><th>좌표</th><th>score</th></tr></thead><tbody>"
        )
        for sel in budget["selected"]:
            budget_html += (
                f"<tr><td>#{sel['rank']}</td>"
                f"<td>{sel['lat']:.5f}, {sel['lon']:.5f}</td>"
                f"<td>{sel['score']:.3f}</td></tr>"
            )
        budget_html += "</tbody></table>"

    # 3대 구역 검증
    focus_html = ""
    for name, info in valid.items():
        hits = info.get("top_hits_in_area", 0)
        dist = info.get("nearest_top_distance_m", 0)
        status = "✓" if hits > 0 else "△"
        cls = "pass" if hits > 0 else "partial"
        focus_html += (
            f"<tr><td>{name}</td>"
            f"<td class='{cls}'>{status}</td>"
            f"<td>{hits}곳</td>"
            f"<td>{dist:.0f}m</td></tr>"
        )

    # 통계
    n_artifacts = sum(1 for p, _ in artifacts if (ROOT / p).exists())
    n_robust = len(robust)
    n_blind = len(rationales) if isinstance(rationales, list) else 0
    n_scenarios = len(scenarios)
    n_selected = budget.get("n_selected", 0)

    # 산출물 표
    artifact_html = "<table><thead><tr><th>파일</th><th>설명</th><th>크기</th></tr></thead><tbody>"
    for path_str, desc in artifacts:
        path = ROOT / path_str
        exists = "✓" if path.exists() else "—"
        size = _file_size(path)
        artifact_html += (
            f"<tr><td><code>{path_str}</code> {exists}</td>"
            f"<td>{desc}</td><td>{size}</td></tr>"
        )
    artifact_html += "</tbody></table>"

    # 생성 시간 (Date.now 류는 못 쓰니 파일 시각 기반)
    try:
        import time
        gen_time = time.strftime("%Y-%m-%d %H:%M")
    except Exception:
        gen_time = "—"

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>실험 보고서 — 동작구 그늘막 입지 분석</title>
<style>
  :root {{
    --c-text: #37352F; --c-sub: #787774; --c-muted: #9B9A97;
    --c-accent: #2383E2; --c-panel: #F7F6F3; --c-border: #E9E9E7;
    --c-green: #0F7B6C; --c-amber: #CB7B26; --c-red: #E03E3E;
  }}
  body {{ font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    color: var(--c-text); background: #fff; margin: 0; padding: 0;
    line-height: 1.5; }}
  .container {{ max-width: 1280px; margin: 0 auto; padding: 30px 40px; }}
  h1 {{ font-size: 28px; margin: 0 0 8px; color: var(--c-text); }}
  h2 {{ font-size: 20px; margin: 36px 0 12px; padding-left: 12px;
        border-left: 5px solid var(--c-accent); color: var(--c-text); }}
  h3 {{ font-size: 16px; color: var(--c-sub); margin: 16px 0 8px; }}
  .meta {{ color: var(--c-muted); font-size: 13px; margin-bottom: 24px; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
                    gap: 14px; margin: 24px 0; }}
  .summary {{ background: var(--c-panel); border: 1px solid var(--c-border);
              border-radius: 8px; padding: 16px 18px; }}
  .summary .num {{ font-size: 28px; font-weight: bold;
                    color: var(--c-accent); margin: 4px 0; }}
  .summary .lbl {{ font-size: 11px; color: var(--c-sub);
                    text-transform: uppercase; letter-spacing: 0.5px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0;
            font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left;
            border-bottom: 1px solid var(--c-border); }}
  th {{ background: var(--c-text); color: white; font-weight: 600; }}
  tbody tr:nth-child(even) {{ background: var(--c-panel); }}
  .card {{ display: inline-block; background: var(--c-panel);
            border: 1px solid var(--c-border); border-radius: 8px;
            padding: 12px 16px; margin: 6px 6px 0 0; min-width: 200px; }}
  .card .coord {{ font-family: Consolas, monospace; color: var(--c-sub);
                   font-size: 12px; }}
  .note {{ background: #F0F8FF; border-left: 4px solid var(--c-accent);
           padding: 10px 16px; margin: 12px 0; font-size: 13px; }}
  .pass {{ color: var(--c-green); font-weight: bold; }}
  .partial {{ color: var(--c-amber); font-weight: bold; }}
  .delta-up {{ color: var(--c-red); font-weight: bold; }}
  .delta-down {{ color: var(--c-green); font-weight: bold; }}
  iframe {{ width: 100%; height: 540px; border: 1px solid var(--c-border);
             border-radius: 8px; margin: 8px 0; }}
  .maps-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  .maps-grid iframe {{ height: 420px; }}
  code {{ background: var(--c-panel); padding: 1px 5px; border-radius: 3px;
           font-family: Consolas, monospace; font-size: 12px; }}
  .footer {{ margin-top: 40px; padding-top: 16px;
              border-top: 1px solid var(--c-border);
              color: var(--c-muted); font-size: 12px; }}
</style></head><body><div class="container">

<h1>📊 실험 보고서 — 동작구 그늘막 입지 분석</h1>
<div class="meta">자동 생성: {gen_time} · MCDA + CV-A/B + CV-DSM(9시점) + OSMnx + BayesOpt + 배낭 최적화</div>

<div class="summary-grid">
  <div class="summary"><div class="lbl">강건 입지</div><div class="num">{n_robust}</div><div>6 시나리오 공통</div></div>
  <div class="summary"><div class="lbl">시나리오</div><div class="num">{n_scenarios}</div><div>가중치 프리셋</div></div>
  <div class="summary"><div class="lbl">배낭 선정</div><div class="num">{n_selected}</div><div>예산 4천만원</div></div>
  <div class="summary"><div class="lbl">산출물</div><div class="num">{n_artifacts}</div><div>파일</div></div>
</div>

<h2>🎯 시나리오 비교 · 강건 입지</h2>
{sc_table_html}
<h3>강건 입지 (6 시나리오 공통 추천)</h3>
{robust_html}

<h2>📌 1차 발표 3대 집중구역 검증</h2>
<table><thead><tr><th>구역</th><th>판정</th><th>반경 내 TOP</th><th>최근접</th></tr></thead>
<tbody>{focus_html}</tbody></table>

<h2>🎯 가중치 자동 튜닝 (Bayesian Optimization)</h2>
{tuned_html or '<p class="note">결과 없음 — src/weight_tuning.py 실행 필요</p>'}

<h2>💰 예산 제약 배낭 최적화 (Knapsack)</h2>
{budget_html or '<p class="note">결과 없음</p>'}

<h2>🌐 인터랙티브 지도</h2>
<h3>기본 TOP10</h3>
<iframe src="shade_map.html" loading="lazy"></iframe>
<div class="maps-grid">
<div><h3>6 시나리오 토글</h3><iframe src="scenarios_map.html" loading="lazy"></iframe></div>
<div><h3>예산 4천만원 배낭 결과</h3><iframe src="budget_optimal.html" loading="lazy"></iframe></div>
</div>
<h3>흑석동 정밀 (NGII + Self-consistency + 학습 가중치)</h3>
<iframe src="heukseok_focus.html" style="height:620px;" loading="lazy"></iframe>

<h2>📁 산출물 파일 목록</h2>
{artifact_html}

<div class="footer">
  데이터기반 도시설계 기말 · 한영재·문치국·원우식<br>
  Repository: github.com/thgtot92/project_1 · MIT License
</div>

</div></body></html>
"""
    out_path = OUTPUT / "report.html"
    out_path.write_text(html, encoding="utf-8")
    n_kb = out_path.stat().st_size / 1024
    print(f"[REPORT] saved: {out_path} ({n_kb:.0f} KB · iframe 임베드 포함 ~10MB)")
    print(f"  · 강건 입지: {n_robust}, 시나리오: {n_scenarios}, "
          f"배낭 선정: {n_selected}, 산출물: {n_artifacts}")


if __name__ == "__main__":
    build()
