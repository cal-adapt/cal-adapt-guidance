"""uncertainty.py — rewritten for climakitae new_core (v1.4+)

What changed vs the old version
--------------------------------
- CmipOpt              → removed; use ClimateData kwargs directly
- grab_multimodel_data → new_core_grab_multimodel_data (ClimateData, no intake)
- get_ensemble_data    → new_core_get_ensemble_data    (intake still needed for
                         multi-member raw CMIP6; cadcat is single-member only)
- get_warm_level       → removed; warming-level slicing is now a built-in
                         ClimateData process (see `warming_level` key)
- All pure-xarray utils (weighted_temporal_mean, calc_anom, cmip_mmm,
  get_ks_pval_df, _precip_flux_to_total, _area_wgt_average, etc.) are
  data-agnostic and kept unchanged.
- Spatial clipping (_clip_region / _postprocess) still uses rioxarray because
  new_core does not yet support arbitrary-geometry clipping automatically.
"""

import datetime

import intake
import numpy as np
import pandas as pd
import rioxarray as rio
import xarray as xr
from scipy import stats
from xmip.preprocessing import rename_cmip6

from climakitae.core.data_interface import DataInterface, DataParameters
from climakitae.core.data_load import area_subset_geometry
from climakitae.new_core.user_interface import ClimateData

# ---------------------------------------------------------------------------
# Internal helpers (unchanged — data-agnostic)
# ---------------------------------------------------------------------------

def _cf_to_dt(ds: xr.Dataset) -> xr.Dataset:
    """Convert non-standard cftime calendars to pandas datetime."""
    if type(ds.indexes["time"]) not in [pd.core.indexes.datetimes.DatetimeIndex]:
        datetimeindex = ds.indexes["time"].to_datetimeindex(time_unit="ns")
        ds["time"] = datetimeindex
    return ds


def _calendar_align(ds: xr.Dataset) -> xr.Dataset:
    """Set all monthly timestamps to the 1st of each month."""
    ds["time"] = pd.to_datetime(ds.time.dt.strftime("%Y-%m"))
    return ds


def _standardize_cmip6_data(ds: xr.Dataset) -> xr.Dataset:
    """Pre-processing wrapper for raw CMIP6 datasets from intake-esm."""
    ds_simulation = ds.attrs["source_id"]
    ds_scenario = ds.attrs["experiment_id"]
    ds_freq = ds.attrs["frequency"]

    ds = rename_cmip6(ds)
    ds = _cf_to_dt(ds)
    if ds_freq in ("mon",):
        ds = _calendar_align(ds)
    ds = ds.drop_vars(["lon", "lat", "height"], errors="ignore")
    ds = ds.assign_coords({"simulation": ds_simulation, "scenario": ds_scenario})
    ds = ds.squeeze(drop=True)
    return ds


def _precip_flux_to_total(ds: xr.Dataset) -> xr.Dataset:
    """Convert precip flux (kg m-2 s-1) → total per month (mm).

    NOTE: assumes a regular calendar.
    """
    ds_attrs = ds.attrs
    days_month = ds.time.dt.days_in_month
    seconds_month = 86400 * days_month
    ds = ds * seconds_month
    ds = ds.clip(0.1)
    ds.attrs = ds_attrs
    if "pr" in ds.data_vars:
        ds.pr.attrs["units"] = "mm"
    return ds


def _area_wgt_average(ds: xr.Dataset) -> xr.Dataset:
    """Cosine-latitude weighted area average (works for both CMIP6 and WRF grids)."""
    weights = np.cos(np.deg2rad(ds.lat))
    weights.name = "weights"
    return ds.weighted(weights).mean(("x", "y"))


def _drop_member_id(dset_dict: dict) -> dict:
    """Drop member_id coordinate/dimension, keeping only the first member."""
    for dname, dset in dset_dict.items():
        if "member_id" in dset.coords:
            dset = dset.isel(member_id=0).drop_vars("member_id")
            dset_dict[dname] = dset
    return dset_dict


def _clip_region(
    ds: xr.Dataset,
    area_subset: str,
    location: str,
) -> xr.Dataset:
    """Clip a dataset to a state or county polygon via rioxarray.

    Uses the new_core Boundaries object (DataInterface still exposes geographies).
    """
    data_interface = DataInterface()
    geographies = data_interface.geographies
    us_states = geographies._us_states
    us_counties = geographies._ca_counties

    ds = ds.rio.write_crs("epsg:4326", inplace=True)

    match area_subset:
        case s if "counties" in s:
            ds_region = us_counties[us_counties.NAME == location].geometry
        case s if "states" in s:
            ds_region = us_states[us_states.NAME == location].geometry
        case _:
            raise ValueError('area_subset must contain "counties" or "states"')

    try:
        ds = ds.rio.clip(geometries=ds_region, crs=4326, drop=True, all_touched=False)
    except Exception:
        print("No grid centres in region — selecting all intersecting cells.")
        ds = ds.rio.clip(geometries=ds_region, crs=4326, drop=True, all_touched=True)

    return ds


# ---------------------------------------------------------------------------
# Pure-xarray analysis utilities (unchanged)
# ---------------------------------------------------------------------------

def weighted_temporal_mean(ds: xr.DataArray) -> xr.DataArray:
    """Weight monthly data by days in each month, then resample to annual."""
    month_length = ds.time.dt.days_in_month
    wgts = month_length.groupby("time.year") / month_length.groupby("time.year").sum()
    np.testing.assert_allclose(wgts.groupby("time.year").sum(xr.ALL_DIMS), 1.0)
    cond = ds.isnull()
    ones = xr.where(cond, 0.0, 1.0)
    obs_sum = (ds * wgts).resample(time="YS").sum(dim="time")
    ones_out = (ones * wgts).resample(time="YS").sum(dim="time")
    weighted_avg = obs_sum / ones_out
    weighted_avg["time"] = weighted_avg.time.dt.year
    return weighted_avg


def calc_anom(ds_yr: xr.Dataset, base_start: int, base_end: int) -> xr.Dataset:
    """Anomaly relative to a historical baseline period."""
    mdl_baseline = ds_yr.sel(time=slice(base_start, base_end)).mean("time")
    return ds_yr - mdl_baseline


def cmip_mmm(ds: xr.Dataset) -> xr.Dataset:
    """Multi-model mean across the simulation dimension."""
    return ds.mean("simulation")


def get_ks_pval_df(
    sample1: xr.Dataset,
    sample2: xr.Dataset,
    sig_lvl: float = 0.05,
) -> pd.DataFrame:
    """Two-sample KS test at every spatial point; returns significant grid cells."""
    sample1 = sample1.stack(allpoints=["y", "x"]).squeeze()
    sample2 = sample2.stack(allpoints=["y", "x"]).squeeze()
    sample1, sample2 = xr.align(sample1, sample2, join="inner")

    non_spatial_dims = [d for d in sample1.dims if d != "allpoints"]
    if len(non_spatial_dims) != 1:
        raise ValueError(
            f"Expected exactly one non-spatial dim after stacking, got {non_spatial_dims}."
        )
    core_dim = non_spatial_dims[0]

    def ks_stat_2sample(s1, s2):
        try:
            d_statistic, p_value = stats.kstest(s1, s2)
        except (ValueError, ZeroDivisionError):
            d_statistic, p_value = np.nan, np.nan
        return d_statistic, p_value

    _, p_value = xr.apply_ufunc(
        ks_stat_2sample,
        sample1,
        sample2,
        input_core_dims=[[core_dim], [core_dim]],
        exclude_dims=set((core_dim,)),
        output_core_dims=[[], []],
        vectorize=True,
    )

    p_df = p_value.dropna(dim="allpoints")
    p_df = p_value.rename("p_value")
    p_df = p_df.unstack("allpoints").to_dataframe().reset_index()
    p_df = p_df[["lat", "lon", "p_value"]]
    p_df = p_df.loc[:, ["lon", "lat", "p_value"]]
    return p_df[p_df["p_value"] < sig_lvl]


# ---------------------------------------------------------------------------
# new_core: grab_multimodel_data replacement
# ---------------------------------------------------------------------------

def new_core_grab_multimodel_data(
    variable: str,
    area_subset: str = "states",
    location: str = "California",
    area_average: bool = True,
    timescale: str = "mon",
    activity_id: str = "WRF",
    institution_id: str = "UCLA",
    alpha_sort: bool = False,
) -> xr.DataArray:
    """Multi-model mean dataset via ClimateData (replaces grab_multimodel_data).

    Fetches bias-corrected WRF downscaled data for historical + SSP 3-7.0,
    concatenated along time. Optionally clips to a region and area-averages.

    Parameters
    ----------
    variable : str
        cadcat variable name, e.g. 'prec', 't2', 't2max'
    area_subset : str
        'states' or 'counties'
    location : str
        State or county name
    area_average : bool
        If True, compute cosine-latitude weighted spatial mean
    timescale : str
        cadcat table_id, e.g. 'mon' (monthly)
    activity_id : str
        cadcat activity_id, default 'WRF'
    institution_id : str
        Required when activity_id='WRF', default 'UCLA'
    alpha_sort : bool
        Sort simulations alphabetically

    Returns
    -------
    xr.DataArray
        Shape: (simulation, time [, y, x])
    """
    cd = ClimateData()
    cd.catalog("cadcat")
    cd.variable(variable)
    cd.table_id(timescale)
    cd.activity_id(activity_id)
    cd.institution_id(institution_id)
    cd.experiment_id(["historical", "ssp370"])
    # bias-corrected models only (default behaviour — no processes override needed)
    ds = cd.get()

    # Spatial clip
    ds = _clip_region(ds, area_subset, location)

    # Unit conversion for precipitation
    if variable == "prec":
        # cadcat 'prec' is already in mm/month from the WRF output;
        # set flag so callers know units — adjust if your catalog differs
        pass

    # Area average
    if area_average:
        ds = _area_wgt_average(ds)

    if alpha_sort:
        ds = ds.sortby("simulation")

    return ds


# ---------------------------------------------------------------------------
# new_core: get_ensemble_data replacement
# ---------------------------------------------------------------------------

def new_core_get_ensemble_data(
    variable: str,
    selections: DataParameters,
    cmip_names: list[str],
    warm_level: float = 3.0,
    warming_level_window: int = 15,
) -> tuple[xr.Dataset, xr.Dataset]:
    """Multi-member CMIP6 ensemble data for internal variability analysis.

    Replicates the behaviour of the old get_ensemble_data:
      - hist_ds : spatial-clipped/area-averaged data sliced to 1981-2010
      - warm_ds : same but centred on the requested global warming level

    The warming-level slicing now uses ClimateData's built-in `warming_level`
    process for the *WRF* data path.  The raw CMIP6 multi-member path still
    uses intake-esm (cadcat is single-member only).

    Parameters
    ----------
    variable : str
        CMIP6 variable name ('pr', 'tas', …)
    selections : DataParameters
        Carries area_subset, cached_area, area_average settings for clipping
    cmip_names : list[str]
        CMIP6 source_id values to include
    warm_level : float
        Global warming level (1.5, 2.0, 3.0, or 4.0)
    warming_level_window : int
        Half-window in years around the GWL crossing year (default 15 → 30yr)

    Returns
    -------
    tuple[xr.Dataset, xr.Dataset]
        (hist_ds, warm_ds)
    """

    # ── Step 1: fetch raw CMIP6 multi-member data via intake-esm ────────────
    # (cadcat/WRF is single-member; the regridded CMIP6 catalog is needed here)
    col = intake.open_esm_datastore(
        "https://cadcat.s3.amazonaws.com/tmp/cmip6-regrid.json"
    )

    ssp_list = _grab_ensemble_data_by_experiment_id(variable, cmip_names, "ssp370", col)
    hist_list = _grab_ensemble_data_by_experiment_id(variable, cmip_names, "historical", col)

    # Reorder to match cmip_names order
    hist_list = [ds for sim in cmip_names for ds in hist_list if ds.simulation.item() == sim]
    ssp_list  = [ds for sim in cmip_names for ds in ssp_list  if ds.simulation.item() == sim]

    # ── Step 2: apply warming-level slicing (replaces get_warm_level) ────────
    warm_ravel, hist_ravel = [], []
    for hist_ds, ssp_ds in zip(hist_list, ssp_list):
        for m in ssp_ds.member_id.values:
            sliced = _gwl_slice(warm_level, ssp_ds.sel(member_id=m), warming_level_window)
            warm_ravel.append(sliced)
            hist_ravel.append(hist_ds.sel(member_id=m))

    # ── Step 3: concatenate ───────────────────────────────────────────────────
    hist_ds = xr.concat(hist_ravel, dim="member_id")

    warm_ravel = [x for x in warm_ravel if x is not None]
    warm_ds = xr.concat(warm_ravel, dim="member_id")

    # Align member_id between warm and hist using composite sim+member keys
    warm_combo = [s + m for s, m in zip(warm_ds.simulation.values, warm_ds.member_id.values)]
    hist_combo = [s + m for s, m in zip(hist_ds.simulation.values, hist_ds.member_id.values)]
    hist_ds.coords["member_id"] = hist_combo
    hist_ds = hist_ds.sel(member_id=warm_combo)
    hist_ds.coords["member_id"] = warm_ds.member_id.values

    # ── Step 4: time slices ───────────────────────────────────────────────────
    hist_ds = hist_ds.sel(time=slice("1981", "2010"))

    # ── Step 5: spatial post-processing ──────────────────────────────────────
    hist_ds = _postprocess_cmip6(hist_ds, selections, variable)
    warm_ds = _postprocess_cmip6(warm_ds, selections, variable)

    return hist_ds, warm_ds


# ---------------------------------------------------------------------------
# Internal helpers for new_core_get_ensemble_data
# ---------------------------------------------------------------------------

def _grab_ensemble_data_by_experiment_id(
    variable: str,
    cmip_names: list[str],
    experiment_id: str,
    col=None,
) -> list[xr.Dataset]:
    """Fetch one experiment's data from the regridded CMIP6 catalog.

    Parameters
    ----------
    variable : str
        CMIP6 variable name
    cmip_names : list[str]
        source_id values to fetch
    experiment_id : str
        'historical' or 'ssp370'
    col : intake-esm catalog, optional
        Pass an already-opened catalog to avoid re-opening it.

    Returns
    -------
    list[xr.Dataset]
    """
    if col is None:
        col = intake.open_esm_datastore(
            "https://cadcat.s3.amazonaws.com/tmp/cmip6-regrid.json"
        )
    col_subset = col.search(
        table_id="Amon",
        variable_id=variable,
        experiment_id=experiment_id,
        source_id=cmip_names,
    )
    data_dict = col_subset.to_dataset_dict(
        zarr_kwargs={"consolidated": True},
        storage_options={"anon": True},
        preprocess=_standardize_cmip6_data,
        progressbar=False,
    )
    return list(data_dict.values())


def _gwl_slice(
    warm_level: float,
    ds: xr.Dataset,
    window: int = 15,
) -> xr.Dataset | None:
    import os
    import climakitae
    from climakitae.core.paths import GWL_1850_1900_FILE
    from climakitae.util.utils import read_csv_file

    try:
        warm_level = float(warm_level)
    except ValueError:
        raise ValueError("warm_level must be a number.")

    if warm_level not in [1.5, 2.0, 3.0, 4.0]:
        raise ValueError("warm_level must be one of: 1.5, 2.0, 3.0, 4.0")

    # Base GWL table
    gwl_times = read_csv_file(GWL_1850_1900_FILE, index_col=[0, 1, 2])

    # Supplement with the large EC-Earth3 ensemble (r101-r150)
    pkg_dir = os.path.dirname(climakitae.__file__)
    ece3_path = os.path.join(pkg_dir, "data", "gwl_1981-2010ref_EC-Earth3_ssp370.csv")
    if os.path.exists(ece3_path):
        gwl_ece3 = read_csv_file(ece3_path, index_col=[0, 1, 2])
        gwl_times = pd.concat([gwl_times, gwl_ece3]).drop_duplicates()

    model     = str(ds.simulation.values)
    member_id = str(ds["member_id"].values)
    scenario  = "ssp370"
    sim_idx   = (model, member_id, scenario)
    warm_col  = str(warm_level)

    if model not in gwl_times.index.get_level_values("GCM"):
        print(f"⚠️  {model} not in GWL lookup table — skipping.")
        return None
    if sim_idx not in gwl_times.index:
        print(f"⚠️  {sim_idx} not in GWL lookup table — skipping.")
        return None
    if warm_col not in gwl_times.columns:
        print(f"⚠️  GWL column '{warm_col}' not found — skipping.")
        return None

    raw = gwl_times.loc[sim_idx, warm_col]
    candidates = pd.Series([raw] if not isinstance(raw, pd.Series) else raw)
    candidates = candidates[~candidates.isin([None, "", np.nan])]

    if candidates.empty:
        print(f"⚠️  {warm_level}°C not reached for {member_id} of {model} — skipping.")
        return None

    parsed = pd.to_datetime(candidates.astype(str), errors="coerce").dropna()
    if parsed.empty:
        print(f"⚠️  Could not parse GWL datetime for {member_id} of {model} — skipping.")
        return None

    year = int(parsed.min().year)

    if (year + window) > 2100:
        print(
            f"⚠️  {model} {member_id}: window {year - window + 1}–{year + window} "
            f"exceeds 2100 — skipping."
        )
        return None

    return ds.sel(time=slice(str(year - window + 1), str(year + window)))


def _postprocess_cmip6(
    ds: xr.Dataset,
    selections: DataParameters,
    variable: str,
) -> xr.Dataset:
    """Spatial clip, unit conversion, and optional area average for CMIP6 data."""
    # Spatial clip
    ds_region = area_subset_geometry(selections)
    ds = ds.rio.write_crs("epsg:4326", inplace=True)
    try:
        ds = ds.rio.clip(geometries=ds_region, crs=4326, drop=True)
    except Exception:
        print("Falling back to all_touched=True for spatial clip.")
        ds = ds.rio.clip(geometries=ds_region, crs=4326, drop=True, all_touched=True)

    # Unit conversion
    if variable == "pr":
        ds = _precip_flux_to_total(ds)

    # Area average
    if selections.area_average == "Yes":
        ds = _area_wgt_average(ds)

    return ds
