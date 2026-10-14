import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from pipeline.config import N_YEARS
from pipeline.run import adm1_lookup
from pipeline.zonal import accumulate, row_area_ha


def test_pixel_area_at_equator_is_about_0_077_ha():
    a = row_area_ha(top_lat=0.0, first_row=0, n_rows=1)[0]
    assert a == pytest.approx(0.0769, abs=0.0005)


def test_pixel_area_shrinks_with_latitude():
    near_equator, high = row_area_ha(1.0, 0, 1)[0], row_area_ha(60.0, 0, 1)[0]
    assert high == pytest.approx(near_equator * 0.5, rel=0.02)


def test_accumulate_sums_by_unit_and_year():
    loss = np.array([[0, 1, 2], [3, 3, 0]], dtype=np.uint8)
    cover = np.array([[90, 90, 90], [90, 10, 90]], dtype=np.uint8)  # pixel (1,1) is below the canopy threshold
    ids = np.array([[0, 0, 1], [1, 1, -1]], dtype=np.int32)  # pixel (1,2) is outside every unit
    area = np.array([1.0, 2.0])  # per-row pixel area in ha
    forest, lost, total = accumulate(loss, cover, ids, area, n_ids=2)

    assert total.tolist() == [2.0, 1.0 + 2.0 + 2.0]
    assert forest.tolist() == [2.0, 1.0 + 2.0]  # unit 1 forest: (0,2) and (1,0); (1,1) too sparse
    assert lost[0, 0] == 1.0      # unit 0, year index 0 (2001): pixel (0,1)
    assert lost[1, 1] == 1.0      # unit 1, 2002: pixel (0,2)
    assert lost[1, 2] == 2.0      # unit 1, 2003: pixel (1,0) counted, pixel (1,1) excluded by canopy rule
    assert lost.sum() == 4.0


def test_loss_on_sparse_canopy_is_not_counted():
    loss = np.full((1, 3), 5, dtype=np.uint8)
    cover = np.array([[29, 30, 100]], dtype=np.uint8)
    ids = np.zeros((1, 3), dtype=np.int32)
    _, lost, _ = accumulate(loss, cover, ids, np.array([1.0]), n_ids=1)
    assert lost.sum() == 2.0  # 29% is out, 30% and 100% are in


def test_loss_year_beyond_range_is_rejected():
    loss = np.array([[N_YEARS + 1]], dtype=np.uint8)
    with pytest.raises(ValueError):
        accumulate(loss, np.array([[90]], dtype=np.uint8), np.zeros((1, 1), dtype=np.int32), np.array([1.0]), 1)


def test_no_pixels_gives_zeros():
    empty = np.zeros((2, 2), dtype=np.uint8)
    forest, lost, total = accumulate(empty, empty + 90, np.full((2, 2), -1, dtype=np.int32), np.ones(2), 3)
    assert forest.sum() == lost.sum() == total.sum() == 0


def test_district_is_assigned_to_region_of_same_country():
    regions = gpd.GeoDataFrame({"iso": ["AAA", "AAA", "BBB"], "name": ["North", "South", "Other"],
                                "geometry": [box(0, 1, 2, 2), box(0, 0, 2, 1), box(0, 0, 2, 2)]}, crs="EPSG:4326")
    districts = gpd.GeoDataFrame({"iso": ["AAA", "AAA"], "name": ["d1", "d2"],
                                  "geometry": [box(0.2, 1.2, 0.8, 1.8), box(0.2, 0.2, 0.8, 0.8)]}, crs="EPSG:4326")
    assert adm1_lookup(districts, regions).tolist() == ["North", "South"]


def test_district_outside_all_regions_falls_back_to_nearest():
    regions = gpd.GeoDataFrame({"iso": ["AAA"], "name": ["Only"], "geometry": [box(0, 0, 1, 1)]}, crs="EPSG:4326")
    districts = gpd.GeoDataFrame({"iso": ["AAA"], "name": ["edge"], "geometry": [box(1.1, 0.4, 1.2, 0.6)]},
                                 crs="EPSG:4326")
    assert adm1_lookup(districts, regions).tolist() == ["Only"]
