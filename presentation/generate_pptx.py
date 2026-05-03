"""최종 발표자료 (PPTX) 생성 스크립트.

실행:
    python presentation/generate_pptx.py

산출물:
    presentation/동작구_그늘막_최종발표.pptx
"""
from __future__ import annotations
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "presentation" / "동작구_그늘막_최종발표.pptx"

# 색상
COLOR_PRIMARY = RGBColor(0x1E, 0x88, 0xE5)   # blue
COLOR_ACCENT  = RGBColor(0xE5, 0x39, 0x35)   # red
COLOR_WARN    = RGBColor(0xFB, 0x8C, 0x00)   # orange
COLOR_VULN    = RGBColor(0x8E, 0x24, 0xAA)   # purple
COLOR_DARK    = RGBColor(0x21, 0x21, 0x21)
COLOR_SUB     = RGBColor(0x55, 0x55, 0x55)
COLOR_LIGHT   = RGBColor(0xEE, 0xEE, 0xEE)
FONT = "맑은 고딕"

# 16:9 크기
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _set_font(run, size=18, bold=False, color=COLOR_DARK, font=FONT):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def _add_text(slide, left, top, width, height, text,
              size=18, bold=False, color=COLOR_DARK, align=PP_ALIGN.LEFT):
    tx = slide.shapes.add_textbox(left, top, width, height)
    tf = tx.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    _set_font(run, size=size, bold=bold, color=color)
    return tx


def _add_bullets(slide, left, top, width, height, items, size=18):
    tx = slide.shapes.add_textbox(left, top, width, height)
    tf = tx.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        run = p.add_run()
        run.text = "• " + item
        _set_font(run, size=size, color=COLOR_DARK)
        p.space_after = Pt(6)
    return tx


def _add_header_bar(slide, title, subtitle=None):
    """좌측 세로 컬러 바 + 제목 + 옵션 부제."""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(0.5),
        Inches(0.12), Inches(0.8),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_PRIMARY
    bar.line.fill.background()

    _add_text(slide, Inches(0.75), Inches(0.45),
              Inches(12), Inches(0.6),
              title, size=30, bold=True, color=COLOR_DARK)
    if subtitle:
        _add_text(slide, Inches(0.75), Inches(1.0),
                  Inches(12), Inches(0.4),
                  subtitle, size=14, color=COLOR_SUB)


def _add_footer(slide, page_num=None, total=None):
    _add_text(slide, Inches(0.5), Inches(7.0),
              Inches(10), Inches(0.4),
              "동작구 여름 그늘막 최적 입지 추천 시스템 · 한영재 · 2025961227",
              size=10, color=COLOR_SUB)
    if page_num and total:
        _add_text(slide, Inches(12.3), Inches(7.0),
                  Inches(1), Inches(0.4),
                  f"{page_num} / {total}", size=10,
                  color=COLOR_SUB, align=PP_ALIGN.RIGHT)


def _placeholder_image(slide, left, top, width, height, caption):
    """스크린샷 자리 placeholder."""
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = COLOR_LIGHT
    box.line.color.rgb = COLOR_SUB
    box.line.width = Pt(1)

    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = f"📷 {caption}"
    _set_font(run, size=14, bold=True, color=COLOR_SUB)


# ─────────────────────────────────────────────────────────────
def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    TOTAL = 14

    # ────────── 1. 표지 ──────────
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = COLOR_DARK
    bg.line.fill.background()

    _add_text(s, Inches(1.0), Inches(2.0), Inches(11.3), Inches(1.0),
              "동작구 여름 그늘막 최적 입지 추천 시스템",
              size=40, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _add_text(s, Inches(1.0), Inches(3.1), Inches(11.3), Inches(0.6),
              "채권 트레이더의 다변수 최적화 방법론을 도시 공간 데이터에 이식",
              size=18, color=RGBColor(0xBB, 0xBB, 0xBB))
    # 구분선
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                               Inches(1.0), Inches(4.2),
                               Inches(2.0), Emu(50800))  # 약 4pt
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_PRIMARY
    line.line.fill.background()

    _add_text(s, Inches(1.0), Inches(4.5), Inches(11), Inches(0.4),
              "데이터기반 도시설계 · 기말 프로젝트",
              size=16, color=RGBColor(0xCC, 0xCC, 0xCC))
    _add_text(s, Inches(1.0), Inches(5.0), Inches(11), Inches(0.4),
              "한영재 / 인공지능융합대학원 인공지능컴퓨팅 / 2025961227",
              size=14, color=RGBColor(0xAA, 0xAA, 0xAA))
    _add_text(s, Inches(1.0), Inches(5.5), Inches(11), Inches(0.4),
              "2026년 4월",
              size=12, color=RGBColor(0x88, 0x88, 0x88))

    # ────────── 2. 문제 정의 + 접근 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "문제 정의 · 접근",
                    "어디에 설치할 것인가 — 민원·직관이 아닌 데이터의 논리로")
    _add_bullets(s, Inches(0.75), Inches(1.8), Inches(12), Inches(2.5), [
        "그늘막은 유한한 예산 → 어느 격자에 설치해야 '폭염 스트레스 × 유동인구 × 취약계층' 효용이 최대인가?",
        "기존 방식: 민원 기반 · 담당자 직관 → 공간적 편향, 이미 커버된 곳 중복 설치",
        "제안: 다변수 가중합 + 공간 필터 + 시나리오 민감도 + 자연그늘까지 반영한 입지 추천 파이프라인",
    ], size=18)

    # 강조 박스: 채권 트레이더 프레임
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(0.75), Inches(4.2),
                              Inches(12), Inches(2.3))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xF5, 0xF8, 0xFD)
    box.line.color.rgb = COLOR_PRIMARY
    box.line.width = Pt(1.5)
    tf = box.text_frame
    tf.margin_left = Inches(0.3); tf.margin_top = Inches(0.2)
    tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = "채권 트레이더 관점의 다변수 최적화"
    _set_font(r, size=20, bold=True, color=COLOR_PRIMARY)
    for line_txt in [
        "• 피처 = 채권의 수익률 곡선 요인 · 격자 = 포트폴리오 후보",
        "• 가중합 + 제약조건(보행로·기존그늘막) = 리스크 예산 내 최적 포지션",
        "• 시나리오 민감도 = 금리 시나리오 스트레스 테스트와 동형(同形)",
    ]:
        p = tf.add_paragraph()
        r = p.add_run(); r.text = line_txt
        _set_font(r, size=16, color=COLOR_DARK)
        p.space_before = Pt(4)
    _add_footer(s, 2, TOTAL)

    # ────────── 3. 파이프라인 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "파이프라인 개요",
                    "격자 생성 → 스코어 → 필터 → 시나리오 → LLM 근거")

    steps = [
        ("STEP 0", "격자", "동작구 100m 격자\n3,672 cells", COLOR_SUB),
        ("STEP 1", "스코어", "pop·lst·vuln(+) −shade·natural(−)\n시간대 가중 9~18시", COLOR_PRIMARY),
        ("STEP 2", "필터", "보행로 20m 이내\n기존그늘막 150m 외\n3,672 → 23 → 19", COLOR_WARN),
        ("STEP 3", "시나리오+LLM", "4개 프리셋 × TOP10\nLLM 자연어 근거", COLOR_ACCENT),
    ]
    left0 = Inches(0.75)
    top0 = Inches(2.2)
    w = Inches(2.95); h = Inches(3.2)
    gap = Inches(0.15)
    for i, (tag, title, body, color) in enumerate(steps):
        x = left0 + Inches(i * (2.95 + 0.15))
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top0, w, h)
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xFA, 0xFA, 0xFA)
        box.line.color.rgb = color
        box.line.width = Pt(2)
        tf = box.text_frame; tf.word_wrap = True
        tf.margin_left = Inches(0.2); tf.margin_top = Inches(0.2)
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = tag
        _set_font(r, size=12, bold=True, color=color)
        p2 = tf.add_paragraph()
        r = p2.add_run(); r.text = title
        _set_font(r, size=22, bold=True, color=COLOR_DARK)
        p2.space_before = Pt(4)
        for line_txt in body.split("\n"):
            p = tf.add_paragraph()
            r = p.add_run(); r.text = line_txt
            _set_font(r, size=13, color=COLOR_SUB)
            p.space_before = Pt(3)
        # 화살표 (마지막 제외)
        if i < len(steps) - 1:
            arrow_x = x + w + Inches(-0.05)
            arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,
                                      arrow_x, top0 + Inches(1.4),
                                      Inches(0.25), Inches(0.35))
            arr.fill.solid()
            arr.fill.fore_color.rgb = COLOR_SUB
            arr.line.fill.background()

    _add_text(s, Inches(0.75), Inches(5.8), Inches(12), Inches(0.5),
              "산출물: shade_map.html · scenarios_map.html · rationales.json · "
              "scenarios_comparison.csv · focus_areas_validation.json",
              size=12, color=COLOR_SUB)
    _add_footer(s, 3, TOTAL)

    # ────────── 4. 데이터 5종 + 시간 가중 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "입력 데이터 5종 · 시간대 가중",
                    "실데이터 ↔ 더미 자동 스위칭 / 역세권·시장 프로파일 분리")

    # 표
    rows = [
        ("데이터", "출처", "시간 프로파일"),
        ("생활인구 (SKT)", "서울 열린데이터광장", "역세권=출퇴근 / 시장=오후 피크"),
        ("지표면 온도 LST", "서울연구원 Landsat", "오후 1~3시 1.0 (피크 가중)"),
        ("취약계층 비율", "KOSIS 동별 통계", "상수 (연령 구조)"),
        ("기존 그늘막 위치", "서울 열린데이터광장", "반경 150m 제외 (커버리지)"),
        ("인도·횡단보도", "국가공간정보포털", "폭 ≥ 2m / 20m 이내 강제"),
    ]
    left = Inches(0.75); top = Inches(1.9)
    col_widths = [Inches(3.5), Inches(3.8), Inches(5.0)]
    tbl = s.shapes.add_table(rows=len(rows), cols=3,
                              left=left, top=top,
                              width=sum(col_widths, Inches(0)),
                              height=Inches(3.4)).table
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = cw
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            tf = cell.text_frame
            p = tf.paragraphs[0]
            r = p.add_run(); r.text = val
            if ri == 0:
                _set_font(r, size=14, bold=True,
                           color=RGBColor(0xFF, 0xFF, 0xFF))
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_PRIMARY
            else:
                _set_font(r, size=13, color=COLOR_DARK)

    _add_text(s, Inches(0.75), Inches(5.6), Inches(12), Inches(0.5),
              "⚙ data/raw/*.csv·geojson 배치 시 data_loader.py가 자동 전환 "
              "→ 현재는 동작구 실제 거점(역세권·시장·주거축) 기반 더미 데이터로 파이프라인 검증",
              size=13, color=COLOR_SUB)
    _add_footer(s, 4, TOTAL)

    # ────────── 5. 알고리즘 (Score 식) ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "알고리즘 · Score 식",
                    "MinMax 정규화 후 가중합 (음수 가중치 = 페널티)")

    # Score 식 박스 (CV 통합 후 6 피처)
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(0.75), Inches(1.9),
                              Inches(12), Inches(1.6))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0x21, 0x21, 0x21)
    box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.3); tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("Score = 0.25·popdens + 0.25·lst + 0.20·vuln")
    _set_font(r, size=20, bold=True, color=RGBColor(0xFF, 0xEE, 0x58))
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r = p2.add_run()
    r.text = "− 0.15·shade − 0.05·natural + 0.15·streetview_deficit"
    _set_font(r, size=20, bold=True, color=RGBColor(0xFF, 0xEE, 0x58))

    # 가중치 해설
    _add_bullets(s, Inches(0.75), Inches(3.7), Inches(12), Inches(2.3), [
        "popdens (+0.25) — 시간대 가중 유동인구 (오후 1~3시 1.0 피크)",
        "lst (+0.25) — 지표면 온도, 오후 피크 가중 평균",
        "vuln (+0.20) — 고령자·어린이 비율 (취약계층)",
        "shade (−0.15) — 기존 그늘막 반경 150m 내 커버리지",
        "natural (−0.05) — CV-A SAM 추출 건물 그림자 시뮬레이션",
        "streetview_deficit (+0.15) — CV-B SegFormer 거리뷰 그늘 결핍 (NEW)",
    ], size=15)

    _add_text(s, Inches(0.75), Inches(6.0), Inches(12), Inches(0.5),
              "🎚 Streamlit 대시보드에서 슬라이더로 실시간 조정 가능 "
              "· 시나리오별 프리셋 4종 내장",
              size=13, bold=True, color=COLOR_PRIMARY)
    _add_footer(s, 5, TOTAL)

    # ────────── 6. 공간 필터링 결과 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "공간 필터링 · TOP 10",
                    "보행로·횡단보도 강제 제약으로 강변/건물 후보 원천 제외")

    # 퍼널 숫자
    funnel = [
        ("3,672", "전체 격자", COLOR_SUB),
        ("23", "보행로 20m 이내", COLOR_WARN),
        ("19", "기존그늘막 제외", COLOR_ACCENT),
        ("10", "최종 추천 (TOP 10)", COLOR_PRIMARY),
    ]
    left = Inches(0.75); top = Inches(2.0)
    box_w = Inches(2.8); box_h = Inches(2.2)
    gap = Inches(0.25)
    for i, (num, label, color) in enumerate(funnel):
        x = left + Inches(i * 3.05)
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  x, top, box_w, box_h)
        box.fill.solid()
        box.fill.fore_color.rgb = color
        box.line.fill.background()
        tf = box.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num
        _set_font(r, size=44, bold=True,
                   color=RGBColor(0xFF, 0xFF, 0xFF))
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r = p2.add_run(); r.text = label
        _set_font(r, size=14, color=RGBColor(0xFF, 0xFF, 0xFF))

    _placeholder_image(s, Inches(0.75), Inches(4.5),
                       Inches(12), Inches(2.3),
                       "shade_map.html — 기본 시나리오 TOP 10 지도 캡처 배치")
    _add_footer(s, 6, TOTAL)

    # ────────── 7. 자연 그늘 시뮬레이션 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "자연 그늘 시뮬레이션",
                    "건물 footprint + 오후 3시 태양위치 → 격자별 그림자 커버 비율")

    _add_bullets(s, Inches(0.75), Inches(1.9), Inches(7.5), Inches(4.5), [
        "태양 위치: 서울 7월 말 오후 3시 · 고도 52° · 방위 252°",
        "그림자 = 건물 footprint ∪ 태양반대방향 평행이동의 convex hull",
        "격자별 자연그늘 면적 / 격자 면적 → [0,1] natural 피처",
        "외부 라이브러리 없이 shapely.affinity.translate 로 직접 계산",
        "건물 입력은 다음 슬라이드의 CV-A로 자동 교체됨",
    ], size=15)

    _placeholder_image(s, Inches(8.5), Inches(1.9),
                       Inches(4.5), Inches(4.5),
                       "건물 + 그림자 시각화\n(선택)")
    _add_footer(s, 7, TOTAL)

    # ────────── 8. CV-A: 위성 + Mobile-SAM (NEW) ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "CV-A · 위성 항공사진 + Mobile-SAM",
                    "딥러닝 zero-shot segmentation으로 동작구 건물 자동 추출")

    _add_bullets(s, Inches(0.75), Inches(1.9), Inches(6.5), Inches(4.5), [
        "V-World WMTS z=15 항공사진 → 동작구 BBOX 48 타일 합성",
        "Mobile-SAM (Meta, 2023) — 40MB 경량 SAM, CPU 추론 가능",
        "필터: 면적 200~30k px², 종횡비 0.2~5, 평균 밝기 80~220",
        "결과: 더미 19동 → 실측 30동 자동 추출",
        "픽셀 → EPSG:3857 → WGS84 polygon 변환 → buildings.geojson",
        "파이프라인 첫 실행 시 자동 1회, 이후 캐시 사용",
    ], size=14)

    # 산출물 박스
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(7.5), Inches(1.9),
                              Inches(5.3), Inches(4.5))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xF5, 0xF8, 0xFD)
    box.line.color.rgb = COLOR_PRIMARY
    box.line.width = Pt(1.5)
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.3); tf.margin_top = Inches(0.3)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "📁 output/cv_buildings_overlay.png"
    _set_font(r, size=14, bold=True, color=COLOR_PRIMARY)
    for line_txt in [
        "",
        "위성 이미지 (2048×1536)",
        "+ SAM 마스크 노란색 오버레이",
        "+ 추출 polygon 녹색 외곽선",
        "",
        "30동 분포: 노량진·사당·이수·",
        "상도로·장승배기·흑석동",
    ]:
        p = tf.add_paragraph()
        r = p.add_run(); r.text = line_txt
        _set_font(r, size=12, color=COLOR_DARK)
        p.space_before = Pt(2)
    _add_footer(s, 8, TOTAL)

    # ────────── 9. CV-B: 거리뷰 + SegFormer (NEW) ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "CV-B · 거리뷰 + SegFormer (CityScapes)",
                    "지면 시점에서 본 보행 환경을 19-class 의미 분할")

    _add_bullets(s, Inches(0.75), Inches(1.9), Inches(6.5), Inches(4.5), [
        "Mapillary 거리뷰 — 동작구 BBOX 4×4 분할 검색 → 1,302장 발견",
        "후보 19개 격자에 nearest 매핑 → 격자당 ≤3장 다운로드",
        "HuggingFace SegFormer-b0 (CityScapes 19 classes pretrained)",
        "주요 클래스: building · vegetation · road · sidewalk · sky",
        "Treepedia(MIT)·Place Pulse 류 선행연구의 그늘막 응용",
    ], size=14)

    # Score 식 박스
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(7.5), Inches(1.9),
                              Inches(5.3), Inches(2.0))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0x21, 0x21, 0x21)
    box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.2); tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "그늘 결핍 지수"
    _set_font(r, size=14, bold=True, color=RGBColor(0xFF, 0xEE, 0x58))
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r = p2.add_run(); r.text = "deficit ="
    _set_font(r, size=12, color=RGBColor(0xCC, 0xCC, 0xCC))
    p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.CENTER
    r = p3.add_run(); r.text = "(road + sidewalk)"
    _set_font(r, size=14, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    p4 = tf.add_paragraph(); p4.alignment = PP_ALIGN.CENTER
    r = p4.add_run(); r.text = "× (1 − building − vegetation)"
    _set_font(r, size=14, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    # 결과 박스
    box2 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                               Inches(7.5), Inches(4.1),
                               Inches(5.3), Inches(2.3))
    box2.fill.solid()
    box2.fill.fore_color.rgb = RGBColor(0xFFF, 0xFA, 0xE6) \
        if False else RGBColor(0xFF, 0xF4, 0xE5)
    box2.line.color.rgb = COLOR_WARN
    box2.line.width = Pt(1.5)
    tf = box2.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.25); tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "📊 결과"
    _set_font(r, size=14, bold=True, color=COLOR_WARN)
    for line_txt in [
        "TOP10 평균 deficit: 0.190",
        "Score 식 6번째 피처 통합",
        "강건 입지 +1: 흑석동 (CV-B 부각)",
    ]:
        p = tf.add_paragraph()
        r = p.add_run(); r.text = "• " + line_txt
        _set_font(r, size=13, color=COLOR_DARK)
        p.space_before = Pt(4)
    _add_footer(s, 9, TOTAL)

    # ────────── 10. 시나리오 5개 민감도 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "시나리오 민감도 분석 (5개 프리셋)",
                    "정책 관점별 가중치 × 동일 피처셋 → TOP 10 변화")

    rows = [
        ("시나리오", "강조", "최고 Score", "유니크"),
        ("기본", "균형 (25/25/20)", "0.620", "0곳"),
        ("고령자 중시", "vuln 0.40", "0.585", "0곳"),
        ("폭염 중시", "lst 0.40", "0.664", "1곳 독점"),
        ("유동인구 중시", "pop 0.40", "0.726", "3곳 독점"),
        ("보행환경 중시 (NEW)", "streetview_deficit 0.40", "0.665", "0곳"),
    ]
    left = Inches(0.75); top = Inches(1.9)
    tbl = s.shapes.add_table(rows=len(rows), cols=4,
                              left=left, top=top,
                              width=Inches(12), height=Inches(3.0)).table
    widths = [Inches(3.5), Inches(3.5), Inches(2.0), Inches(3.0)]
    for i, cw in enumerate(widths):
        tbl.columns[i].width = cw
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci); cell.text = ""
            tf = cell.text_frame
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = val
            if ri == 0:
                _set_font(r, size=14, bold=True,
                           color=RGBColor(0xFF, 0xFF, 0xFF))
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_PRIMARY
            else:
                bold = ri in (3, 4, 5)  # 폭염·유동인구·보행환경 강조
                _set_font(r, size=13, bold=bold, color=COLOR_DARK)

    _add_text(s, Inches(0.75), Inches(5.2), Inches(12), Inches(0.5),
              "💡 CV-B 통합으로 \"보행환경 중시\" 시나리오 신규 추가 "
              "→ 정책 검증 차원이 한 단계 늘어남",
              size=14, bold=True, color=COLOR_ACCENT)
    _add_text(s, Inches(0.75), Inches(5.8), Inches(12), Inches(0.5),
              "🎯 5가지 관점 모두에서 공통 추천되는 입지가 존재 (다음 슬라이드)",
              size=14, color=COLOR_SUB)
    _add_footer(s, 10, TOTAL)

    # ────────── 11. 강건 입지 3곳 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "강건 입지 · Robust Location",
                    "5개 시나리오 공통 추천 = 어떤 정책 관점에서도 필수")

    # 3 카드
    robust = [
        ("37.4907, 126.9647", "동작대로", "사당-이수 축", COLOR_ACCENT),
        ("37.4898, 126.9670", "동작대로", "사당역 인근", COLOR_ACCENT),
        ("37.5068, 126.9567", "흑석동", "한강변 주거밀집", COLOR_VULN),
    ]
    left = Inches(0.75); top = Inches(2.0)
    w = Inches(3.95); h = Inches(3.2); gap = Inches(0.15)
    for i, (coord, road, area, color) in enumerate(robust):
        x = left + Inches(i * (3.95 + 0.15))
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, w, h)
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xFA, 0xFA, 0xFA)
        box.line.color.rgb = color
        box.line.width = Pt(2.5)
        tf = box.text_frame; tf.word_wrap = True
        tf.margin_left = Inches(0.2); tf.margin_top = Inches(0.3)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = f"#{i+1}"
        _set_font(r, size=16, bold=True, color=color)
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r = p2.add_run(); r.text = road
        _set_font(r, size=28, bold=True, color=COLOR_DARK)
        p2.space_before = Pt(8)
        p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.CENTER
        r = p3.add_run(); r.text = area
        _set_font(r, size=16, color=COLOR_SUB)
        p3.space_before = Pt(6)
        p4 = tf.add_paragraph(); p4.alignment = PP_ALIGN.CENTER
        r = p4.add_run(); r.text = coord
        _set_font(r, size=12, color=COLOR_SUB)
        p4.space_before = Pt(12)

    _add_text(s, Inches(0.75), Inches(5.5), Inches(12), Inches(0.5),
              "정책적 함의: 예산 제약 시 이 3곳이 최우선 설치 대상",
              size=16, bold=True, color=COLOR_PRIMARY,
              align=PP_ALIGN.CENTER)
    _add_text(s, Inches(0.75), Inches(6.1), Inches(12), Inches(0.5),
              "CV-B 보행환경 시나리오까지 통과 → 환승 축 2곳 + 흑석동 주거 1곳",
              size=13, color=COLOR_SUB, align=PP_ALIGN.CENTER)
    _add_footer(s, 11, TOTAL)

    # ────────── 10. 발표자료 3대 구역 검증 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "1차 발표자료 3대 집중구역 검증",
                    "사전 선정한 후보 구역을 알고리즘이 얼마나 재현했는가?")

    rows = [
        ("구역", "판정", "반경 내 TOP", "최근접", "해설"),
        ("노량진역-수산시장", "△", "0곳", "1,355m",
         "기존 그늘막 선배치 → 페널티 작동 (의도대로)"),
        ("사당역-이수역 축", "✓", "2곳 (TOP1·TOP2)", "167m",
         "환승 대기 + 오후 열스트레스 최상위"),
        ("상도로 주거축", "✓", "3곳 (TOP5~7)", "66m",
         "고령자 비율 + 자연그늘 부족 이중 반영"),
    ]
    left = Inches(0.4); top = Inches(2.0)
    tbl = s.shapes.add_table(rows=len(rows), cols=5,
                              left=left, top=top,
                              width=Inches(12.5),
                              height=Inches(3.3)).table
    widths = [Inches(3.0), Inches(1.0), Inches(2.5),
              Inches(1.5), Inches(4.5)]
    for i, cw in enumerate(widths):
        tbl.columns[i].width = cw
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci); cell.text = ""
            tf = cell.text_frame
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = val
            if ri == 0:
                _set_font(r, size=13, bold=True,
                           color=RGBColor(0xFF, 0xFF, 0xFF))
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_PRIMARY
            else:
                is_pass = ci == 1 and val == "✓"
                is_partial = ci == 1 and val == "△"
                color = (COLOR_PRIMARY if is_pass
                         else COLOR_WARN if is_partial
                         else COLOR_DARK)
                _set_font(r, size=13, bold=is_pass or is_partial, color=color)

    _add_text(s, Inches(0.75), Inches(5.7), Inches(12), Inches(0.9),
              "💡 노량진 '0곳'은 실패가 아님: 더미 데이터에서 기존 그늘막을 "
              "노량진 보행로에 우선 배치한 결과,\n"
              "'기존 그늘막 반경 150m 외' 제약으로 자연스럽게 후순위로 밀린 것. "
              "이미 커버된 곳은 제외하는 알고리즘이 의도대로 작동한 사례.",
              size=13, color=COLOR_SUB)
    _add_footer(s, 12, TOTAL)

    # ────────── 13. Streamlit 대시보드 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "인터랙티브 대시보드",
                    "가중치 슬라이더 → TOP 10 실시간 재계산 (Streamlit)")

    _add_bullets(s, Inches(0.75), Inches(1.9), Inches(6.5), Inches(4.5), [
        "`streamlit run app.py` 로 기동 → http://localhost:8501",
        "사이드바: 시나리오 프리셋 드롭다운 + 5개 가중치 슬라이더",
        "본문: Folium 지도 임베드 + TOP 10 표 + 통계",
        "캐싱: @st.cache_resource 로 격자·피처는 1회 계산,\n"
        "  슬라이더 조작은 가중합 재계산만 (밀리초 반응)",
        "발표 현장에서 \"만약 vuln을 더 높이면?\" 질문에 즉답 가능",
    ], size=15)

    _placeholder_image(s, Inches(7.5), Inches(1.9),
                       Inches(5.5), Inches(4.5),
                       "app.py 대시보드\n스크린샷 배치")
    _add_footer(s, 13, TOTAL)

    # ────────── 14. 한계 + 요약 ──────────
    s = prs.slides.add_slide(blank)
    _add_header_bar(s, "한계 · 다음 단계 · 한 줄 요약", None)

    _add_text(s, Inches(0.75), Inches(1.7), Inches(6), Inches(0.4),
              "현재 한계", size=18, bold=True, color=COLOR_ACCENT)
    _add_bullets(s, Inches(0.75), Inches(2.2), Inches(6.5), Inches(2.8), [
        "5종 데이터 모두 더미 (파이프라인 자체는 실데이터 자동 전환)",
        "LST 래스터 직접 파싱 미연결 (Landsat ST_B10)",
        "건물 footprint 더미 19개 → 실 shp 확보 시 교체",
        "예산 제약 미반영 (K개 최적 조합 = 배낭 문제)",
    ], size=14)

    _add_text(s, Inches(7.5), Inches(1.7), Inches(6), Inches(0.4),
              "다음 단계", size=18, bold=True, color=COLOR_PRIMARY)
    _add_bullets(s, Inches(7.5), Inches(2.2), Inches(5.5), Inches(2.8), [
        "서울 열린데이터광장 API 연결 (P0)",
        "국가공간정보포털 도로대장 shp (인도 폭)",
        "격자 스코어 parquet 캐싱",
        "타 자치구 확장 (BBOX 교체만으로 재사용)",
    ], size=14)

    # 한 줄 요약 박스
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(0.75), Inches(5.4),
                              Inches(12), Inches(1.4))
    box.fill.solid()
    box.fill.fore_color.rgb = COLOR_DARK
    box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.3); tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("항공사진과 거리뷰까지 컴퓨터 비전으로 읽어내,")
    _set_font(r, size=18, bold=True, color=RGBColor(0xFF, 0xEE, 0x58))
    p1b = tf.add_paragraph(); p1b.alignment = PP_ALIGN.CENTER
    r = p1b.add_run()
    r.text = "5가지 정책 관점 모두에서 살아남는 강건 입지 3곳을 찾아냈다."
    _set_font(r, size=18, bold=True, color=RGBColor(0xFF, 0xEE, 0x58))
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r = p2.add_run()
    r.text = "— SAM(항공) + SegFormer(거리뷰) + MCDA 가중합 + 시나리오 민감도"
    _set_font(r, size=12, color=RGBColor(0xCC, 0xCC, 0xCC))
    p2.space_before = Pt(8)
    _add_footer(s, 14, TOTAL)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"[완료] {path}")
    print(f"  슬라이드 12장 · 16:9 · 맑은 고딕")
    print(f"  이미지 자리(placeholder) 3곳: shade_map / 건물-그림자 / 대시보드")
