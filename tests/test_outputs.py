"""Checks on the published outputs. They run only when the processed files exist."""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE = ROOT / "docs" / "data"
needs_data = pytest.mark.skipif(not (PROCESSED / "districts.csv").exists(), reason="run the pipeline first")


def loss_cols(df):
    return [c for c in df.columns if c.startswith("loss_")]


@needs_data
def test_loss_never_exceeds_forest_in_any_unit():
    for name in ("districts", "regions", "countries"):
        df = pd.read_csv(PROCESSED / f"{name}.csv")
        assert (df[loss_cols(df)].sum(axis=1) <= df["forest2000_ha"] + 1e-6).all(), name


@needs_data
def test_districts_add_up_to_regions_and_countries():
    d = pd.read_csv(PROCESSED / "districts.csv")
    r = pd.read_csv(PROCESSED / "regions.csv")
    c = pd.read_csv(PROCESSED / "countries.csv")
    cols = ["area_ha", "forest2000_ha"] + loss_cols(d)
    assert d[cols].sum().to_numpy() == pytest.approx(r[cols].sum().to_numpy(), rel=1e-9)
    assert d[cols].sum().to_numpy() == pytest.approx(c[cols].sum().to_numpy(), rel=1e-9)
    assert len(c) == 3 and len(d) == 353


@needs_data
def test_site_files_keep_loss_at_or_below_forest():
    """Guards against rounding in the published files pushing a tiny unit above 100%."""
    for name in ("districts", "regions"):
        features = json.loads((SITE / f"{name}.geojson").read_text(encoding="utf-8"))["features"]
        assert features
        for f in features:
            p = f["properties"]
            loss = p["loss"] if not isinstance(p["loss"], str) else json.loads(p["loss"])
            assert len(loss) == 24
            assert sum(loss) <= p["forest2000_ha"] + 0.5, p["name"]
