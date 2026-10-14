"""Compute tree cover loss per district, then add up to regions and countries.

    python -m pipeline.boundaries      # once: download boundaries
    bash download_hansen.sh            # once: download the six Hansen tiles
    python -m pipeline.run             # about 10-30 minutes
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window

from pipeline.boundaries import load_level
from pipeline.config import (CANOPY_MIN, FIRST_YEAR, HANSEN_DIR, HANSEN_VERSION, N_YEARS,
                             PIXEL_DEG, PROCESSED_DIR, SITE_DATA_DIR, TILES)
from pipeline.zonal import accumulate, row_area_ha

CHUNK_ROWS = 1000
YEARS = list(range(FIRST_YEAR, FIRST_YEAR + N_YEARS))


def tile_path(layer: str, tag: str):
    return HANSEN_DIR / f"Hansen_{HANSEN_VERSION}_{layer}_{tag}.tif"


def process_tile(tag: str):
    """Returns (tag, forest_ha, loss_ha, total_ha, seconds) for one tile, over all districts."""
    t0 = time.time()
    districts = load_level("ADM2")
    n = len(districts)
    sindex = districts.sindex
    forest = np.zeros(n)
    loss = np.zeros((n, N_YEARS))
    total = np.zeros(n)

    with rasterio.open(tile_path("lossyear", tag)) as lsrc, rasterio.open(tile_path("treecover2000", tag)) as tsrc:
        top = lsrc.bounds.top
        minx, miny, maxx, maxy = districts.total_bounds
        col0 = max(0, int(np.floor((minx - lsrc.bounds.left) / PIXEL_DEG)))
        col1 = min(lsrc.width, int(np.ceil((maxx - lsrc.bounds.left) / PIXEL_DEG)))
        row0 = max(0, int(np.floor((top - maxy) / PIXEL_DEG)))
        row1 = min(lsrc.height, int(np.ceil((top - miny) / PIXEL_DEG)))
        if col1 <= col0 or row1 <= row0:
            return tag, forest, loss, total, time.time() - t0

        for r in range(row0, row1, CHUNK_ROWS):
            h = min(CHUNK_ROWS, row1 - r)
            win = Window(col0, r, col1 - col0, h)
            transform = lsrc.window_transform(win)
            west, north = transform * (0, 0)
            east, south = transform * (win.width, win.height)
            hits = sindex.query(__import__("shapely").box(west, south, east, north), predicate="intersects")
            if len(hits) == 0:
                continue
            sub = districts.iloc[hits]
            ids = rasterize(((g, int(u)) for g, u in zip(sub.geometry, sub.uid)),
                            out_shape=(h, win.width), transform=transform, fill=-1, dtype="int32")
            if (ids < 0).all():
                continue
            lo = lsrc.read(1, window=win)
            tc = tsrc.read(1, window=win)
            f, l, t = accumulate(lo, tc, ids, row_area_ha(top, r, h), n)
            forest += f
            loss += l
            total += t
    return tag, forest, loss, total, time.time() - t0


def adm1_lookup(districts: gpd.GeoDataFrame, regions: gpd.GeoDataFrame) -> pd.Series:
    """Region name for each district: the region (same country) that contains the district's
    representative point; if none does, the nearest region."""
    pts = districts.copy()
    pts["geometry"] = districts.representative_point()
    out = pd.Series(index=districts.index, dtype=object)
    for iso in districts["iso"].unique():
        d = pts[pts.iso == iso]
        r = regions[regions.iso == iso][["name", "geometry"]].rename(columns={"name": "region"})
        j = gpd.sjoin(d, r, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        missing = j["region"].isna()
        if missing.any():
            near = gpd.sjoin_nearest(d[missing.reindex(d.index, fill_value=False).values], r, how="left")
            near = near[~near.index.duplicated(keep="first")]
            j.loc[near.index, "region"] = near["region"]
        out[j.index] = j["region"]
    return out


def build_tables(districts, forest, loss, total, regions):
    cols = {f"loss_{y}_ha": loss[:, i] for i, y in enumerate(YEARS)}
    d = districts[["uid", "iso", "country", "name"]].copy()
    d["region"] = adm1_lookup(districts, regions).values
    d["area_ha"] = total
    d["forest2000_ha"] = forest
    for k, v in cols.items():
        d[k] = v
    value_cols = ["area_ha", "forest2000_ha"] + list(cols)
    r = d.groupby(["iso", "country", "region"], as_index=False)[value_cols].sum()
    c = d.groupby(["iso", "country"], as_index=False)[value_cols].sum()
    return d, r, c


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    districts = load_level("ADM2")
    regions = load_level("ADM1")
    n = len(districts)
    forest = np.zeros(n)
    loss = np.zeros((n, N_YEARS))
    total = np.zeros(n)

    print(f"{n} districts, {len(TILES)} tiles, canopy >= {CANOPY_MIN}%", flush=True)
    with ProcessPoolExecutor(max_workers=3) as pool:
        for tag, f, l, t, secs in pool.map(process_tile, TILES):
            forest += f
            loss += l
            total += t
            print(f"  tile {tag}: {secs:.0f}s", flush=True)

    d, r, c = build_tables(districts, forest, loss, total, regions)
    d.drop(columns="uid").to_csv(PROCESSED_DIR / "districts.csv", index=False)
    r.to_csv(PROCESSED_DIR / "regions.csv", index=False)
    c.to_csv(PROCESSED_DIR / "countries.csv", index=False)

    write_site_data(d, r, districts, regions)
    meta = {"source": f"Hansen/UMD/Google/USGS/NASA {HANSEN_VERSION}", "canopy_min_percent": CANOPY_MIN,
            "years": [YEARS[0], YEARS[-1]], "boundaries": "geoBoundaries gbOpen (CC BY-SA)"}
    (SITE_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(c.assign(loss_total_ha=c[[f"loss_{y}_ha" for y in YEARS]].sum(axis=1))
           [["country", "area_ha", "forest2000_ha", "loss_total_ha"]].round(0).to_string(index=False))


def _round_geom(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out["geometry"] = out.geometry.simplify(tol, preserve_topology=True)
    return out


def write_site_data(d: pd.DataFrame, r: pd.DataFrame, districts: gpd.GeoDataFrame, regions: gpd.GeoDataFrame) -> None:
    """Small GeoJSON files for the web map. Loss is stored as a list of 24 yearly values in hectares."""
    ycols = [f"loss_{y}_ha" for y in YEARS]

    def pack(tbl: pd.DataFrame) -> list:
        return [[round(float(x), 2) for x in row] for row in tbl[ycols].to_numpy()]

    dg = districts[["uid", "geometry"]].merge(d.drop(columns=["iso", "country", "name"]), on="uid")
    dg = _round_geom(dg.merge(districts[["uid", "iso", "country", "name"]], on="uid"), 0.002)
    dg["loss"] = pack(dg)
    dg = dg[["iso", "country", "name", "region", "area_ha", "forest2000_ha", "loss", "geometry"]]
    dg[["area_ha", "forest2000_ha"]] = dg[["area_ha", "forest2000_ha"]].round(2)
    dg.to_file(SITE_DATA_DIR / "districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

    rg = regions[["iso", "country", "name", "geometry"]].rename(columns={"name": "region"})
    rg = _round_geom(rg.merge(r, on=["iso", "country", "region"], how="left"), 0.005)
    rg["loss"] = pack(rg)
    rg = rg.rename(columns={"region": "name"})[["iso", "country", "name", "area_ha", "forest2000_ha", "loss", "geometry"]]
    rg[["area_ha", "forest2000_ha"]] = rg[["area_ha", "forest2000_ha"]].round(2)
    rg.to_file(SITE_DATA_DIR / "regions.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)


if __name__ == "__main__":
    main()
