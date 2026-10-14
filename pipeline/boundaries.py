"""Download administrative boundaries from geoBoundaries (gbOpen).

geoBoundaries is built from OpenStreetMap and other open sources and is
released under CC BY-SA. ADM1 is the region level and ADM2 the district level.
"""

from __future__ import annotations

import json
import urllib.request

import geopandas as gpd
import pandas as pd

from pipeline.config import BOUNDARY_DIR, COUNTRIES, LEVELS

API = "https://www.geoboundaries.org/api/current/gbOpen/{iso}/{level}/"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def fetch_all() -> None:
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)
    for iso in COUNTRIES:
        for level in LEVELS:
            meta = json.loads(_get(API.format(iso=iso, level=level)))
            path = BOUNDARY_DIR / f"{iso}_{level}.geojson"
            path.write_bytes(_get(meta["gjDownloadURL"]))
            (BOUNDARY_DIR / f"{iso}_{level}.meta.json").write_text(
                json.dumps({k: meta.get(k) for k in
                            ("boundaryID", "boundaryName", "boundaryYearRepresented", "boundarySource",
                             "boundaryLicense", "buildDate", "admUnitCount")}, indent=2),
                encoding="utf-8")
            print(f"{iso} {level}: {path.name} ({path.stat().st_size / 1e6:.1f} MB)")


def load_level(level: str) -> gpd.GeoDataFrame:
    """All countries for one level, with an integer `uid` used for rasterising."""
    frames = []
    for iso, country in COUNTRIES.items():
        g = gpd.read_file(BOUNDARY_DIR / f"{iso}_{level}.geojson")[["shapeName", "geometry"]]
        g = g.rename(columns={"shapeName": "name"})
        g["iso"] = iso
        g["country"] = country
        frames.append(g)
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    out["uid"] = range(len(out))
    return out


if __name__ == "__main__":
    fetch_all()
