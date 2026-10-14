"""Core arithmetic: tree cover loss area per admin unit and year for one block of pixels."""

from __future__ import annotations

import numpy as np

from pipeline.config import CANOPY_MIN, M_PER_DEG_LAT, M_PER_DEG_LON_EQ, N_YEARS, PIXEL_DEG


def row_area_ha(top_lat: float, first_row: int, n_rows: int) -> np.ndarray:
    """Pixel area in hectares for each row of a block.

    Pixels are 0.00025 degrees square, so their east-west width shrinks with
    the cosine of latitude. `top_lat` is the latitude of the tile's top edge
    and `first_row` the tile row where the block starts.
    """
    lat = top_lat - (first_row + np.arange(n_rows) + 0.5) * PIXEL_DEG
    width_m = PIXEL_DEG * M_PER_DEG_LON_EQ * np.cos(np.radians(lat))
    height_m = PIXEL_DEG * M_PER_DEG_LAT
    return width_m * height_m / 10_000.0


def accumulate(loss: np.ndarray, treecover: np.ndarray, ids: np.ndarray,
               area_ha: np.ndarray, n_ids: int, canopy_min: int = CANOPY_MIN):
    """Sum areas by admin unit for one block.

    loss       uint8, 0 = no loss, 1..24 = loss in 2001..2024
    treecover  uint8, percent canopy cover in 2000
    ids        int, admin unit index per pixel, -1 outside every unit
    area_ha    float, pixel area per row (length = number of rows)

    Returns (forest2000_ha, loss_ha[n_ids, N_YEARS], total_ha). Loss counts
    only pixels that had at least `canopy_min` percent canopy in 2000.
    """
    if loss.size and int(loss.max()) > N_YEARS:
        raise ValueError(f"loss year value {int(loss.max())} is above {N_YEARS}")
    weight = np.broadcast_to(area_ha[:, None], ids.shape)
    inside = ids >= 0
    forest = inside & (treecover >= canopy_min)
    lost = forest & (loss > 0)

    total = np.bincount(ids[inside], weights=weight[inside], minlength=n_ids)
    forest_ha = np.bincount(ids[forest], weights=weight[forest], minlength=n_ids)
    key = ids[lost].astype(np.int64) * N_YEARS + (loss[lost].astype(np.int64) - 1)
    loss_ha = np.bincount(key, weights=weight[lost], minlength=n_ids * N_YEARS).reshape(n_ids, N_YEARS)
    return forest_ha, loss_ha, total
