"""STEP CV-A — 위성 항공사진 + SAM 건물 footprint 자동 추출.

V-World WMS 에서 동작구 BBOX 항공사진 타일 다운로드 →
Mobile-SAM (zero-shot segmentation) → 면적·종횡비·밝기 필터로 건물만 추림 →
EPSG:4326 polygon 좌표로 변환 → data/raw/buildings.geojson 저장.

실행:
    python -X utf8 -m src.cv_buildings

산출물:
    data/raw/satellite_dongjak.png       — 합성 항공사진 (SAM 입력)
    data/raw/satellite_dongjak.world     — 좌표 변환 메타 (lon/lat per pixel)
    data/raw/buildings.geojson           — Polygon + height_m
    output/cv_buildings_overlay.png      — SAM 결과 시각화
"""
from __future__ import annotations
import io
import json
import math
from pathlib import Path
import numpy as np
import requests
from PIL import Image
from .config import (DATA_RAW, OUTPUT, DONGJAK_BBOX, VWORLD_API_KEY)


# WGS84 → Web Mercator 헬퍼 (V-World WMS 좌표계 EPSG:3857)
def _wgs_to_merc(lon: float, lat: float) -> tuple[float, float]:
    R = 6378137.0
    x = R * math.radians(lon)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def _merc_to_wgs(x: float, y: float) -> tuple[float, float]:
    R = 6378137.0
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return lon, lat


def _lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    """WGS84 → XYZ 타일 좌표 (Slippy map tilenames)."""
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)
            / 2.0 * n)
    return x, y


def _tile_to_lonlat(x: int, y: int, z: int) -> tuple[float, float]:
    """XYZ 타일 좌상단 → WGS84."""
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    return lon, math.degrees(lat_rad)


def fetch_vworld_satellite(out_path: Path, zoom: int = 15) -> tuple[Path, dict]:
    """V-World WMTS Satellite 타일을 동작구 BBOX 범위만큼 다운받아 합성.

    Returns: (out_path, world_meta dict)
    world_meta = {tile_size, x0, y0, nx, ny, zoom, width, height,
                   minx_merc, maxy_merc, px_x, px_y}
    """
    if not VWORLD_API_KEY:
        raise RuntimeError("VWORLD_API_KEY 가 .env 에 없습니다.")

    bbox = DONGJAK_BBOX
    x0, y0 = _lonlat_to_tile(bbox["min_lon"], bbox["max_lat"], zoom)  # 좌상단
    x1, y1 = _lonlat_to_tile(bbox["max_lon"], bbox["min_lat"], zoom)  # 우하단
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    tile_size = 256

    print(f"  [V-World] WMTS z={zoom} 타일 {nx}x{ny} = {nx*ny}장 다운로드")
    canvas = Image.new("RGB", (nx * tile_size, ny * tile_size), (0, 0, 0))

    # V-World WMTS 표준 URL 패턴
    base_url = (f"https://api.vworld.kr/req/wmts/1.0.0/"
                f"{VWORLD_API_KEY}/Satellite/{{z}}/{{y}}/{{x}}.jpeg")

    fetched = 0
    for j, ty in enumerate(range(y0, y1 + 1)):
        for i, tx in enumerate(range(x0, x1 + 1)):
            url = base_url.format(z=zoom, x=tx, y=ty)
            try:
                r = requests.get(url, timeout=20)
                if r.status_code == 200 and len(r.content) > 100:
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    canvas.paste(img, (i * tile_size, j * tile_size))
                    fetched += 1
                else:
                    print(f"    tile {tx},{ty} 실패 status={r.status_code}")
            except Exception as e:
                print(f"    tile {tx},{ty} 예외: {e}")

    if fetched == 0:
        # 응답 디버그
        url = base_url.format(z=zoom, x=x0, y=y0)
        r = requests.get(url, timeout=20)
        snippet = r.content[:300].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"V-World WMTS 모든 타일 실패. 첫 응답 status={r.status_code}\n"
            f"URL: {url}\nBody: {snippet}"
        )

    canvas.save(out_path, "PNG")
    print(f"  [V-World] saved {out_path} "
          f"({canvas.size[0]}x{canvas.size[1]}, {fetched}/{nx*ny} 타일)")

    # 좌표 변환 메타: 타일 좌상단 lon/lat 과 픽셀당 deg
    nw_lon, nw_lat = _tile_to_lonlat(x0, y0, zoom)
    se_lon, se_lat = _tile_to_lonlat(x1 + 1, y1 + 1, zoom)
    width, height = canvas.size

    minx_merc, maxy_merc = _wgs_to_merc(nw_lon, nw_lat)
    maxx_merc, miny_merc = _wgs_to_merc(se_lon, se_lat)
    px_x = (maxx_merc - minx_merc) / width
    px_y = (maxy_merc - miny_merc) / height

    world_meta = {
        "tile_size": tile_size, "x0": x0, "y0": y0,
        "nx": nx, "ny": ny, "zoom": zoom,
        "width": width, "height": height,
        "minx": minx_merc, "maxy": maxy_merc,
        "px_x": px_x, "px_y": px_y,
    }
    # 메타 저장
    world_path = out_path.with_suffix(".world.json")
    world_path.write_text(json.dumps(world_meta), encoding="utf-8")
    return out_path, world_meta


def _pixel_to_lonlat(px: float, py: float, world: dict) -> tuple[float, float]:
    """이미지 픽셀 (px, py) → WGS84 (lon, lat)."""
    x = world["minx"] + px * world["px_x"]
    y = world["maxy"] - py * world["px_y"]
    return _merc_to_wgs(x, y)


def _load_world(world_path: Path) -> dict:
    return json.loads(world_path.read_text(encoding="utf-8"))


def extract_buildings_with_sam(image_path: Path,
                                world: dict) -> list[dict]:
    """Mobile-SAM 자동 마스크 → 건물 footprint 후보 추출.

    필터:
      - 면적 200 ~ 30,000 px² (너무 작거나 큰 건 제외)
      - 평균 밝기 80 ~ 220 (너무 어둡거나 밝으면 그림자/구름)
      - 마스크의 bbox 종횡비 0.2 ~ 5.0 (도로처럼 가늘면 제외)

    각 건물에 추정 높이 부여:
      - 면적 기반 단순 추정: height_m = clip(15 + log(area)*4, 10, 60)
      - 실데이터(국토부 건축물대장) 확보 전 임시
    """
    print("  [SAM] Mobile-SAM 로딩 중...")
    from ultralytics import SAM

    # Mobile-SAM (Ultralytics 자동 다운로드, 약 40MB)
    model = SAM("mobile_sam.pt")

    print(f"  [SAM] 추론 중: {image_path}")
    results = model(str(image_path), verbose=False, retina_masks=True)

    img = np.array(Image.open(image_path).convert("RGB"))
    H, W = img.shape[:2]

    buildings = []
    for r in results:
        if r.masks is None:
            continue
        masks = r.masks.data.cpu().numpy()  # (N, H, W) bool/0-1
        for mask in masks:
            mask_b = mask > 0.5
            area = int(mask_b.sum())
            if area < 200 or area > 30000:
                continue

            # bbox & 종횡비
            ys, xs = np.where(mask_b)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            ratio = bw / max(bh, 1)
            if ratio < 0.2 or ratio > 5.0:
                continue

            # 평균 밝기 (그림자·구름 제외)
            mean_rgb = img[mask_b].mean(axis=0)
            brightness = float(mean_rgb.mean())
            if brightness < 80 or brightness > 220:
                continue

            # 마스크 외곽선 단순화 (cv2 contour → polygon)
            import cv2
            mask_u8 = (mask_b.astype(np.uint8)) * 255
            contours, _ = cv2.findContours(
                mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                continue
            cnt = max(contours, key=cv2.contourArea)
            eps = 0.01 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            if len(approx) < 3:
                continue

            # 픽셀 → 경위도
            ring = []
            for p in approx[:, 0, :]:
                lon, lat = _pixel_to_lonlat(float(p[0]), float(p[1]), world)
                ring.append([lon, lat])
            ring.append(ring[0])  # 닫기

            # 추정 높이
            height_m = float(np.clip(15 + math.log(area) * 4, 10, 60))

            buildings.append({
                "polygon": ring,
                "height_m": height_m,
                "area_px": area,
                "brightness": brightness,
            })

    print(f"  [SAM] 건물 후보 {len(buildings)}동 추출")
    return buildings


def save_buildings_geojson(buildings: list[dict], out_path: Path):
    """GeoJSON FeatureCollection 형식으로 저장."""
    features = []
    for i, b in enumerate(buildings):
        features.append({
            "type": "Feature",
            "id": i,
            "geometry": {
                "type": "Polygon",
                "coordinates": [b["polygon"]],
            },
            "properties": {
                "height_m": b["height_m"],
                "area_px": b["area_px"],
            },
        })
    geojson = {"type": "FeatureCollection", "features": features}
    out_path.write_text(json.dumps(geojson, ensure_ascii=False),
                         encoding="utf-8")
    print(f"  [GeoJSON] saved {out_path} ({len(features)} features)")


def render_overlay(image_path: Path, buildings: list[dict],
                   world: dict, out_path: Path):
    """SAM 마스크 + 추출 건물 폴리곤 시각화."""
    import cv2
    img = cv2.imread(str(image_path))
    overlay = img.copy()
    for b in buildings:
        # WGS84 polygon → pixel
        pts = []
        for lon, lat in b["polygon"]:
            x_merc, y_merc = _wgs_to_merc(lon, lat)
            px = int((x_merc - world["minx"]) / world["px_x"])
            py = int((world["maxy"] - y_merc) / world["px_y"])
            pts.append([px, py])
        pts = np.array(pts, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], (0, 255, 255))  # yellow fill
        cv2.polylines(img, [pts], True, (0, 255, 0), 2)
    blended = cv2.addWeighted(overlay, 0.35, img, 0.65, 0)
    cv2.imwrite(str(out_path), blended)
    print(f"  [overlay] saved {out_path}")


def run(zoom: int = 15):
    print("[CV-A] 위성 항공사진 + SAM 건물 추출")
    sat_path = DATA_RAW / "satellite_dongjak.png"
    world_path = sat_path.with_suffix(".world.json")

    if not sat_path.exists() or not world_path.exists():
        fetch_vworld_satellite(sat_path, zoom=zoom)
    else:
        print(f"  [skip] {sat_path} 이미 존재")

    world = _load_world(world_path)
    buildings = extract_buildings_with_sam(sat_path, world)

    save_buildings_geojson(buildings, DATA_RAW / "buildings.geojson")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render_overlay(sat_path, buildings, world,
                    OUTPUT / "cv_buildings_overlay.png")

    print(f"[CV-A] 완료. data_loader.load_buildings() 가 자동 인식합니다.")


if __name__ == "__main__":
    run()
