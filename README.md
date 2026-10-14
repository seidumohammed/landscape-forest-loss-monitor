# Tree Cover Loss Monitor: Ghana, Côte d'Ivoire, Cameroon

A web map and a reproducible pipeline that show annual tree cover loss from
2001 to 2024 for every region and district in Ghana, Côte d'Ivoire and
Cameroon. Pick a country, a level (regions or districts), a range of years,
and either hectares lost or the share of year-2000 forest lost.

It is a screening view. Tree cover loss is not the same as deforestation (see
Limits).

Live map: set up GitHub Pages from the `/docs` folder (see below).

## What it covers

| Country | Forest in 2000 (30%+ canopy) | Loss 2001-2024 | Share lost |
|---|---|---|---|
| Ghana | 6.96 Mha | 1.75 Mha | 25.2% |
| Côte d'Ivoire | 14.89 Mha | 3.99 Mha | 26.8% |
| Cameroon | 31.46 Mha | 2.23 Mha | 7.1% |

353 districts (Ghana 260, Cameroon 60, Côte d'Ivoire 33) and 40 regions. The
full tables are in [data/processed](data/processed).

## How it works

1. `python -m pipeline.boundaries` downloads district (ADM2) and region (ADM1)
   boundaries from geoBoundaries.
2. `bash download_hansen.sh` downloads the six Hansen Global Forest Change
   v1.12 tile pairs that cover the three countries (about 2 GB, stored outside
   the repository).
3. `python -m pipeline.run` reads the tiles in blocks of 1,000 rows, rasterises
   the districts onto each block, and adds up pixel area by district and year.
   Pixel area is computed per row from latitude. A pixel counts as forest if it
   had 30% or more canopy in 2000, and as loss if `lossyear` is set.
   Districts are then added up to regions and countries, so the totals always
   agree.
4. The same run writes small GeoJSON files for the map into `docs/data`.

```bash
pip install -r requirements.txt
python -m pipeline.boundaries
bash download_hansen.sh
python -m pipeline.run        # about 5 minutes on a laptop
pytest
python -m http.server 8002 --directory docs
```

## How it was checked

- Pixel-area totals match the boundary polygon areas to within 0.1% for each
  country (polygon area computed in an equal-area projection).
- Four randomly chosen districts were recomputed with a separate method
  (`rasterio.mask`). Forest and loss matched the pipeline exactly.
- Unit tests cover the area-by-year arithmetic, the canopy threshold, the
  latitude effect on pixel area, and the district-to-region assignment.
- Output tests check that loss never exceeds forest in any unit, that
  districts add up to regions and countries, and that the rounded files used
  by the map keep every unit at or below 100%. That last test exists because a
  rounding bug once showed tiny districts above 100%.
- I have not compared the totals with Global Forest Watch's published figures.

## Limits

- **Tree cover loss is not deforestation.** The Hansen data detects loss of
  tree canopy. Harvested tree crops, plantations, shade-tree thinning and
  fire all register as loss.
- **No gain, no cocoa or oil palm layer.** Regrowth is not netted off, and
  loss is not split by crop. Public cocoa and oil palm maps were not
  available in a form I could use here, so they are not included.
- **Baseline is the year 2000.** Forest cleared before 2001 does not appear.
- **Small areas are noisy.** Areas with under 1,000 ha of forest in 2000 are
  not coloured or ranked by share. 111 of the 353 districts fall below that.
- **Area is approximate.** Pixel area uses a fixed degree-to-metre factor for
  north-south size, which is accurate to well under 1% in these latitudes.
- **Boundaries** come from geoBoundaries (OpenStreetMap-derived) and may differ
  from official boundaries. Côte d'Ivoire has only 33 districts in this
  release, so its district view is coarse.

## Publishing the map

The map is a static site in `docs/`. On GitHub, open Settings, then Pages,
choose "Deploy from a branch", branch `main`, folder `/docs`.

## Data and licences

- Hansen, M. C., et al. (2013). High-resolution global maps of 21st-century
  forest cover change. *Science* 342, 850-853. Data version GFC-2024-v1.12,
  released under CC BY 4.0.
- Boundaries: geoBoundaries gbOpen (Runfola et al., 2020), OpenStreetMap-derived,
  CC BY-SA. The simplified boundaries in `docs/data` carry the same licence.

## Related

[eudr-plot-risk-checker](https://github.com/seidumohammed/eudr-plot-risk-checker)
screens individual farm plots with the same Hansen data. This project looks at
the landscape level across three countries.
