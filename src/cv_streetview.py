"""STEP CV-B — Mapillary 거리뷰 + DeepLabV3/SegFormer semantic segmentation.

각 격자 후보 좌표 주변의 Mapillary 거리뷰 이미지를 검색·다운로드하고,
CityScapes 19-class pretrained SegFormer 로 분할 → 픽셀 비율 계산:
  - building, vegetation, road, sidewalk, sky, ...

shade_deficit (그늘 결핍 지수) [0,1]:
  = (보도+도로 비율) × (1 − 건물 − 식생)
  → 보행 공간은 많은데 그늘 만드는 요소(건물 그림자·가로수)가 적을수록 ↑

격자별 점수: 격자 중심에서 가장 가까운 N장 거리뷰의 평균 deficit.

실행:
    python -X utf8 -m src.cv_streetview --candidates output/candidate_grids.json

산출물:
    data/processed/streetview_images/*.jpg     캐시
    data/processed/streetview_features.json    이미지별 클래스 비율
    data/processed/grid_streetview.csv         격자ID, lon, lat, shade_deficit
    output/cv_streetview_overlay.png           (선택) 한 장 segmentation 시각화
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Iterable
import numpy as np
import pandas as pd
import requests
from PIL import Image
from .config import (DATA_RAW, DATA_PROCESSED, OUTPUT, MAPILLARY_TOKEN,
                      DONGJAK_BBOX)


# CityScapes 19-class label index (SegFormer 모델 기준)
CITYSCAPES_LABELS = [
    "road", "sidewalk", "building", "wall", "fence",
    "pole", "traffic light", "traffic sign", "vegetation", "terrain",
    "sky", "person", "rider", "car", "truck",
    "bus", "train", "motorcycle", "bicycle",
]
LBL = {name: i for i, name in enumerate(CITYSCAPES_LABELS)}

# 각 클래스별 시각화 색상 (CityScapes 표준 팔레트)
PALETTE = np.array([
    [128, 64,128], [244, 35,232], [ 70, 70, 70], [102,102,156], [190,153,153],
    [153,153,153], [250,170, 30], [220,220,  0], [107,142, 35], [152,251,152],
    [ 70,130,180], [220, 20, 60], [255,  0,  0], [  0,  0,142], [  0,  0, 70],
    [  0, 60,100], [  0, 80,100], [  0,  0,230], [119, 11, 32],
], dtype=np.uint8)


# ─────────────────────────────────────────────────────────
# Mapillary
# ─────────────────────────────────────────────────────────
def _mask_token(s: str) -> str:
    """에러 메시지에서 토큰 마스킹."""
    if MAPILLARY_TOKEN and MAPILLARY_TOKEN in s:
        return s.replace(MAPILLARY_TOKEN, "MLY|***MASKED***")
    # URL-encoded 형태도 처리
    import urllib.parse
    if MAPILLARY_TOKEN:
        enc = urllib.parse.quote(MAPILLARY_TOKEN, safe="")
        if enc in s:
            return s.replace(enc, "MLY%7C***MASKED***")
    return s


def _split_bbox(min_lon, min_lat, max_lon, max_lat, n=4):
    """BBOX를 n×n 격자로 분할."""
    dlon = (max_lon - min_lon) / n
    dlat = (max_lat - min_lat) / n
    cells = []
    for i in range(n):
        for j in range(n):
            cells.append((
                min_lon + i * dlon, min_lat + j * dlat,
                min_lon + (i + 1) * dlon, min_lat + (j + 1) * dlat,
            ))
    return cells


def _request_mapillary_page(bbox_str: str, limit: int = 200) -> list[dict]:
    url = "https://graph.mapillary.com/images"
    params = {
        "access_token": MAPILLARY_TOKEN,
        "fields": "id,thumb_1024_url,geometry",
        "bbox": bbox_str,
        "limit": str(limit),
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"    [Mapillary] bbox={bbox_str} status={r.status_code}")
            return []
        return r.json().get("data", [])
    except Exception as e:
        print(f"    [Mapillary] bbox={bbox_str} 실패: {_mask_token(str(e))}")
        return []


def search_mapillary_in_bbox(min_lon: float, min_lat: float,
                               max_lon: float, max_lat: float,
                               limit_per_cell: int = 200,
                               grid_n: int = 4) -> list[dict]:
    """BBOX를 grid_n×grid_n으로 나눠 각 셀 검색 (Mapillary 500 회피 + 더 많은 결과).

    Returns: [{"id": str, "thumb_url": str, "lon": float, "lat": float}, ...]
    """
    if not MAPILLARY_TOKEN:
        raise RuntimeError("MAPILLARY_TOKEN 가 .env 에 없습니다.")

    cells = _split_bbox(min_lon, min_lat, max_lon, max_lat, n=grid_n)
    print(f"  [Mapillary] BBOX {grid_n}x{grid_n} 분할 검색 ({len(cells)} 셀)")

    seen_ids = set()
    out = []
    for k, (lo, la, lo2, la2) in enumerate(cells, 1):
        bbox = f"{lo},{la},{lo2},{la2}"
        data = _request_mapillary_page(bbox, limit=limit_per_cell)
        new = 0
        for d in data:
            if d.get("id") in seen_ids:
                continue
            coord = d.get("geometry", {}).get("coordinates", [None, None])
            if coord[0] is None or coord[1] is None:
                continue
            seen_ids.add(d["id"])
            out.append({
                "id": d["id"],
                "thumb_url": d.get("thumb_1024_url"),
                "lon": coord[0], "lat": coord[1],
            })
            new += 1
        if k % 4 == 0 or new > 0:
            print(f"    cell {k}/{len(cells)}: +{new} (누적 {len(out)})")
        time.sleep(0.05)
    return out


def assign_images_to_candidates(candidates: list[dict],
                                  images: list[dict],
                                  per_point: int = 3) -> list[dict]:
    """각 후보 좌표에 가장 가까운 N장의 이미지를 할당."""
    if not images:
        return []
    img_arr = np.array([[img["lon"], img["lat"]] for img in images])
    from scipy.spatial import cKDTree
    tree = cKDTree(img_arr)
    out = []
    for c in candidates:
        k = min(per_point, len(images))
        _, idx = tree.query([c["lon"], c["lat"]], k=k)
        if isinstance(idx, (int, np.integer)):
            idx = [idx]
        for i in idx:
            img = images[int(i)]
            out.append({**img, "grid_id": c["id"],
                         "grid_lon": c["lon"], "grid_lat": c["lat"]})
    return out


def download_image(url: str, out_path: Path) -> bool:
    if out_path.exists():
        return True
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  [download] 실패 {url[:60]}...: {e}")
        return False


# ─────────────────────────────────────────────────────────
# Segmentation
# ─────────────────────────────────────────────────────────
def load_segformer():
    """HuggingFace SegFormer-b0 (CityScapes 19 classes pretrained)."""
    from transformers import (SegformerForSemanticSegmentation,
                                SegformerImageProcessor)
    model_name = "nvidia/segformer-b0-finetuned-cityscapes-1024-1024"
    print(f"  [SegFormer] {model_name} 로딩 중...")
    processor = SegformerImageProcessor.from_pretrained(model_name)
    model = SegformerForSemanticSegmentation.from_pretrained(model_name)
    model.eval()
    return processor, model


def segment_image(img_path: Path, processor, model) -> np.ndarray:
    """이미지 → CityScapes 19-class label map (H, W) int."""
    import torch
    img = Image.open(img_path).convert("RGB")
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    # logits shape: (1, 19, H/4, W/4)
    logits = outputs.logits
    # 원본 이미지 크기로 upsample
    upsampled = torch.nn.functional.interpolate(
        logits, size=img.size[::-1], mode="bilinear", align_corners=False
    )
    pred = upsampled.argmax(dim=1).squeeze().cpu().numpy().astype(np.int32)
    return pred


def class_ratios(pred: np.ndarray) -> dict[str, float]:
    """각 CityScapes 클래스별 픽셀 비율."""
    total = pred.size
    ratios = {}
    for name, idx in LBL.items():
        ratios[name] = float((pred == idx).sum() / total)
    return ratios


def shade_deficit(ratios: dict[str, float]) -> float:
    """그늘 결핍 지수 [0,1].

    walkable = road + sidewalk (보행 공간)
    shading  = building + vegetation (그늘 자원)
    deficit  = walkable * (1 - shading)
    """
    walkable = ratios["road"] + ratios["sidewalk"]
    shading = ratios["building"] + ratios["vegetation"]
    return float(walkable * (1.0 - min(shading, 1.0)))


def render_seg_overlay(img_path: Path, pred: np.ndarray, out_path: Path):
    """원본 + segmentation 오버레이 시각화."""
    img = np.array(Image.open(img_path).convert("RGB"))
    color_seg = PALETTE[pred.clip(0, len(PALETTE) - 1)]
    blended = (img * 0.55 + color_seg * 0.45).astype(np.uint8)
    Image.fromarray(blended).save(out_path)


# ─────────────────────────────────────────────────────────
# 격자별 집계
# ─────────────────────────────────────────────────────────
def process_candidates(candidates: list[dict],
                        per_point: int = 3,
                        max_total: int | None = None) -> dict:
    """후보 좌표 리스트 → 거리뷰 이미지 수집·세그멘테이션 → 격자별 deficit.

    candidates: [{"id": str, "lon": float, "lat": float}, ...]
    """
    img_dir = DATA_PROCESSED / "streetview_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 1) 동작구 BBOX 전체에서 거리뷰 한 번에 검색
    print(f"[B-1] Mapillary 동작구 BBOX 전체 검색")
    all_images = search_mapillary_in_bbox(
        DONGJAK_BBOX["min_lon"], DONGJAK_BBOX["min_lat"],
        DONGJAK_BBOX["max_lon"], DONGJAK_BBOX["max_lat"],
    )
    print(f"  [B-1] 동작구 가용 거리뷰: {len(all_images)} 장")

    if not all_images:
        print("  [B-1] Mapillary 한국 커버리지 부족. streetview_deficit=0 으로 진행.")
        return {"images": [], "grid_deficit": []}

    # 후보 좌표별 nearest 이미지 매핑
    assigned = assign_images_to_candidates(candidates, all_images,
                                              per_point=per_point)
    print(f"  [B-1] 후보 매핑: {len(assigned)} 매칭")

    # 다운로드 (중복 제거)
    seen = set()
    img_records = []
    for a in assigned:
        if a["id"] in seen or not a.get("thumb_url"):
            continue
        seen.add(a["id"])
        local = img_dir / f"{a['id']}.jpg"
        if download_image(a["thumb_url"], local):
            img_records.append({
                "img_id": a["id"], "local": str(local),
                "img_lon": a["lon"], "img_lat": a["lat"],
                "grid_id": a["grid_id"],
                "grid_lon": a["grid_lon"], "grid_lat": a["grid_lat"],
            })
        time.sleep(0.03)
        if max_total and len(img_records) >= max_total:
            break

    if not img_records:
        print("  [B-1] thumb_url 모두 실패. streetview_deficit=0.")
        return {"images": [], "grid_deficit": []}

    print(f"  [B-1] 다운로드 완료: {len(img_records)} 장")

    # 2) Segmentation
    print(f"[B-2] CityScapes SegFormer 추론 ({len(img_records)}장)")
    processor, model = load_segformer()
    feature_records = []
    overlay_done = False
    for i, rec in enumerate(img_records, 1):
        try:
            pred = segment_image(Path(rec["local"]), processor, model)
            ratios = class_ratios(pred)
            deficit = shade_deficit(ratios)
            rec.update(ratios)
            rec["shade_deficit"] = deficit
            feature_records.append(rec)
            if not overlay_done:
                render_seg_overlay(Path(rec["local"]), pred,
                                    OUTPUT / "cv_streetview_overlay.png")
                overlay_done = True
            if i % 5 == 0 or i == len(img_records):
                print(f"  [seg] {i}/{len(img_records)}")
        except Exception as e:
            print(f"  [seg] {rec['img_id']} 실패: {e}")

    # 3) 격자별 평균 deficit (좌표는 first 로 보존 → data_loader 매칭용)
    df = pd.DataFrame(feature_records)
    grid_agg = df.groupby("grid_id").agg(
        grid_lon=("grid_lon", "first"),
        grid_lat=("grid_lat", "first"),
        shade_deficit=("shade_deficit", "mean"),
        n_images=("img_id", "count"),
        building_ratio=("building", "mean"),
        vegetation_ratio=("vegetation", "mean"),
        sidewalk_ratio=("sidewalk", "mean"),
    ).reset_index()

    return {
        "images": feature_records,
        "grid_deficit": grid_agg.to_dict(orient="records"),
    }


def save_outputs(result: dict):
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    feat_path = DATA_PROCESSED / "streetview_features.json"
    feat_path.write_text(json.dumps(result["images"], ensure_ascii=False,
                                      indent=2),
                          encoding="utf-8")
    print(f"  [save] {feat_path} ({len(result['images'])} images)")

    grid_path = DATA_PROCESSED / "grid_streetview.csv"
    pd.DataFrame(result["grid_deficit"]).to_csv(grid_path, index=False,
                                                  encoding="utf-8-sig")
    print(f"  [save] {grid_path}")


def run_for_top_candidates(top_gdf, per_point: int = 3):
    """main 파이프라인에서 호출: TOP K 후보지 거리뷰 분석."""
    candidates = [
        {"id": int(i), "lon": float(r["lon"]), "lat": float(r["lat"])}
        for i, r in top_gdf.iterrows()
    ]
    result = process_candidates(candidates, per_point=per_point)
    save_outputs(result)
    return result


if __name__ == "__main__":
    # CLI: 임의 격자 좌표 JSON 전달 (디버그용)
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", type=str, default=None,
                    help='JSON: [{"id":1,"lon":...,"lat":...}, ...]')
    p.add_argument("--per_point", type=int, default=3)
    args = p.parse_args()
    if args.candidates:
        cands = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    else:
        # 기본: 동작구 핵심 좌표 (디버그)
        cands = [
            {"id": 1, "lon": 126.9647, "lat": 37.4907},  # 사당-이수
            {"id": 2, "lon": 126.9353, "lat": 37.4986},  # 상도로
            {"id": 3, "lon": 126.9410, "lat": 37.5131},  # 노량진
        ]
    result = process_candidates(cands, per_point=args.per_point)
    save_outputs(result)
