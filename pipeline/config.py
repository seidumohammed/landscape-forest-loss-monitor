from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY_DIR = ROOT / "data" / "raw" / "boundaries"
PROCESSED_DIR = ROOT / "data" / "processed"
SITE_DATA_DIR = ROOT / "docs" / "data"

# Tiles are large and kept outside the repo (and outside OneDrive). Override with HANSEN_DIR.
HANSEN_DIR = Path(os.environ.get("HANSEN_DIR", Path.home() / "forest-loss-data" / "hansen"))
HANSEN_VERSION = "GFC-2024-v1.12"
TILES = ["10N_010W", "20N_010W", "10N_000E", "20N_000E", "10N_010E", "20N_010E"]

COUNTRIES = {"GHA": "Ghana", "CIV": "Côte d'Ivoire", "CMR": "Cameroon"}
LEVELS = ["ADM1", "ADM2"]

CANOPY_MIN = 30  # percent canopy cover in 2000 that counts as forest
FIRST_YEAR = 2001
LAST_YEAR = 2024
N_YEARS = LAST_YEAR - FIRST_YEAR + 1

PIXEL_DEG = 0.00025  # Hansen pixel size in degrees (1 arc-second / 4)
M_PER_DEG_LAT = 110_574.0  # near the equator; varies by under 1% across these countries
M_PER_DEG_LON_EQ = 111_320.0
