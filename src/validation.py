"""발표자료의 3대 집중구역과 알고리즘 TOP 10 의 정량 일치도 검증."""
from __future__ import annotations
import math
import geopandas as gpd
from .config import FOCUS_AREAS


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """두 좌표 간 거리 (미터)."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def validate_against_focus_areas(top: gpd.GeoDataFrame) -> dict:
    """각 집중구역 안에 들어간 TOP 후보지 수 + 최근접 거리 집계."""
    result = {}
    for area_name, meta in FOCUS_AREAS.items():
        clat, clon = meta["center"]
        radius = meta["radius_m"]
        hits = []
        nearest_d = float("inf")
        for i, row in top.iterrows():
            d = _haversine_m(clat, clon, row["lat"], row["lon"])
            if d < nearest_d:
                nearest_d = d
            if d <= radius:
                hits.append({
                    "rank": i + 1,
                    "lat": round(row["lat"], 5),
                    "lon": round(row["lon"], 5),
                    "score": round(float(row["score"]), 3),
                    "distance_m": round(d, 0),
                })
        result[area_name] = {
            "center": [clat, clon],
            "radius_m": radius,
            "reason": meta["reason"],
            "top_hits_in_area": len(hits),
            "nearest_top_distance_m": round(nearest_d, 0),
            "hits": hits,
        }
    return result


def print_report(validation: dict) -> None:
    print("\n  === 발표자료 3대 집중구역 일치도 검증 ===")
    for name, v in validation.items():
        status = "✓" if v["top_hits_in_area"] > 0 else "△"
        print(f"  [{status}] {name}")
        print(f"        반경 {v['radius_m']}m 내 TOP 후보: {v['top_hits_in_area']}곳")
        print(f"        최근접 거리: {v['nearest_top_distance_m']:.0f}m")
        if v["hits"]:
            for h in v["hits"]:
                print(f"          · TOP{h['rank']} (score {h['score']}, "
                      f"거리 {h['distance_m']:.0f}m)")
