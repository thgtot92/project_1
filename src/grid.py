"""동작구 100m 격자 생성"""
import geopandas as gpd
import numpy as np
from shapely.geometry import box
from .config import DONGJAK_BBOX, GRID_SIZE_M, CRS_WGS84, CRS_KOREA


def build_grid() -> gpd.GeoDataFrame:
    """동작구 BBOX를 100m 격자로 분할한 GeoDataFrame 반환 (EPSG:5179)."""
    bbox_wgs = gpd.GeoSeries(
        [box(DONGJAK_BBOX["min_lon"], DONGJAK_BBOX["min_lat"],
             DONGJAK_BBOX["max_lon"], DONGJAK_BBOX["max_lat"])],
        crs=CRS_WGS84,
    )
    bbox_m = bbox_wgs.to_crs(CRS_KOREA).iloc[0].bounds  # (minx, miny, maxx, maxy)
    minx, miny, maxx, maxy = bbox_m

    xs = np.arange(minx, maxx, GRID_SIZE_M)
    ys = np.arange(miny, maxy, GRID_SIZE_M)
    cells = [box(x, y, x + GRID_SIZE_M, y + GRID_SIZE_M) for x in xs for y in ys]

    gdf = gpd.GeoDataFrame({"geometry": cells}, crs=CRS_KOREA)
    gdf["cell_id"] = np.arange(len(gdf))
    gdf["centroid"] = gdf.geometry.centroid
    return gdf


if __name__ == "__main__":
    g = build_grid()
    print(f"격자 수: {len(g):,}  /  CRS: {g.crs}")
    print(g.head())
