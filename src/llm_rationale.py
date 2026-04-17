"""STEP 3 — LLM 자연어 설치 근거 생성.

OPENAI_API_KEY 가 없으면 룰 베이스 템플릿으로 fallback.
"""
from __future__ import annotations
import os
import json
import geopandas as gpd
from .config import LLM_MODEL


def _rule_based(row) -> str:
    return (
        f"유동인구 {row['pop']:.0f}명/셀, 지표온도 {row['lst_c']:.1f}℃, "
        f"취약계층 비율 {row['vuln_ratio']*100:.1f}%. "
        f"기존 그늘막 커버리지 낮아 설치 시 체감 효과가 큰 구역."
    )


def generate_rationale(top: gpd.GeoDataFrame) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [
            {"rank": i + 1, "lat": r["lat"], "lon": r["lon"],
             "score": float(r["score"]), "rationale": _rule_based(r)}
            for i, r in top.iterrows()
        ]

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    rows = [
        {
            "rank": i + 1,
            "lat": float(r["lat"]), "lon": float(r["lon"]),
            "score": float(r["score"]),
            "pop": float(r["pop"]),
            "lst_c": float(r["lst_c"]),
            "vuln_ratio": float(r["vuln_ratio"]),
        } for i, r in top.iterrows()
    ]
    prompt = (
        "다음은 서울 동작구 여름 그늘막 설치 후보지 데이터다. "
        "각 후보지에 대해 2문장으로 정책 결정자를 위한 설치 근거를 작성하라. "
        "유동인구·지표온도·취약계층 수치를 자연스럽게 인용하라.\n"
        + json.dumps(rows, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    text = resp.choices[0].message.content
    # 단순 반환 (LLM 출력을 그대로 근거 블록으로 사용)
    return [{"rank": r["rank"], "lat": r["lat"], "lon": r["lon"],
             "score": r["score"], "rationale": text} for r in rows]
